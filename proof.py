#!/usr/bin/env python3
"""Render proof sheets for a built font with HarfBuzz (hb-view), so shaping is the real thing."""

import subprocess
import sys
from pathlib import Path

from PIL import Image

TITLE = "തേന്മാവിൻ\n    കൊമ്പത്ത്"  # the poster indents line two, which keeps its ് clear of the ൻ above
# Traced and untraced letters side by side, and the big െ / േ both opening a word and inside one.
MIXED = "\n".join([
    "വ വാ കവി തത്ത കൊമ്പ് വന്നു",
    "കിലുക്കം മണിച്ചിത്രത്താഴ്",
    "ചിത്രം നാടോടിക്കാറ്റ് തേൻ",
    "തേനീച്ച പൂന്തേൻ കൊക്ക് പുതുക്കൊട്ടാരം",
])
# Conjuncts, chillus, every vowel sign, ra/la forms, digits and Latin.
STRESS = "\n".join([
    "അ ആ ഇ ഈ ഉ ഊ ഋ എ ഏ ഐ ഒ ഓ ഔ",
    "ക ഖ ഗ ഘ ങ ച ഛ ജ ഝ ഞ ട ഠ ഡ ഢ ണ",
    "ത ഥ ദ ധ ന പ ഫ ബ ഭ മ യ ര ല വ ശ ഷ സ ഹ ള ഴ റ",
    "കാ കി കീ കു കൂ കൃ കെ കേ കൈ കൊ കോ കൗ കം കഃ ക്",
    "ൻ ൺ ർ ൽ ൾ ൿ  ക്ക ങ്ക ങ്ങ ച്ച ഞ്ച ഞ്ഞ ട്ട ണ്ട ണ്ണ ത്ത ന്ത ന്ന",
    "പ്പ മ്പ മ്മ യ്യ ല്ല വ്വ ശ്ശ സ്സ ള്ള റ്റ ന്റ ക്ഷ ക്ത സ്ത്ര ന്ദ്ര ദ്ധ ജ്ഞ",
    "ക്ര പ്ര ത്ര ക്ല പ്ല ക്യ ത്യ ക്വ സ്വ ശ്രീ സ്ഥ ഷ്ട ശ്ച ഹ്മ",
    "മലയാളം എന്റെ മാതൃഭാഷ  0123456789  Thenmavu ABC xyz !?&",
])


def render(font, text, out, size, line_space=0):
    subprocess.run(
        ["hb-view", f"--font-file={font}", f"--text={text}", f"--font-size={size}",
         "--background=000000", "--foreground=FFD21F", "--margin=40",
         f"--line-space={line_space}", f"--output-file={out}"],
        check=True,
    )


def stack(images, out):
    width = max(i.width for i in images)
    sheet = Image.new("RGB", (width, sum(i.height for i in images)), "black")
    y = 0
    for image in images:
        sheet.paste(image, ((width - image.width) // 2, y))
        y += image.height
    sheet.save(out)


if __name__ == "__main__":
    font, reference = sys.argv[1], sys.argv[2]
    proofs = Path("proofs")
    stem = Path(font).stem
    title_png, stress_png = proofs / f"{stem}-title.png", proofs / f"{stem}-stress.png"
    render(font, TITLE, title_png, 230, line_space=-170)  # the poster's lines nest: pitch ~0.74 em
    render(font, STRESS, stress_png, 72, line_space=20)
    render(font, MIXED, proofs / f"{stem}-mixed.png", 150, line_space=-40)
    poster = Image.open(reference).convert("RGB")
    title = Image.open(title_png).convert("RGB")
    title = title.resize((poster.width, round(title.height * poster.width / title.width)))
    stack([poster, title], proofs / f"{stem}-vs-poster.png")
    print(f"wrote {title_png}, {stress_png}, {proofs / f'{stem}-vs-poster.png'}")
