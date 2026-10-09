#!/usr/bin/env python3
"""
Model bake-off: run the same prompts through several image models and build a
blind-scoring gallery (model names hidden until you click "Reveal").

Usage:
    # Generation test — same headshots + prompts across models
    python3 compare_models.py \
        --headshot assets/headshots/a.jpg assets/headshots/b.jpg ... \
        --prompt "Prompt 1 ..." --prompt "Prompt 2 ..." \
        --seeds 2 --output-dir output/bakeoff/gen-test

    # Edit test — same source + mask + instruction across models, with drift scores
    python3 compare_models.py \
        --source frame.png --mask frame-mask.png \
        --prompt "Replace the background with a dark navy studio wall" \
        --output-dir output/bakeoff/edit-test

    # Preview jobs and estimated cost without calling any API
    python3 compare_models.py ... --dry-run

Prompts can also come from a file (--prompt-file), one prompt per paragraph
(separated by a blank line).

Output: one image per model/prompt/seed, results.json, and index.html.
"""

import argparse
import html
import json
import random
import string
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from image_models import MODELS, RESOLUTIONS, drift_report, estimate_cost, run, tier_for_source

DEFAULT_MODELS = [
    "gemini", "nano-banana-2.1", "gpt-image-2.5-flare",
    "gpt-image-2.5-sunburst", "flux-3", "ideogram-4.5",
]


def parse_args():
    parser = argparse.ArgumentParser(description="Compare image models side by side")
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS,
                        help=f"Models to compare (default: {' '.join(DEFAULT_MODELS)})")
    parser.add_argument("--prompt", action="append", default=[], help="A test prompt (repeatable)")
    parser.add_argument("--prompt-file", default=None, help="File with prompts separated by blank lines")
    parser.add_argument("--headshot", nargs="*", default=[], help="Headshots sent with every generation prompt")
    parser.add_argument("--source", default=None, help="Edit mode: image to edit")
    parser.add_argument("--mask", default=None, help="Edit mode: mask (WHITE = change, BLACK = keep)")
    parser.add_argument("--seeds", type=int, default=1, help="Runs per model per prompt (default: 1)")
    parser.add_argument("--resolution", default=None, choices=RESOLUTIONS,
                        help="Resolution tier (default: 2k, or closest to the source in edit mode)")
    parser.add_argument("--quality", default=None, help="Quality override for models that have one")
    parser.add_argument("--aspect-ratio", default="16:9", help="Aspect ratio for generation (default: 16:9)")
    parser.add_argument("--output-dir", required=True, help="Where to write images and the gallery")
    parser.add_argument("--max-cost", type=float, default=10.0, help="Abort if the estimate exceeds this (USD)")
    parser.add_argument("--workers", type=int, default=6, help="Parallel requests (default: 6)")
    parser.add_argument("--dry-run", action="store_true", help="List jobs and estimated cost, then exit")
    args = parser.parse_args()

    if args.prompt_file:
        text = Path(args.prompt_file).read_text()
        args.prompt += [p.strip() for p in text.split("\n\n") if p.strip()]
    if not args.prompt:
        parser.error("give at least one --prompt or --prompt-file")
    if args.mask and not args.source:
        parser.error("--mask needs --source")
    if not args.source and not args.headshot:
        parser.error("give --headshot (generation test) or --source (edit test)")
    unknown = [m for m in args.models if m not in MODELS]
    if unknown:
        parser.error(f"unknown model(s): {', '.join(unknown)}. Options: {', '.join(MODELS)}")
    return args


def build_jobs(args, out_dir, resolution):
    jobs = []
    for p_idx, prompt in enumerate(args.prompt, 1):
        for model in args.models:
            for s in range(args.seeds):
                jobs.append({
                    "prompt_index": p_idx,
                    "prompt": prompt,
                    "model": model,
                    "seed": 1000 + s,
                    "path": out_dir / f"prompt-{p_idx}" / f"{model}-s{s + 1}.png",
                    "est_cost": estimate_cost(model, resolution, args.quality),
                })
    return jobs


def run_job(job, args, resolution):
    images = [args.source] if args.source else list(args.headshot)
    try:
        result = run(
            job["model"], job["prompt"], images, job["path"],
            mask=args.mask,
            aspect_ratio="auto" if args.source else args.aspect_ratio,
            resolution=resolution, quality=args.quality, seed=job["seed"],
        )
        job["warnings"] = result.warnings
        if args.source:
            job["drift"] = drift_report(args.source, result.path, args.mask)
        job["ok"] = True
    except (Exception, SystemExit) as e:  # run() exits on API errors — one failure shouldn't stop the bake-off
        job["ok"] = False
        job["error"] = str(e)[:500]
    return job


def write_gallery(jobs, args, out_dir):
    """Blind gallery: each card gets a random letter per prompt; Reveal shows the model."""
    rows = []
    for p_idx, prompt in enumerate(args.prompt, 1):
        cards = [j for j in jobs if j["prompt_index"] == p_idx]
        random.shuffle(cards)
        letters = iter(string.ascii_uppercase + string.ascii_lowercase)
        card_html = []
        for job in cards:
            letter = next(letters)
            job["blind_label"] = f"{p_idx}{letter}"
            rel = job["path"].relative_to(out_dir).as_posix()
            if job["ok"]:
                media = f'<a href="{html.escape(rel)}" target="_blank"><img src="{html.escape(rel)}" loading="lazy"></a>'
            else:
                media = f'<div class="err">Failed: {html.escape(job.get("error", ""))}</div>'
            drift = ""
            if job.get("drift"):
                d = job["drift"]
                drift = f' · drift {d["region"]}: PSNR {d["psnr_db"]} dB, MAD {d["mean_abs_diff"]}'
            card_html.append(f"""
      <figure class="card" data-id="{job['blind_label']}">
        {media}
        <figcaption>
          <strong>{job['blind_label']}</strong>
          <span class="reveal">{html.escape(job['model'])} · seed {job['seed']} · ~${job['est_cost']:.3f}{html.escape(drift)}</span>
          <label>Likeness <select data-k="likeness">{''.join(f'<option>{v}</option>' for v in ['', 1, 2, 3, 4, 5])}</select></label>
          <label>Real photo <select data-k="realism">{''.join(f'<option>{v}</option>' for v in ['', 1, 2, 3, 4, 5])}</select></label>
        </figcaption>
      </figure>""")
        rows.append(f"""
  <section>
    <h2>Prompt {p_idx}</h2>
    <p class="prompt">{html.escape(prompt)}</p>
    <div class="grid">{''.join(card_html)}
    </div>
  </section>""")

    mapping = {j["blind_label"]: j["model"] for j in jobs}
    total = sum(j["est_cost"] for j in jobs if j["ok"])
    mode = "Edit test" if args.source else "Generation test"
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Model Bake-off</title>
<style>
  :root {{ --bg:#0f0f0f; --fg:#f1f1f1; --muted:#aaa; --card:#1c1c1c; --accent:#3ea6ff; }}
  body {{ background:var(--bg); color:var(--fg); font:14px/1.5 system-ui, sans-serif; margin:0; padding:24px 16px; }}
  header {{ display:flex; flex-wrap:wrap; gap:12px; align-items:center; justify-content:space-between; }}
  h1 {{ margin:0; font-size:20px; }}
  .prompt {{ color:var(--muted); max-width:900px; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(320px, 1fr)); gap:16px; }}
  .card {{ margin:0; background:var(--card); border-radius:10px; overflow:hidden; }}
  .card img {{ width:100%; display:block; aspect-ratio:16/9; object-fit:cover; }}
  figcaption {{ padding:8px 10px; display:flex; flex-wrap:wrap; gap:8px 14px; align-items:center; }}
  .reveal {{ display:none; color:var(--accent); width:100%; }}
  body.revealed .reveal {{ display:block; }}
  button {{ background:var(--accent); color:#000; border:0; border-radius:6px; padding:8px 12px; font-weight:600; cursor:pointer; }}
  .err {{ padding:24px; color:#ff8080; aspect-ratio:16/9; overflow:auto; }}
  select {{ background:#000; color:var(--fg); border:1px solid #444; border-radius:4px; }}
</style></head>
<body>
<header>
  <h1>{mode} · {len(jobs)} images · ~${total:.2f}</h1>
  <div>
    <button onclick="document.body.classList.toggle('revealed')">Reveal models</button>
    <button onclick="exportScores()">Export scores</button>
  </div>
</header>
{''.join(rows)}
<script>
  const MAPPING = {json.dumps(mapping)};
  const KEY = "bakeoff-scores:" + location.pathname;
  let scores = {{}};
  try {{ scores = JSON.parse(localStorage.getItem(KEY) || "{{}}"); }} catch (e) {{}}
  document.querySelectorAll(".card").forEach(card => {{
    const id = card.dataset.id;
    card.querySelectorAll("select").forEach(sel => {{
      const k = sel.dataset.k;
      if (scores[id] && scores[id][k]) sel.value = scores[id][k];
      sel.addEventListener("change", () => {{
        scores[id] = Object.assign(scores[id] || {{}}, {{[k]: sel.value}});
        try {{ localStorage.setItem(KEY, JSON.stringify(scores)); }} catch (e) {{}}
      }});
    }});
  }});
  function exportScores() {{
    const rows = Object.entries(scores).map(([id, s]) => ({{id, model: MAPPING[id], ...s}}));
    const blob = new Blob([JSON.stringify(rows, null, 2)], {{type: "application/json"}});
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = "scores.json"; a.click();
  }}
</script>
</body></html>
"""
    (out_dir / "index.html").write_text(page)


def main():
    args = parse_args()
    out_dir = Path(args.output_dir)
    resolution = args.resolution or (tier_for_source(args.source) if args.source else "2k")
    jobs = build_jobs(args, out_dir, resolution)
    total = sum(j["est_cost"] for j in jobs)

    print(f"{len(jobs)} jobs · {len(args.models)} models × {len(args.prompt)} prompts × {args.seeds} seeds "
          f"· resolution {resolution} · estimated ~${total:.2f}")
    for m in args.models:
        print(f"  {m:<24} ~${estimate_cost(m, resolution, args.quality):.3f}/image")
    if args.dry_run:
        return
    if total > args.max_cost:
        sys.exit(f"Estimated cost ${total:.2f} exceeds --max-cost ${args.max_cost:.2f}. Raise it to proceed.")

    out_dir.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run_job, job, args, resolution) for job in jobs]
        for f in as_completed(futures):
            job = f.result()
            status = "ok " if job["ok"] else "ERR"
            extra = f" drift PSNR {job['drift']['psnr_db']} dB" if job.get("drift") else ""
            extra += f" — {job['error']}" if not job["ok"] else ""
            print(f"  [{status}] prompt {job['prompt_index']} · {job['model']} · seed {job['seed']}{extra}")

    write_gallery(jobs, args, out_dir)
    results = [{**j, "path": str(j["path"])} for j in jobs]
    (out_dir / "results.json").write_text(json.dumps(results, indent=2))

    spent = sum(j["est_cost"] for j in jobs if j["ok"])
    failed = sum(1 for j in jobs if not j["ok"])
    print(f"\nDone: {len(jobs) - failed}/{len(jobs)} succeeded · estimated spend ~${spent:.2f}")
    print(f"Gallery: {out_dir / 'index.html'}")


if __name__ == "__main__":
    main()
