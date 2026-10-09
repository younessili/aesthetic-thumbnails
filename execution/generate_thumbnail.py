#!/usr/bin/env python3
"""
Generate a YouTube thumbnail with any registered image model (see image_models.py).

Usage:
    python3 generate_thumbnail.py \
        --headshot path/to/headshot.png \
        --prompt "detailed prompt text" \
        --output path/to/output.png

    Pick a model (default: $IMAGE_MODEL, else "gemini" = Nano Banana Pro):
    python3 generate_thumbnail.py --model flux-3 \
        --headshot a.jpg b.jpg c.jpg \
        --prompt "..." --output path/to/output.png

    With reference image (for iteration):
    python3 generate_thumbnail.py \
        --headshot path/to/headshot.png \
        --reference path/to/previous-thumbnail.png \
        --prompt "edit instruction" \
        --output path/to/output-v2.png

    With example thumbnails from high-performing videos:
    python3 generate_thumbnail.py \
        --headshot path/to/headshot.png \
        --examples path/to/example1.jpg path/to/example2.jpg \
        --prompt "detailed prompt text" \
        --output path/to/output.png

    List models, costs and limits:
    python3 generate_thumbnail.py --list-models

Environment:
    GEMINI_API_KEY for the "gemini" model, FAL_KEY for every other model.
"""

import argparse
import os
import sys

from dotenv import load_dotenv, find_dotenv

from image_models import MODELS, RESOLUTIONS, print_models, run


def parse_args():
    parser = argparse.ArgumentParser(description="Generate YouTube thumbnail")
    parser.add_argument(
        "--model", default=None,
        help=f"Image model: {', '.join(MODELS)} (default: $IMAGE_MODEL or 'gemini')"
    )
    parser.add_argument(
        "--headshot", nargs="+",
        help="Path(s) to headshot reference image(s)"
    )
    parser.add_argument(
        "--reference", nargs="*", default=[],
        help="Path(s) to additional reference images (e.g., previous thumbnail for iteration)"
    )
    parser.add_argument(
        "--examples", nargs="*", default=[],
        help="Path(s) to example thumbnails from high-performing videos (style inspiration)"
    )
    parser.add_argument(
        "--prompt",
        help="Detailed prompt for thumbnail generation"
    )
    parser.add_argument(
        "--output",
        help="Output file path for the generated thumbnail"
    )
    parser.add_argument(
        "--resolution", default="2k", choices=RESOLUTIONS,
        help="Output resolution tier (default: 2k)"
    )
    parser.add_argument(
        "--quality", default=None,
        help="Quality tier for models that have one (GPT Image: low..max, Ideogram: low/medium/high)"
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Seed, for models that support it"
    )
    parser.add_argument(
        "--aspect-ratio", default="16:9",
        help="Aspect ratio (default: 16:9)"
    )
    parser.add_argument(
        "--list-models", action="store_true",
        help="List available models and exit"
    )
    args = parser.parse_args()
    if not args.list_models:
        missing = [f for f in ("headshot", "prompt", "output") if not getattr(args, f)]
        if missing:
            parser.error("the following arguments are required: " + ", ".join(f"--{m}" for m in missing))
    return args


def main():
    args = parse_args()

    if args.list_models:
        print_models()
        return

    load_dotenv(find_dotenv(usecwd=True))
    model = args.model or os.environ.get("IMAGE_MODEL", "gemini")

    # Image order sent to the model:
    #   1. Headshot(s)
    #   2. Reference images (logos, icons, previous thumbnails)
    #   3. Example thumbnails (high-performing videos for style inspiration)
    #
    # The prompt should reference these by position (Image 1, Image 2, etc.)
    # Examples are appended last and prefixed with a system note so the model
    # knows they're style references, not elements to reproduce exactly.

    prompt = args.prompt

    if args.examples:
        prompt += (
            "\n\nSTYLE EXAMPLES:\n"
            "The final attached images are thumbnails from high-performing YouTube videos "
            "on this topic. Study their composition, color usage, text placement, and visual "
            "hierarchy — then apply those patterns to create an ORIGINAL thumbnail. "
            "Do NOT copy these thumbnails. Use them as inspiration for what works."
        )

    images = list(args.headshot) + list(args.reference) + list(args.examples)

    result = run(
        model, prompt, images, args.output,
        aspect_ratio=args.aspect_ratio, resolution=args.resolution,
        quality=args.quality, seed=args.seed,
    )

    for warning in result.warnings:
        print(f"Warning: {warning}", file=sys.stderr)
    print(f"Thumbnail saved to: {result.path}")
    print(f"Model: {model} · estimated cost: ~${result.est_cost:.3f}")
    if result.notes:
        print(f"\nModel notes: {result.notes}")


if __name__ == "__main__":
    main()
