# Aesthetic Thumbnails

AI-powered thumbnail creation system that researches your niche, designs concepts, generates photorealistic images, and pairs them with titles.

Built for creators who want thumbnails that stop the scroll.

<!-- TODO: Add 3-4 example thumbnail images here -->
<!-- ![Example 1](examples/example-1.png) -->
<!-- ![Example 2](examples/example-2.png) -->
<!-- ![Example 3](examples/example-3.png) -->

---

## How It Works

**3-phase creative workflow — not a template filler.**

```
Phase 1: Research       → Find outlier thumbnails in your niche
                           Study what's working and what's not
                           Identify the visual gap

Phase 2: Concept Design → 2-3 visual metaphor concepts
                           Each with mood, color, headshot selection
                           Grounded in research + visual psychology

Phase 3: Refine         → AI-generated photorealistic thumbnails
                           Auto-evaluated against 12 quality checkpoints
                           Paired with 3 title options per thumbnail
                           Previewed across YouTube contexts (desktop, mobile, TV)
```

---

## Quick Start

```bash
git clone https://github.com/younessili/aesthetic-thumbnails.git
cd aesthetic-thumbnails
```

Open Claude Code in this folder and say:

> "I just cloned this repo. Help me get set up."

Pim (the creative director built into this tool) will walk you through everything — API keys, headshots, brand setup, and your first thumbnail session.

---

## What You Need

- **Python 3.10+**
- **Claude Code** (CLI, desktop app, or IDE extension)
- **Gemini API key** — free from [ai.google.dev](https://ai.google.dev)
- **YouTube API key** (optional) — free from [Google Cloud Console](https://console.cloud.google.com). Powers the research phase.

---

## Cost

| Operation | Estimated Cost |
|-----------|---------------|
| Thumbnail generation | ~$0.134 per image |
| Outlier research | Free (YouTube API) |
| Headshot analysis | ~$0.002 per image |
| **Typical session** | **$1.50 - $2.50** |

All API keys are local — stored in your `.env` file, never uploaded anywhere.

---

## What's Inside

```
aesthetic-thumbnails/
├── CLAUDE.md              ← The brain — Pim's persona + workflow routing
├── prompt.md              ← Full 3-phase execution manual
├── learnings.md           ← Grows smarter with each session
├── execution/             ← Python scripts for generation + research
├── context/               ← Visual psychology, aesthetics, brand, titles
├── assets/headshots/      ← Your headshot photos
├── assets/inspiration/    ← Thumbnails you admire (optional)
└── output/                ← Generated thumbnails land here
```

---

## Credits

Built by [Ali Younessi](https://aliyounessi.com) / [OperateU](https://aliyounessi.com).

---

## License

MIT — free to use, customize, and fork.

This tool is actively developed. Future updates are free and available via `git pull`. Customizing core files may cause update conflicts — most people use it as-is.
