#!/usr/bin/env python3
"""Plant Pulse: turn weekly plant metrics into a one-page brief plus a slide deck.

Two steps, standard library only:

  python3 plant_pulse.py analyze --metrics weekly_metrics.csv [--downtime downtime_log.csv]
      Prints the facts as JSON: status of every metric vs target, week-over-week
      change, streaks, and the downtime Pareto. Claude (or you) reads this and
      writes narrative.json.

  python3 plant_pulse.py render --metrics weekly_metrics.csv [--downtime downtime_log.csv] \
      --narrative narrative.json --out report.html
      Builds one self-contained HTML file: the brief (prints to PDF) and a
      Present mode (press P or click Present) with five slides.

The script never writes the story and Claude never does the math.
"""
import argparse
import csv
import html
import json
import sys
from collections import OrderedDict

CATEGORY_ORDER = ["Safety", "Quality", "Delivery", "Cost", "Maintenance", "People"]
HISTORY_PREFIX = "w-"


# ---------------------------------------------------------------- loading

def num(v):
    v = (v or "").strip().replace(",", "").replace("$", "")
    if v == "":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def load_metrics(path):
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        hist_cols = sorted(
            [c for c in reader.fieldnames if c.strip().lower().startswith(HISTORY_PREFIX)],
            key=lambda c: -int(c.strip()[2:]),
        )  # oldest first: w-5, w-4, ...
        for r in reader:
            if not (r.get("metric") or "").strip():
                continue
            m = {
                "category": (r.get("category") or "Other").strip(),
                "metric": r["metric"].strip(),
                "unit": (r.get("unit") or "").strip(),
                "direction": (r.get("direction") or "higher").strip().lower(),
                "current": num(r.get("current")),
                "target": num(r.get("target")),
                "amber": num(r.get("amber")),
                "last_week": num(r.get("last_week")),
            }
            hist = [num(r.get(c)) for c in hist_cols]
            m["history"] = [h for h in hist if h is not None]
            rows.append(m)
    return rows


def load_downtime(path):
    if not path:
        return []
    out = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            mins = num(r.get("minutes"))
            if mins is None:
                continue
            out.append({
                "line": (r.get("line") or "").strip(),
                "cause": (r.get("cause") or "Other").strip(),
                "minutes": mins,
            })
    return out


# ---------------------------------------------------------------- analysis

def status_of(m):
    cur, tgt, amb, d = m["current"], m["target"], m["amber"], m["direction"]
    if cur is None:
        return "none"
    if d.startswith("band:"):
        try:
            lo, hi = [float(x) for x in d[5:].split("-")]
        except ValueError:
            return "none"
        if lo <= cur <= hi:
            return "ok"
        span = (hi - lo) * 0.25
        return "warn" if (lo - span) <= cur <= (hi + span) else "risk"
    if tgt is None:
        return "none"
    if d == "lower":
        if cur <= tgt:
            return "ok"
        limit = amb if amb is not None else tgt * 1.05
        return "warn" if cur <= limit else "risk"
    # higher is better
    if cur >= tgt:
        return "ok"
    limit = amb if amb is not None else tgt * 0.95
    return "warn" if cur >= limit else "risk"


def is_better(direction, new, old):
    if direction == "lower":
        return new < old
    if direction.startswith("band:"):
        lo, hi = [float(x) for x in direction[5:].split("-")]
        mid = (lo + hi) / 2
        return abs(new - mid) < abs(old - mid)
    return new > old


def analyze(metrics, downtime):
    facts = {"metrics": [], "categories": OrderedDict(), "downtime": None}
    for m in metrics:
        s = status_of(m)
        series = m["history"] + ([m["last_week"]] if m["last_week"] is not None else []) + (
            [m["current"]] if m["current"] is not None else [])
        delta = None
        delta_pct = None
        trend = "flat"
        if m["current"] is not None and m["last_week"] is not None:
            delta = round(m["current"] - m["last_week"], 3)
            if m["last_week"]:
                delta_pct = round(100 * delta / abs(m["last_week"]), 1)
            if delta != 0:
                trend = "better" if is_better(m["direction"], m["current"], m["last_week"]) else "worse"
        # streak: consecutive weeks moving the same way, ending this week
        streak = 0
        if len(series) >= 2:
            sign = None
            for a, b in zip(series[-2::-1], series[:0:-1]):
                step = (b > a) - (b < a)
                if step == 0:
                    break
                if sign is None:
                    sign = step
                if step != sign:
                    break
                streak += 1
        lowest = len(series) >= 3 and m["current"] is not None and m["current"] == min(series)
        highest = len(series) >= 3 and m["current"] is not None and m["current"] == max(series)
        rec = dict(m)
        rec.update({
            "status": s, "delta": delta, "delta_pct": delta_pct, "trend": trend,
            "streak_weeks": streak, "series": series,
            "worst_in_window": (lowest if m["direction"] == "higher" else highest) and s != "ok",
            "weeks_in_window": len(series),
        })
        facts["metrics"].append(rec)
        facts["categories"].setdefault(m["category"], []).append(rec)

    # category headline = first metric listed in that category
    cat_summary = OrderedDict()
    for cat in sorted(facts["categories"], key=lambda c: CATEGORY_ORDER.index(c) if c in CATEGORY_ORDER else 99):
        ms = facts["categories"][cat]
        cat_summary[cat] = {
            "status": ms[0]["status"],
            "headline_metric": ms[0]["metric"],
            "red": [x["metric"] for x in ms if x["status"] == "risk"],
            "amber": [x["metric"] for x in ms if x["status"] == "warn"],
        }
    facts["categories"] = cat_summary

    if downtime:
        by_cause = OrderedDict()
        by_line = OrderedDict()
        for d in downtime:
            by_cause[d["cause"]] = by_cause.get(d["cause"], 0) + d["minutes"]
            if d["line"]:
                by_line[d["line"]] = by_line.get(d["line"], 0) + d["minutes"]
        total = sum(by_cause.values())
        causes = sorted(by_cause.items(), key=lambda kv: -kv[1])
        # keep "Other" last
        causes = [c for c in causes if c[0].lower() != "other"] + [c for c in causes if c[0].lower() == "other"]
        cum = 0
        pareto = []
        for cause, mins in causes:
            cum += mins
            lines = sorted({d["line"] for d in downtime if d["cause"] == cause and d["line"]})
            pareto.append({"cause": cause, "minutes": mins, "share": round(100 * mins / total, 1),
                           "cumulative": round(100 * cum / total, 1), "lines": lines})
        top3 = sum(p["minutes"] for p in pareto[:3])
        facts["downtime"] = {
            "total_minutes": total, "total_hours": round(total / 60, 1),
            "top3_share": round(100 * top3 / total) if total else 0,
            "pareto": pareto,
            "by_line": sorted(({"line": k, "minutes": v} for k, v in by_line.items()), key=lambda x: -x["minutes"]),
        }
    return facts


# ---------------------------------------------------------------- formatting

def fmt(v, unit):
    if v is None:
        return "–"
    if unit == "$":
        if abs(v) >= 1000:
            return "${:,.0f}".format(v)
        return "${:,.2f}".format(v)
    if unit == "h":
        return "{:,.1f} h".format(v)
    if float(v).is_integer():
        s = "{:,.0f}".format(v)
    else:
        s = "{:,.1f}".format(v) if abs(v) >= 10 else "{:,.2f}".format(v).rstrip("0").rstrip(".")
    if unit == "%":
        return s + "%"
    if unit in ("", "count"):
        return s
    return s + " " + unit


def fmt_delta(m):
    if m["delta"] is None:
        return ""
    d = m["delta"]
    if d == 0:
        return "no change"
    arrow = "▲" if d > 0 else "▼"
    if m["unit"] == "%":
        body = "{:.1f} pts".format(abs(d)).replace(".0 pts", " pts")
    elif m["unit"] == "$":
        body = fmt(abs(d), "$")
    elif m["delta_pct"] is not None and m["unit"] not in ("count",):
        body = "{:.0f}%".format(abs(m["delta_pct"]))
    else:
        body = fmt(abs(d), m["unit"] if m["unit"] != "count" else "")
    return "{} {}".format(arrow, body)


def target_text(m):
    d = m["direction"]
    if d.startswith("band:"):
        return "Target {}–{} {}".format(*d[5:].split("-"), m["unit"]).strip()
    if m["target"] is None:
        return "No target set"
    sign = "≤" if d == "lower" else "≥"
    return "Target {} {}".format(sign, fmt(m["target"], m["unit"]))


STATUS_LABEL = {"ok": "On target", "warn": "Watch", "risk": "Off target", "none": "No target"}


def spark(series, status, w=200, h=40, uid="s"):
    pts = [p for p in series if p is not None]
    if len(pts) < 2:
        return ""
    lo, hi = min(pts), max(pts)
    step = w / (len(pts) - 1)
    coords = []
    for i, p in enumerate(pts):
        y = h / 2 if hi == lo else (h - 5) - (p - lo) / (hi - lo) * (h - 12)
        coords.append((round(i * step, 1), round(y, 1)))
    poly = " ".join("{},{}".format(x, y) for x, y in coords)
    area = "0,{h} {p} {w},{h}".format(h=h, p=poly, w=w)
    x, y = coords[-1]
    return ('<svg class="spark s-{s}" viewBox="-4 0 {w2} {h}" preserveAspectRatio="none" aria-hidden="true">'
            '<polygon class="area" points="{a}"/><polyline points="{p}"/>'
            '<line class="dotp" x1="{x}" y1="{y}" x2="{x}" y2="{y}"/></svg>').format(s=status, w2=w + 8, h=h, a=area, p=poly, x=x, y=y)


def pareto_html(dt, big=False):
    if not dt:
        return ""
    mx = max(p["minutes"] for p in dt["pareto"])
    rows = []
    for i, p in enumerate(dt["pareto"]):
        lines = ", ".join(p["lines"]) if p["lines"] else ""
        rows.append(
            '<div class="prow{hot}"><div class="pl"><b>{c}</b><span>{ln}</span></div>'
            '<div class="ptrack"><div class="pbar" style="width:{w:.1f}%"></div></div>'
            '<div class="pm">{m:,.0f}<small> min</small></div><div class="pc">{cum:.0f}%</div></div>'.format(
                hot=" hot" if i < 3 else "", c=e(p["cause"]), ln=e(lines), w=100 * p["minutes"] / mx,
                m=p["minutes"], cum=p["cumulative"]))
    return ('<div class="pareto{b}"><div class="phead"><span>Cause</span><span></span><span>Minutes</span>'
            '<span>Running total</span></div>{r}</div>').format(b=" big" if big else "", r="".join(rows))


def e(s):
    return html.escape(str(s or ""))


# ---------------------------------------------------------------- render

def render(facts, nar):
    cats = facts["categories"]
    by_cat = OrderedDict()
    for m in facts["metrics"]:
        by_cat.setdefault(m["category"], []).append(m)
    order = list(cats.keys())
    n_off = sum(1 for c in order if cats[c]["status"] == "risk")
    n_watch = sum(1 for c in order if cats[c]["status"] == "warn")
    n_ok = sum(1 for c in order if cats[c]["status"] == "ok")

    def chip(status):
        return '<span class="chip c-{s}">{l}</span>'.format(s=status, l=STATUS_LABEL[status])

    def delta_chip(m):
        d = fmt_delta(m)
        return '<span class="dl t-{t}">{d}</span>'.format(t=m["trend"], d=e(d)) if d else ""

    notes = nar.get("category_notes", {})
    tiles = []
    for ci, c in enumerate(order):
        ms = by_cat[c]
        h = ms[0]
        subs = "".join(
            '<div class="sub"><span class="sd d-{s}"></span><span class="sn">{n}</span>'
            '<span class="sv">{v}</span>{dc}</div>'.format(s=m["status"], n=e(m["metric"]),
                                                         v=e(fmt(m["current"], m["unit"])), dc=delta_chip(m))
            for m in ms[1:])
        tiles.append(
            '<section class="card tile b-{s}"><div class="th"><h3>{c}</h3>{chip}</div>'
            '<div class="hm">{n}</div><div class="hv"><span class="v v-{s}">{v}</span>{dc}</div>'
            '<div class="tg">{t}</div>{sp}<div class="subs">{subs}</div><p class="note">{note}</p></section>'.format(
                s=cats[c]["status"], c=e(c), chip=chip(cats[c]["status"]), n=e(h["metric"]),
                v=e(fmt(h["current"], h["unit"])), dc=delta_chip(h), t=e(target_text(h)),
                sp=spark(h["series"], h["status"], uid="t%d" % ci), subs=subs, note=e(notes.get(c, ""))))

    dt = facts["downtime"]
    pareto_block = ""
    if dt:
        pareto_block = (
            '<section class="card pad"><div class="sh"><div><span class="ey">Downtime by cause</span>'
            '<h2>Where the time went</h2></div><div class="stats"><div><b>{h} h</b><span>lost this week</span></div>'
            '<div><b class="red">{t}%</b><span>from the top 3 causes</span></div></div></div>{p}'
            '<p class="pnote">{pn}</p></section>').format(h=dt["total_hours"], t=dt["top3_share"],
                                                          p=pareto_html(dt), pn=e(nar.get("pareto_note", "")))

    changed = "".join("<li>{}</li>".format(e(x)) for x in nar.get("what_changed", []))
    acts = nar.get("actions", [])[:3]
    actions = "".join(
        '<article class="act"><div class="an">{i}</div><h4>{t}</h4><p>{w}</p>'
        '<div class="meta"><span class="who">{o}</span><span class="due">{d}</span></div></article>'.format(
            i=i + 1, t=e(a.get("title")), w=e(a.get("why")), o=e(a.get("owner")),
            d=e(a.get("due") if str(a.get("due", "")).lower().startswith(("start", "by ", "due")) else "Due " + str(a.get("due", ""))))
        for i, a in enumerate(acts))
    decisions = "".join("<li>{}</li>".format(e(x)) for x in nar.get("decisions", []))
    good = "".join("<li>{}</li>".format(e(x)) for x in nar.get("good_news", []))

    summary = ('<div class="sum"><div><b class="red">{r}</b><span>off target</span></div>'
               '<div><b class="amb">{a}</b><span>to watch</span></div><div><b class="grn">{g}</b><span>on target</span></div></div>'
               ).format(r=n_off, a=n_watch, g=n_ok)

    # ---- slides
    stiles = "".join(
        '<div class="card stile b-{s}"><div class="th"><h3>{c}</h3>{chip}</div><div class="hm">{n}</div>'
        '<div class="hv"><span class="v v-{s}">{v}</span>{dc}</div><div class="tg">{t}</div>{sp}</div>'.format(
            s=cats[c]["status"], c=e(c), chip=chip(cats[c]["status"]), n=e(by_cat[c][0]["metric"]),
            v=e(fmt(by_cat[c][0]["current"], by_cat[c][0]["unit"])), dc=delta_chip(by_cat[c][0]),
            t=e(target_text(by_cat[c][0])), sp=spark(by_cat[c][0]["series"], by_cat[c][0]["status"]))
        for c in order)
    off = sorted([m for m in facts["metrics"] if m["status"] == "risk"], key=lambda m: -(abs(m["delta_pct"] or 0)))[:6]
    tcards = "".join(
        '<div class="card tcard"><div class="hm">{n}</div><div class="hv"><span class="v v-risk">{v}</span>{dc}</div>'
        '{sp}<div class="tg">{t}</div></div>'.format(n=e(m["metric"]), v=e(fmt(m["current"], m["unit"])),
                                                    dc=delta_chip(m), sp=spark(m["series"], "risk", uid="c%d" % i),
                                                    t=e(target_text(m))) for i, m in enumerate(off))

    def slide(ey, title, body, lead=""):
        return ('<section class="slide"><header class="sbar"><span class="mark"></span><span>PLANT PULSE</span>'
                '<span class="sp">{pl} · {pe}</span></header><div class="sbody"><span class="ey">{ey}</span>'
                '<h1>{t}</h1>{lead}{b}</div></section>').format(
            pl=e(nar.get("plant")), pe=e(nar.get("period")), ey=e(ey), t=e(title),
            lead='<p class="slead">{}</p>'.format(e(lead)) if lead else "", b=body)

    slides = [slide("The week in one line", nar.get("headline"), '<div class="sgrid">{}</div>'.format(stiles),
                    nar.get("lead"))]
    if dt:
        slides.append(slide("Downtime by cause · {} h lost · top 3 = {}%".format(dt["total_hours"], dt["top3_share"]),
                            "Where the time went", pareto_html(dt, big=True), nar.get("pareto_note")))
    slides.append(slide("Off target this week", "What changed",
                        '<div class="tgrid">{}</div><ul class="slist">{}</ul>'.format(tcards, changed)))
    slides.append(slide("This week", "Top 3 actions", '<div class="acts big">{}</div>'.format(actions)))
    slides.append(slide("Needs the plant manager's OK", "Decisions needed",
                        '<ul class="dec big">{}</ul>{}'.format(
                            decisions or "<li>None this week.</li>",
                            '<div class="good big"><span class="ey g">Worth keeping</span><ul>{}</ul></div>'.format(good)
                            if good else "")))

    page = TEMPLATE
    repl = {
        "{{TITLE}}": e("Plant Pulse · {} · {}".format(nar.get("plant", ""), nar.get("period", ""))),
        "{{PLANT}}": e(nar.get("plant")), "{{PERIOD}}": e(nar.get("period")),
        "{{HEADLINE}}": e(nar.get("headline")), "{{LEAD}}": e(nar.get("lead")), "{{SUMMARY}}": summary,
        "{{TILES}}": "".join(tiles), "{{PARETO}}": pareto_block, "{{CHANGED}}": changed,
        "{{ACTIONS}}": actions, "{{DECISIONS}}": decisions or "<li>None this week.</li>",
        "{{GOOD}}": ('<section class="card pad good"><span class="ey g">Worth keeping</span><ul>' + good + "</ul></section>") if good else "",
        "{{SLIDES}}": "".join(slides), "{{NSLIDES}}": str(len(slides)),
        "{{GENERATED}}": e(nar.get("generated", "")),
    }
    for k, v in repl.items():
        page = page.replace(k, v)
    return page


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{TITLE}}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
:root{--bg:#F3F4F6;--card:#fff;--ink:#111827;--ink2:#374151;--mut:#6B7280;--line:#E5E7EB;--dark:#0B1220;
--red:#DC2626;--red-bg:#FEF2F2;--amb:#D97706;--amb-bg:#FFFBEB;--grn:#059669;--grn-bg:#ECFDF5;--gry-bg:#F3F4F6;
--accent:#F06050;--bar:#CBD5E1;--font:Inter,-apple-system,"Segoe UI",system-ui,sans-serif}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--ink);font:14.5px/1.5 var(--font);
font-feature-settings:"tnum" 1,"cv11" 1;-webkit-font-smoothing:antialiased}
.top{background:var(--dark);color:#fff}
.wrap{max-width:1120px;margin:0 auto;padding:0 32px}
.brandrow{display:flex;justify-content:space-between;align-items:center;padding:22px 0 0;font:600 12px/1 var(--font);letter-spacing:1.6px;color:#9CA3AF}
.brand{display:flex;align-items:center;gap:10px;color:#fff}.mark{width:14px;height:14px;background:var(--accent);border-radius:3px;display:inline-block}
.hero{display:grid;grid-template-columns:1fr auto;gap:40px;align-items:end;padding:28px 0 34px}
.ey{display:block;font:600 11.5px/1 var(--font);letter-spacing:1.5px;text-transform:uppercase;color:var(--mut);margin-bottom:8px}
.top .ey{color:var(--accent)}
.hero h1{font:800 44px/1.08 var(--font);letter-spacing:-1.2px;margin:0 0 14px;max-width:760px}
.hero p{margin:0;font-size:16.5px;line-height:1.55;color:#D1D5DB;max-width:720px}
.sum{display:flex;gap:10px}.sum>div{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);border-radius:12px;padding:14px 18px;min-width:104px}
.sum b{display:block;font:800 34px/1 var(--font)}.sum span{font-size:12.5px;color:#9CA3AF}
.red{color:#F87171}.amb{color:#FBBF24}.grn{color:#34D399}
main.wrap{padding-top:26px;padding-bottom:48px}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:0 1px 2px rgba(16,24,40,.04)}
.pad{padding:22px 24px}
.tile{padding:18px 20px 16px;border-top:4px solid var(--line);display:flex;flex-direction:column}
.b-risk{border-top-color:var(--red)}.b-warn{border-top-color:var(--amb)}.b-ok{border-top-color:var(--grn)}
.th{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}.th h3{margin:0;font:700 15px var(--font)}
.chip{font:600 11.5px/1 var(--font);padding:5px 9px;border-radius:999px}
.c-risk{background:var(--red-bg);color:var(--red)}.c-warn{background:var(--amb-bg);color:var(--amb)}
.c-ok{background:var(--grn-bg);color:var(--grn)}.c-none{background:var(--gry-bg);color:var(--mut)}
.hm{font-size:13px;color:var(--mut);font-weight:500}
.hv{display:flex;align-items:baseline;gap:10px;margin:2px 0 0}
.v{font:800 34px/1.15 var(--font);letter-spacing:-.8px}.v-risk{color:var(--red)}.v-warn{color:var(--amb)}.v-ok{color:var(--ink)}
.dl{font:600 12.5px var(--font);color:var(--mut);white-space:nowrap}.t-worse{color:var(--red)}.t-better{color:var(--grn)}
.tg{font-size:12.5px;color:var(--mut)}
.spark{width:100%;height:40px;margin:8px 0 4px;overflow:visible}
.spark polyline{fill:none;stroke-width:2;stroke:var(--mut);vector-effect:non-scaling-stroke}.spark .area{fill:var(--mut);opacity:.08}
.spark .dotp{stroke:var(--mut);stroke-width:9;stroke-linecap:round;vector-effect:non-scaling-stroke}
.s-risk polyline{stroke:var(--red)}.s-risk .area{fill:var(--red)}.s-risk .dotp{stroke:var(--red)}
.s-ok polyline{stroke:var(--grn)}.s-ok .area{fill:var(--grn)}.s-ok .dotp{stroke:var(--grn)}
.s-warn polyline{stroke:var(--amb)}.s-warn .area{fill:var(--amb)}.s-warn .dotp{stroke:var(--amb)}
.subs{border-top:1px solid var(--line);margin-top:6px}
.sub{display:grid;grid-template-columns:10px 1fr auto auto;gap:8px;align-items:center;padding:8px 0;border-bottom:1px solid var(--line);font-size:13px}
.sd{width:8px;height:8px;border-radius:50%;background:var(--bar)}.d-risk{background:var(--red)}.d-warn{background:var(--amb)}.d-ok{background:var(--grn)}
.sn{color:var(--ink2)}.sub .sv{font-weight:700}.sub .dl{font-size:12px;min-width:62px;text-align:right}
.note{margin:12px 0 0;font-size:13px;color:var(--ink2);line-height:1.5}
.sec{margin-top:16px}
.sh{display:flex;justify-content:space-between;align-items:flex-start;gap:20px;margin-bottom:16px}
h2{font:800 24px/1.15 var(--font);letter-spacing:-.5px;margin:0}
.stats{display:flex;gap:28px;text-align:right}.stats b{display:block;font:800 30px/1 var(--font);letter-spacing:-.6px}
.stats b.red{color:var(--red)}.stats span{font-size:12.5px;color:var(--mut)}
.pareto .phead,.prow{display:grid;grid-template-columns:210px 1fr 92px 96px;gap:16px;align-items:center}
.phead{font:600 11px var(--font);letter-spacing:1.2px;text-transform:uppercase;color:var(--mut);padding:0 0 8px;border-bottom:1px solid var(--line)}
.phead span:nth-child(3),.phead span:nth-child(4){text-align:right}
.prow{padding:9px 0;border-bottom:1px solid var(--line)}
.pl b{display:block;font-weight:600;font-size:14px}.pl span{font-size:12px;color:var(--mut)}
.ptrack{height:22px;background:#F9FAFB;border-radius:6px;overflow:hidden}.pbar{height:100%;background:var(--bar);border-radius:6px}
.prow.hot .pbar{background:var(--red)}.pm{text-align:right;font-weight:700;font-size:15px}.pm small{font-weight:500;color:var(--mut);font-size:12px}
.pc{text-align:right;color:var(--mut);font-weight:600}.prow.hot .pc{color:var(--ink)}
.pnote{margin:14px 0 0;font-size:14px;color:var(--ink2)}
.two{display:grid;grid-template-columns:1.25fr 1fr;gap:16px;margin-top:16px}
ul{margin:4px 0 0;padding-left:18px}li{margin:7px 0;color:var(--ink2)}
.decide{border:1.5px solid var(--amb);background:var(--amb-bg)}.decide .ey{color:var(--amb)}.decide li{color:var(--ink);font-weight:600}
.acts{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:14px}
.act{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 20px;display:flex;flex-direction:column}
.an{width:30px;height:30px;border-radius:8px;background:var(--dark);color:#fff;font:800 15px/30px var(--font);text-align:center;margin-bottom:12px}
.act h4{margin:0 0 6px;font:700 16px/1.3 var(--font)}.act p{margin:0 0 14px;font-size:13.5px;color:var(--ink2);flex:1}
.meta{display:flex;flex-wrap:wrap;gap:6px}.meta span{font:600 12px var(--font);padding:5px 9px;border-radius:7px;background:var(--gry-bg);color:var(--ink2)}
.meta .due{background:var(--dark);color:#fff}
.col{display:flex;flex-direction:column;gap:16px}.col .good{margin-top:0;flex:1}.good{background:var(--grn-bg);border-color:#A7F3D0;margin-top:16px}.ey.g{color:var(--grn)}.good li{color:#065F46}
.foot{display:flex;justify-content:space-between;gap:20px;margin-top:26px;padding-top:16px;border-top:1px solid #D1D5DB;font-size:12.5px;color:var(--mut)}
.foot a{color:var(--ink);font-weight:600;text-decoration:none;white-space:nowrap}
.toolbar{display:flex;gap:8px}
.toolbar button{font:600 13px var(--font);padding:9px 14px;border-radius:9px;border:1px solid rgba(255,255,255,.2);background:var(--accent);color:#fff;cursor:pointer}
.toolbar button.ghost{background:transparent}
/* ---- present mode */
.deck{display:none;position:fixed;inset:0;background:var(--bg);z-index:10}
body.presenting .deck{display:block}body.presenting .top,body.presenting main{display:none}
.slide{display:none;position:absolute;inset:0;flex-direction:column}.slide.on{display:flex}
.sbar{background:var(--dark);color:#fff;display:flex;align-items:center;gap:10px;padding:16px 56px;font:700 12px/1 var(--font);letter-spacing:1.6px}
.sbar .sp{margin-left:auto;color:#9CA3AF;letter-spacing:.4px;font-weight:500;font-size:13px}
.sbody{padding:36px 56px 80px;flex:1;overflow:hidden;display:flex;flex-direction:column}
.slide h1{font:800 50px/1.06 var(--font);letter-spacing:-1.4px;margin:0 0 12px;max-width:1300px}
.slead{font-size:19px;color:var(--ink2);max-width:1180px;margin:0 0 24px}
.sgrid{display:grid;grid-template-columns:repeat(3,1fr);grid-auto-rows:1fr;gap:18px;flex:1}.stile{padding:22px 26px;border-top:5px solid var(--line);display:flex;flex-direction:column}.stile .spark{flex:1;min-height:50px;height:auto;margin-top:12px}
.stile .v{font-size:54px}.stile .th h3{font-size:18px}.stile .hm{font-size:15px}
.pareto.big .phead,.pareto.big .prow{grid-template-columns:300px 1fr 120px 130px}.pareto.big .prow{padding:13px 0}
.pareto.big .pl b{font-size:18px}.pareto.big .ptrack{height:30px}.pareto.big .pm{font-size:20px}.pareto.big .pc{font-size:17px}
.tgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.tcard{padding:16px 20px}.tcard .v{font-size:32px}.tcard .spark{height:54px}
.slist{font-size:18px;margin-top:22px}.slist li{margin:6px 0}
.acts.big{grid-template-columns:1fr;grid-auto-rows:1fr;gap:18px;flex:1;margin-top:8px}.acts.big .act{display:grid;grid-template-columns:64px 1fr 340px;grid-template-areas:"n h m" "n p m";column-gap:24px;align-content:center;padding:24px 32px}.acts.big .an{grid-area:n}.acts.big h4{grid-area:h;font-size:26px}.acts.big p{grid-area:p;font-size:18px;margin:0}.acts.big .meta{grid-area:m;flex-direction:column;align-items:flex-end;justify-content:center}.acts.big .meta span{font-size:15px;padding:8px 12px}
.acts.big .an{width:52px;height:52px;line-height:52px;font-size:24px;border-radius:12px;margin:0}
ul.dec.big{list-style:none;padding:0;margin:10px 0 0;display:grid;gap:16px}ul.dec.big li{margin:0;background:#fff;border:1.5px solid #FCD34D;border-left:8px solid var(--amb);border-radius:14px;padding:30px 34px;font:700 28px/1.3 var(--font);color:var(--ink);display:flex;justify-content:space-between;align-items:center;gap:30px}ul.dec.big li::after{content:"\2610  Yes     \2610  No";white-space:pre;font:600 20px var(--font);color:var(--mut)}
.good.big{border-radius:14px;padding:20px 26px;margin-top:36px;border:1px solid #A7F3D0}.good.big li{font-size:19px}
.deckbar{position:absolute;right:56px;bottom:22px;display:flex;gap:6px;align-items:center;font:600 13px var(--font);color:var(--mut)}
.deckbar button{font:600 13px var(--font);background:#fff;border:1px solid var(--line);border-radius:8px;padding:6px 12px;cursor:pointer;color:var(--ink)}
@media (max-width:900px){.grid,.acts,.two{grid-template-columns:1fr}.hero{grid-template-columns:1fr}.hero h1{font-size:32px}
.pareto .phead,.pareto .prow{grid-template-columns:130px 1fr 70px 60px}}
@media print{@page{size:letter;margin:10mm}html,body{background:#fff}.toolbar,.deck{display:none!important}
.wrap{max-width:none;padding:0 6mm}.hero{padding:18px 0 22px}.hero h1{font-size:30px}.card,.act{break-inside:avoid;box-shadow:none}
*{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
</style></head>
<body>
<header class="top"><div class="wrap">
  <div class="brandrow"><span class="brand"><span class="mark"></span>PLANT PULSE · WEEKLY PLANT REVIEW</span>
    <span class="toolbar"><button onclick="present(0)">Present ▸</button><button class="ghost" onclick="window.print()">Download PDF</button></span></div>
  <div class="hero"><div><span class="ey">{{PLANT}} · {{PERIOD}}</span><h1>{{HEADLINE}}</h1><p>{{LEAD}}</p></div>{{SUMMARY}}</div>
</div></header>
<main class="wrap">
  <div class="grid">{{TILES}}</div>
  <div class="sec">{{PARETO}}</div>
  <div class="two">
    <section class="card pad"><span class="ey">What changed</span><ul>{{CHANGED}}</ul></section>
    <div class="col"><section class="card pad decide"><span class="ey">Decisions needed</span><ul class="dec">{{DECISIONS}}</ul></section>{{GOOD}}</div>
  </div>
  <section class="sec"><span class="ey">This week</span><h2>Top 3 actions</h2><div class="acts">{{ACTIONS}}</div></section>
  <div class="foot"><span>Generated with the <b>Plant Pulse</b> Claude skill by Ivan Getov{{GENERATED}}. The script does the math; Claude writes the story from your notes. Check it before you present it.</span>
    <a href="https://getov.substack.com">getov.substack.com →</a></div>
</main>
<div class="deck" id="deck">{{SLIDES}}
  <div class="deckbar"><button onclick="go(-1)">‹</button><span id="cnt">1 / {{NSLIDES}}</span><button onclick="go(1)">›</button><button onclick="stop()">Esc</button></div>
</div>
<script>
var cur=0,S=document.querySelectorAll('.slide');
function show(){S.forEach(function(s,i){s.classList.toggle('on',i===cur)});document.getElementById('cnt').textContent=(cur+1)+' / '+S.length}
function present(i){cur=i||0;document.body.classList.add('presenting');show();if(document.documentElement.requestFullscreen){document.documentElement.requestFullscreen().catch(function(){})}}
function stop(){document.body.classList.remove('presenting');if(document.fullscreenElement){document.exitFullscreen()}}
function go(d){cur=Math.max(0,Math.min(S.length-1,cur+d));show()}
document.addEventListener('keydown',function(ev){var on=document.body.classList.contains('presenting');
 if(!on&&(ev.key==='p'||ev.key==='P')){present(0);return}
 if(!on)return;if(['ArrowRight','PageDown',' '].indexOf(ev.key)>-1){ev.preventDefault();go(1)}
 else if(['ArrowLeft','PageUp'].indexOf(ev.key)>-1){go(-1)}else if(ev.key==='Escape'){stop()}});
document.getElementById('deck').addEventListener('click',function(ev){if(ev.target.tagName!=='BUTTON'){go(1)}});
var m=location.hash.match(/^#slide-(\d+)$/);if(location.hash==='#present'){present(0)}else if(m){present(parseInt(m[1],10)-1)}
</script>
</body></html>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("analyze", "render"):
        p = sub.add_parser(name)
        p.add_argument("--metrics", required=True)
        p.add_argument("--downtime")
        if name == "render":
            p.add_argument("--narrative", required=True)
            p.add_argument("--out", required=True)
    a = ap.parse_args()
    facts = analyze(load_metrics(a.metrics), load_downtime(a.downtime))
    if a.cmd == "analyze":
        slim = {
            "categories": facts["categories"],
            "metrics": [{k: m[k] for k in ("category", "metric", "unit", "current", "target", "last_week", "status",
                                           "delta", "delta_pct", "trend", "streak_weeks", "worst_in_window",
                                           "weeks_in_window")} for m in facts["metrics"]],
            "downtime": facts["downtime"],
        }
        json.dump(slim, sys.stdout, indent=2)
        print()
        return
    with open(a.narrative, encoding="utf-8") as f:
        nar = json.load(f)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(render(facts, nar))
    print("wrote", a.out)


if __name__ == "__main__":
    main()
