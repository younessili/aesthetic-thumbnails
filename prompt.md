# YouTube Thumbnail Generator — V2

Generate original YouTube thumbnails using Gemini 3 Pro Image Preview (Nano Banana Pro). V2 uses a 3-phase creative workflow: Research outliers, design concepts as visual metaphors, then iteratively refine until the thumbnail is right.

---

## Background: How Viewers Decide to Click

Understand this flow — but don't let it dictate your design. It's context, not a checklist.

1. **Visual stop** — Something in the thumbnail breaks the scroll pattern. This can be an unusual composition, a striking color choice, a powerful emotion, or a visual that doesn't look like everything else in the feed.
2. **Title check** — The viewer reads the title to understand the promise. Thumbnail and title work as a package — the thumbnail provides the feeling, the title provides the information.
3. **Trust check** — The viewer looks back at the thumbnail. Does it reinforce the title's promise? Does it look authentic, not clickbait?

The best thumbnails don't follow a formula — they break patterns. Study what's working (Phase 1), then create something that stands out FROM it, not something that copies it.

---

## Phase 1: Research

Before designing anything, gather inspiration from two sources.

### 1a: Find Outlier Thumbnails

Run the outlier research script to find videos that massively outperformed their channel's average. Search within the video's topic space — the goal is to understand what thumbnails exist in this niche so you can break the pattern.

**Choosing niches:** Search 2-3 variations of the video's actual topic, plus optionally one adjacent-audience niche that shares viewers but isn't the exact same thing. The purpose is niche gap analysis — understanding what's working and what's NOT in this space.

Example for a video about "surrender and letting go":
- "surrender letting go mindset"
- "personal transformation becoming"
- "stoicism inner peace" (adjacent audience)

Do NOT use generic creative niches like "cinematic filmmaking" or "visual essays" — they return the same thumbnails every time regardless of topic and don't inform concepts.

```bash
.venv/bin/python execution/find_outliers.py \
  --topic "{video topic}" \
  --niches "{topic variation 1}" "{adjacent niche}" \
  --min-outlier-score 3.0 \
  --top 10 \
  --output-dir "output/{today}/{video-slug}/outliers"
```

Outliers are saved inside the video's output folder so all assets for one video stay together.

After running, review the downloaded thumbnails visually with the `Read` tool. Don't just look at them — study them:
- What does the TYPICAL thumbnail in this niche look like? (This is what you need to be different from.)
- What visual technique or metaphor did the outliers use to break the pattern?
- What's MISSING from this niche — what approach has nobody tried?

### 1b: Check Your Curated Inspiration

Check `assets/inspiration/` for thumbnails you have manually saved. These represent your actual taste — they carry as much (or more) weight as algorithmic outliers.

```bash
ls assets/inspiration/
```

If files exist, review them visually with the `Read` tool. Note what speaks to you aesthetically.

### 1c: Understand the Video Topic

Ask the user (if not already provided):
- What is the video about?
- What's the core message or takeaway?
- What emotion should the viewer feel?
- Any specific imagery or metaphors you have in mind?

Use these answers as the "outline" for concept design and title generation.

**Video slug for output paths:** Generate a URL-safe slug from the user's topic for the output directory. Example: "How AI Is Replacing the Operations Manager" → `ai-replacing-ops-manager`. Use this slug wherever `{video-slug}` appears in output paths (e.g., `output/{today}/ai-replacing-ops-manager/concept-a/v1.png`).

### 1d: Read Visual Psychology & Aesthetic Guides

Before designing concepts, read these two context files to ground your creative decisions in visual psychology and aesthetic principles:

```
context/visual-psychology.md   — how visual elements trigger specific emotions
context/visual-aesthetic.md    — how to make images beautiful (depth, balance, simplicity, novelty)
```

These apply to ALL visual work, not just thumbnails. Use them to make intentional choices about lighting, color, composition, and mood — don't just pick what "looks cool."

### 1e: Read Session Learnings

Read accumulated creative feedback from past thumbnail sessions:

```
learnings.md
```

These entries capture what you have picked and rejected in the past, and WHY. They contain pattern knowledge that should influence concept design and prompt writing — color palette choices for specific concept types, pose/expression combinations with unexpected emotional reads, composition patterns that perform better at thumbnail size.

Apply relevant learnings when designing concepts and writing Gemini prompts. If a learning contradicts a visual psychology rule, the learning takes precedence — it's based on actual results, not theory.

### 1f: Write Research Takeaways

After reviewing ALL outliers and inspiration, write a structured analysis before moving to Phase 2. This is NOT optional — concepts that skip this step produce generic thumbnails.

```
RESEARCH TAKEAWAYS:

Outliers reviewed: [count]

Top 3 visual techniques I observed:
1. [specific technique] — seen in [which thumbnail] — works because [why]
2. [specific technique] — seen in [which thumbnail] — works because [why]
3. [specific technique] — seen in [which thumbnail] — works because [why]

What the WORST thumbnails in this niche look like:
- [common bad pattern to avoid]
- [common bad pattern to avoid]

What's MISSING from this niche (opportunity):
- [gap — a visual approach nobody is using]
```

Every concept in Phase 2 must reference at least one takeaway. If a concept doesn't connect to any research finding, it's not research-informed — it's a guess.

### 1g: Load Headshot Index

Read the headshot index to prepare for concept design and generation:

```
assets/headshots/index.md
```

**From this file, note two things:**

1. **Consensus Identity Description** — you will paste this into every Gemini generation prompt (Phase 3) to anchor likeness. This is the text description of the user's permanent physical features.
2. **Headshot Catalog** — scan the catalog to understand what headshots are available and what each one is best suited for. Use the `Mood keywords` and `Best for` fields when selecting headshots for concepts in Phase 2.

---

## Phase 2: Concept Design

Propose 2-3 visual METAPHORS. Not layouts. Not "person on right, icon on left." Each concept should be a genuinely different creative direction.

### Where concepts come from

Draw from three sources:

1. **Script-driven** — the most visually powerful moment from the video outline. What image captures the core idea without words?
2. **Inspiration-driven** — a visual approach borrowed from an outlier or curated thumbnail, adapted (not copied) for this video
3. **Wild card** — something original. A creative risk that doesn't come from any reference.

You can also bring your own concept and skip straight to Phase 3.

### Concept brief format

For each concept, write:

```
CONCEPT: [2-3 word name]

Visual metaphor: What's the core image? Describe the SCENE, not the layout.
  Think cinematically — what would a film poster for this video look like?
  Examples:
  - "Half of a face dissolving into fragments of data and code"
  - "A man standing alone in a vast empty office, every desk cleared out"
  - "Close-up portrait in black and white, one eye reflecting a glowing screen"

Mood/tone: What does it FEEL like? (cinematic, eerie, warm, stark, surreal,
  melancholic, triumphant, unsettling, intimate)

Color approach: Be specific. Not "dark" but "black and white with a single
  warm light source" or "deep navy with gold accent on the face only"

Headshot selection: Read assets/headshots/index.md and select using this method:
  1. FILTER by pose/body needs (Head angle, Body visible, Pose/hands fields)
  2. MATCH mood and expression (Mood keywords, Expression fields)
  3. CHECK lighting compatibility (concept lighting vs headshot Lighting field)
  4. SELECT 2 headshots: primary match + secondary from a different angle
     (gives Gemini more facial geometry for better likeness)
  Present as:
    Headshot 1: [filename] — [why: cite which index fields matched]
    Headshot 2: [filename] — [why: different angle/reference for likeness]

Text: [1-3 words that capture the FEELING] or "no text — visual only"
  Consider text when it would amplify the emotion without competing with the visual.
  Text is emotional gut-reaction, not information — the title handles information.
  Skip text when negative space, darkness, or emptiness IS the concept.
  If using text: where, what color, what feeling does it trigger?

Reference: [REQUIRED — which outlier/inspiration informed this + which
  specific visual technique from Research Takeaways you're adapting.
  If this is a wild card: say "Wild card — no reference" and explain
  why this direction is better than anything in the research.]

Why this works: One sentence — why would someone stop scrolling?
```

### Key principles

- **Concept first, layout second.** Figure out what the image IS before deciding where elements go.
- **Originality over formula.** "Person on right with crossed arms and big text" is what every AI channel does. What would a film director do?
- **Restraint.** The shattering-face thumbnail works because it has ONE idea executed well — not three ideas fighting for attention.
- **3 visual elements max.** Thumbnails are tiny on mobile (320x180px). If it has more than 3 distinct visual elements, it's too busy. A face + one strong visual + text is plenty. Note: negative space, darkness, and emptiness count as visual elements when they serve the concept — don't fill them just because they look "empty."
- **Text captures feeling, not information.** When text appears on a thumbnail, it should be an emotional gut-reaction (1-3 words, the kind of thing a viewer would mutter seeing the visual), not a description or label. Big, bold, readable at 320x180. But text is a tool, not a default — use it when it amplifies the emotion, skip it when the image already says everything.
- **Color and brightness contrast.** Strong contrast between light and dark areas adds depth, makes the image feel three-dimensional, and draws the eye. A face lit warmly against a dark background. A single bright element against muted surroundings. Flat, evenly-lit images look amateur. Push for dramatic lighting with clear bright/dark separation.
- **Symmetry and balance.** The human eye is drawn to symmetrical compositions. A centered face, a balanced split, mirrored elements — these feel intentional and beautiful. Not every concept needs perfect symmetry, but consider it. Asymmetry works too when it's clearly deliberate (rule of thirds), not accidental.
- **Don't default to clickbait.** No red X's over dollar amounts. No shocked faces unless the concept genuinely calls for it. Your channel provides real value — the thumbnail should signal that.

Present all concepts to the user, then ask: "Would you like me to generate all three so you can compare side by side, or pick one to start with?" Wait for their response before generating. If the user picks one, generate that concept first. If they want all three, generate all concepts in parallel.

---

## Phase 3: Refine

Once the user picks a concept (or brings their own), generate and auto-refine.

### MANDATORY: Completion Checklist (per concept, every time)

**Every thumbnail presented to the user MUST have completed ALL of these steps in order. No steps may be skipped or deferred for any reason.**

```
□ 1. Generate image
□ 2. Read the generated image with Read tool
□ 3. Re-read headshot(s) for likeness comparison
□ 4. Write full Tier 1 quality gates (pass/fail each gate)
□ 5. If any gate fails → refine and restart from step 1
□ 6. Write full Tier 2 diagnostic scoring (all 12 checkpoints with scores)
□ 7. If score < 30 → refine weakest checkpoints and restart from step 1
□ 8. Generate 3 title options (read title-guide.md, write triangle check)
□ 9. Generate preview HTML (preview_thumbnail.py)
□ 10. Open preview for the user
□ 11. THEN present thumbnail + diagnostic + titles + preview to the user
```

**A thumbnail is not ready to present until every step above is complete.**

### Auto-Refinement Loop

Each concept goes through up to 3 rounds of automatic generation and self-evaluation. You generate, visually review the result, check it against quality gates, and if any gate fails — rewrite the prompt and try again. The user only sees thumbnails that pass all gates.

**Communicating during auto-refinement:** When a gate fails and you need to regenerate, tell the user explicitly what happened before regenerating. Example: "Concept C didn't pass the likeness gate — the face doesn't match your headshots closely enough. I'm regenerating with stronger identity instructions." The user should never wonder why you're generating again.

**Cost limit: $2.50 max per thumbnail session** (~$0.134/generation, so ~18 generations max). Track running cost across all concepts. Stop generating if approaching the limit.

#### The loop (per concept):

```
Round 1: Generate from concept brief
  → Read the image with the Read tool
  → Run Tier 1 quality gates (see below)
  → If all gates pass: write Tier 2 diagnostic → generate 3 titles → present
  → If any gate fails: note which gate failed, pick recovery strategy (see below), go to Round 2

Round 2: Recovery generation (strategy depends on WHICH gate failed — see below)
  → Run quality gates again
  → If all pass: write diagnostic → generate 3 titles → present
  → If any fail: pick recovery strategy, go to Round 3

Round 3: Final attempt
  → Run quality gates + write diagnostic → generate 3 titles
  → Present to the user regardless (3 rounds is the max)
```

**Always save every version** (v1, v2, v3) — never overwrite. The user may want to review any round.

#### Recovery strategies (which gate failed determines the Round 2+ approach):

| Gate that failed | Use `--reference`? | Recovery strategy |
|-----------------|-------------------|-------------------|
| **Likeness SOFT FAIL** | **NO** | Same headshots. Add Consensus Identity Description from `index.md` directly into prompt text. Add explicit corrections for the specific wrong features. Full prompt rewrite. |
| **Likeness HARD FAIL** | **NO** | Switch to different headshots (consult index for different angles/lighting). Add full identity description. Simplify composition if possible. If 2nd likeness failure on this concept → KILL. |
| **Photorealism** | YES | Face may be fine. Add photorealism anchors. |
| **Technical** | YES | Overall image may be good. Simplify the element causing artifacts. |
| **Readability** | YES | Overall image may be good. Remove weakest visual element. |

**Why no `--reference` on likeness failures:** The `--reference` flag tells Gemini "make something like this image." When the image has the wrong face, passing it as reference reinforces the wrong face. Fresh generation with better prompt instructions is the only path to fixing likeness.

**Concept-kill rules:**
- Same Tier 1 gate fails twice → KILL
- Likeness HARD FAIL on Round 1 + any likeness fail on Round 2 → KILL (don't waste Round 3)
- Same Tier 2 checkpoint scores WEAK twice in a row → KILL
- Gemini cannot produce what you're asking for with this prompt approach. Tell the user the concept needs a different execution strategy (e.g., real photo + post-processing) or pivot the concept.

#### Tier 1: Quality Gates (auto-refinement uses ONLY these)

Quality gates are binary pass/fail. The auto-refinement loop regenerates when any gate fails. No scores — either it passes or it doesn't.

**Gate 1: Likeness (check FIRST)**

**Important: Likeness evaluation is a filter, not a guarantee.** AI evaluating AI-generated faces has inherent limits. This gate catches obvious misses (wrong person entirely) but is not 100% reliable for subtle cases. **The user always makes the final likeness call** — never claim a thumbnail "looks like the user" with certainty. Present your assessment and let them decide.

**Step 1:** Re-read the headshot(s) passed to Gemini with the `Read` tool. Read the Consensus Identity Description from `assets/headshots/index.md`.

**Step 2: WRITTEN COMPARISON (mandatory — cannot skip).**
Write 2-3 sentences describing what you observe. You MUST address:

> "The identity description says: [paste the key features from index.md].
> The generated face shows: [describe what you actually see — face shape, nose, jawline, glasses frame, beard, skin tone].
> Match/mismatch: [specific observations about what matches and what doesn't]."

This is not a checklist. You must DESCRIBE what you see in your own words. The act of writing forces observation — if you can't describe a mismatch, there probably isn't one. If you can, there is.

**Step 3: ONE BINARY QUESTION.**
"Would someone who knows the user recognize this person?"
- YES → **PASS**
- NO or UNCERTAIN → **FAIL**

**Step 4: If FAIL — classify:**
- **SOFT FAIL:** Features are mostly right but something is off (slightly wrong face shape, one wrong feature like round vs rectangular glasses). Recoverable with a retry.
- **HARD FAIL:** This is a different person. Wrong face structure entirely, or 2+ features completely wrong. Kill-track — do NOT pass `--reference` on retry (see recovery strategies below).

**Gate 2: Photorealism**

Does it look like a real DSLR photograph? Check:
- [ ] Skin texture: visible pores, stubble, natural imperfections (not smooth/plastic)
- [ ] Lighting: natural falloff with clear bright/dark areas (not CG-uniform)
- [ ] Materials: real fabric texture on clothing (not plastic/painted)
- [ ] Depth of field: natural bokeh where present (not flat/artificial)

**If it looks like a 3D render, illustration, or digital art: FAIL.** Add photorealism anchors and regenerate.

**Gate 3: Technical Quality**

- [ ] No extra or missing fingers
- [ ] No warped or distorted hands
- [ ] No garbled text (if text is present)
- [ ] No asymmetric glasses (if present)
- [ ] No doubled edges or ghost artifacts
- [ ] No neck-body join artifacts
- [ ] No ear distortion
- [ ] No face distortion

**If face distortion or 2+ artifacts: FAIL.** Simplify the prompt (remove the element causing issues) and regenerate. If text is garbled, remove text entirely.

**Gate 4: Readability at Thumbnail Size**

Mentally shrink the image to 320x180px (YouTube mobile). Ask:
- [ ] Can you instantly tell what this image IS?
- [ ] Is there one clear dominant subject?
- [ ] Are there 3 or fewer distinct visual elements?

**If you can't tell what it is at thumbnail size: FAIL.** Remove the weakest visual element and regenerate.

#### Tier 2: Diagnostic Scoring (drives auto-refinement after gates pass)

After all Tier 1 gates pass, score 12 checkpoints across 3 zoom levels. Each checkpoint: **STRONG (3)** / **ADEQUATE (2)** / **WEAK (1)**.

**MACRO (does the whole image work?)**

| # | Checkpoint | How to assess |
|---|-----------|--------------|
| M1 | **Emotional first impression** | Look at the image for 1 second. List 3 emotions. Compare to concept brief's intended mood. Match = 3. Partial = 2. Mismatch = 1. |
| M2 | **Concept execution** | Compare generated image against brief point-by-point (pose, metaphor, lighting, key elements). All match = 3. Minor deviations = 2. Major deviation or missing key element = 1. |
| M3 | **Composition & framing** | Clear dominant subject? Placement intentional (rule of thirds or symmetry)? Frame filled, no dead zones? All yes = 3. Mostly = 2. No = 1. |
| M4 | **Scroll-stop / novelty** | Would this break a scroll in this niche? Completely different = 3. Somewhat = 2. Looks like everything else = 1. |

**MESO (do the visual elements work together?)**

| # | Checkpoint | How to assess |
|---|-----------|--------------|
| E1 | **Lighting → emotion** | Map light position/brightness/hardness/color to visual-psychology.md. Do all light factors support the intended mood? All = 3. Most = 2. Any contradict = 1. |
| E2 | **Color → emotion** | Map hue/saturation/luminance to visual-psychology.md. Does palette support intended mood? All = 3. Mostly = 2. Wrong associations = 1. |
| E3 | **Depth** | Check 3 factors from visual-aesthetic.md: brightness contrast, color contrast, sharpness contrast. All 3 present = 3. Two = 2. One or none = 1. (Monochromatic is valid if it serves the concept — per learnings.) |
| E4 | **Balance** | Brightness distribution, color distribution, subject weight. All balanced (or deliberately imbalanced) = 3. Mostly = 2. Accidentally lopsided = 1. |

**MICRO (are the details right?)**

| # | Checkpoint | How to assess |
|---|-----------|--------------|
| D1 | **Skin & texture** | Visible pores, stubble, imperfections? Natural = 3. Slightly smooth = 2. Plastic/CG = 1. |
| D2 | **Edge quality** | Clean transitions at body outline, clothing edges, head boundary? All clean = 3. Minor issues = 2. Obvious artifacts = 1. |
| D3 | **Eyes & expression** | Correct expression per brief, realistic iris, appropriate catch lights? All good = 3. Minor issues = 2. Wrong expression or dead eyes = 1. |
| D4 | **Background quality** | Clean, intentional, serves composition? Clean = 3. Minor issues = 2. Distracting = 1. |

**Scoring & auto-refinement decision:**

- **30-36 (83%+):** Present to the user — ready
- **24-29 (67-80%):** Identify WEAK checkpoints → refine prompt targeting those → regenerate
- **Below 24:** Consider killing the concept
- **Priority:** Fix Macro WEAK first, then Meso, then Micro (high-impact before details)
- **Concept-kill:** If the same checkpoint scores WEAK twice in a row → KILL (Gemini can't deliver it)

**Context rule:** When scoring, consider combinations and learnings. A checkpoint that "fails" per individual psychology rules but works in the COMBINATION can still be ADEQUATE or STRONG. Reference specific learnings when overriding a rule.

#### How to write the full evaluation

After reading each generated image, first re-read the headshot(s) for comparison, then write:

```
QUALITY GATES (concept-{letter}/v{n}):
  Likeness:      ✓/✗ — {feature-by-feature}
  Photorealism:  ✓/✗ — {what looks real, what doesn't}
  Technical:     ✓/✗ — {list any artifacts}
  Readability:   ✓/✗ — {element count, thumbnail-size check}
  → ALL PASS / FAIL on {which gate}

DIAGNOSTIC SCORING (concept-{letter}/v{n}):
  MACRO:
    M1 Emotional impression: {3/2/1} — {3 emotions felt vs intended mood}
    M2 Concept execution:    {3/2/1} — {brief vs actual, point-by-point}
    M3 Composition:          {3/2/1} — {subject, placement, frame fill}
    M4 Scroll-stop:          {3/2/1} — {vs niche}
  MESO:
    E1 Lighting → emotion:   {3/2/1} — {position/brightness/hardness/color → guide}
    E2 Color → emotion:      {3/2/1} — {hue/saturation/luminance → guide}
    E3 Depth:                {3/2/1} — {brightness/color/sharpness contrast}
    E4 Balance:              {3/2/1} — {distribution checks}
  MICRO:
    D1 Skin & texture:       {3/2/1} — {pores, stubble, imperfections}
    D2 Edge quality:         {3/2/1} — {boundary transitions}
    D3 Eyes & expression:    {3/2/1} — {expression match, iris, catch lights}
    D4 Background:           {3/2/1} — {clean, intentional}

  Total: {sum}/36 ({percentage}%)
  → PRESENT / REFINE {weakest checkpoints} / KILL
  Running cost: ~${cost} / $2.50 limit
```

#### Title Generation (runs after diagnostic, before presenting to the user)

After a thumbnail passes quality gates and diagnostic scoring, generate 3 title options before presenting to the user. Read `context/title-guide.md` for the full process.

**Process:**

1. **Look at the generated thumbnail.** What does it SHOW? What emotion does it trigger? What question does it raise?

2. **Re-read the video topic and core message** (from Phase 1c). What is this video actually about? What's the core promise?

3. **Find the gap.** What information does the viewer need — that the thumbnail alone doesn't convey — to decide "I need to watch this"?

4. **Write 3 title options.** Each title must:
   - Complete the thumbnail's visual message (not repeat it)
   - Accurately represent the actual video content
   - Front-load the hook (first 5-6 words work alone on mobile)
   - Be under 60 characters
   - Be specific (numbers, dollar amounts, named things)

5. **Check the triangle for each title.** Ask: if a viewer sees this thumbnail + this title, clicks, and watches the video — will they feel the promise was kept? If not, rewrite.

**Title presentation format:**

```
THUMBNAIL + TITLE OPTIONS (concept-{letter}/v{n}):

[Tier 2 diagnostic as before]

Title options:
  1. "{title}" — {why this pairs with the thumbnail + what gap it fills}
  2. "{title}" — {why this pairs with the thumbnail + what gap it fills}
  3. "{title}" — {why this pairs with the thumbnail + what gap it fills}

Triangle check:
  Thumbnail shows: {what the image conveys}
  Titles tell: {what information the titles add}
  Video delivers: {what the viewer actually gets}
```

**During the user's feedback rounds:** When the user refines a thumbnail, also check if the title options still fit. If the thumbnail's visual direction changes significantly, regenerate titles. If the user picks a title, keep it stable across subsequent thumbnail refinements unless the user says otherwise.

#### Preview (runs after title generation, before presenting to the user)

After generating title options, create a visual preview so the user can see the thumbnail + title packages the way viewers will. The preview HTML lives at the **video-slug level** (next to the concept folders), not inside a concept folder.

**Comparing multiple concepts (typical):**
```bash
.venv/bin/python \
  execution/preview_thumbnail.py \
  --thumbnail \
    "output/{today}/{video-slug}/concept-a/v{n}.png" \
    "output/{today}/{video-slug}/concept-b/v{n}.png" \
    "output/{today}/{video-slug}/concept-c/v{n}.png" \
  --titles "{title for A}" "{title for B}" "{title for C}" \
  --output "output/{today}/{video-slug}/preview.html"
```

**Single concept with 3 title options:**
```bash
.venv/bin/python \
  execution/preview_thumbnail.py \
  --thumbnail "output/{today}/{video-slug}/concept-{letter}/v{n}.png" \
  --titles "{title 1}" "{title 2}" "{title 3}" \
  --output "output/{today}/{video-slug}/preview.html"
```

Open the preview:
```bash
open "output/{today}/{video-slug}/preview.html"
```

The user sees each option rendered across 4 YouTube contexts (Desktop Home, Sidebar, Mobile, TV) in dark mode. The "Open in Finder" link in the preview opens the folder where the thumbnail PNGs are saved.

**During the user's feedback rounds:** Regenerate the preview after each new thumbnail version. The preview always overwrites `preview.html` at the video-slug level.

#### How to fix failing checkpoints

When refining, add EXPLICIT counter-instructions to the prompt targeting the WEAK checkpoints:

- **M2 (concept execution)** → Rewrite the specific element that deviated. Be more explicit and repetitive about the key visual requirement.
- **M1 (emotional impression)** → Adjust lighting hardness, color temperature, or pose to shift the mood. Reference visual-psychology.md for which element triggers which emotion.
- **E1 (lighting)** → Specify exact light position, hardness, and color. Add: "The lighting must feel [emotion] — use [position] light with [hardness] quality."
- **E3 (depth)** → Add missing contrast factor. If color contrast missing: add a complementary temperature. If sharpness missing: specify depth of field.
- **Likeness SOFT FAIL** → Do NOT use `--reference`. Keep same headshot(s). Add Consensus Identity Description from `index.md` directly into prompt. Add explicit corrections: "glasses must be RECTANGULAR frames, not round" etc.
- **Likeness HARD FAIL** → Do NOT use `--reference`. Switch to different headshot(s) from the index — pick ones with different angles/lighting. Add full identity description. Simplify composition. If 2nd failure → KILL.
- **Photorealism gate fails** → Add: "PHOTOREALISTIC. Shot on Canon EOS R5, 85mm f/1.8. Real skin texture with visible pores. NOT a 3D render, NOT digital art."
- **Technical gate fails (text)** → Remove text entirely or simplify to 1-2 words.
- **Technical gate fails (hands)** → Remove hands from the prompt or reframe pose.
- **Readability gate fails** → Remove the weakest visual element until 3 or fewer remain.

### First generation prompt rules

Every prompt should include these photorealism anchors from the start (don't wait for a failed eval):
- "PHOTOREALISTIC — this must look like a real photograph, not a 3D render or illustration"
- Specific camera + lens reference (e.g., "Shot on Canon EOS R5 with 85mm portrait lens")
- "Real skin texture with visible pores, stubble, natural imperfections"
- Pass 2 headshots when possible for better likeness (selected via index — see Phase 2)
- Copy the Consensus Identity Description from `assets/headshots/index.md` into every generation prompt. Place it after the scene description. Format: "The person in this image MUST match this description: [paste identity paragraph]. These features must be accurate — especially [most critical key features]."
- Do NOT rely on Gemini to infer physical features from the headshot alone — the identity description spells them out explicitly.

### Generation commands

**Round 1:**
```bash
.venv/bin/python execution/generate_thumbnail.py \
  --headshot "assets/headshots/{headshot-1}" \
    "assets/headshots/{headshot-2}" \
  --prompt "{complete prompt with photorealism anchors}" \
  --output "output/{today}/{video-slug}/concept-{letter}/v1.png"
```

**Round 2+ when photorealism/technical/readability failed (pass reference):**
```bash
.venv/bin/python execution/generate_thumbnail.py \
  --headshot "assets/headshots/{headshot-1}" \
    "assets/headshots/{headshot-2}" \
  --reference "output/{today}/{video-slug}/concept-{letter}/v{n-1}.png" \
  --prompt "{complete revised prompt — full rewrite, not just 'change X'}" \
  --output "output/{today}/{video-slug}/concept-{letter}/v{n}.png"
```

**Round 2+ when LIKENESS failed (NO reference — fresh generation):**
```bash
.venv/bin/python execution/generate_thumbnail.py \
  --headshot "assets/headshots/{headshot-1}" \
    "assets/headshots/{headshot-2}" \
  --prompt "{complete revised prompt with identity description from index.md}" \
  --output "output/{today}/{video-slug}/concept-{letter}/v{n}.png"
```

### Critical rules

- Write a NEW complete prompt every round — Gemini doesn't remember previous calls
- Always pass headshot(s) every round — likeness degrades without the reference
- **Outlier thumbnails are for YOUR creative reference only** — do NOT pass them to Gemini via `--examples`. Study them yourself and translate what you learn into prompt text.
- Run concepts in parallel when refining multiple concepts
- After auto-refinement, present the best version of each concept to the user with the Tier 2 diagnostic and 3 title options

### Refining multiple concepts

After presenting concepts, ask: "Which concept(s) do you want me to refine?"

- "Refine A" → auto-refine concept A only (up to 3 rounds)
- "Refine all three" → auto-refine A, B, C in parallel
- "Refine A and C" → just those two
- The user can say "actually here's my own idea" and you refine from that

### The user's feedback rounds

After auto-refinement presents the best version, the user may still want changes. These are SEPARATE from the auto-refinement loop — the user's creative feedback always gets additional rounds (no limit, just cost awareness). Show the running cost and warn if approaching $1.

### Output structure

```
output/{today}/{video-slug}/
  concept-a/
    v1.png       ← auto-refinement round 1
    v2.png       ← auto-refinement round 2
    v3.png       ← auto-refinement round 3 (best auto result)
    v4.png       ← the user's feedback round 1
    v5.png       ← the user's feedback round 2 (final)
  concept-b/
    v1.png       ← auto-refinement passed on round 1
    v2.png       ← the user's feedback (final)
```

---

## Post-Session: Capture Learnings

After the user picks their final thumbnail (or the session ends), log what was learned to `learnings.md`.

Present the final thumbnail file path and chosen title to the user.

**When to write a learning:**
- The user chose one concept over another — why? What made it better?
- The user rejected a "technically correct" refinement — what did the eval miss?
- A specific prompt technique produced unexpectedly good or bad results
- A visual psychology rule was confirmed or contradicted by context
- An aesthetic principle worked differently than expected at thumbnail size
- The user chose one title over another — why? What made it pair better with the thumbnail?

**Format:** Append to the appropriate category section:

```markdown
## [Category]
- [YYYY-MM-DD] [Observation]. [Context/reasoning].
```

**Rules:**
- Group by category (Creative Direction, Composition, Color, Lighting, Prompting, Eval)
- Each entry includes the date and specific context
- Prune entries that are contradicted by newer learnings
- These are creative PATTERN knowledge, not rules — always consider context
- Keep entries concise: 1-2 sentences max

---

## Technical Constraints

These apply to ALL concepts regardless of creative direction:

- **16:9 aspect ratio** — YouTube standard. The script enforces this automatically.
- **Readable at 320x180px** — the smallest YouTube thumbnail display size (mobile). If you can't see it at that size, it's too small or too cluttered.
- **Bottom-right corner clear** — YouTube's timestamp overlay covers this area. Don't put important elements there.
- **Text (if used): 1-3 words max.** Emotional gut-reaction, not labels or descriptions. Must complement the title, never repeat it. Must be readable at 320x180px — if it can't be bold and clear at thumbnail size, skip it.
- **Output format:** PNG

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| No image returned / `candidates` is None | Simplify the prompt. Reduce the number of attached images (max 2-3 total). Try again — API calls can intermittently fail. |
| Person doesn't look like the headshot | Add more explicit instruction: "Use the exact likeness from the attached reference photo including facial hair and glasses." Try passing 2 headshots for more reference angles. |
| Text is garbled or unreadable | Gemini's text rendering isn't perfect. Consider generating without text and adding it in post-production (Figma, Canva). |
| Wrong aspect ratio | The script sets 16:9 automatically. If the output looks wrong, check the saved file dimensions. |
| API error or timeout | Check that GEMINI_API_KEY is set in `.env`. Try again — transient 500 errors happen. |
| find_outliers.py returns no results | Lower `--min-outlier-score` to 2.0. Try different niche search terms. Check that YOUTUBE_API_KEY is set. If API quota is exhausted, proceed to Phase 2 using curated inspiration only. |
| YouTube API quota exhausted (403) | The script exits immediately on quota errors. Wait until tomorrow (resets daily) or proceed without Phase 1 research — it's valuable but not blocking. |
| Too many images cause generation failure | Gemini has limits on input images. Use max 1-2 headshots + 1 reference. Don't pass `--examples` alongside `--reference`. |
