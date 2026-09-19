# 🎛️ Tuning

Every knob on `build.py`, and the measurements that set its default. All sizes are fractions of
the em, so they mean the same on any base font.

```sh
.venv/bin/python build.py --help
.venv/bin/python build.py --grow 0.022 --out dist/heavier.ttf      # try something without touching the release
```

The build verifies whatever it produces. A setting that closes a counter fails loudly instead of
shipping.

## 🎚️ The flags

| Flag | Default | Effect | What happens at the extremes |
|---|---|---|---|
| `--x-scale` | `0.80` | horizontal squeeze before growth | `0.68` matches the traced widths but `ഞ ണ ഭ മ്മ` clot into blobs |
| `--y-scale` | `0.94` | vertical scale | chosen so body height lands on the traced letters' ~600 units after growth |
| `--grow` | `0.019` | how much fatter every stroke gets | the traced strokes are ~180 units; this matches them at `0.80` squeeze |
| `--soften` | `0.006` | rounding of inner crotches | the poster's crotches are fairly sharp; more reads as melted |
| `--pinhole` | `0.035` | smallest counter allowed | the poster's smallest counters are ~5 px on a 100 px body |
| `--spacing` | `0.3` | share of Baloo's side-bearing whitespace kept, each side | `1.0` = Baloo's spacing |
| `--optical` | `1.0` | Malayalam glyphs: `0` box spacing, `1` facing-edge spacing | see below |
| `--lean` | `9` | forward lean, degrees | refused for a base whose GPOS uses mark anchors |
| `--traced` | `traced/glyphs.json` | the poster's letterforms | `''` builds with only the OFL-derived letters |
| `--base` / `--license` | Baloo Chettan 2 | another static TrueType base and its OFL text | glyph names in `trace.py` are Baloo's |

## ⚖️ Weight: what was measured

Stroke thickness ÷ letter-body height, same estimator (`2 × area ÷ perimeter`) on every image:

| | stroke ÷ body |
|---|---|
| 🖼️ Poster, both lines | ≈ 0.20 |
| 🅱️ Baloo Chettan 2 ExtraBold | 0.211 |
| Manjari Bold (version 1's base) | 0.154 |

Baloo already had the poster's weight; what it lacked was the poster's *width*. Squeeze and growth
are tuned as a pair:

| `--x-scale` / `--grow` | Result |
|---|---|
| `0.68` / `0.028` | matches traced widths; `ദ ഭ മ` are blobs ❌ |
| `0.76` / `0.022` | mostly readable; `ഭ ഞ` marginal |
| **`0.80` / `0.019`** | **shipped** ✅ |
| `0.84` / `0.016` | everything legible, a little wide beside the traced glyphs |

## 📏 Spacing: what was measured

The gap between neighbouring letters, taken in the body band with the lean removed, across every
letter pair in the proof text:

| | middle 80% of gaps | widest | note |
|---|---|---|---|
| 🅱️ Baloo as designed | 56–112 units | 248 | a 2 : 1 rhythm |
| box spacing (`--optical 0`) | 11–56 | 88 | 5 : 1 — gappy |
| half blend (`0.5`) | 10–55 | 71 | gained nothing |
| **facing edge (`1.0`), Malayalam only** | **7–40** | **50** | **shipped** ✅ |
| facing edge for *every* glyph | 5–37 | 48 | `T→h` collides at −67 ❌ |

> 💡 A gap has two parts: side-bearing whitespace, and how far each shape *recedes* from its own box
> at body height. At Baloo's loose spacing the first dominates and hides the second. At poster-tight
> spacing the recess **is** most of the gap — so round or hooked letters look far apart while square
> ones touch. Signs that hang below the line (`ു ൂ ൃ`) are the worst case: box spacing reserves room
> for a tail the next letter sits *above*.

> ⚠️ When measuring gaps in a leaning font, undo the lean first. Measuring sheared glyphs directly
> biased every reading here by about 47 units.

The `ി` stem ends up nearly fused with its consonant (`ചി ടി ണി`), which is what the poster's artist
did with `വി`. If a pair looks too glued, lower `--optical`.

## 🖼️ Re-tracing from a better poster

The current reference has letters ~100 px tall, which caps edge quality. With a larger image:

1. Replace `proofs/reference-poster.jpeg`.
2. In `trace.py`, update `GLYPHS` (a point near each blob's centre), `BASELINE` (the y of each text
   line), `VA_BODY_TOP`, and `UNITS_PER_PX` (≈ 595 ÷ the letter-body height in pixels).
3. Run `trace.py`. It prints each glyph's size in units; `ത` should come out about 580 × 600.
4. Run `build.py`, then `proof.py`, and compare `proofs/*-vs-poster.png`.

`trace.py` stops with a message if it cannot find a blob near a configured point, rather than
tracing the wrong letter.

## ➕ Tracing another letter

Add a line to `GLYPHS` in `trace.py` with Baloo's glyph name — find it with:

```sh
hb-shape --no-positions --no-clusters --font-file=base/BalooChettan2-ExtraBold.ttf "ക്ഷ"
```

Flourishes that should only open a word go in `WORD_INITIAL_ONLY`; shapes that fuse two glyphs go in
`LIGATURES`. Then rebuild — and add a word using the new glyph to `MIXED` in `proof.py` so
`verify()` and the proof sheet cover it.
