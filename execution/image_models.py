#!/usr/bin/env python3
"""
One interface over every image model the thumbnail workflow can use.

Each model is reached either directly (Gemini, via GEMINI_API_KEY) or through
fal.ai (via FAL_KEY), so trying a new model means adding one entry to MODELS.

    from image_models import run

    result = run(
        "flux-3",
        prompt="...",
        images=["assets/headshots/a.jpg", "assets/headshots/b.jpg"],
        output="output/x/v1.png",
    )

Image conventions shared by all models:
  - `images` are local paths, sent in order. Prompts refer to them by
    position ("Image 1", "Image 2", ...). For edits, images[0] is the source.
  - `mask` is a local image where WHITE = area to change, BLACK = keep.
    It's translated to each model's own convention (alpha, inverted, or a
    bounding box). Models without mask support regenerate the whole image —
    a warning is printed.

Run `python3 execution/image_models.py` to list models, endpoints and costs.
"""

import io
import json
import math
import os
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from dotenv import load_dotenv, find_dotenv
from PIL import Image, ImageChops, ImageOps, ImageStat

# Enable AVIF support — YouTube thumbnails are often AVIF
try:
    import pillow_avif  # noqa: F401
except ImportError:
    pass


RESOLUTIONS = ("1k", "2k", "4k")

# Long edge in pixels per resolution tier, for models that take explicit sizes
LONG_EDGE = {"1k": 1536, "2k": 2560, "4k": 3840}


# ---------------------------------------------------------------------------
# Result + helpers
# ---------------------------------------------------------------------------

@dataclass
class Result:
    path: Path
    model: str
    est_cost: float
    notes: str = ""
    warnings: list = field(default_factory=list)


def validate_image_file(path):
    """Check that a file is actually an image, not HTML or other junk from a failed download."""
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"Error: File not found: {path}")
    with open(p, "rb") as f:
        header = f.read(256)
    if b"<!DOCTYPE" in header or b"<html" in header or b"<HTML" in header:
        raise SystemExit(
            f"Error: '{path}' is an HTML file, not an image. "
            f"The download URL likely returned a web page instead of the actual image. "
            f"Try downloading from a different source."
        )
    if len(header) < 8:
        raise SystemExit(f"Error: '{path}' is too small to be a valid image ({len(header)} bytes).")


def open_image(path):
    """Open an image upright. Camera JPEGs often store pixels sideways plus an EXIF
    rotation tag; re-encoding drops the tag, so models would see a sideways face."""
    return ImageOps.exif_transpose(Image.open(path))


def resize_if_needed(img, max_edge=2048):
    """Resize image if larger than max_edge on any side."""
    w, h = img.size
    if max(w, h) > max_edge:
        ratio = max_edge / max(w, h)
        return img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
    return img


def tier_for_source(path):
    """Pick the resolution tier closest to a source image, so edits don't downscale it."""
    w, h = open_image(path).size
    mp = w * h / 1_000_000
    if mp <= 1.3:
        return "1k"
    if mp <= 4.5:
        return "2k"
    return "4k"


def dims_for(aspect_ratio, resolution):
    """Width/height for an aspect ratio at a resolution tier, rounded to multiples of 16."""
    if aspect_ratio == "auto":
        return "auto"
    aw, ah = (int(x) for x in aspect_ratio.split(":"))
    long_edge = LONG_EDGE[resolution]
    if aw >= ah:
        w, h = long_edge, long_edge * ah / aw
    else:
        w, h = long_edge * aw / ah, long_edge
    return {"width": int(round(w / 16) * 16), "height": int(round(h / 16) * 16)}


def load_mask(mask_path, source_path):
    """Load a WHITE=edit mask as an 'L' image matching the source size."""
    src_size = open_image(source_path).size
    mask = Image.open(mask_path).convert("L")
    if mask.size != src_size:
        mask = mask.resize(src_size, Image.NEAREST)
    return mask.point(lambda v: 255 if v >= 128 else 0)


def mask_bbox_1000(mask):
    """Bounding box of the white area as [y_min, x_min, y_max, x_max] on a 0-1000 grid (FLUX 3 format)."""
    box = mask.getbbox()
    if box is None:
        raise SystemExit("Error: mask is entirely black — nothing to edit.")
    x0, y0, x1, y1 = box
    w, h = mask.size
    return [round(y0 / h * 1000), round(x0 / w * 1000), round(y1 / h * 1000), round(x1 / w * 1000)]


def drift_report(source_path, result_path, mask_path=None):
    """
    How much did the model change pixels it was supposed to leave alone?

    Compares result to source outside the mask (or across the whole image if no
    mask). Returns mean absolute difference (0-255) and PSNR in dB. PSNR above
    ~40 dB is visually identical; below ~30 dB the change is noticeable.
    """
    src = open_image(source_path).convert("RGB")
    out = Image.open(result_path).convert("RGB")
    resized = out.size != src.size
    if resized:
        out = out.resize(src.size, Image.LANCZOS)

    keep = None
    if mask_path:
        keep = ImageOps.invert(load_mask(mask_path, source_path))
        if keep.getbbox() is None:
            return None

    diff = ImageChops.difference(src, out)
    stat = ImageStat.Stat(diff, mask=keep)
    mae = sum(stat.mean) / 3
    mse = sum(r * r for r in stat.rms) / 3
    psnr = float("inf") if mse == 0 else 20 * math.log10(255 / math.sqrt(mse))
    return {
        "region": "outside mask" if mask_path else "whole image",
        "mean_abs_diff": round(mae, 2),
        "psnr_db": round(psnr, 2) if psnr != float("inf") else "inf",
        "result_resized_to_source": resized,
        "source_size": list(src.size),
        "result_size": list(Image.open(result_path).size),
    }


def save_image_bytes(data, output_path):
    """Save downloaded image bytes, converting only if the format differs from the extension."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.open(io.BytesIO(data))
    wanted = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP"}.get(output_path.suffix.lower(), "PNG")
    if img.format == wanted:
        output_path.write_bytes(data)
    else:
        if wanted == "JPEG":
            img = img.convert("RGB")
        img.save(output_path, wanted, **({"quality": 95} if wanted == "JPEG" else {}))


# ---------------------------------------------------------------------------
# fal.ai backend
# ---------------------------------------------------------------------------

def _fal_upload(path, keep_full_res=False):
    """Upload a local image to fal storage and return its URL."""
    import fal_client

    validate_image_file(path)
    raw = Image.open(path)
    if keep_full_res and raw.format in ("PNG", "JPEG", "WEBP") and raw.getexif().get(0x0112, 1) == 1:
        return fal_client.upload_file(path)
    # Re-encode upright as PNG (handles AVIF and EXIF rotation) and cap size for references
    img = ImageOps.exif_transpose(raw)
    if not keep_full_res:
        img = resize_if_needed(img)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        img.save(tmp.name, "PNG")
        return fal_client.upload_file(tmp.name)


def _fal_upload_pil(img):
    import fal_client

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        img.save(tmp.name, "PNG")
        return fal_client.upload_file(tmp.name)


TRANSIENT_MARKERS = ("429", "500", "502", "503", "504", "high demand", "overloaded", "timed out", "unavailable")


def with_retries(fn, attempts=4, first_delay=5):
    """Retry transient server errors (503 'high demand' spikes can last minutes) with backoff."""
    delay = first_delay
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as e:
            transient = any(m in str(e).lower() for m in TRANSIENT_MARKERS)
            if not transient or attempt == attempts:
                raise
            print(f"Transient error ({str(e)[:80]}); retrying in {delay}s...", file=sys.stderr)
            time.sleep(delay)
            delay *= 3


def _fal_call(endpoint, arguments):
    import fal_client

    return with_retries(lambda: fal_client.subscribe(endpoint, arguments=arguments))


def _download(url):
    if url.startswith("data:"):
        import base64
        return base64.b64decode(url.split(",", 1)[1])
    # httpx ships with fal_client and uses certifi; urllib relies on the system CA
    # store, which python.org builds on macOS often lack (CERTIFICATE_VERIFY_FAILED).
    import httpx

    response = httpx.get(url, timeout=300, follow_redirects=True)
    response.raise_for_status()
    return response.content


# ---------------------------------------------------------------------------
# Model specs
# ---------------------------------------------------------------------------
#
# build(ctx) returns (endpoint, arguments) for a fal model. ctx holds:
#   prompt, image_urls, mask (PIL 'L', WHITE=edit, or None), aspect_ratio,
#   resolution, quality, seed, is_edit (True when images were given)

@dataclass
class ModelSpec:
    key: str
    label: str
    backend: str                       # "gemini" or "fal"
    max_images: int
    mask_support: str                  # "none", "alpha", "inverted", "bbox"
    cost: Callable[[str, Optional[str]], float]   # (resolution, quality) -> est USD
    build: Optional[Callable[[dict], tuple]] = None
    default_quality: Optional[str] = None
    notes: str = ""


def _build_nano_banana(t2i, edit):
    def build(ctx):
        args = {
            "prompt": ctx["prompt"],
            "aspect_ratio": ctx["aspect_ratio"],
            "resolution": ctx["resolution"].upper(),
            "output_format": "png",
        }
        if ctx["seed"] is not None:
            args["seed"] = ctx["seed"]
        if ctx["image_urls"]:
            args["image_urls"] = ctx["image_urls"]
            return edit, args
        return t2i, args
    return build


def _build_gpt_image(tier):
    def build(ctx):
        args = {
            "prompt": ctx["prompt"],
            "quality": ctx["quality"],
            "output_format": "png",
        }
        if ctx["image_urls"]:
            args["image_urls"] = ctx["image_urls"]
            # Edits keep the source geometry; generation-from-references uses the requested ratio
            args["image_size"] = "auto" if ctx["mask"] is not None or ctx["aspect_ratio"] == "auto" \
                else dims_for(ctx["aspect_ratio"], ctx["resolution"])
            if ctx["mask"] is not None:
                # OpenAI convention: transparent pixels = area to edit
                src = open_image(ctx["source_path"]).convert("RGBA")
                src.putalpha(ImageOps.invert(ctx["mask"]))
                args["mask_url"] = _fal_upload_pil(src)
            return f"openai/gpt-image-2.5/{tier}/edit", args
        args["image_size"] = dims_for(ctx["aspect_ratio"], ctx["resolution"])
        return f"openai/gpt-image-2.5/{tier}/text-to-image", args
    return build


def _build_flux3(ctx):
    prompt = ctx["prompt"]
    if ctx["mask"] is not None:
        box = mask_bbox_1000(ctx["mask"])
        rows = [{"id": "edit_1", "from": None, "src_bbox": None, "tgt_bbox": box, "desc": ctx["prompt"]}]
        prompt = (
            f"In <ref_image_0>, inside the region <edit_1>: {ctx['prompt']} "
            f"Keep everything outside <edit_1> exactly unchanged. {json.dumps(rows)}"
        )
    args = {
        "prompt": prompt,
        "aspect_ratio": ctx["aspect_ratio"],
        "resolution": ctx["resolution"],
        "output_format": "png",
    }
    if ctx["image_urls"]:
        args["image_urls"] = ctx["image_urls"]
        return "blackforestlabs/flux-3/edit-image", args
    return "blackforestlabs/flux-3/text-to-image", args


# Ideogram only accepts specific sizes; these cover the ratios thumbnails use (max 2K)
IDEOGRAM_SIZES = {
    ("16:9", "1k"): (1280, 720), ("16:9", "2k"): (2560, 1440),
    ("9:16", "1k"): (720, 1280), ("9:16", "2k"): (1440, 2560),
    ("1:1", "1k"): (1024, 1024), ("1:1", "2k"): (2048, 2048),
    ("4:3", "1k"): (1152, 864), ("3:4", "1k"): (864, 1152),
}


def _ideogram_size(aspect_ratio, resolution):
    tier = "2k" if resolution == "4k" else resolution
    size = IDEOGRAM_SIZES.get((aspect_ratio, tier)) or IDEOGRAM_SIZES.get((aspect_ratio, "1k"))
    if size is None:
        return "landscape_16_9"
    return {"width": size[0], "height": size[1]}


def _build_ideogram45(ctx):
    if not ctx["image_urls"]:
        args = {"prompt": ctx["prompt"], "quality": ctx["quality"],
                "image_size": _ideogram_size(ctx["aspect_ratio"], ctx["resolution"])}
        if ctx["seed"] is not None:
            args["seed"] = ctx["seed"]
        return "ideogram/v4.5", args

    max_refs = 3 if ctx["mask"] is not None else 4
    args = {
        "prompt": ctx["prompt"],
        "image_url": ctx["image_urls"][0],
        "reference_image_urls": ctx["image_urls"][1:1 + max_refs],
        # High precision = Precise Edit, restores pixels outside the change
        "edit_precision": "high" if ctx["mask"] is not None else "regular",
        "quality": ctx["quality"],
    }
    if ctx["mask"] is not None:
        # Ideogram convention: black = edit, white = keep
        args["mask_url"] = _fal_upload_pil(ImageOps.invert(ctx["mask"]))
    elif ctx["aspect_ratio"] != "auto":
        args["image_size"] = _ideogram_size(ctx["aspect_ratio"], ctx["resolution"])
    if ctx["seed"] is not None:
        args["seed"] = ctx["seed"]
    return "ideogram/v4.5/edit", args


def _flux3_cost(res, _q):
    return {"1k": 0.048, "2k": 0.10, "4k": 0.607}[res]


def _gpt_cost(res, q):
    base = {"1k": 0.045, "2k": 0.064, "4k": 0.108}[res]   # high quality, one reference
    return base * {"low": 0.3, "medium": 0.45, "high": 1.0, "xhigh": 1.6, "max": 2.2}.get(q or "high", 1.0)


MODELS = {
    "gemini": ModelSpec(
        key="gemini", label="Nano Banana Pro (Gemini direct)", backend="gemini",
        max_images=14, mask_support="none",
        cost=lambda res, q: 0.24 if res == "4k" else 0.134,
        notes="Default. Uses GEMINI_API_KEY. Regenerates every pixel, even for small edits.",
    ),
    "nano-banana-pro": ModelSpec(
        key="nano-banana-pro", label="Nano Banana Pro (fal)", backend="fal",
        max_images=14, mask_support="none",
        cost=lambda res, q: 0.30 if res == "4k" else 0.15,
        build=_build_nano_banana("fal-ai/nano-banana-pro", "fal-ai/nano-banana-pro/edit"),
        notes="Same model as 'gemini', billed through fal.",
    ),
    "nano-banana-2.1": ModelSpec(
        key="nano-banana-2.1", label="Nano Banana 2.1", backend="fal",
        max_images=14, mask_support="none",
        cost=lambda res, q: 0.08 if res == "4k" else 0.05,   # token-based, rough estimate
        build=_build_nano_banana("google/nano-banana-2.1", "google/nano-banana-2.1/edit"),
        notes="Released 2026-10-06. Token-based pricing; cost is a rough estimate.",
    ),
    "gpt-image-2.5-flare": ModelSpec(
        key="gpt-image-2.5-flare", label="GPT Image 2.5 Flare", backend="fal",
        max_images=16, mask_support="alpha", default_quality="high",
        cost=_gpt_cost, build=_build_gpt_image("flare"),
        notes="Faster GPT Image 2.5 tier. Quality: low/medium/high/xhigh/max.",
    ),
    "gpt-image-2.5-sunburst": ModelSpec(
        key="gpt-image-2.5-sunburst", label="GPT Image 2.5 Sunburst", backend="fal",
        max_images=16, mask_support="alpha", default_quality="high",
        cost=_gpt_cost, build=_build_gpt_image("sunburst"),
        notes="Precision GPT Image 2.5 tier, slower. Same pricing as Flare.",
    ),
    "flux-3": ModelSpec(
        key="flux-3", label="FLUX 3 Image", backend="fal",
        max_images=10, mask_support="bbox",
        cost=_flux3_cost, build=_build_flux3,
        notes="Released 2026-10-01. Masks become a bounding-box edit; rest of image is kept.",
    ),
    "ideogram-4.5": ModelSpec(
        key="ideogram-4.5", label="Ideogram 4.5", backend="fal",
        max_images=5, mask_support="inverted", default_quality="high",
        cost=lambda res, q: {"very_low": 0.008, "low": 0.03, "medium": 0.06}.get(q, 0.22),
        build=_build_ideogram45,
        notes="Text-to-image takes NO reference photos. With images: images[0] is the source, "
              "up to 4 more are references. Mask = Precise Edit (pixels outside restored). Max 2K.",
    ),
}


def estimate_cost(model_key, resolution="2k", quality=None):
    spec = MODELS[model_key]
    return spec.cost(resolution, quality or spec.default_quality)


# ---------------------------------------------------------------------------
# Gemini direct backend
# ---------------------------------------------------------------------------

def _run_gemini(prompt, images, aspect_ratio, resolution, output_path):
    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("Error: GEMINI_API_KEY environment variable not set")

    client = genai.Client(api_key=api_key)
    contents = [prompt]
    for path in images:
        validate_image_file(path)
        contents.append(resize_if_needed(open_image(path)))

    image_config = {"image_size": resolution.upper()}
    if aspect_ratio != "auto":
        image_config["aspect_ratio"] = aspect_ratio

    response = with_retries(lambda: client.models.generate_content(
        model=os.environ.get("GEMINI_IMAGE_MODEL", "gemini-3-pro-image-preview"),
        contents=contents,
        config=types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
            image_config=types.ImageConfig(**image_config),
        ),
    ))

    text = ""
    saved = False
    for part in response.candidates[0].content.parts:
        if getattr(part, "inline_data", None) is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            part.as_image().save(str(output_path))
            saved = True
        elif getattr(part, "text", None):
            text += part.text
    if not saved:
        raise SystemExit(f"Error: No image was generated in the response.\n{text}".rstrip())
    return text


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(model_key, prompt, images=(), output="out.png", *, mask=None,
        aspect_ratio="16:9", resolution="2k", quality=None, seed=None):
    """
    Generate or edit an image with any registered model. Returns a Result.

    images[0] is treated as the edit source when a mask is given; its full
    resolution is uploaded. Other images are capped at 2048px.
    """
    load_dotenv(find_dotenv(usecwd=True))

    if model_key not in MODELS:
        raise SystemExit(f"Error: unknown model '{model_key}'. Options: {', '.join(MODELS)}")
    if resolution not in RESOLUTIONS:
        raise SystemExit(f"Error: resolution must be one of {RESOLUTIONS}")
    spec = MODELS[model_key]
    images = list(images)
    output_path = Path(output)
    warnings = []

    if mask and not images:
        raise SystemExit("Error: a mask needs a source image (pass it as the first image).")
    if len(images) > spec.max_images:
        warnings.append(f"{spec.label} accepts {spec.max_images} images; extra images were dropped.")
        images = images[:spec.max_images]
    if mask and spec.mask_support == "none":
        warnings.append(f"{spec.label} has no mask support — the whole image will be regenerated.")
    if model_key == "ideogram-4.5" and images and not mask and len(images) > 1:
        warnings.append("Ideogram 4.5 treats Image 1 as the source to edit, not as a reference.")
    if model_key == "ideogram-4.5" and resolution == "4k":
        warnings.append("Ideogram 4.5 maxes out at 2K; using 2K.")

    quality = quality or spec.default_quality
    notes = ""

    if spec.backend == "gemini":
        notes = _run_gemini(prompt, images, aspect_ratio, resolution, output_path)
    else:
        if not os.environ.get("FAL_KEY"):
            raise SystemExit("Error: FAL_KEY not set. Add it to .env (get one at fal.ai/dashboard/keys).")
        mask_img = load_mask(mask, images[0]) if mask else None
        ctx = {
            "prompt": prompt,
            "image_urls": [_fal_upload(p, keep_full_res=(i == 0 and mask is not None)) for i, p in enumerate(images)],
            "source_path": images[0] if images else None,
            "mask": mask_img if spec.mask_support != "none" else None,
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
            "quality": quality,
            "seed": seed,
        }
        endpoint, arguments = spec.build(ctx)
        response = _fal_call(endpoint, arguments)
        result_images = response.get("images") or ([response["image"]] if response.get("image") else [])
        if not result_images:
            raise SystemExit(f"Error: {spec.label} returned no image. Response: {json.dumps(response)[:500]}")
        save_image_bytes(_download(result_images[0]["url"]), output_path)
        notes = response.get("description") or ""

    return Result(
        path=output_path, model=model_key,
        est_cost=estimate_cost(model_key, resolution, quality),
        notes=notes, warnings=warnings,
    )


def print_models():
    print(f"{'model':<24} {'backend':<7} {'imgs':>4}  {'mask':<9} {'~$/img @2k':>10}  notes")
    for spec in MODELS.values():
        print(f"{spec.key:<24} {spec.backend:<7} {spec.max_images:>4}  {spec.mask_support:<9} "
              f"{estimate_cost(spec.key):>10.3f}  {spec.notes}")


if __name__ == "__main__":
    print_models()
