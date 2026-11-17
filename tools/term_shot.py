"""Render a text log as a terminal-style PNG (used to produce console 'screenshots').

Usage:  python term_shot.py log.txt out.png "window title" [max_lines]
The picture is drawn from the real captured console output; replace it with a
genuine OS screenshot if your instructor requires one.
"""
import sys
from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"

def render(text, out, title="terminal", max_lines=None, width_chars=None, size=15):
    lines = text.rstrip("\n").split("\n")
    if max_lines and len(lines) > max_lines:
        keep_head = max_lines // 2
        keep_tail = max_lines - keep_head - 1
        lines = lines[:keep_head] + [f"... ({len(lines) - keep_head - keep_tail} lines omitted) ..."] + lines[-keep_tail:]
    font = ImageFont.truetype(FONT, size)
    cw = font.getlength("M")
    lh = int(size * 1.35)
    if width_chars:
        lines = [l[:width_chars] for l in lines]
    maxc = max(len(l) for l in lines) if lines else 20
    pad, bar = 14, 32
    W = max(int(maxc * cw + 2 * pad), 560)
    H = bar + pad * 2 + lh * len(lines)
    img = Image.new("RGB", (W, H), (24, 26, 31))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, bar], fill=(52, 55, 64))
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse([12 + i * 20, 10, 24 + i * 20, 22], fill=c)
    tfont = ImageFont.truetype(FONT, 13)
    d.text((W // 2 - len(title) * 4, 9), title, font=tfont, fill=(210, 212, 218))
    y = bar + pad
    for l in lines:
        col = (220, 223, 228)
        if l.startswith("$"):
            col = (130, 220, 140)
        elif "ALERT" in l:
            col = (255, 140, 120)
        elif "LWT" in l or "offline" in l:
            col = (255, 205, 110)
        elif "retained" in l.lower():
            col = (120, 190, 255)
        d.text((pad, y), l, font=font, fill=col)
        y += lh
    img.save(out)

if __name__ == "__main__":
    src, out, title = sys.argv[1], sys.argv[2], sys.argv[3]
    ml = int(sys.argv[4]) if len(sys.argv) > 4 else None
    render(open(src).read(), out, title, ml)
