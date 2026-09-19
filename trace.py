#!/usr/bin/env python3
"""Trace the poster's own letterforms into font-unit outlines -> traced/glyphs.json.

Each letter on the poster is a separate yellow blob. A blob is isolated, upscaled and smoothed
(the source is a low-res JPEG), vectorised with potrace, and mapped into the base font's
coordinate space: one poster pixel = UNITS_PER_PX font units, y measured up from the text
line's baseline. build.py swaps these outlines in for the named glyphs.
"""

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pathops
from fontTools.misc.transform import Transform
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.svgLib.path import parse_path
from PIL import Image, ImageFilter

POSTER = "proofs/reference-poster.jpeg"
OUT = "traced/glyphs.json"

UNITS_PER_PX = 6.0  # Baloo's letter body is ~595 units; the poster's is ~99 px
UPSCALE = 8
SMOOTH_PX = 1.1  # edge blur, in poster pixels
BASELINE = {1: 212.5, 2: 335.5}  # poster y of each text line's baseline

# glyph name -> (a point near the blob's centre, text line, kind)
# "va_body" is the fused വി blob with the ി ascender cut away, so വ can stand alone.
GLYPHS = {
    "matraE.mlm":      ((178, 162), 1, "base"),      # േ
    "Ta.mlm":          ((286, 164), 1, "base"),      # ത
    "NaMa.mlm":        ((391, 161), 1, "base"),      # ന്മ
    "Va.mlm":          ((553, 134), 1, "va_body"),   # വ
    "Va_matraI.trace": ((553, 134), 1, "ligature"),  # വി, fused on the poster
    "chilluN.mlm":     ((687, 141), 1, "base"),      # ൻ
    "matrashortE.mlm": ((364, 299), 2, "base"),      # െ
    "Ka.mlm":          ((514, 283), 2, "base"),      # ക
    "matraA.mlm":      ((598, 282), 2, "base"),      # ാ
    "MaPa.mlm":        ((687, 285), 2, "base"),      # മ്പ
    "TaTa.mlm":        ((828, 292), 2, "base"),      # ത്ത
    "Virama.mlm":      ((896, 211), 2, "mark"),      # ്
}
LIGATURES = {"Va_matraI.trace": [["Va.mlm", "matraI1.mlm"], ["Va.mlm", "matraI.mlm"]]}
# The poster draws these two vowel signs as oversized opening flourishes. That only works at the
# start of a word; inside one, build.py falls back to the base font's plain form.
WORD_INITIAL_ONLY = {"matraE.mlm", "matrashortE.mlm"}
VA_BODY_TOP = 112  # poster y where വ's body ends and the ി ascender begins


def yellowness(rgb):
    """Tells yellow ink from the white credits. Blocky: JPEG stores colour at half resolution."""
    r, g, b = rgb
    return max(0, min(255, round((min(r, g) - b) * 255 / 170)))


def brightness(rgb):
    """Where exactly the ink's edge is. JPEG keeps luminance at full resolution, so this is the
    sharp signal; yellow ink is ~205 bright, scaled here so that the edge sits at 128."""
    r, g, b = rgb
    return min(255, round((0.299 * r + 0.587 * g + 0.114 * b) * 255 / 205))


def label_blobs(image):
    """Connected yellow blobs: returns (label map, {label: (area, box)})."""
    width, height = image.size
    px = image.load()
    ink = [[yellowness(px[x, y]) > 128 for x in range(width)] for y in range(height)]
    label = [[0] * width for _ in range(height)]
    blobs = {}
    for y0 in range(height):
        for x0 in range(width):
            if not ink[y0][x0] or label[y0][x0]:
                continue
            n = len(blobs) + 1
            label[y0][x0] = n
            stack, area, box = [(x0, y0)], 0, [x0, y0, x0, y0]
            while stack:
                x, y = stack.pop()
                area += 1
                box = [min(box[0], x), min(box[1], y), max(box[2], x), max(box[3], y)]
                for u, v in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= u < width and 0 <= v < height and ink[v][u] and not label[v][u]:
                        label[v][u] = n
                        stack.append((u, v))
            blobs[n] = (area, box)
    return label, blobs


def blob_at(blobs, point):
    """The sizeable blob whose box centre is nearest `point`."""
    def distance(item):
        _, (_, (x0, y0, x1, y1)) = item
        return ((x0 + x1) / 2 - point[0]) ** 2 + ((y0 + y1) / 2 - point[1]) ** 2
    n, (area, box) = min(((n, b) for n, b in blobs.items() if b[0] > 150), key=distance)
    if distance((n, (area, box))) > 30 ** 2:
        sys.exit(f"no blob near {point}: nearest is box {box}; has the poster image changed?")
    return n, box


def vectorise(image, label, n, box, cut_above=None):
    """potrace one blob. Returns (svg path data list, crop origin, upscaled crop height)."""
    pad = 6
    x0, y0 = max(box[0] - pad, 0), max(box[1] - pad, 0)
    x1, y1 = min(box[2] + pad, image.width - 1), min(box[3] + pad, image.height - 1)
    px = image.load()
    grey = Image.new("L", (x1 - x0 + 1, y1 - y0 + 1), 0)
    gp = grey.load()
    def beside_another_letter(x, y):
        """Background within 2 px of a different blob carries that blob's anti-aliased halo."""
        return any(label[v][u] not in (0, n)
                   for v in range(max(y - 2, 0), min(y + 3, image.height))
                   for u in range(max(x - 2, 0), min(x + 3, image.width)))

    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if cut_above is not None and y < cut_above:
                continue
            if label[y][x] == n or (label[y][x] == 0 and not beside_another_letter(x, y)):
                gp[x - x0, y - y0] = brightness(px[x, y])  # keeps this blob's own anti-aliased edge
    big = grey.resize((grey.width * UPSCALE, grey.height * UPSCALE), Image.BICUBIC)
    # The letters are only ~100 px tall, so the pixel staircase has to be blurred away: about one
    # source pixel is enough to lose it and still keep the 5 px pinhole counters open.
    big = big.filter(ImageFilter.GaussianBlur(UPSCALE * SMOOTH_PX))
    bitmap = big.point(lambda v: 0 if v > 128 else 255).convert("1")  # potrace traces black
    with tempfile.TemporaryDirectory() as tmp:
        pbm, svg = Path(tmp) / "blob.pbm", Path(tmp) / "blob.svg"
        bitmap.save(pbm)
        # alphamax 1.334 = no corners at all (this lettering has none); a loose opttolerance
        # merges short curve runs into long ones, which is what makes an edge look drawn.
        subprocess.run(["potrace", "--svg", "--alphamax", "1.334", "--opttolerance", "1.2",
                        "--turdsize", "200", "--output", str(svg), str(pbm)], check=True)
        text = svg.read_text()
    if not re.search(r'transform="translate\(0\.0+,[\d.]+\) scale\(0\.10+,-0\.10+\)"', text):
        sys.exit("potrace SVG no longer uses the translate/scale(0.1,-0.1) group transform this script assumes")
    return re.findall(r'<path d="([^"]+)"', text), (x0, y0), big.height


def to_font_units(paths, origin, big_height, baseline):
    """potrace path units (0.1 upscaled px, y up from the crop's bottom) -> font units."""
    k = 0.1 / UPSCALE  # path unit -> poster px
    crop_bottom = origin[1] + big_height / UPSCALE
    transform = Transform(k * UNITS_PER_PX, 0, 0, k * UNITS_PER_PX,
                          origin[0] * UNITS_PER_PX, (baseline - crop_bottom) * UNITS_PER_PX)
    outline = pathops.Path()
    pen = TransformPen(Cu2QuPen(outline.getPen(), max_err=1.0), transform)  # glyf needs quadratics
    for d in paths:
        parse_path(d, pen)
    outline.simplify(fix_winding=True)
    return outline


def round_cut_stem(outline, cut_y):
    """The cut through the ി stem leaves a flat top; cap it with a disc as wide as the stem."""
    from build import disc
    probe = pathops.Path()
    x_min, _, x_max, _ = outline.bounds
    probe.moveTo(x_min - 10, cut_y - 14); probe.lineTo(x_max + 10, cut_y - 14)
    probe.lineTo(x_max + 10, cut_y - 10); probe.lineTo(x_min - 10, cut_y - 10); probe.close()
    slices = [c.bounds for c in pathops.op(outline, probe, pathops.PathOp.INTERSECTION, fix_winding=True).contours]
    left, _, right, _ = max(slices, key=lambda b: b[0])  # the stem is the right-most piece on that row
    cap = disc(((left + right) / 2, cut_y - 12), (right - left) / 2)
    return pathops.op(outline, cap, pathops.PathOp.UNION, fix_winding=True)


def main():
    image = Image.open(POSTER).convert("RGB")
    label, blobs = label_blobs(image)
    traced = {}
    for name, (point, line, kind) in GLYPHS.items():
        n, box = blob_at(blobs, point)
        cut = VA_BODY_TOP if kind == "va_body" else None
        paths, origin, big_height = vectorise(image, label, n, box, cut_above=cut)
        outline = to_font_units(paths, origin, big_height, BASELINE[line])
        if kind == "va_body":
            outline = round_cut_stem(outline, (BASELINE[line] - VA_BODY_TOP) * UNITS_PER_PX)
        x_min, y_min, x_max, y_max = outline.bounds
        outline = outline.transform(1, 0, 0, 1, -x_min, 0)  # x starts at 0; build.py sets the side bearings
        pen = SVGPathPen(None)
        outline.draw(pen)
        traced[name] = {
            "kind": "base" if kind == "va_body" else kind,
            "d": pen.getCommands(),
            **({"ligature_of": LIGATURES[name]} if name in LIGATURES else {}),
            **({"word_initial_only": True} if name in WORD_INITIAL_ONLY else {}),
        }
        print(f"{name:18s} blob box {box}  ->  {round(x_max - x_min)} x {round(y_max - y_min)} units, "
              f"y {round(y_min)}..{round(y_max)}, {len(list(outline.contours))} contours")
    Path(OUT).parent.mkdir(exist_ok=True)
    Path(OUT).write_text(json.dumps(traced, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
