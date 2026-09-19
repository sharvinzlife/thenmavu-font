# 🧰 Technology

Everything Thenmavu is built with, what it does here, and why it was the right tool.

## 🧪 The stack at a glance

| | Tool | Version | Role |
|---|---|---|---|
| 🐍 | [Python](https://www.python.org/) | 3.13 | the whole pipeline is three scripts |
| 📦 | [uv](https://docs.astral.sh/uv/) | 0.7+ | creates the virtualenv and installs the pinned requirements |
| 🔤 | [fontTools](https://github.com/fonttools/fonttools) | 4.65.0 | font I/O, glyph pens, OpenType table surgery, variable-font instancing |
| ✂️ | [skia-pathops](https://github.com/fonttools/skia-pathops) | 0.9.2 | boolean operations and stroking on outlines |
| 🔡 | [uharfbuzz](https://github.com/harfbuzz/uharfbuzz) | 0.56.1 | HarfBuzz from Python: the build's shaping self-check |
| 🖼️ | [Pillow](https://python-pillow.github.io/) | 12.3.0 | pixel work on the poster; proof-sheet assembly |
| ✒️ | [potrace](https://potrace.sourceforge.net/) | 1.16 | bitmap → Bézier curves |
| 👁️ | [`hb-view` / `hb-shape`](https://harfbuzz.github.io/utilities.html) | HarfBuzz 14 | render and inspect shaped text from the command line |
| 🧭 | [Archify](https://github.com/tt-a1i/archify) | — | the validated pipeline diagram |
| 🅱️ | [Baloo Chettan 2](https://github.com/EkType/Baloo2) | ExtraBold (wght 800) | the base font: ~1000 glyphs and all the shaping rules |

Python packages are pinned in [`requirements.txt`](../requirements.txt). potrace and the HarfBuzz
utilities come from the system package manager: `brew install potrace harfbuzz`.

## 🔤 fontTools — the font as data

| Used for | How |
|---|---|
| Reading outlines | `glyphSet[name].draw(pen)` — components are decomposed for free |
| Writing outlines | `TTGlyphPen` → a `glyf` glyph; it rounds coordinates itself |
| Curve conversion | `Cu2QuPen`: potrace emits cubic Béziers, TrueType holds quadratics |
| Parsing traces | `svgLib.path.parse_path` reads the SVG path data in `glyphs.json` |
| Pinning the weight | `varLib.instancer` turns the variable font into a static ExtraBold |
| Adding rules | `otlLib.builder` builds the ligature, single-substitution and coverage tables; the `calt` feature is inserted by hand, renumbering every `LangSys` feature index after it |

## ✂️ skia-pathops — geometry that glyphs need

Fonts need *offsetting*: make this shape 19 units fatter, all the way round. Skia has no offset
operation, but it has stroking and booleans, and three morphological operations fall out of those:

| Operation | Recipe | Used for |
|---|---|---|
| **Dilate** | shape ∪ stroke(shape) | fattening |
| **Erode** | shape − stroke(shape) | shrinking counters, softening |
| **Close** | dilate, then erode | rounding inner crotches |

> ⚠️ **Three things Skia will not tell you** — each cost a debugging round:
> 1. `stroke()` emits **conic** arcs for round joins. `glyf` has no conics, and `Path.area` raises on
>    them. Call `convertConicsToQuads()` first.
> 2. A boolean op on **nearly coincident** edges returns garbage, not an error. Restructure so they
>    never occur: counters are carved from a solid silhouette, never subtracted from a near-copy.
> 3. Erosion leaves **phantom islands** once the radius exceeds the local half-width — the area
>    *grows* as you erode more. Dilation is always safe, so each eroded piece is validated with a
>    probe disc: a real piece's boundary is exactly `r` from the source's edge; a phantom's is closer.

## 🔡 HarfBuzz — the judge

Malayalam is a complex script: the engine reorders glyphs, then the font substitutes them. The only
honest test that shaping still works is to *shape text*. `verify()` runs every proof line through
HarfBuzz with the base font and the built font, and compares glyph names.

HarfBuzz is also the shaping engine in Chrome, Firefox, Android, LibreOffice and most Linux
applications, so passing here covers a lot of ground. Apple's CoreText and Microsoft's DirectWrite
are separate engines and have not been tested; see the [roadmap](ROADMAP.md).

## 🔣 OpenType features touched

| Feature | Status | Purpose |
|---|---|---|
| `psts` post-base substitutions | **one lookup added** | the `വി` ligature |
| `calt` contextual alternates | **new feature** | plain `െ` / `േ` inside a word |
| `akhn` `pref` `pstf` `blws` `haln` `liga` `locl` … | untouched | Baloo's conjuncts, reph and below-base forms |
| GPOS `kern`, `dist` | values scaled | distances follow the squeeze |

GSUB lookup types used: **1** (single substitution), **4** (ligature), **6** (chaining context,
format 3 — coverage-based).

## ✒️ potrace + 🖼️ Pillow — pixels to curves

Pillow finds each letter (flood fill), builds a clean greyscale edge for it (luminance, neighbours
masked), upscales 8× and blurs. potrace fits curves. The settings that mattered:
`--alphamax 1.334` (no corners anywhere), `--opttolerance 1.2` (merge short curve runs into long
ones — that is what makes an edge look *drawn*), `--turdsize 200` (drop specks).

## 🎞️ The animated SVGs

Pure SVG + CSS. GitHub renders README images through `<img>`, which permits CSS `@keyframes` inside
the SVG but strips scripts and blocks external fonts. So every letter is an outline lifted from the
built font, the Latin caption uses a system font stack set on the `<svg>` root, and each file is
complete at rest — under `prefers-reduced-motion`, everything is simply visible.

> 🔬 **Verifying them:** headless Chrome freezes `<img>`-embedded SVG animation at t=0 when given
> `--virtual-time-budget`. The check that works is real time: serve the page over HTTP, hold the load
> event open with a slow image, and screenshot at 0.6 s and 4 s.

## 🧭 Archify

The pipeline diagram is authored as typed JSON and rendered to a standalone HTML viewer. It was
accepted at the `showcase` quality profile: 9 of 9 artifact checks, 0 composition errors, 0 warnings,
and first-screen containment at 1440×900 through 2048×1320.
