# 🤝 Contributing

A short loop. The build checks its own output, so a green build means more than usual here.

1. 🌿 Branch off `main`.
2. 🏗️ Make the change, then run `.venv/bin/python build.py`. It must end with `verify: OK`.
3. 🖼️ Regenerate what people look at:
   ```sh
   .venv/bin/python proof.py dist/Thenmavu-Regular.ttf proofs/reference-poster.jpeg
   .venv/bin/python tools/make_svgs.py
   ```
   and **look** at `proofs/*.png`. `verify()` catches closed counters and broken shaping; it cannot
   catch ugly.
4. 📝 Add an entry to [`CHANGELOG.md`](CHANGELOG.md). If the font changed, bump `VERSION` in `build.py`
   and the version badge in the README to match.
5. 🧭 Changed the pipeline's shape? Edit `docs/diagrams/build-pipeline.dataflow.json` and re-deliver
   it with Archify at `--quality showcase`.

House rules: fail loudly, never silently; pin versions; if a number goes in the docs, measure it
first. [`docs/TUNING.md`](docs/TUNING.md) shows the standard.
