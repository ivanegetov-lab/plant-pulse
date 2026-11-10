---
name: plant-pulse
description: Turn a plant's weekly numbers (safety, quality, delivery, cost, maintenance, people), a downtime log and supervisor notes into a one-page weekly plant review plus a 5-slide deck for the Monday meeting, in one self-contained HTML file. Use when someone wants a weekly plant report, SQDC review, Monday meeting deck, KPI summary for a plant manager, or asks to "turn these numbers into a report I can present".
argument-hint: "[folder or files with this week's numbers] [--plant NAME] [--period LABEL]"
allowed-tools: Bash, Read, Write, Glob, Grep
---

# Plant Pulse

One HTML file with two views of the same week:

- **The brief**: one page. Headline, scorecard by category (on target / watch / off target, with trend lines), downtime Pareto, what changed, top 3 actions with owners, decisions needed. Prints to PDF.
- **Present mode**: press **P** (or click Present). Five slides: Scorecard → Where the time went → What changed → Top 3 actions → Decisions needed. Arrow keys to move, Esc to leave.

**The rule that makes it trustworthy: the script does the math, you write the story.** `scripts/plant_pulse.py` computes every status, delta, streak and Pareto number. You never calculate a number in your head, and every number you write in the narrative must appear in the `analyze` output or in the user's notes.

## Step 1. Get the data into shape

Look at what the user gave you (CSV, Excel, a pasted table, a folder of exports). Convert it to these files in a working folder. Write a small Python script for messy exports rather than retyping numbers.

**`weekly_metrics.csv`** (required). One row per metric:

```
category,metric,unit,direction,current,target,amber,last_week,w-5,w-4,w-3,w-2
Safety,Recordable injuries,count,lower,0,0,0,0,0,1,0,0
Quality,First pass yield,%,higher,96.2,98,97,97.4,97.9,98.1,97.6,97.8
Maintenance,Backlog,crew-weeks,band:2-4,3.4,3,,3.7,4.1,4.0,3.9,3.8
```

- `category`: Safety, Quality, Delivery, Cost, Maintenance, People (others are allowed and go last). The **first metric listed in a category is its headline metric** and sets the tile's color, so list the one the plant manager cares about most first.
- `unit`: `%`, `$`, `count`, `h`, or any short label.
- `direction`: `higher`, `lower`, or `band:LOW-HIGH`.
- `target`: the plant's own target. **Ask for it if it's missing. Never invent a target.** For maintenance KPIs with no plant target you may offer the benchmark from `references/maintenance-benchmarks.md` and say where it came from. Otherwise leave it blank (the tile shows "No target").
- `amber` (optional): the "watch" limit. Blank = within 5% of target.
- `last_week`, `w-5`…`w-2` (optional): history for the trend lines. More history, better trends.

**`downtime_log.csv`** (optional, drives the Pareto): `line,cause,minutes`. One row per event or per cause per line. Group near-duplicate causes ("labeler jam", "Labeler jams") before writing.

**`notes.md`** (optional): supervisor notes, shift logs, emails. This is where the *why* comes from.

If the user only has a few numbers, that's fine. Three metrics and a downtime log still make a good report.

## Step 2. Run the analysis

```bash
python3 scripts/plant_pulse.py analyze --metrics weekly_metrics.csv --downtime downtime_log.csv
```

Read the JSON. It gives you, per metric: `status` (ok / warn / risk / none), `delta`, `delta_pct`, `trend` (better / worse / flat), `streak_weeks` (weeks in a row moving the same way), `worst_in_window`; per category: status and which metrics are red or amber; downtime: total, Pareto with cumulative %, top-3 share, lines per cause.

## Step 3. Write `narrative.json`

```json
{
  "plant": "Plant 2 · 3 packaging lines",
  "period": "Week 45 · Nov 2–8, 2026",
  "headline": "Line 3's labeler cost us the week.",
  "lead": "2–3 sentences, under 60 words, with the 2–3 numbers that explain the week.",
  "category_notes": {"Safety": "one line", "Quality": "one line"},
  "pareto_note": "one or two sentences on which causes to work on and why",
  "what_changed": ["3–5 bullets: cause and effect, not a list of numbers"],
  "actions": [{"title": "", "why": "", "owner": "", "due": ""}],
  "decisions": ["yes/no asks for the plant manager"],
  "good_news": ["1–3 things worth keeping"]
}
```

How to write it:

- **Headline = the one thing that explains the most red.** Connect the dots across categories: one root problem usually shows up in quality, delivery and cost at once. Say it in plain words, under 10 words. If the week was good, say so.
- **Every number must come from the analyze output or the notes.** Round the way the script does. No new percentages.
- **Cause and effect beats a list.** "Overtime rose to 11.8% to catch up on plan, and conversion cost followed it" is better than "Overtime 11.8%. Conversion cost $4.62."
- **Actions: exactly 3**, each tied to a specific line, asset or metric, with an owner (a role is fine) and a due day. The first step should be something someone can do this week.
- **Decisions** are things only the plant manager can approve: downtime, money, a supplier switch, people. If there are none, leave the list empty.
- **Good news is required when it exists.** A report that's all red is less believable.
- Use the plant's own words for lines, assets and causes. No consultant words (leverage, optimize, synergy, robust).
- Don't explain the metric definitions. The audience runs the plant.

## Step 4. Render

```bash
python3 scripts/plant_pulse.py render --metrics weekly_metrics.csv --downtime downtime_log.csv \
  --narrative narrative.json --out plant-pulse-<plant>-<week>.html
```

Then open it (`open <file>` on macOS) and tell the user: brief on screen, **Download PDF** for the one-pager, **P** for present mode, `#slide-3` at the end of the URL to jump to a slide.

## Step 5. Check before you hand it over

1. Every number in the headline, lead, notes and actions matches the analyze output or the notes.
2. The headline names a cause, not just a symptom ("OEE fell" is a symptom).
3. Each action has an owner and a due day.
4. Look at the result (screenshot it if you can). Nothing overlaps, nothing is cut off, the slides read from across a room.
5. Tell the user to check the story before presenting. The math is exact; the story is your best read of their notes.

## Files

- `scripts/plant_pulse.py`: analysis + HTML renderer (Python 3 standard library, no installs).
- `examples/`: a complete fictional week (`weekly_metrics.csv`, `downtime_log.csv`, `notes.md`, `narrative.json`) and the finished report `plant-pulse-week-45.html`. Use them as the reference for tone and length.
- `references/maintenance-benchmarks.md` and `references/sources.md`: published maintenance benchmarks (SMRP, Palmer, etc.), only for when the plant has no target of its own.
