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

`images` are local paths, sent in order. Prompts refer to them by position
("Image 1", "Image 2", ...).

Run `python3 execution/image_models.py` to list models, endpoints and costs.
"""

import io
import json
import os
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from dotenv import load_dotenv, find_dotenv
from PIL import Image, ImageOps

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

def _fal_upload(path):
    """Upload a local image to fal storage (upright, as PNG, capped at 2048px) and return its URL."""
    import fal_client

    validate_image_file(path)
    img = resize_if_needed(open_image(path))
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
#   prompt, image_urls, aspect_ratio, resolution, quality, seed

@dataclass
class ModelSpec:
    key: str
    label: str
    backend: str                       # "gemini" or "fal"
    max_images: int
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
            args["image_size"] = dims_for(ctx["aspect_ratio"], ctx["resolution"])
            return f"openai/gpt-image-2.5/{tier}/edit", args
        args["image_size"] = dims_for(ctx["aspect_ratio"], ctx["resolution"])
        return f"openai/gpt-image-2.5/{tier}/text-to-image", args
    return build


def _build_flux3(ctx):
    args = {
        "prompt": ctx["prompt"],
        "aspect_ratio": ctx["aspect_ratio"],
        "resolution": ctx["resolution"],
        "output_format": "png",
    }
    if ctx["image_urls"]:
        args["image_urls"] = ctx["image_urls"]
        return "blackforestlabs/flux-3/edit-image", args
    return "blackforestlabs/flux-3/text-to-image", args


def _flux3_cost(res, _q):
    return {"1k": 0.048, "2k": 0.10, "4k": 0.607}[res]


def _gpt_cost(res, q):
    base = {"1k": 0.045, "2k": 0.064, "4k": 0.108}[res]   # high quality, one reference
    return base * {"low": 0.3, "medium": 0.45, "high": 1.0, "xhigh": 1.6, "max": 2.2}.get(q or "high", 1.0)


MODELS = {
    "gemini": ModelSpec(
        key="gemini", label="Nano Banana Pro (Gemini direct)", backend="gemini",
        max_images=14,
        cost=lambda res, q: 0.24 if res == "4k" else 0.134,
        notes="Default. Uses GEMINI_API_KEY.",
    ),
    "nano-banana-pro": ModelSpec(
        key="nano-banana-pro", label="Nano Banana Pro (fal)", backend="fal",
        max_images=14,
        cost=lambda res, q: 0.30 if res == "4k" else 0.15,
        build=_build_nano_banana("fal-ai/nano-banana-pro", "fal-ai/nano-banana-pro/edit"),
        notes="Same model as 'gemini', billed through fal.",
    ),
    "nano-banana-2.1": ModelSpec(
        key="nano-banana-2.1", label="Nano Banana 2.1", backend="fal",
        max_images=14,
        cost=lambda res, q: 0.08 if res == "4k" else 0.05,   # token-based, rough estimate
        build=_build_nano_banana("google/nano-banana-2.1", "google/nano-banana-2.1/edit"),
        notes="Released 2026-10-06. Token-based pricing; cost is a rough estimate.",
    ),
    "gpt-image-2.5-flare": ModelSpec(
        key="gpt-image-2.5-flare", label="GPT Image 2.5 Flare", backend="fal",
        max_images=16, default_quality="high",
        cost=_gpt_cost, build=_build_gpt_image("flare"),
        notes="Faster GPT Image 2.5 tier. Quality: low/medium/high/xhigh/max.",
    ),
    "gpt-image-2.5-sunburst": ModelSpec(
        key="gpt-image-2.5-sunburst", label="GPT Image 2.5 Sunburst", backend="fal",
        max_images=16, default_quality="high",
        cost=_gpt_cost, build=_build_gpt_image("sunburst"),
        notes="Precision GPT Image 2.5 tier, slower. Same pricing as Flare.",
    ),
    "flux-3": ModelSpec(
        key="flux-3", label="FLUX 3 Image", backend="fal",
        max_images=10,
        cost=_flux3_cost, build=_build_flux3,
        notes="Released 2026-10-01. Garbles small text.",
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

def run(model_key, prompt, images=(), output="out.png", *,
        aspect_ratio="16:9", resolution="2k", quality=None, seed=None):
    """Generate an image with any registered model. Images are capped at 2048px. Returns a Result."""
    load_dotenv(find_dotenv(usecwd=True))

    if model_key not in MODELS:
        raise SystemExit(f"Error: unknown model '{model_key}'. Options: {', '.join(MODELS)}")
    if resolution not in RESOLUTIONS:
        raise SystemExit(f"Error: resolution must be one of {RESOLUTIONS}")
    spec = MODELS[model_key]
    images = list(images)
    output_path = Path(output)
    warnings = []

    if len(images) > spec.max_images:
        warnings.append(f"{spec.label} accepts {spec.max_images} images; extra images were dropped.")
        images = images[:spec.max_images]

    quality = quality or spec.default_quality
    notes = ""

    if spec.backend == "gemini":
        notes = _run_gemini(prompt, images, aspect_ratio, resolution, output_path)
    else:
        if not os.environ.get("FAL_KEY"):
            raise SystemExit("Error: FAL_KEY not set. Add it to .env (get one at fal.ai/dashboard/keys).")
        ctx = {
            "prompt": prompt,
            "image_urls": [_fal_upload(p) for p in images],
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
    print(f"{'model':<24} {'backend':<7} {'imgs':>4}  {'~$/img @2k':>10}  notes")
    for spec in MODELS.values():
        print(f"{spec.key:<24} {spec.backend:<7} {spec.max_images:>4}  "
              f"{estimate_cost(spec.key):>10.3f}  {spec.notes}")


if __name__ == "__main__":
    print_models()
