#!/usr/bin/env python3
"""Generate the README's animated SVGs from the font itself -> docs/assets/.

GitHub shows SVGs through <img>, which means no scripts and no external fonts. So every letter
is drawn as an outline taken from the built font, and the motion is plain CSS. Each file is
complete at rest: with animation unavailable or `prefers-reduced-motion`, everything is visible.
"""

import math
import sys
from pathlib import Path

import uharfbuzz as hb
from fontTools.misc.transform import Transform
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from build import glyph_shape, inflate  # noqa: E402

FONT = "dist/Thenmavu-Regular.ttf"
BASE = "base/BalooChettan2-ExtraBold.ttf"
OUT = Path("docs/assets")

INK, YELLOW, CREAM, DIM, LINE = "#0b0906", "#ffd21f", "#efe6cf", "#9c9279", "#2e2617"
SANS = "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"


def number(value):
    return f"{value:.1f}".rstrip("0").rstrip(".")


def shape_line(font_path, text):
    """[(glyph name, x, y)] in font units, as HarfBuzz lays the text out."""
    font = hb.Font(hb.Face(hb.Blob.from_file_path(font_path)))
    buffer = hb.Buffer()
    buffer.add_str(text)
    buffer.guess_segment_properties()
    hb.shape(font, buffer)
    placed, pen_x = [], 0
    for info, pos in zip(buffer.glyph_infos, buffer.glyph_positions):
        placed.append((font.glyph_to_string(info.codepoint), pen_x + pos.x_offset, pos.y_offset))
        pen_x += pos.x_advance
    return placed, pen_x


def outline(draw, scale, x, y):
    """SVG path data for anything with a .draw(pen), scaled and flipped into SVG space at (x, y)."""
    pen = SVGPathPen(None, ntos=number)
    draw(TransformPen(pen, Transform(scale, 0, 0, -scale, x, y)))
    return pen.getCommands()


def hero():
    """The film title, letter by letter, set in the font."""
    width, height, scale = 1200, 540, 0.2
    glyph_set = TTFont(FONT).getGlyphSet()
    line_one, width_one = shape_line(FONT, "തേന്മാവിൻ")
    line_two, width_two = shape_line(FONT, "കൊമ്പത്ത്")
    indent = 760  # font units; the poster starts its second line under the ന്മ
    total = max(width_one, indent + width_two) * scale
    left = (width - total) / 2
    first = 222  # baseline of line one: leaves room above for the ി hook, the tallest thing in the title
    rows = [(line_one, left, first), (line_two, left + indent * scale, first + 0.74 * 1000 * scale)]

    letters = []
    for glyphs, x0, baseline in rows:
        for name, x, y in glyphs:
            data = outline(glyph_set[name].draw, scale, x0 + x * scale, baseline - y * scale)
            if data:
                letters.append(f'<path class="letter" style="animation-delay:{len(letters) * 0.13:.2f}s" d="{data}"/>')

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" font-family="{SANS}"
     aria-label="Thenmavin Kombathu, set in the Thenmavu font, letters appearing one by one">
  <style>
    .letter {{ fill: {YELLOW}; transform-box: fill-box; transform-origin: 50% 100%; animation: pop 9s cubic-bezier(.3,1.4,.5,1) infinite both; }}
    @keyframes pop {{
      0%   {{ opacity: 0; transform: translateY(22px) scale(.72) rotate(-5deg); }}
      5%   {{ opacity: 1; transform: translateY(-5px) scale(1.06) rotate(1deg); }}
      9%, 88% {{ opacity: 1; transform: none; }}
      95%, 100% {{ opacity: 0; transform: translateY(-10px) scale(.96); }}
    }}
    .glow {{ animation: breathe 9s ease-in-out infinite; }}
    @keyframes breathe {{ 0%, 100% {{ opacity: .35; }} 50% {{ opacity: .8; }} }}
    @media (prefers-reduced-motion: reduce) {{ .letter, .glow {{ animation: none; }} }}
  </style>
  <defs>
    <radialGradient id="spot" cx="50%" cy="46%" r="60%">
      <stop offset="0" stop-color="#3a2c05"/><stop offset="1" stop-color="{INK}" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="{width}" height="{height}" rx="22" fill="{INK}"/>
  <rect class="glow" width="{width}" height="{height}" rx="22" fill="url(#spot)"/>
  {chr(10).join("  " + letter for letter in letters).strip()}
  <text x="{width / 2}" y="{height - 58}" text-anchor="middle" fill="{CREAM}" font-size="25" font-weight="700" letter-spacing="9">THENMAVU</text>
  <text x="{width / 2}" y="{height - 28}" text-anchor="middle" fill="{DIM}" font-size="15" letter-spacing="1.2">a Malayalam display font, traced from a hand-lettered film title</text>
</svg>
"""


def glyph_stages():
    """One base glyph through the build: as drawn, squeezed, fattened, leaned."""
    width, height, scale = 1200, 330, 0.24
    upm = 1000
    base = glyph_shape(TTFont(BASE).getGlyphSet(), "Ma.mlm")  # മ, a letter the poster never shows
    squeezed = base.transform(0.80, 0, 0, 0.94, 0, 0)
    fattened, _ = inflate(squeezed, 0.019 * upm, 0.006 * upm, 0.035 * upm)
    leaned = fattened.transform(1, 0, math.tan(math.radians(9)), 1, 0, 0)
    stages = [
        (base, "Baloo Chettan 2", "as its designers drew it"),
        (squeezed, "squeeze", "80% wide: the poster is condensed"),
        (fattened, "fatten", "+1.9% em, counters kept open"),
        (leaned, "lean", "9 degrees, like the brush"),
    ]
    column = width / len(stages)
    parts = []
    for index, (shape, title, note) in enumerate(stages):
        x_min, _, x_max, _ = shape.bounds
        centre = column * index + column / 2
        data = outline(shape.draw, scale, centre - (x_min + x_max) / 2 * scale, 190)
        fill = YELLOW if index == len(stages) - 1 else CREAM
        parts.append(
            f'<g class="stage" style="animation-delay:{index * 1.5:.1f}s">'
            f'<path fill="{fill}" d="{data}"/>'
            f'<text x="{number(centre)}" y="252" text-anchor="middle" fill="{CREAM}" font-size="19" font-weight="700">{title}</text>'
            f'<text x="{number(centre)}" y="278" text-anchor="middle" fill="{DIM}" font-size="14">{note}</text>'
            f"</g>")
        if index:
            x = column * index
            parts.append(f'<path d="M{number(x - 16)} 120h26m-9 -8l9 8l-9 8" fill="none" stroke="{DIM}" '
                         f'stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>')

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" font-family="{SANS}"
     aria-label="The letter ma going through the build: Baloo Chettan 2 as drawn, squeezed, fattened, then leaned">
  <style>
    .stage {{ animation: step 6s ease-in-out infinite both; }}
    @keyframes step {{ 0%, 100% {{ opacity: .38; }} 8%, 25% {{ opacity: 1; }} 33% {{ opacity: .38; }} }}
    @media (prefers-reduced-motion: reduce) {{ .stage {{ animation: none; }} }}
  </style>
  <rect width="{width}" height="{height}" rx="22" fill="{INK}"/>
  <path d="M40 300h{width - 80}" stroke="{LINE}" stroke-width="1"/>
  {chr(10).join("  " + part for part in parts).strip()}
</svg>
"""


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, make in (("hero.svg", hero), ("glyph-stages.svg", glyph_stages)):
        (OUT / name).write_text(make())
        print(f"wrote {OUT / name} ({(OUT / name).stat().st_size / 1024:.0f} KB)")
