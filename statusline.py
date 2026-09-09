#!/usr/bin/env python3
"""Claude Code status line.

Draws the model, effort, advisor, context window and rate limits from the
JSON that Claude Code sends on stdin.
Schema: https://code.claude.com/docs/en/statusline

The advisor model is not part of that JSON (as of 2.1.229), so it is recovered
from the advisorModel field of the last assistant message in the transcript.

The look owes a lot to ccstatusline: a continuous truecolor gradient and bars
drawn at sub-cell precision. The Powerline separator needs a Nerd Font, so it
is not the default.

  Style   : CC_STATUSLINE_STYLE=powerline (default is minimal)
  Reset   : CC_STATUSLINE_RESET="in " if your font has no ↻ (U+21BB)
  Compare : python3 ~/.claude/statusline.py --demo
  Debug   : touch ~/.claude/.statusline-debug and the raw JSON lands in
            ~/.claude/.statusline-input.json
"""

import json
import os
import re
import sys
import time

HOME = os.path.expanduser("~")
DEBUG_FLAG = os.path.join(HOME, ".claude", ".statusline-debug")
DEBUG_OUT = os.path.join(HOME, ".claude", ".statusline-input.json")

STYLE = os.environ.get("CC_STATUSLINE_STYLE", "minimal")

R = "\033[0m"
BOLD = "\033[1m"
NORMAL = "\033[22m"  # cancels the dim Claude Code applies to the line

# ANSI dim (SGR 2) stacks with Claude Code's own dim and the text disappears.
# Anything that should recede gets an explicit grey instead of dim.
C_VALUE = (222, 228, 240)
C_LABEL = (154, 165, 184)
C_DETAIL = (138, 148, 168)
C_MUTED = (125, 135, 155)
C_DIVIDER = (88, 97, 116)
C_EMPTY = (74, 82, 99)

BAR_W = 5
# Partial cells: the end of the bar is drawn in 1/8 steps, so a small value
# such as 8% still leaves something visible
EIGHTHS = " ▏▎▍▌▋▊▉"
FULL = "█"
EMPTY = "·"

PL_SEP = ""  # Powerline right arrow (needs a Nerd Font)

# Marks the time until a limit resets. U+21BB is missing from most coding fonts
# (1 of the 9 mainstream ones checked), so the terminal has to fall back to
# another face for it. Set CC_STATUSLINE_RESET to anything you like -- "in " is
# a safe ASCII choice, an empty string drops the marker.
RESET_MARK = os.environ.get("CC_STATUSLINE_RESET", "↻")

# Usage to colour stops. green = room, amber = watch it, red = nearly out
HEAT_STOPS = ((0, (126, 196, 140)), (55, (223, 190, 100)),
              (80, (228, 148, 78)), (100, (222, 88, 88)))

ACCENT_MODEL = (128, 190, 235)
ACCENT_ADVISOR = (120, 200, 190)
ACCENT_FLAG = (238, 200, 110)
NEUTRAL = (150, 158, 172)
PL_INK = (26, 28, 34)  # ink laid over the coloured backgrounds in powerline


def fg(rgb):
    return f"\033[38;2;{rgb[0]};{rgb[1]};{rgb[2]}m"


def bg(rgb):
    return f"\033[48;2;{rgb[0]};{rgb[1]};{rgb[2]}m"


def heat(pct):
    """Usage to a continuous colour. It leans towards red gradually rather
    than jumping at a threshold."""
    pct = max(0.0, min(100.0, pct))
    for (p0, c0), (p1, c1) in zip(HEAT_STOPS, HEAT_STOPS[1:]):
        if pct <= p1:
            t = (pct - p0) / (p1 - p0) if p1 > p0 else 0.0
            return tuple(round(a + (b - a) * t) for a, b in zip(c0, c1))
    return HEAT_STOPS[-1][1]


def bar_cells(pct, width=BAR_W):
    """A bar at sub-cell precision. 8% at width=7 still raises a ▍."""
    cells = max(0.0, min(width, pct / 100 * width))
    full = int(cells)
    part = EIGHTHS[int((cells - full) * 8)].strip()
    filled = FULL * full + part
    return filled, EMPTY * (width - len(filled))


def bar(pct, width=BAR_W):
    filled, rest = bar_cells(pct, width)
    return f"{filled}{fg(C_EMPTY)}{rest}{R}"


def tokens(n):
    """Reads 999,950 as 1.0M rather than 1000k (ccstatusline's rounding)."""
    if n >= 999_500:
        v = n / 1_000_000
        return f"{v:.1f}M".replace(".0M", "M")
    if n >= 1_000:
        return f"{n / 1_000:.0f}k"
    return str(n)


def until(epoch):
    """Time left until the reset, as 2h19m / 3d5h."""
    if not epoch:
        return ""
    left = int(epoch) - int(time.time())
    if left <= 0:
        return ""
    d, rem = divmod(left, 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    if d:
        return f"{d}d{h}h"
    if h:
        return f"{h}h{m:02d}m"
    return f"{m}m"


def short_model(name, model_id):
    """Shortens "Opus 5 (1M context)" to "Opus 5 1M"."""
    name = re.sub(r"\s*\((\d+M) context\)", r" \1", name or model_id or "?")
    if "1M" not in name and "[1m]" in (model_id or ""):
        name += " 1M"
    return name.strip()


def advisor_of(transcript_path):
    """The advisorModel of the last assistant message, or None."""
    if not transcript_path or not os.path.exists(transcript_path):
        return None
    try:
        size = os.path.getsize(transcript_path)
        with open(transcript_path, "rb") as f:
            f.seek(max(0, size - 512 * 1024))
            chunk = f.read()
        lines = chunk.split(b"\n")
        if size > 512 * 1024 and lines:
            lines.pop(0)  # the first line was cut mid-way, drop it
        for line in reversed(lines):
            if b'"type":"assistant"' not in line:
                continue
            m = re.search(rb'"advisorModel"\s*:\s*"([^"]+)"', line)
            return m.group(1).decode() if m else None
    except OSError:
        return None
    return None


def pretty_advisor(model_id):
    """Turns "claude-opus-4-8" into "Opus 4.8"."""
    low = model_id.lower()
    for key, label in (("fable", "Fable"), ("opus", "Opus"),
                       ("sonnet", "Sonnet"), ("haiku", "Haiku")):
        if key in low:
            ver = re.search(rf"{key}-(\d+)(?:-(\d+))?", low)
            if not ver:
                return label
            return f"{label} {ver.group(1)}.{ver.group(2)}" if ver.group(2) \
                else f"{label} {ver.group(1)}"
    return model_id


def limit_label(key):
    return {
        "five_hour": "5h",
        "seven_day": "wk",
        "seven_day_opus": "wk:opus",
        "seven_day_sonnet": "wk:sonnet",
        "seven_day_fable": "wk:fable",
    }.get(key, key.replace("seven_day_", "wk:"))


def seg(label="", value="", detail="", accent=None, pct=None,
        bold=False, muted=False):
    return {"label": label, "value": value, "detail": detail, "accent": accent,
            "pct": pct, "bold": bold, "muted": muted}


def render_minimal(segs):
    """Segments split by a thin rule. Colour carries the gauge meaning;
    everything else is a shade of grey."""
    out = []
    for s in segs:
        parts = []
        if s["label"]:
            parts.append(f"{fg(C_LABEL)}{s['label']}{R}")
        if s["pct"] is not None:
            parts.append(f"{fg(s['accent'])}{bar(s['pct'])}{R}")
        if s["value"]:
            color = s["accent"] or (C_MUTED if s["muted"] else C_VALUE)
            parts.append(f"{BOLD if s['bold'] else ''}{fg(color)}{s['value']}{R}")
        if s["detail"]:
            parts.append(f"{fg(C_DETAIL)}{s['detail']}{R}")
        out.append(" ".join(parts))
    return NORMAL + f" {fg(C_DIVIDER)}│{R} ".join(out)


def render_powerline(segs):
    """The classic Powerline: filled backgrounds joined by arrows. Needs a
    Nerd Font."""
    out = []
    for i, s in enumerate(segs):
        back = s["accent"] or NEUTRAL
        gauge = "".join(bar_cells(s["pct"])) if s["pct"] is not None else ""
        text = " ".join(x for x in (s["label"], gauge, s["value"], s["detail"]) if x)
        out.append(f"{bg(back)}{fg(PL_INK)} {text} ")
        nxt = segs[i + 1]["accent"] or NEUTRAL if i + 1 < len(segs) else None
        out.append(f"{fg(back)}{bg(nxt) if nxt else R}{PL_SEP}{R}")
    return "".join(out)


def build(d):
    """Builds the segment list from the JSON. How it looks is the renderer's job.

    The model segments and the gauge segments are returned separately. They are
    joined into one line today; to go back to two lines, render them apart in
    emit().
    """
    model = d.get("model") or {}
    head = [seg(value=short_model(model.get("display_name"), model.get("id")),
                accent=ACCENT_MODEL, bold=True)]

    effort = (d.get("effort") or {}).get("level")
    head.append(seg("effort", effort) if effort
                else seg(value="effort —", muted=True))

    adv = advisor_of(d.get("transcript_path"))
    head.append(seg("adv", pretty_advisor(adv), accent=ACCENT_ADVISOR) if adv
                else seg(value="adv —", muted=True))

    if d.get("fast_mode"):
        head.append(seg(value="⚡fast", accent=ACCENT_FLAG))
    if (d.get("thinking") or {}).get("enabled") is False:
        head.append(seg(value="no-think", muted=True))
    if (d.get("agent") or {}).get("name"):
        head.append(seg(value=f"@{d['agent']['name']}"))

    tail = []
    ctx = d.get("context_window") or {}
    used = ctx.get("used_percentage")
    if used is not None:
        total = ctx.get("total_input_tokens", 0) + ctx.get("total_output_tokens", 0)
        size = ctx.get("context_window_size", 0)
        tail.append(seg("ctx", f"{float(used):.0f}%",
                        f"{tokens(total)}/{tokens(size)}" if size else "",
                        accent=heat(float(used)), pct=float(used)))

    rl = d.get("rate_limits") or {}
    # Known windows first; anything added later (Fable, etc.) follows as-is
    keys = [k for k in ("five_hour", "seven_day") if k in rl]
    keys += [k for k in sorted(rl) if k not in ("five_hour", "seven_day")]
    for key in keys:
        win = rl.get(key) or {}
        pct = win.get("used_percentage")
        if pct is None:
            continue
        left = until(win.get("resets_at"))
        tail.append(seg(limit_label(key), f"{float(pct):.0f}%",
                        f"{RESET_MARK}{left}" if left else "",
                        accent=heat(float(pct)), pct=float(pct)))
    return head, tail


def emit(d, style=STYLE):
    render = render_powerline if style == "powerline" else render_minimal
    head, tail = build(d)
    print(render(head + tail))


SAMPLE = {
    "model": {"id": "claude-opus-5", "display_name": "Opus 5"},
    "effort": {"level": "xhigh"},
    "thinking": {"enabled": True},
    "transcript_path": "",
    "context_window": {"total_input_tokens": 420000, "total_output_tokens": 8000,
                       "context_window_size": 1000000, "used_percentage": 42.8},
    "rate_limits": {"five_hour": {"used_percentage": 8, "resets_at": 0},
                    "seven_day": {"used_percentage": 63, "resets_at": 0},
                    "seven_day_fable": {"used_percentage": 91, "resets_at": 0}},
}


def demo():
    print(f"\n{BOLD}minimal{R} {fg(C_DETAIL)}(default. no Nerd Font needed){R}\n")
    emit(SAMPLE, "minimal")
    print(f"\n{BOLD}powerline{R} {fg(C_DETAIL)}(unusable if the arrow below is a box){R}\n")
    emit(SAMPLE, "powerline")
    print(f"\n{BOLD}glyph check{R} {fg(C_DETAIL)}look for anything broken{R}\n")
    print(f"  partial {EIGHTHS[1:]}{FULL}   empty {EMPTY}   rule │   arrow {PL_SEP}")
    print(f"  gradient " + "".join(
        f"{fg(heat(p))}{FULL}{R}" for p in range(0, 101, 4)) + "  0% → 100%\n")


def main():
    if "--demo" in sys.argv:
        demo()
        return
    raw = sys.stdin.read()
    if os.path.exists(DEBUG_FLAG):
        try:
            with open(DEBUG_OUT, "w") as f:
                f.write(raw)
        except OSError:
            pass
    try:
        d = json.loads(raw)
    except json.JSONDecodeError:
        print("statusline: bad input")
        return
    emit(d)


if __name__ == "__main__":
    main()
