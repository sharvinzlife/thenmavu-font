# 🗺️ Roadmap

What would make Thenmavu better, roughly in order of payoff. Nothing here is promised.

## 🥇 Worth doing next

- [ ] 🖼️ **Re-trace from a higher-resolution poster.** The current source has letters ~100 px tall,
      which caps edge quality. The re-tracing steps are in [Tuning](TUNING.md).
- [ ] 🧪 **Test outside HarfBuzz.** The `calt` rule and the ligature are verified in HarfBuzz only.
      Check Pages / Keynote (CoreText) and Word (DirectWrite), and record the results in
      [Troubleshooting](TROUBLESHOOTING.md).
- [ ] 📦 **Tag a release** with the `.ttf` attached, so installing does not mean cloning.

## 🥈 Would be nice

- [ ] ✍️ **Redraw the most-used untraced letters by hand** in the poster's manner — `മ ല യ ള ര ന പ`
      first. Each one narrows the visible gap between the twelve and the thousand.
- [ ] 🔗 **Kerning for the worst pairs.** Optical spacing is per-glyph; a handful of pairs
      (`ൗ` after `ക`, digits) still want pair adjustments.
- [ ] 🌐 **A WOFF2 build** for use on the web.
- [ ] 🅰️ **A matching Latin.** The Latin is Baloo's, fattened and leaned; it was never the point.

## 🚫 Deliberately not planned

- **A Bold, a Light, an Italic.** It is one poster's lettering. One style is the whole idea.
- **Text-size legibility.** Pinhole counters are the look. Use another face for paragraphs.
- **Making the repository public as it stands.** See the warning at the end of the
  [README](../README.md).
