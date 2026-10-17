#!/usr/bin/env python3
"""Usage-aware routing for herdr-delegate.

  usage.py report [PANE]   human summary + advice (PANE adds that orchestrator's context)
  usage.py route TIER      print kind:model:effort for TIER, routing note on stderr
  usage.py bar             one-line summary for herdr's tab bar

Sources:
  * Claude: ~/.cache/herdr-delegate/usage/claude.json, written by the Claude Code
    statusline on every render (rate_limits + context_window).
  * Codex: the newest `rate_limits` event in ~/.codex/sessions rollout logs.

A provider's score is the worst of its windows. The 5-hour window counts as-is.
Weekly windows blend used% toward projected end-of-window use (used / elapsed
fraction), weighted by elapsed fraction, so a fast burn counts more as the
week goes on.

Routing: Claude stays the orchestrator and GPT is a constant supplement. Mixed
tiers (scout/light/work/heavy) alternate providers to hold GPT near a target
share of recent helper spawns: 35% when the providers are even, sliding
between 20% and 75% with the pressure gap. A provider at critical (>= 85)
hands all mixed and pinned tiers to the other one.
"""
import glob
import json
import os
import re
import sys
import time

USAGE_DIR = os.path.join(os.environ.get("HERDR_DELEGATE_STATE", os.path.expanduser("~/.cache/herdr-delegate")), "usage")
NOW = time.time()
TIGHT, CRITICAL = 60, 85  # score thresholds
STALE_S = 6 * 3600        # older data is shown but not trusted for routing

# Mixed tiers have an equivalent on each provider; spawns alternate between them
# to hold GPT at a target share of helper work (see gpt_target).
MIXED = {
    "scout": {"claude": "claude:haiku:medium",  "gpt": "codex:gpt-6-luna:medium"},
    "light": {"claude": "claude:haiku:high",    "gpt": "codex:gpt-6-luna:high"},
    "work":  {"claude": "claude:sonnet:medium", "gpt": "codex:gpt-6.1-sol:medium"},
    "heavy": {"claude": "claude:opus:high",     "gpt": "codex:gpt-6.1-sol:high"},
}
# Pinned tiers stay on their provider unless it is critical and the other isn't.
PINNED = {
    "work-gpt":   ("codex:gpt-6.1-sol:medium", "claude:sonnet:medium"),
    "heavy-gpt":  ("codex:gpt-6.1-sol:high",   "claude:opus:high"),
    "review-gpt": ("codex:gpt-6-astra:high",   "claude:opus:high"),
}
TIERS = list(MIXED) + list(PINNED)
PROVIDER = {"claude": "claude", "codex": "gpt"}
# Claude orchestrates, so GPT is always a supplement: never below MIN or above
# MAX of helper spawns. It drifts with relative pressure, with no cliff.
GPT_BASE, GPT_MIN, GPT_MAX = 0.35, 0.20, 0.75
HISTORY = 12  # recent spawns considered when balancing


def window(name, used, resets_at, minutes):
    w = {"name": name, "used": float(used), "resets_at": resets_at, "minutes": minutes}
    if resets_at and NOW >= resets_at:
        w["used"] = 0.0  # window rolled over since we last saw it
    w["score"] = w["used"]
    if minutes >= 24 * 60 and resets_at:
        elapsed = 1 - max(0.0, resets_at - NOW) / (minutes * 60)
        w["projected"] = min(200.0, w["used"] / max(elapsed, 0.15))
        # Early-week pace is noise (one heavy evening skews it), so trust the
        # projection in proportion to how much of the window has elapsed.
        w["score"] = w["used"] + (w["projected"] - w["used"]) * elapsed
    return w


def claude_usage():
    try:
        d = json.load(open(os.path.join(USAGE_DIR, "claude.json")))
    except (OSError, ValueError):
        return None
    wins = []
    for key, rl in (d.get("rate_limits") or {}).items():
        if isinstance(rl, dict) and rl.get("used_percentage") is not None:
            minutes = 300 if key.startswith("five") else 7 * 24 * 60
            label = {"five_hour": "5h", "seven_day": "7d"}.get(key, key.replace("seven_day_", "7d-"))
            wins.append(window(label, rl["used_percentage"], rl.get("resets_at"), minutes))
    return {"at": d.get("at", 0), "windows": wins}


def codex_usage():
    files = sorted(glob.glob(os.path.expanduser("~/.codex/sessions/*/*/*/*.jsonl")), key=os.path.getmtime, reverse=True)
    for path in files[:5]:
        try:
            with open(path, "rb") as f:
                f.seek(max(0, os.path.getsize(path) - 400_000))
                tail = f.read().decode(errors="ignore")
        except OSError:
            continue
        for line in reversed(tail.splitlines()):
            if '"rate_limits"' not in line:
                continue
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            rl = (ev.get("payload") or {}).get("rate_limits") or {}
            wins = []
            for slot in ("primary", "secondary"):
                w = rl.get(slot)
                if w and w.get("used_percent") is not None:
                    mins = w.get("window_minutes") or 0
                    wins.append(window("5h" if mins <= 300 else "7d", w["used_percent"], w.get("resets_at"), mins))
            if wins:
                return {"at": os.path.getmtime(path), "windows": wins}
    return None


def summarize():
    out = {}
    for prov, data in (("claude", claude_usage()), ("gpt", codex_usage())):
        if not data:
            out[prov] = {"known": False, "score": 0.0, "windows": []}
            continue
        stale = NOW - data["at"] > STALE_S
        score = max((w["score"] for w in data["windows"]), default=0.0)
        out[prov] = {"known": True, "stale": stale, "age_s": NOW - data["at"],
                     "score": 0.0 if stale else score, "raw_score": score, "windows": data["windows"]}
    return out


def level(score):
    return "critical" if score >= CRITICAL else "tight" if score >= TIGHT else "ok"


def gpt_target(usage):
    """Share of helper spawns that should go to GPT. Starts at GPT_BASE and
    slides smoothly with the pressure gap (Claude score minus GPT score)."""
    c, g = usage["claude"]["score"], usage["gpt"]["score"]
    return max(GPT_MIN, min(GPT_MAX, GPT_BASE + (c - g) / 200))


def history_path():
    return os.path.join(USAGE_DIR, "spawns.jsonl")


def recent_spawns():
    try:
        rows = [json.loads(l) for l in open(history_path()) if l.strip()]
    except (OSError, ValueError):
        return []
    return [r for r in rows if NOW - r.get("at", 0) < 24 * 3600][-HISTORY:]


def record(prov, tier, spec):
    os.makedirs(USAGE_DIR, exist_ok=True)
    rows = recent_spawns() + [{"at": int(NOW), "prov": prov, "tier": tier, "spec": spec}]
    with open(history_path(), "w") as f:
        f.writelines(json.dumps(r) + "\n" for r in rows[-HISTORY:])


def critical_override(usage, prov):
    other = "gpt" if prov == "claude" else "claude"
    return usage[prov]["score"] >= CRITICAL and usage[other]["score"] < CRITICAL, other


def route(tier, usage):
    """Return (spec, provider, note). Raw kind:model[:effort] specs are pinned."""
    if tier in PINNED:
        spec, alt = PINNED[tier]
        prov = PROVIDER[spec.split(":")[0]]
        flip, other = critical_override(usage, prov)
        if flip:
            return alt, other, f"{tier}: {prov} is critical ({usage[prov]['score']:.0f}), using {alt}"
        return spec, prov, None
    if tier not in MIXED:
        return tier, PROVIDER.get(tier.split(":")[0]), None
    # Critical quota wins outright; otherwise pick whichever provider moves the
    # recent GPT share closest to target (ties go to Claude).
    for prov in ("claude", "gpt"):
        flip, other = critical_override(usage, prov)
        if flip:
            return MIXED[tier][other], other, f"{tier}: {prov} is critical ({usage[prov]['score']:.0f}), using {other}"
    target = gpt_target(usage)
    rows = recent_spawns()
    n, g = len(rows), sum(r["prov"] == "gpt" for r in rows)
    pick = "gpt" if abs((g + 1) / (n + 1) - target) < abs(g / (n + 1) - target) else "claude"
    note = f"{tier}: {pick} (GPT share {g}/{n} recent, target {target:.0%})"
    return MIXED[tier][pick], pick, note


def fmt_windows(p):
    parts = []
    for w in p["windows"]:
        s = f"{w['name']} {w['used']:.0f}%"
        if w.get("projected") and w["projected"] > w["used"] + 5:
            s += f" (pace {w['projected']:.0f}%)"
        parts.append(s)
    return " ".join(parts) or "no data"


def context_for(pane):
    try:
        d = json.load(open(os.path.join(USAGE_DIR, f"ctx-{pane.replace(':', '_')}.json")))
        return d.get("context_window") or {}
    except (OSError, ValueError):
        return None


def report(pane):
    u = summarize()
    lines = []
    for prov, name in (("claude", "Claude Code"), ("gpt", "Codex/GPT")):
        p = u[prov]
        if not p["known"]:
            lines.append(f"{name:12} unknown (no data yet)")
            continue
        age = f"{p['age_s'] / 3600:.1f}h old, not used for routing" if p["stale"] else "fresh"
        lines.append(f"{name:12} {level(p['raw_score']):8} {fmt_windows(p)}  [{age}]")
    advice = []
    c, g = u["claude"]["score"], u["gpt"]["score"]
    rows = recent_spawns()
    lines.append(f"{'GPT share':12} target {gpt_target(u):.0%} of helper spawns; recent {sum(r['prov'] == 'gpt' for r in rows)}/{len(rows)}")
    if c >= TIGHT:
        advice.append("Claude is tight: the balancer is already shifting helpers toward GPT. Also use review-gpt for reviews and keep your own turns short (read reports and diffs, not whole files).")
    if c >= CRITICAL and g >= CRITICAL:
        advice.append("Both providers are critical: delegate only what's necessary, at scout/light tiers.")
    ctx = context_for(pane) if pane else None
    if ctx and ctx.get("remaining_percentage") is not None:
        rem = ctx["remaining_percentage"]
        lines.append(f"{'Your context':12} {rem:.0f}% left of {ctx.get('context_window_size', 0) // 1000}k")
        if rem < 30:
            advice.append("Your context is low: push reading/searching to scout helpers, ask for short reports, and avoid pasting large outputs.")
    print("\n".join(lines))
    print("advice:" + ("".join(f"\n  - {a}" for a in advice) if advice else " nothing special; tiers are balancing normally."))


def bar():
    u = summarize()
    parts = []
    for prov, name in (("claude", "cc"), ("gpt", "gpt")):
        p = u[prov]
        if p["known"]:
            parts.append(f"{name} " + " ".join(f"{w['name']} {w['used']:.0f}%" for w in p["windows"]) + ("?" if p["stale"] else ""))
    print(" · ".join(parts))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    if cmd == "route":  # route TIER [--commit]: --commit records the spawn for balancing
        tier = sys.argv[2]
        spec, prov, note = route(tier, summarize())
        if "--commit" in sys.argv:
            if prov:
                record(prov, tier, spec)
            if note:
                print(f"delegate: {note}", file=sys.stderr)
        print(spec)
    elif cmd == "bar":
        bar()
    else:
        report(sys.argv[2] if len(sys.argv) > 2 else os.environ.get("HERDR_PANE_ID", ""))
