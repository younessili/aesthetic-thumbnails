#!/usr/bin/env python3
"""
Analyze headshot images using Gemini and rename them based on pose and expression.
Also builds a structured headshot index for informed selection during thumbnail generation.

Scans all images in assets/headshots/, sends each to Gemini for analysis,
and renames them with descriptive filenames like:
  confident-smile-front-facing.jpg
  serious-direct-camera-arms-crossed.jpg
  pointing-left-excited.jpg

Usage:
    # Preview renames (dry run — no files changed):
    python3 rename_headshots.py

    # Actually rename files:
    python3 rename_headshots.py --apply

    # Build/update headshot index without renaming:
    python3 rename_headshots.py --index-only

    # Build index + generate consensus identity description:
    python3 rename_headshots.py --index-only --identity

    # Rename + build index + identity in one pass:
    python3 rename_headshots.py --apply --index --identity

    # Custom headshot directory:
    python3 rename_headshots.py --dir path/to/headshots --apply

Environment:
    GEMINI_API_KEY must be set (or present in .env).
"""

import argparse
import datetime
import os
import random
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv, find_dotenv
from google import genai
from google.genai import types
from PIL import Image


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

RENAME_PROMPT = """Analyze this headshot photo and describe it for use as a filename.

I need a highly descriptive filename (5-8 words, hyphenated) so that someone choosing a headshot for a YouTube thumbnail can pick the perfect photo WITHOUT seeing it — just by reading the filename.

Describe ALL of the following that apply:

1. **Expression/emotion** (lead with this — be very specific):
   - Don't just say "smiling" — say what KIND: warm-genuine-smile, confident-smirk, big-toothy-grin, subtle-closed-mouth-smile, laughing-eyes-squinting
   - For serious: intense-focused-stare, calm-neutral-gaze, stern-no-nonsense, contemplative-thoughtful
   - For surprise/energy: wide-eyed-shocked, excited-open-mouth, eyebrows-raised-curious, mind-blown
   - Describe the eyes specifically if notable: squinting, wide-open, looking-into-camera, looking-away, eye-contact

2. **Head angle and direction**:
   - facing-camera, three-quarter-left, three-quarter-right, full-side-profile-left, full-side-profile-right
   - chin-up, chin-down, head-tilted-left, head-tilted-right, looking-over-shoulder

3. **Body and hands** (everything visible):
   - shoulders-up, waist-up, chest-up
   - arms-crossed, hand-on-chin, pointing-up, pointing-at-camera, gesturing-open-palm, hands-clasped, one-hand-raised, thumbs-up, fist-pump, leaning-forward, leaning-back
   - If holding something: holding-laptop, holding-phone, holding-coffee

4. **Lighting and mood** (only if distinctive):
   - dramatic-side-light, soft-even-light, backlit-silhouette, warm-golden-light, cool-blue-tone, high-contrast

5. **Clothing/appearance** (only if it affects thumbnail usability):
   - blazer, hoodie, t-shirt, glasses-on, glasses-off, hat

6. **Background context** (only if notable):
   - plain-backdrop, office-setup, outdoor, desk-with-monitors

Rules:
- Use lowercase with hyphens
- Be 5-8 words — more descriptive is better than shorter
- Lead with expression, then head angle, then body, then extras
- No generic words like "headshot", "photo", "portrait", "man", "person"
- Be specific enough that two similar-but-different photos get clearly different names
- The goal is: the thumbnail tool reads the filename and knows EXACTLY what this photo looks like

Respond with ONLY the filename (no extension, no explanation). Example responses:
- warm-smile-direct-camera-shoulders-up-soft-light
- intense-stare-three-quarter-right-arms-crossed-dramatic-light
- big-laugh-head-tilted-pointing-up-hoodie-bright
- serious-chin-down-eye-contact-blazer-dark-moody
- shocked-wide-eyes-open-mouth-leaning-forward-glasses
- confident-smirk-side-profile-left-hand-on-chin
- excited-eyebrows-up-gesturing-both-hands-waist-up
"""

INDEX_PROMPT = """Analyze this headshot photo and return structured metadata for a headshot index.

This index helps a content manager choose the right headshot for YouTube thumbnail concepts.

Return your analysis in EXACTLY this format (field name, pipe, value — one per line):

Expression | [specific emotion — not just "smiling" but "warm genuine smile with eyes crinkling" or "intense focused stare with slight brow furrowing"]
Eye direction | [where eyes are looking: direct at camera, looking up-right, looking down, looking left, etc.]
Mouth | [closed neutral, closed slight smile, open smile teeth showing, open surprised, etc.]
Head angle | [facing camera / three-quarter left / three-quarter right / profile left / profile right] + [tilt: tilted left / tilted right / straight / chin up / chin down]
Camera angle | [eye level, slightly below (looking up at subject), slightly above (looking down at subject)]
Body visible | [head only, shoulders up, chest up, waist up]
Pose/hands | [what hands/arms are doing if visible: arms crossed, finger pointing up, hand on chin, hands clasped, thumbs up, fist raised, etc. Say "not visible" if hands aren't in frame]
Lighting | [direction: front / side-left / side-right / Rembrandt / rim / overhead] [hardness: soft / hard / dramatic] [temperature: warm / cool / neutral]
Clothing | [what's visible: black t-shirt, white hoodie, dark jacket, etc.]
Background | [plain dark, plain light, blurred room, outdoor, etc.]
Mood keywords | [3-5 comma-separated mood words: authoritative, teaching, friendly, intense, contemplative, etc.]
Best for | [1-2 sentences: what thumbnail concepts this headshot is ideal for. Be specific — e.g. "Educational concepts where the subject is making a key point, especially with the pointing gesture" or "Dark moody concepts about struggle, reflection, or transformation"]

Be extremely specific. Two similar headshots must get clearly different descriptions.
Do NOT include the person's name or identity — describe ONLY what you see in the image.
"""

IDENTITY_PROMPT = """Look at this photo and describe ONLY the person's permanent physical features.
Be extremely specific and precise about:
- Hair (bald, hair color, style, length — be exact)
- Facial hair (beard style, length, color, any gray pattern)
- Glasses (present? frame shape — rectangular/round/aviator, frame color, lens shape)
- Face shape (oval, round, square, angular, heart, etc.)
- Skin tone (be specific — light olive, medium brown, etc.)
- Build/body type (slim, athletic, stocky, etc.)
- Eyebrow shape and thickness
- Nose shape and size (narrow, wide, prominent bridge, etc.)
- Jaw and chin (strong jawline, rounded, angular, etc.)
- Any other distinguishing permanent features

Do NOT describe expression, pose, clothing, or mood.
Respond in 5-7 bullet points, each one sentence. Be precise enough to distinguish this person from someone who shares 1-2 features."""

CONSENSUS_PROMPT = """Below are {count} independent descriptions of the SAME person, each analyzed from a different photo angle and lighting condition.

{descriptions}

Synthesize these into a single, authoritative identity description. For each feature:
- If {majority}+ of {count} agree on a feature: state it as definitive fact
- If {half}-{majority_minus} agree: state it with the majority view
- If descriptions are split: note the most common description

Output in EXACTLY this format:

PARAGRAPH:
[Write a 4-6 sentence paragraph describing this person's permanent physical features. Be extremely specific — someone reading this should be able to distinguish this person from any other person who shares one or two features. Focus on: head/hair, facial hair, glasses, face shape, skin tone, build, and any distinguishing features.]

KEY FEATURES:
- [FEATURE NAME] — [specific description, not generic. e.g. "GLASSES — rectangular black plastic frames, not round or wire-rimmed"]
- [FEATURE NAME] — [specific description]
- [FEATURE NAME] — [specific description]
- [FEATURE NAME] — [specific description]
- [FEATURE NAME] — [specific description]
- [FEATURE NAME] — [specific description]

List 4-6 key features. These are the features most critical for AI image generation to get right. Order by importance (most distinctive first)."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def resize_for_analysis(img, max_edge=1024):
    """Resize image for API analysis — don't need full resolution."""
    w, h = img.size
    if max(w, h) > max_edge:
        ratio = max_edge / max(w, h)
        new_size = (int(w * ratio), int(h * ratio))
        return img.resize(new_size, Image.LANCZOS)
    return img


def slugify(text):
    """Clean up Gemini's response into a valid filename slug."""
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text


def get_image_files(directory):
    """Get all image files in a directory."""
    extensions = {".png", ".jpg", ".jpeg", ".webp", ".avif"}
    files = []
    for f in sorted(Path(directory).iterdir()):
        if f.is_file() and f.suffix.lower() in extensions:
            files.append(f)
    return files


def deduplicate_name(name, extension, directory, used_names):
    """Add a numeric suffix if the name already exists."""
    candidate = name
    counter = 2
    while candidate in used_names or (directory / f"{candidate}{extension}").exists():
        candidate = f"{name}-{counter}"
        counter += 1
    return candidate


# ---------------------------------------------------------------------------
# Rename (existing functionality)
# ---------------------------------------------------------------------------

def analyze_headshot_for_rename(client, image_path):
    """Send a headshot to Gemini and get a descriptive filename."""
    img = Image.open(image_path)
    img = resize_for_analysis(img)

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[RENAME_PROMPT, img],
        config=types.GenerateContentConfig(
            temperature=0.1,
        ),
    )

    raw = response.text.strip()
    return slugify(raw)


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------

def analyze_headshot_for_index(client, image_path):
    """Send a headshot to Gemini and get structured metadata for the index."""
    img = Image.open(image_path)
    img = resize_for_analysis(img)

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[INDEX_PROMPT, img],
        config=types.GenerateContentConfig(
            temperature=0.1,
        ),
    )

    raw = response.text.strip()
    metadata = {}
    for line in raw.splitlines():
        if "|" in line:
            parts = line.split("|", 1)
            key = parts[0].strip().lower().replace(" ", "_")
            value = parts[1].strip()
            metadata[key] = value

    return metadata


def analyze_headshot_for_identity(client, image_path):
    """Analyze a single headshot for permanent physical features only."""
    img = Image.open(image_path)
    img = resize_for_analysis(img)

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[IDENTITY_PROMPT, img],
        config=types.GenerateContentConfig(
            temperature=0.1,
        ),
    )

    return response.text.strip()


def generate_identity_description(client, headshot_dir, sample_count=8):
    """Generate a consensus identity description from multiple headshot analyses."""
    files = get_image_files(headshot_dir)
    if not files:
        return None

    # Select a representative sample — spread across the collection
    if len(files) <= sample_count:
        sample = files
    else:
        # Pick evenly spaced + some random for coverage
        step = len(files) // sample_count
        sample = [files[i * step] for i in range(sample_count)]
        # Shuffle to avoid bias from filename ordering
        random.shuffle(sample)

    print(f"\nGenerating consensus identity from {len(sample)} headshots...")

    # Collect independent descriptions in parallel
    descriptions = []
    with ThreadPoolExecutor(max_workers=min(8, len(sample))) as executor:
        futures = {
            executor.submit(analyze_headshot_for_identity, client, path): path
            for path in sample
        }
        for future in as_completed(futures):
            path = futures[future]
            try:
                desc = future.result()
                descriptions.append((path.name, desc))
                print(f"  Analyzed: {path.name}")
            except Exception as e:
                print(f"  FAILED: {path.name}: {e}")

    if len(descriptions) < 1:
        print("  No successful headshot analyses. Cannot generate identity description.")
        return None

    # Build consensus
    desc_text = "\n\n".join(
        f"--- Photo {i+1} ({name}) ---\n{desc}"
        for i, (name, desc) in enumerate(descriptions)
    )

    count = len(descriptions)
    majority = max(count * 3 // 4, 1)  # ~75% threshold
    half = count // 2 + 1

    prompt = CONSENSUS_PROMPT.format(
        count=count,
        descriptions=desc_text,
        majority=majority,
        half=half,
        majority_minus=majority - 1,
    )

    print("  Synthesizing consensus...")
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[prompt],
        config=types.GenerateContentConfig(
            temperature=0.1,
        ),
    )

    raw = response.text.strip()

    # Parse the paragraph and key features
    paragraph = ""
    key_features = ""
    if "PARAGRAPH:" in raw and "KEY FEATURES:" in raw:
        parts = raw.split("KEY FEATURES:")
        paragraph = parts[0].replace("PARAGRAPH:", "").strip()
        key_features = parts[1].strip()
    else:
        # Fallback: use the whole response
        paragraph = raw

    return {
        "paragraph": paragraph,
        "key_features": key_features,
        "sample_count": len(descriptions),
        "date": datetime.date.today().isoformat(),
    }


def build_index(client, headshot_dir, existing_entries=None, max_workers=8):
    """Build or update the headshot index. Only analyzes new files."""
    files = get_image_files(headshot_dir)
    if not files:
        return {}

    existing_entries = existing_entries or {}
    to_analyze = []
    results = {}

    for f in files:
        if f.name in existing_entries:
            results[f.name] = existing_entries[f.name]
        else:
            to_analyze.append(f)

    if not to_analyze:
        print("  All headshots already indexed.")
        return results

    print(f"  Analyzing {len(to_analyze)} new headshot(s)...")

    with ThreadPoolExecutor(max_workers=min(max_workers, len(to_analyze))) as executor:
        futures = {
            executor.submit(analyze_headshot_for_index, client, path): path
            for path in to_analyze
        }
        for future in as_completed(futures):
            path = futures[future]
            try:
                metadata = future.result()
                results[path.name] = metadata
                print(f"    Indexed: {path.name}")
            except Exception as e:
                print(f"    FAILED: {path.name}: {e}")

    return results


def parse_existing_index(index_path):
    """Parse an existing index.md into identity section + catalog entries."""
    if not index_path.exists():
        return None, {}

    content = index_path.read_text()
    identity_section = None
    entries = {}

    # Extract identity section
    if "## Consensus Identity Description" in content:
        parts = content.split("## Consensus Identity Description", 1)
        if "## Headshot Catalog" in parts[1]:
            identity_raw = parts[1].split("## Headshot Catalog", 1)[0].strip()
            identity_section = identity_raw
        else:
            identity_section = parts[1].strip()

    # Extract catalog entries
    # Each entry starts with ### filename
    catalog_section = ""
    if "## Headshot Catalog" in content:
        catalog_section = content.split("## Headshot Catalog", 1)[1]

    current_file = None
    current_metadata = {}

    for line in catalog_section.splitlines():
        line_stripped = line.strip()
        if line_stripped.startswith("### ") and (line_stripped.endswith(".jpg") or line_stripped.endswith(".jpeg") or line_stripped.endswith(".png") or line_stripped.endswith(".webp") or line_stripped.endswith(".avif")):
            # Save previous entry
            if current_file and current_metadata:
                entries[current_file] = current_metadata
            current_file = line_stripped[4:].strip()
            current_metadata = {}
        elif "|" in line_stripped and "**" in line_stripped and current_file:
            # Parse table row: | **Field** | Value |
            parts = line_stripped.split("|")
            if len(parts) >= 3:
                key = parts[1].strip().replace("**", "").strip().lower().replace(" ", "_")
                value = parts[2].strip()
                if key and value and key not in ("field", "---"):
                    current_metadata[key] = value

    # Save last entry
    if current_file and current_metadata:
        entries[current_file] = current_metadata

    return identity_section, entries


def write_index(index_path, identity_info, entries):
    """Write the complete index.md file."""
    lines = []
    lines.append("# Headshot Index")
    lines.append("")
    lines.append(f"> Auto-generated by rename_headshots.py. Last updated: {datetime.date.today().isoformat()}.")
    lines.append("> Re-run with --index-only to update catalog. Re-run with --identity to regenerate identity description.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Identity section
    lines.append("## Consensus Identity Description")
    lines.append("")
    if identity_info and isinstance(identity_info, dict):
        lines.append(identity_info["paragraph"])
        lines.append("")
        lines.append("**Key features for AI generation:**")
        lines.append("")
        lines.append(identity_info["key_features"])
        lines.append("")
        lines.append(f"*Generated from consensus analysis of {identity_info['sample_count']} headshots on {identity_info['date']}.*")
    elif identity_info and isinstance(identity_info, str):
        # Preserved from existing index
        lines.append(identity_info)
    else:
        lines.append("*Not yet generated. Run with --identity to create.*")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Catalog section
    lines.append("## Headshot Catalog")
    lines.append("")

    # Field display order and labels
    field_order = [
        ("expression", "Expression"),
        ("eye_direction", "Eye direction"),
        ("mouth", "Mouth"),
        ("head_angle", "Head angle"),
        ("camera_angle", "Camera angle"),
        ("body_visible", "Body visible"),
        ("pose/hands", "Pose/hands"),
        ("lighting", "Lighting"),
        ("clothing", "Clothing"),
        ("background", "Background"),
        ("mood_keywords", "Mood keywords"),
        ("best_for", "Best for"),
    ]

    for filename in sorted(entries.keys()):
        metadata = entries[filename]
        lines.append(f"### {filename}")
        lines.append("")
        lines.append("| Field | Value |")
        lines.append("|-------|-------|")
        for key, label in field_order:
            value = metadata.get(key, "—")
            lines.append(f"| **{label}** | {value} |")
        lines.append("")

    index_path.write_text("\n".join(lines))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Rename headshots based on AI-detected pose and expression")
    parser.add_argument(
        "--dir",
        default=str(Path(__file__).resolve().parent.parent / "assets" / "headshots"),
        help="Directory containing headshot images (default: assets/headshots/)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually rename files. Without this flag, only previews changes (dry run).",
    )
    parser.add_argument(
        "--index",
        action="store_true",
        help="Generate/update headshot index after renaming.",
    )
    parser.add_argument(
        "--index-only",
        action="store_true",
        help="Build/update headshot index without renaming files.",
    )
    parser.add_argument(
        "--identity",
        action="store_true",
        help="Generate/update consensus identity description in the index.",
    )
    args = parser.parse_args()

    load_dotenv(find_dotenv(usecwd=True))

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)

    client = genai.Client(api_key=api_key)
    headshot_dir = Path(args.dir)

    if not headshot_dir.exists():
        print(f"Error: Directory not found: {headshot_dir}", file=sys.stderr)
        sys.exit(1)

    files = get_image_files(headshot_dir)
    if not files:
        print(f"No image files found in {headshot_dir}", file=sys.stderr)
        sys.exit(1)

    index_path = headshot_dir / "index.md"

    # --index-only mode: skip renaming, just build/update the index
    if args.index_only:
        print(f"Found {len(files)} headshot(s) in {headshot_dir}")
        print("Building headshot index...\n")

        # Load existing index for incremental update
        existing_identity, existing_entries = parse_existing_index(index_path)

        # Build/update catalog entries
        entries = build_index(client, headshot_dir, existing_entries)

        # Generate identity description if requested
        identity_info = None
        if args.identity:
            identity_info = generate_identity_description(client, headshot_dir)
        elif existing_identity:
            identity_info = existing_identity  # preserve existing

        # Write index
        write_index(index_path, identity_info, entries)
        print(f"\nIndex written to {index_path} ({len(entries)} headshots)")
        if args.identity and identity_info:
            print("Consensus identity description generated.")
        return

    # Normal rename mode
    print(f"Found {len(files)} headshot(s) in {headshot_dir}")
    if not args.apply:
        print("DRY RUN — no files will be renamed. Use --apply to rename.\n")
    else:
        print("APPLYING renames.\n")

    used_names = set()
    renames = []

    for i, filepath in enumerate(files):
        print(f"[{i+1}/{len(files)}] Analyzing: {filepath.name}...", end=" ", flush=True)

        try:
            new_name = analyze_headshot_for_rename(client, filepath)
            new_name = deduplicate_name(new_name, filepath.suffix.lower(), headshot_dir, used_names)
            used_names.add(new_name)

            new_filename = f"{new_name}{filepath.suffix.lower()}"
            new_path = headshot_dir / new_filename

            if filepath.name == new_filename:
                print(f"already named correctly")
            else:
                print(f"-> {new_filename}")
                renames.append((filepath, new_path))
        except Exception as e:
            print(f"FAILED: {e}")

    if not renames:
        print("\nNo renames needed.")
    else:
        print(f"\n{len(renames)} file(s) to rename:")
        for old, new in renames:
            print(f"  {old.name}  ->  {new.name}")

        if args.apply:
            for old, new in renames:
                old.rename(new)
            print(f"\nDone. Renamed {len(renames)} file(s).")
        else:
            print("\nDry run complete. Run with --apply to execute renames.")

    # Build index after rename if --index flag is set
    if args.index or (args.apply and args.identity):
        print("\nBuilding headshot index...")
        # Re-read files after rename
        files = get_image_files(headshot_dir)
        existing_identity, existing_entries = parse_existing_index(index_path)

        entries = build_index(client, headshot_dir, existing_entries if not args.apply else None)

        identity_info = None
        if args.identity:
            identity_info = generate_identity_description(client, headshot_dir)
        elif existing_identity:
            identity_info = existing_identity

        write_index(index_path, identity_info, entries)
        print(f"Index written to {index_path} ({len(entries)} headshots)")


if __name__ == "__main__":
    main()
