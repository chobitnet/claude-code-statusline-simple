#!/usr/bin/env python3
"""Has statusline.py draw the images used in the README.

Not a terminal screenshot: the ANSI that `emit()` actually prints is transcribed
into SVG. The colours come from statusline.py's own HEAT_STOPS, so the picture
in the README cannot drift from what the script does. Each character is placed
at an explicit coordinate, so the bars stay on the grid whatever font the
reader's browser falls back to.

  python3 tools/render_svg.py
"""

import importlib.util
import io
import os
import re
import sys
import time
from contextlib import redirect_stdout
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT_DIR = os.path.join(ROOT, "docs")

FONT = "ui-monospace, SFMono-Regular, Menlo, Consolas, 'DejaVu Sans Mono', monospace"
FONT_SIZE = 14
CELL_W = FONT_SIZE * 0.6
LINE_H = 26
PAD_X = 14
PAD_Y = 16
BG = "#0b0d11"
DEFAULT_FG = "#dee4f0"

SGR = re.compile(r"\033\[([0-9;]*)m")


def load_statusline():
    spec = importlib.util.spec_from_file_location(
        "statusline", os.path.join(ROOT, "statusline.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def ansi_cells(line):
    """Unpacks an ANSI string into a list of (char, colour, bold)."""
    color, bold, cells, pos = DEFAULT_FG, False, [], 0
    for m in SGR.finditer(line):
        for ch in line[pos:m.start()]:
            cells.append((ch, color, bold))
        codes = [c for c in m.group(1).split(";") if c != ""] or ["0"]
        i = 0
        while i < len(codes):
            c = codes[i]
            if c == "0":
                color, bold = DEFAULT_FG, False
            elif c == "1":
                bold = True
            elif c == "22":
                bold = False
            elif c == "38" and codes[i + 1:i + 2] == ["2"]:
                r, g, b = (int(x) for x in codes[i + 2:i + 5])
                color = f"#{r:02x}{g:02x}{b:02x}"
                i += 4
            i += 1
        pos = m.end()
    for ch in line[pos:]:
        cells.append((ch, color, bold))
    return cells


def sample(model, effort, ctx_pct, five_h, week, in_5h, in_wk):
    """in_5h / in_wk are seconds until the reset, passed relative so the times
    shown in the image stay the same on every run."""
    total = round(1_000_000 * ctx_pct / 100)
    now = int(time.time())
    return {
        "model": {"id": model[1], "display_name": model[0]},
        "effort": {"level": effort},
        "thinking": {"enabled": True},
        "transcript_path": "",
        "context_window": {"total_input_tokens": total, "total_output_tokens": 0,
                           "context_window_size": 1_000_000,
                           "used_percentage": ctx_pct},
        "rate_limits": {
            "five_hour": {"used_percentage": five_h, "resets_at": now + in_5h},
            "seven_day": {"used_percentage": week, "resets_at": now + in_wk},
        },
    }


def render(rows, path, caption_color="#7d8799"):
    # The note sits two cells right of the line, so count it in the width
    cols = max(len(cells) + (len(note) + 2 if note else 0) for cells, note in rows)
    width = cols * CELL_W + PAD_X * 2
    height = len(rows) * LINE_H + PAD_Y * 2
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" '
        f'height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}" '
        f'font-family="{escape(FONT)}" font-size="{FONT_SIZE}">',
        f'<rect width="{width:.0f}" height="{height:.0f}" rx="8" fill="{BG}"/>',
    ]
    for row, (cells, note) in enumerate(rows):
        y = PAD_Y + LINE_H * row + FONT_SIZE
        for i, (ch, color, bold) in enumerate(cells):
            if ch == " ":
                continue
            weight = ' font-weight="700"' if bold else ""
            out.append(f'<text x="{PAD_X + i * CELL_W:.1f}" y="{y:.0f}" '
                       f'fill="{color}"{weight}>{escape(ch)}</text>')
        if note:
            x = PAD_X + (len(cells) + 2) * CELL_W
            out.append(f'<text x="{x:.1f}" y="{y:.0f}" fill="{caption_color}" '
                       f'font-size="{FONT_SIZE - 2}">{escape(note)}</text>')
    out.append("</svg>")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print(f"wrote {os.path.relpath(path, ROOT)}")


def line_of(sl, data):
    buf = io.StringIO()
    with redirect_stdout(buf):
        sl.emit(data)
    return ansi_cells(buf.getvalue().rstrip("\n"))


def main():
    sl = load_statusline()
    os.makedirs(OUT_DIR, exist_ok=True)
    opus = ("Opus 5", "claude-opus-5")

    render([(line_of(sl, sample(opus, "medium", 8, 39, 42, 4 * 3600 + 21 * 60, 4 * 86400 + 4 * 3600)),
             None)],
           os.path.join(OUT_DIR, "statusline.svg"))

    steps = [
        (12, 18, 24, "plenty left"),
        (46, 52, 55, "past half, shading amber"),
        (74, 81, 78, "getting tight"),
        (93, 97, 96, "nearly out"),
    ]
    rows = []
    for ctx, five, week, note in steps:
        data = sample(opus, "xhigh", ctx, five, week,
                      2 * 3600 + 7 * 60, 2 * 86400 + 9 * 3600)
        rows.append((line_of(sl, data), note))
    render(rows, os.path.join(OUT_DIR, "heat.svg"))


if __name__ == "__main__":
    main()
    sys.exit(0)
