# 🖼️ Proofs

Rendered proof sheets, and the one piece of film material this repository reproduces.

## What is reproduced, and why

| File | What it shows | Why it is here |
|---|---|---|
| `reference-poster.jpeg` | The title card of *Thenmavin Kombathu* (1994): the hand-lettered title in yellow on black, with the "Mohanlal in" and "written & directed by Priyadarshan" credit lines. 1033 × 435 px, 36 KB. No other part of the poster or the film. | It is the image `trace.py` reads and the reference `proof.py` compares against. This project documents how twelve letters of that lettering were traced into a font, which cannot be shown without the lettering itself, and no free equivalent of it exists. |
| `Thenmavu-Regular-vs-poster.png` | The same title card above the same words typed in Thenmavu. | The comparison is the point: it shows what was traced, what was reshaped from Baloo Chettan 2, and where the two differ. |

**Basis.** The crops are used to compare with, and comment on, the letterforms: criticism or comment that
targets the work (17 U.S.C. § 107), and fair dealing for criticism or review (Copyright Act, 1957
§ 52(1)(a)(ii)). They take only the title lettering, at proof resolution, and substitute for nothing the
film's rights holders sell. The letterforms themselves are not copyright subject matter in the United
States or in India; [LICENSE.md](../LICENSE.md) has the citations.

The film, its title and its artwork belong to its rights holders. This project is not affiliated with or
endorsed by them. If you hold those rights and object, open an issue and the crops will be removed.

## The other sheets

| File | Contents |
|---|---|
| `Thenmavu-Regular-title.png` | the title, typed |
| `Thenmavu-Regular-mixed.png` | words and film titles that mix traced and untraced letters |
| `Thenmavu-Regular-stress.png` | the whole script: vowel signs, chillus, conjuncts, Latin, digits |
| `Thenmavu-Regular.bridged.txt` | glyphs whose aperture `verify()` found bridged into a new pinhole: worth a look by eye |

`proof.py` regenerates them; the README shows how.
