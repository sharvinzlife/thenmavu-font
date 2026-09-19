# 📝 Changelog

All notable changes to Thenmavu. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions match the font's own name table (`Version 2.200` = 2.2.0 here).

Legend: ✨ added · 🔧 changed · 🐛 fixed · 🗑️ removed

## 2.2.0 — 2026-09-19 · even spacing

Letters inside a word were unevenly spaced: some fused, some stood apart.

### 🐛 Fixed
- **Traced glyphs sat ~60 units too far left.** They already lean, but were positioned by their
  leaning bounding box, whose left edge is wherever the shape bulges rather than where it meets the
  baseline. Each one crowded the letter before it (−53 units) and left a hole after it (+76). Their
  side bearings are now measured with the lean taken out.
- **A sign tucked under its consonant lost its tightening.** `ൂ` has a large negative left bearing
  by design; the old rule summed both sides, got a total below zero, and left the glyph — including
  its generous right side — alone. Each side is now handled separately.

### 🔧 Changed
- **Malayalam glyphs are spaced from their facing edge**, not their box (`--optical`, default `1.0`).
  At poster-tight spacing a gap is mostly how far each shape recedes from its box, so signs hanging
  below the line (`ു ൂ ൃ`) reserved room nothing used. Latin, digits and punctuation keep box
  spacing: a `T`'s arm sits above the band and collided with `h` at −67 units.
- Traced glyphs' side bearing 16 → 6 units, landing their gaps in the base glyphs' range.
- Measured over the whole proof text, the middle 80% of letter gaps went from 11–56 to 7–40 units and
  the widest from 88 to 50. A half-blend (`--optical 0.5`) was tried and gained nothing.

## 2.1.0 — 2026-09-19 · flourishes only open a word

### ✨ Added
- **A `calt` rule that keeps the oversized `െ` and `േ` for word starts.** Inside a word
  (`നാടോടി`, `പൂന്തേൻ`) they become Baloo's normal-height form, carried as new glyphs
  `matraE.mlm.mid` and `matrashortE.mlm.mid`. OpenType cannot say "at the start of a word", only
  "after a letter", so the flourish is the default and the rule removes it. It has to be `calt`:
  HarfBuzz confines `psts` rules to one syllable, and this rule looks back across the boundary.
- `verify()` now fails if the proof text never shows each flourish both opening a word and inside one.
- `proof.py` renders the mixed sample as a third proof sheet.

## 2.0.0 — 2026-09-19 · the poster's own letters

Version 1 matched the poster's weight and roundness and nothing else. Fattening thickens a skeleton;
it cannot change its curves.

### ✨ Added
- **`trace.py`: twelve glyphs traced from the poster** — `േ ത ന്മ ാ വ ൻ െ ക മ്പ ത്ത ്` and the fused
  `വി`. Each letter is isolated as a connected blob, its edge read from luminance (JPEG stores colour
  at half resolution, which traces jagged), blurred by 1.1 px to lose the pixel staircase, and
  vectorised with potrace.
- **A ligature for `വി`**, which the poster's artist fused into one shape; appended to `psts`.
  A standalone `വ` is the same trace with the ascender cut off and capped.
- **Forward lean of 9°** on every base glyph. Refused for a base whose GPOS uses mark anchors, which
  a shear would detach.
- **Horizontal squeeze** (`--x-scale 0.80`, `--y-scale 0.94`), with GPOS distances scaled to match.
  The poster's `ത` is as wide as it is tall; Baloo's is 1.6× wider. 0.68 would match the traced
  widths but clots many-stroked letters (`ഞ ണ ഭ മ്മ`), so 0.80 is the floor.
- `verify()` shapes the proof text through HarfBuzz and compares glyph sequences with the base font.

### 🔧 Changed
- **Base font: Manjari Bold → Baloo Chettan 2 ExtraBold.** Of thirteen open-licence candidates it is
  the one with the poster's print letterforms, which lets it share a line with the traced glyphs.
- Shaping tables are no longer byte-identical to the base (two rules are added), so the check moved
  from comparing bytes to comparing HarfBuzz output.

### 🐛 Fixed
- **A counter with a shape inside it closed up** (`vowelRuu.mlm`, and the ring of `®`). The hole was
  shrunk and the inner shape grown as separate steps, and the grown shape filled the channel. The
  counter's region is now the hole *minus* what sits inside it, eroded as one piece.
- Skia's boolean ops refusing a degenerate intersection outright: retried with the radius nudged by
  under 2%, then through `Simplify` for unions. The count of nudges is printed by the build.

## 1.0.0 — 2026-09-19 · inflate Manjari *(superseded)*

### ✨ Added
- `build.py`: every outline of Manjari Bold dilated with round joins, crotches softened, advances
  tightened; shaping tables kept byte-identical.
- **Counters held open as pinholes.** A counter shrinks by the full growth only if a pinhole still
  fits, otherwise by as much as leaves one.
- `verify()`: re-opens the saved font and fails on any closed counter.
- `proof.py`: title-versus-poster and whole-script proof sheets through `hb-view`.

### 🐛 Fixed along the way
- Skia's stroker emits conic arcs, which `glyf` cannot hold → converted to quadratics.
- Subtracting a pinhole from a hole of nearly the same shape made the boolean op return garbage →
  counters are carved out of a solid silhouette instead.
- `shape − stroke(shape)` leaves **phantom islands** once the radius exceeds the local half-width
  (the area *grows* with more erosion) → every eroded piece is validated with a probe disc.
