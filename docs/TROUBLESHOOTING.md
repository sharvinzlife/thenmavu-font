# 🩹 Troubleshooting

## 🔄 The app still shows the old version

Font caches are sticky, and a rebuilt font keeps the same family name.

| System | Fix |
|---|---|
| 🍎 macOS | Remove the old copy in Font Book (or delete `~/Library/Fonts/Thenmavu-Regular.ttf`), install the new one, then **quit and reopen** the app. If it persists: log out and back in. |
| 🪟 Windows | Settings → Personalisation → Fonts → Thenmavu → **Uninstall**, then install the new file and restart the app. |
| 🐧 Linux | Overwrite the file in `~/.local/share/fonts/` and run `fc-cache -f`. Restart the app. |

To check which version an app could be seeing:

```sh
fc-scan --format '%{family} %{style}  version %{fontversion}\n' dist/Thenmavu-Regular.ttf
# 144179 = 2.2 × 65536, i.e. Version 2.200
```

## 🌀 The big `െ` / `േ` shows up in the middle of a word

The normal-height form inside a word comes from the `calt` (contextual alternates) feature.

- ✅ On by default in browsers, LibreOffice, and most design and video tools.
- 🔧 In apps with an OpenType panel, make sure **Contextual Alternates** is ticked.
- ❓ Only HarfBuzz-based apps have been tested. If it misbehaves in Pages, Keynote or Word, that is
  worth knowing — note the app and version. The fallback is harmless: the big form everywhere.

Check what the font itself does, independent of any app:

```sh
hb-shape --no-positions --no-clusters --font-file=dist/Thenmavu-Regular.ttf "നാടോടി"
# expect ...|matraE.mlm.mid|...   (".mid" = the plain mid-word form)
```

## 🔡 Malayalam shows as boxes, or conjuncts fall apart

The app is not doing complex-script shaping. Some older video titlers and game engines draw glyphs
one by one without a shaping engine; no font can fix that. Set the text in an app that shapes
properly and import it as an image or outlines.

## ↕️ Lines of text collide

The word-opening `െ` is drawn oversized and drops about a quarter of an em below the baseline, as
on the poster. Increase the line spacing; about 1.5× is comfortable.

## 🏗️ Build problems

| Message | Meaning | Fix |
|---|---|---|
| `VERIFY FAILED: <glyph>: counter N closed up` | the growth left no room for that counter | lower `--grow`, or raise `--x-scale`; the build did its job by refusing |
| `VERIFY FAILED: shaping changed for '…'` | the built font shapes that line differently from the base | a rule was added or a glyph renamed without updating `verify()`'s expectation |
| `proof text never shows <glyph> both at a word start and inside a word` | the self-check would be vacuous | add such a word to `MIXED` in `proof.py` |
| `glyph <name>: boolean op failed … at every nudged radius` | Skia refused that geometry even after retries | try a slightly different `--grow`; if it is a new base font, that glyph may have self-intersecting outlines |
| `need a static TrueType (glyf) base` | the base is variable or CFF | pin it first: `fonttools varLib.instancer in.ttf wght=800 -o out.ttf` |
| `GPOS lookups […] attach marks at anchor points` | that base positions marks with anchors, which a lean would detach | `--lean 0`, or a base without anchors |
| `no blob near (x, y)` from `trace.py` | the poster image changed | update the points in `GLYPHS` |
| `potrace: command not found` | — | `brew install potrace` (only `trace.py` needs it) |
| `hb-view: command not found` | — | `brew install harfbuzz` (only `proof.py` needs it) |

## 🗑️ Uninstall

| System | How |
|---|---|
| 🍎 macOS | Font Book → Thenmavu → right-click → **Remove**. Or `rm ~/Library/Fonts/Thenmavu-Regular.ttf` |
| 🪟 Windows | Settings → Personalisation → Fonts → Thenmavu → **Uninstall** |
| 🐧 Linux | `rm ~/.local/share/fonts/Thenmavu-Regular.ttf && fc-cache -f` |
