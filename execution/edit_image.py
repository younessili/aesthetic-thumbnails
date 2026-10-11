#!/usr/bin/env python3
"""
Edit an existing image (a real video frame or an approved thumbnail) with any model,
then report how much the model changed pixels it should have left alone.

This is the "fine edit" half of mix-and-match: one model generates, another edits.

Usage:
    # Change only a box, given as fractions of the image: x0,y0,x1,y1 (0-1)
    python3 edit_image.py --model ideogram-4.5 \
        --source output/.../concept-a/v2.png \
        --region 0,0.05,0.4,0.55 \
        --prompt "Make the screen read DEMO in large white letters" \
        --output output/.../concept-a/v3.png

    # Or a hand-made mask (WHITE = change, BLACK = keep)
    python3 edit_image.py --model ideogram-4.5 \
        --source output/.../concept-a/v2.png \
        --mask output/.../concept-a/mask-board.png \
        --prompt "Replace the whiteboard drawing with a single red circle labelled STUCK" \
        --output output/.../concept-a/v3.png

    # No mask — instruction-only edit (drift is measured over the whole image)
    python3 edit_image.py --model flux-3 \
        --source frame.png --prompt "Make the background a dark navy studio wall" \
        --output frame-navy.png

    # Extra references (logo, prop, headshot) go after the source
    python3 edit_image.py --model gpt-image-2.5-flare --source frame.png \
        --reference logo.png --prompt "Put the logo from Image 2 on the mug" --output out.png

With --region or --mask, the model's output is pasted back into the source inside
the box only (soft edge), so nothing outside it can change, whatever the model does.
The unpasted model output is kept as <output>-raw.png and the mask as <output>-mask.png.
Use --no-composite to keep the model's full output instead.

Drift: mean absolute difference (0-255) and PSNR (dB) between source and the model's
raw output, outside the mask. PSNR above ~40 dB looks identical; below ~30 dB the
change shows. It tells you how well the model itself respected the mask.

Environment:
    GEMINI_API_KEY for the "gemini" model, FAL_KEY for every other model.
"""

import argparse
import json
import sys

from pathlib import Path

from image_models import MODELS, RESOLUTIONS, composite_edit, drift_report, region_mask, run, tier_for_source


def parse_args():
    parser = argparse.ArgumentParser(description="Edit an image and measure drift")
    parser.add_argument("--model", required=True, help=f"Image model: {', '.join(MODELS)}")
    parser.add_argument("--source", required=True, help="Image to edit")
    parser.add_argument("--prompt", required=True, help="Edit instruction")
    parser.add_argument("--output", required=True, help="Output file path")
    area = parser.add_mutually_exclusive_group()
    area.add_argument("--mask", default=None, help="Mask image: WHITE = change, BLACK = keep")
    area.add_argument("--region", default=None, help="Box to change, as fractions x0,y0,x1,y1 (0-1)")
    parser.add_argument("--no-composite", action="store_true",
                        help="Keep the model's full output instead of pasting it back inside the mask")
    parser.add_argument("--reference", nargs="*", default=[], help="Extra reference images (Image 2, 3, ...)")
    parser.add_argument(
        "--resolution", default=None, choices=RESOLUTIONS,
        help="Output resolution tier (default: closest to the source)"
    )
    parser.add_argument("--quality", default=None, help="Quality tier for models that have one")
    parser.add_argument("--seed", type=int, default=None, help="Seed, for models that support it")
    return parser.parse_args()


def main():
    args = parse_args()

    output = Path(args.output)
    mask = args.mask
    if args.region:
        mask = output.with_name(f"{output.stem}-mask.png")
        output.parent.mkdir(parents=True, exist_ok=True)
        region_mask(args.source, args.region).save(mask)
        print(f"Mask saved to: {mask}")
    composite = mask is not None and not args.no_composite
    raw = output.with_name(f"{output.stem}-raw{output.suffix}") if composite else output

    result = run(
        args.model, args.prompt, [args.source] + list(args.reference), raw,
        mask=mask, aspect_ratio="auto",
        resolution=args.resolution or tier_for_source(args.source),
        quality=args.quality, seed=args.seed,
    )

    for warning in result.warnings:
        print(f"Warning: {warning}", file=sys.stderr)
    print(f"Model: {args.model} · estimated cost: ~${result.est_cost:.3f}")

    drift = drift_report(args.source, result.path, mask)
    if drift:
        print(f"Model drift ({drift['region']}): {json.dumps(drift)}")

    if composite:
        composite_edit(args.source, result.path, mask, output)
        print(f"Raw model output: {result.path}")
        print(f"Edited image saved to: {output} (pasted inside the mask only — the rest is the source)")
    else:
        print(f"Edited image saved to: {result.path}")


if __name__ == "__main__":
    main()
