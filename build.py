#!/usr/bin/env python3
"""Build Thenmavu: a fat, leaning Malayalam display font in the style of a hand-lettered film title.

Three layers:
  1. an OFL base font, every outline inflated with round joins (counters kept open as pinholes)
     and sheared into a forward lean;
  2. the poster's own letterforms, traced by trace.py, swapped in for the glyphs the title uses;
  3. one added ligature for the pair the poster's artist fused into a single shape.

The base's shaping rules are otherwise untouched, and verify() proves it by shaping real text
through HarfBuzz with both fonts. Size parameters are fractions of the em.
"""

import argparse
import calendar
import json
import math
import shutil
import sys
import time
from pathlib import Path

import pathops
import uharfbuzz as hb
from fontTools.otlLib.builder import buildCoverage, buildLigatureSubstSubtable, buildSingleSubstSubtable
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.misc.timeTools import epoch_diff
from fontTools.svgLib.path import parse_path
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.tables.otBase import BaseTable, ValueRecord

FAMILY = "Thenmavu"
VERSION = "2.300"
RELEASED = "2026-09-19"  # stamped into the font instead of the build time, so a rebuild is byte-identical
BODY_BAND = (0.15, 0.45)  # em above the baseline where neighbouring letters face each other
TRACED_SIDE_BEARING = 6  # font units each side of a traced glyph: lands their gaps in the base glyphs' 13-36 range

ROUND = (pathops.LineCap.ROUND_CAP, pathops.LineJoin.ROUND_JOIN, 4)


def ring(path, r):
    """The band within `r` of the outline. Skia emits conic arcs for round joins; glyf has no conics."""
    band = pathops.Path(path)
    band.stroke(2 * r, *ROUND)
    band.convertConicsToQuads()
    return band


nudged = 0  # boolean ops that only succeeded at a slightly different radius; reported by build()


def offset(path, r, operator):
    """`path` combined with the band around its outline.

    Skia's boolean ops refuse outright ("operation did not succeed") on rare degenerate
    intersections. A radius under 2% different sidesteps them and cannot be seen.
    """
    global nudged
    for factor in (1.0, 1.007, 0.993, 1.016):
        try:
            result = pathops.op(path, ring(path, r * factor), operator, fix_winding=True)
        except pathops.PathOpsError:
            continue
        nudged += factor != 1.0
        return result
    if operator == pathops.PathOp.UNION:
        # A union is also what Skia's separate Simplify routine computes for overlapping
        # same-direction contours, and it survives some inputs that Op does not.
        # Both pieces are wound the same way first, so overlap adds up instead of cancelling.
        merged, band = pathops.Path(path), ring(path, r)
        merged.simplify(fix_winding=True)
        band.simplify(fix_winding=True)
        merged.addPath(band)
        merged.simplify(fix_winding=True)
        nudged += 1
        return merged
    raise pathops.PathOpsError(f"boolean op failed at radius {r:.1f} and at every nudged radius")


def dilate(path, r):
    return offset(path, r, pathops.PathOp.UNION)


def erode(path, r):
    return offset(path, r, pathops.PathOp.DIFFERENCE)


def disc(center, radius):
    cx, cy = center
    path = pathops.Path()
    path.moveTo(cx + radius, cy)
    for k in range(8):  # eight quadratic arcs: within 0.1% of a true circle
        mid, end = math.radians(45 * k + 22.5), math.radians(45 * k + 45)
        bulge = radius / math.cos(math.radians(22.5))
        path.quadTo(cx + bulge * math.cos(mid), cy + bulge * math.sin(mid),
                    cx + radius * math.cos(end), cy + radius * math.sin(end))
    path.close()
    return path


def shrink(blob, r):
    """Erode a counter region (a hole, minus any shape inside it) by any `r`, however large.

    Once `r` exceeds the local half-width, Skia's stroker inverts the inner offset curve and
    plain erode() leaves phantom islands where the answer should be empty. Every boundary point
    of a real eroded piece is exactly `r` from the edge of `blob`; a phantom's are closer. So a
    probe disc a hair smaller than `r` sits strictly inside `blob` for a real piece and crosses
    its edge for a phantom - either way a clean boolean, never near-coincident edges.
    """
    if r <= 0:
        return blob
    real = pathops.Path()
    for contour in erode(blob, r).contours:
        probe = disc(contour.firstPoints[0], r - max(0.02 * r, 0.5))
        if pathops.op(probe, blob, pathops.PathOp.DIFFERENCE, fix_winding=True).area <= 0.01 * probe.area:
            real.addPath(contour)
    return real


def is_empty(path):
    return path.area < 1.0


def counters(path):
    """Counters of a simplified path: fix_winding makes outers CCW and holes CW."""
    return [pathops.Path(c) for c in path.contours if c.clockwise]


def pinhole(counter, grow, pin):
    """`counter` shrunk by as much of `grow` as still leaves room for a circle of diameter `pin`.

    Returns (shape_to_carve, shrink_used). A counter already narrower than `pin` comes back
    untouched with shrink 0.
    """
    half = pin / 2
    if not is_empty(shrink(counter, grow + half)):
        return shrink(counter, grow), grow
    lo, hi = 0.0, grow
    for _ in range(7):
        mid = (lo + hi) / 2
        if is_empty(shrink(counter, mid + half)):
            hi = mid
        else:
            lo = mid
    if lo < 1:  # no room to give; a sub-unit erosion is numerical noise, so leave the counter as drawn
        return counter, 0.0
    return shrink(counter, lo), lo


def inflate(shape, grow, soften, pin):
    """Fatten `shape` by `grow`, round its crotches by `soften`, keep counters >= `pin` wide.

    Counters are carved out of a solid silhouette rather than shrunk in place: subtracting a
    pinhole from a hole that is already nearly the same shape makes Skia's boolean ops misfire
    on the near-coincident edges.
    """
    # Nesting depth of each contour: 0 = outer, 1 = counter, 2 = shape inside a counter
    # (the R of a registered sign), 3 = that shape's own counter, ...
    contours = [pathops.Path(c) for c in shape.contours]
    layers = sorted(
        ((sum(o.contains(c.firstPoints[0]) for o in contours if o is not c), c) for c in contours),
        key=lambda layer: layer[0],
    )

    silhouette = pathops.Path()
    for depth, contour in layers:
        if depth == 0:
            silhouette.addPath(contour)
    silhouette.simplify(fix_winding=True)
    fat = dilate(silhouette, grow + soften)
    if soften:
        fat = erode(fat, soften)

    # Growth bridges open apertures into new holes. One too small to hold a pinhole reads as
    # a printing defect, so drop its contour (exact - no boolean op needed).
    kept = pathops.Path()
    for contour in fat.contours:
        if contour.clockwise and is_empty(shrink(pathops.Path(contour), pin / 2)):
            continue
        kept.addPath(contour)
    fat = kept

    # A counter's real region is the hole minus any shape sitting inside it (the ring around the
    # R of a registered sign). Shrinking that region moves both of its edges at once, so the
    # inner shape grows by exactly what the channel can spare - no separate step for it.
    squeezed = 0
    for depth, contour in layers:
        if depth % 2 == 0:
            continue
        region = contour
        for inner_depth, inner in layers:
            if inner_depth == depth + 1 and contour.contains(inner.firstPoints[0]):
                region = pathops.op(region, inner, pathops.PathOp.DIFFERENCE, fix_winding=True)
        keep, used = pinhole(region, grow, pin)
        squeezed += used < grow
        fat = pathops.op(fat, keep, pathops.PathOp.DIFFERENCE, fix_winding=True)
    return fat, squeezed


def to_glyph(path):
    path = pathops.Path(path)
    path.simplify(fix_winding=True, clockwise=True)  # TrueType: outers clockwise
    pen = TTGlyphPen(None)
    path.draw(pen)
    return pen.glyph()  # rounds coordinates to integers itself


def glyph_shape(glyph_set, name):
    path = pathops.Path()
    glyph_set[name].draw(path.getPen(glyphSet=glyph_set))  # decomposes components
    path.simplify(fix_winding=True)
    return path


def facing_edges(shape, band, optical):
    """(left, right) edge of a glyph as its neighbours meet it.

    The box edge is wherever the shape sticks out furthest, at any height. Letters face each other
    across the body band, and a round or hooked shape recedes from its box there. At poster-tight
    spacing that recess is most of the gap, so spacing by the box makes such letters look far
    apart while square ones touch. `optical` blends the two: 0 = box edge (can never collide),
    1 = edge inside the band (even rhythm, but ink outside the band may touch a neighbour).
    """
    x_min, _, x_max, _ = shape.bounds
    window = pathops.Path()
    window.moveTo(x_min - 10, band[0])
    window.lineTo(x_max + 10, band[0])
    window.lineTo(x_max + 10, band[1])
    window.lineTo(x_min - 10, band[1])
    window.close()
    body = pathops.op(shape, window, pathops.PathOp.INTERSECTION, fix_winding=True)
    if is_empty(body):  # a mark, a comma: nothing in the band, so the box is all there is
        return x_min, x_max
    body_min, _, body_max, _ = body.bounds
    return x_min + optical * (body_min - x_min), x_max - optical * (x_max - body_max)


def rename(font, base_family, lean):
    name = font["name"]
    original_copyright = name.getDebugName(0)
    name.names = [n for n in name.names if n.nameID not in (16, 17, 21, 22, 25)]
    for name_id, text in {
        0: f"{original_copyright}. {FAMILY} modifications: outlines reshaped and partly redrawn, 2026.",
        1: FAMILY,
        2: "Regular",
        3: f"{VERSION};{FAMILY}-Regular",
        4: FAMILY,
        5: f"Version {VERSION}",
        6: f"{FAMILY}-Regular",
        10: f"Fat leaning Malayalam display face. Derived from {base_family} under the SIL Open Font License 1.1.",
    }.items():
        for record in [n for n in name.names if n.nameID == name_id]:
            name.names.remove(record)
        name.setName(text, name_id, 3, 1, 0x409)
        name.setName(text, name_id, 1, 0, 0)
    os2, head = font["OS/2"], font["head"]
    os2.usWeightClass = 400
    os2.fsSelection = (os2.fsSelection & ~0b100001) | 0b1000000  # clear ITALIC+BOLD, set REGULAR
    head.macStyle = 0
    head.fontRevision = float(VERSION)
    head.modified = calendar.timegm(time.strptime(RELEASED, "%Y-%m-%d")) - epoch_diff
    # The family has one style, so it stays "Regular"; the angle only slants the text cursor to match.
    font["post"].italicAngle = -lean
    font["hhea"].caretSlopeRise, font["hhea"].caretSlopeRun = 1000, round(1000 * math.tan(math.radians(lean)))
    if "STAT" in font:  # a single static style has nothing for STAT to describe
        del font["STAT"]


def scale_positioning(font, kx, ky):
    """Scale every GPOS distance (kerning, mark offsets, anchors) with the outlines they position."""
    if "GPOS" not in font:
        return
    done = set()

    def walk(node):
        if id(node) in done:  # a record shared by two lookups must be scaled once
            return
        done.add(id(node))
        if isinstance(node, ValueRecord):
            fields = (("XPlacement", kx), ("XAdvance", kx), ("YPlacement", ky), ("YAdvance", ky))
        elif isinstance(node, otTables.Anchor):
            fields = (("XCoordinate", kx), ("YCoordinate", ky))
        else:
            fields = ()
        for field, k in fields:
            if getattr(node, field, None):
                setattr(node, field, round(getattr(node, field) * k))
        if isinstance(node, (list, tuple)):
            for item in node:
                walk(item)
        elif isinstance(node, BaseTable):
            node.ensureDecompiled()
            for value in list(vars(node).values()):
                walk(value)

    walk(font["GPOS"].table)


def complete_malayalam_language_systems(font):
    """Give every Malayalam language system the features its script's default system has.

    Baloo Chettan 2 ships a `MAL ` language system without `akhn`, the feature that forms
    conjuncts such as SSA+SSA, TTA+TTA, KA+KA and NA+MA. Text tagged as Malayalam - by libass (ffmpeg
    subtitles, mpv, VLC), by Pango on Linux, by a web page with lang="ml" - is shaped under `MAL `
    and the conjuncts fall apart; untagged text uses the default system and is fine, which is why
    it is easy to miss. Returns how many feature references were added.
    """
    added = 0
    for tag in ("GSUB", "GPOS"):
        if tag not in font:
            continue
        for script in font[tag].table.ScriptList.ScriptRecord:
            default = script.Script.DefaultLangSys
            if script.ScriptTag not in ("mlm2", "mlym") or default is None:
                continue
            for record in script.Script.LangSysRecord:
                system = record.LangSys
                merged = sorted(set(system.FeatureIndex) | set(default.FeatureIndex))
                added += len(merged) - len(system.FeatureIndex)
                system.FeatureIndex, system.FeatureCount = merged, len(merged)
    return added


def anchored_lookups(font):
    """GPOS lookups that attach glyphs at anchor points (cursive, mark-to-base/ligature/mark)."""
    if "GPOS" not in font:
        return []
    found = []
    for index, lookup in enumerate(font["GPOS"].table.LookupList.Lookup):
        kinds = {s.ExtensionLookupType if lookup.LookupType == 9 else lookup.LookupType for s in lookup.SubTable}
        if kinds & {3, 4, 5, 6}:
            found.append(index)
    return found


def add_ligatures(font, ligatures):
    """Append one ligature lookup and run it last in the post-base substitution feature.

    `ligatures` maps a new glyph name to the component sequences that should collapse into it.
    """
    gsub = font["GSUB"].table
    mapping = {tuple(components): name for name, sequences in ligatures.items() for components in sequences}
    lookup = otTables.Lookup()
    lookup.LookupType, lookup.LookupFlag = 4, 0
    lookup.SubTable = [buildLigatureSubstSubtable(mapping)]
    lookup.SubTableCount = 1
    gsub.LookupList.Lookup.append(lookup)
    gsub.LookupList.LookupCount = len(gsub.LookupList.Lookup)
    index = gsub.LookupList.LookupCount - 1  # highest index = applied after every existing rule
    features = [r.Feature for r in gsub.FeatureList.FeatureRecord if r.FeatureTag == "psts"]
    if not features:
        sys.exit("base font has no 'psts' feature to carry the traced ligature")
    for feature in features:
        feature.LookupListIndex.append(index)
        feature.LookupCount = len(feature.LookupListIndex)
    classes = font["GDEF"].table.GlyphClassDef.classDefs
    for name in ligatures:
        classes[name] = 2  # ligature


def malayalam_glyphs(font):
    """Every glyph that can be part of a Malayalam word: what 'preceded by a letter' means."""
    mapped = {glyph for codepoint, glyph in font.getBestCmap().items() if 0x0D00 <= codepoint <= 0x0D7F}
    named = {glyph for glyph in font.getGlyphOrder() if ".mlm" in glyph or glyph.endswith(".trace")}
    return mapped | named


def add_mid_word_forms(font, mid_forms):
    """Inside a word, swap each flourish glyph for its plain form: `calt`, [letter] flourish' -> plain.

    OpenType cannot say "at the start of a word", only "after a letter", so the flourish is the
    default and this rule removes it. The shaper has already moved pre-base vowel signs in front
    of their consonant, so "the glyph before" really is the end of the previous syllable. It has
    to be `calt`: HarfBuzz confines `psts` rules to one syllable and this one must look back
    across the boundary.
    """
    gsub = font["GSUB"].table
    glyph_ids = font.getReverseGlyphMap()
    lookups = gsub.LookupList.Lookup

    swap = otTables.Lookup()
    swap.LookupType, swap.LookupFlag = 1, 0
    swap.SubTable = [buildSingleSubstSubtable(mid_forms)]
    swap.SubTableCount = 1
    lookups.append(swap)

    rule = otTables.ChainContextSubst()
    rule.Format = 3
    rule.BacktrackGlyphCount, rule.BacktrackCoverage = 1, [buildCoverage(malayalam_glyphs(font), glyph_ids)]
    rule.InputGlyphCount, rule.InputCoverage = 1, [buildCoverage(set(mid_forms), glyph_ids)]
    rule.LookAheadGlyphCount, rule.LookAheadCoverage = 0, []
    record = otTables.SubstLookupRecord()
    record.SequenceIndex, record.LookupListIndex = 0, len(lookups) - 1
    rule.SubstCount, rule.SubstLookupRecord = 1, [record]
    context = otTables.Lookup()
    context.LookupType, context.LookupFlag = 6, 0
    context.SubTable = [rule]
    context.SubTableCount = 1
    lookups.append(context)
    gsub.LookupList.LookupCount = len(lookups)

    # The feature list is kept in tag order, so inserting `calt` shifts every later index.
    records = gsub.FeatureList.FeatureRecord
    if any(r.FeatureTag == "calt" for r in records):
        sys.exit("base font already has a 'calt' feature; extend it instead of adding a second one")
    position = sum(r.FeatureTag < "calt" for r in records)
    calt = otTables.FeatureRecord()
    calt.FeatureTag, calt.Feature = "calt", otTables.Feature()
    calt.Feature.FeatureParams, calt.Feature.LookupListIndex, calt.Feature.LookupCount = None, [len(lookups) - 1], 1
    records.insert(position, calt)
    gsub.FeatureList.FeatureCount = len(records)
    wired = 0
    for script in gsub.ScriptList.ScriptRecord:
        systems = [script.Script.DefaultLangSys] + [r.LangSys for r in script.Script.LangSysRecord]
        for system in filter(None, systems):
            system.FeatureIndex = [i + (i >= position) for i in system.FeatureIndex]
            if system.ReqFeatureIndex != 0xFFFF and system.ReqFeatureIndex >= position:
                system.ReqFeatureIndex += 1
            if script.ScriptTag in ("mlm2", "mlym"):
                system.FeatureIndex = sorted(system.FeatureIndex + [position])
                wired += 1
            system.FeatureCount = len(system.FeatureIndex)
    if not wired:
        sys.exit("base font has no Malayalam script (mlm2/mlym) in GSUB to carry the mid-word rule")


def swap_in_traced(font, traced, shear):
    """Replace base glyphs with the poster's own outlines. `shear` is tan(lean) of the base glyphs.

    Returns ({new ligature glyph: component sequences}, {flourish glyph: its plain mid-word form}).
    """
    glyf, hmtx = font["glyf"], font["hmtx"]
    classes = font["GDEF"].table.GlyphClassDef.classDefs
    ligatures, mid_forms = {}, {}
    for name, entry in traced.items():
        if entry.get("word_initial_only"):
            # Keep the base's own (already squeezed, fattened, leaned) glyph as the mid-word form.
            plain = name + ".mid"
            glyf[plain], hmtx[plain] = glyf[name], hmtx[name]
            if name in classes:
                classes[plain] = classes[name]
            mid_forms[name] = plain
        path = pathops.Path()
        parse_path(entry["d"], path.getPen())
        if entry["kind"] == "mark":
            # A mark sits where the base's mark sat: same horizontal centre, zero advance.
            old = glyf[name]
            x_min, _, x_max, _ = path.bounds
            path = path.transform(1, 0, 0, 1, (old.xMin + old.xMax) / 2 - (x_min + x_max) / 2, 0)
            advance = 0
        else:
            if entry["kind"] == "base" and name not in glyf.glyphs:
                sys.exit(f"traced glyph {name} is not in the base font")
            # The poster's letters already lean. Side bearings only mean the same thing as the
            # sheared base glyphs' if they are measured with that lean taken out: on a leaning
            # shape the box's left edge is wherever it bulges, not where it meets the baseline.
            x_min, _, x_max, _ = path.transform(1, 0, -shear, 1, 0, 0).bounds
            path = path.transform(1, 0, 0, 1, TRACED_SIDE_BEARING - x_min, 0)
            advance = round(x_max - x_min) + 2 * TRACED_SIDE_BEARING
        glyf[name] = to_glyph(path)
        glyf[name].recalcBounds(glyf)
        hmtx[name] = (advance, glyf[name].xMin)
        if entry["kind"] == "ligature":
            ligatures[name] = entry["ligature_of"]
    added = list(ligatures) + list(mid_forms.values())
    font.setGlyphOrder([g for g in font.getGlyphOrder() if g not in added] + added)
    if ligatures:
        add_ligatures(font, ligatures)  # lower lookup index, so it runs before the mid-word rule sees the glyphs
    if mid_forms:
        add_mid_word_forms(font, mid_forms)
    return ligatures, mid_forms


def build(base_path, out_path, grow_em, soften_em, pin_em, spacing, lean, traced_path, x_scale, y_scale, optical):
    font = TTFont(base_path, recalcTimestamp=False)  # rename() sets head.modified from RELEASED
    if "glyf" not in font or "fvar" in font:
        sys.exit(f"{base_path}: need a static TrueType (glyf) base; instantiate variable fonts first")
    if lean and anchored_lookups(font):
        sys.exit(f"{base_path}: GPOS lookups {anchored_lookups(font)} attach marks at anchor points. A lean shears "
                 "outlines only, which would detach them. Use --lean 0 or a base without anchors.")
    upm = font["head"].unitsPerEm
    grow, soften, pin = grow_em * upm, soften_em * upm, pin_em * upm
    shear = math.tan(math.radians(lean))
    base_family = font["name"].getDebugName(1)

    glyph_set = font.getGlyphSet()
    # Condense first, then fatten: the squeeze thins the vertical stems and the growth puts the
    # weight back evenly, which also flattens the base's thick/thin contrast.
    shapes = {name: glyph_shape(glyph_set, name).transform(x_scale, 0, 0, y_scale, 0, 0)
              for name in font.getGlyphOrder()}
    scale_positioning(font, x_scale, y_scale)
    language_fixes = complete_malayalam_language_systems(font)

    glyf, hmtx = font["glyf"], font["hmtx"]
    for name in font.getGlyphOrder():
        hmtx[name] = (round(hmtx[name][0] * x_scale), hmtx[name][1])
    squeezed_glyphs = []
    shifts = {}  # how far each outline moved sideways; verify() needs it to find the counters again
    band = (BODY_BAND[0] * upm * y_scale, BODY_BAND[1] * upm * y_scale)
    # The band is where Malayalam letter bodies sit. Latin, digits and punctuation do not share it
    # (a T's arm is above it), so they are spaced by their box, which can never collide.
    malayalam = malayalam_glyphs(font)
    for name, shape in shapes.items():
        if is_empty(shape):
            continue
        try:
            fat, squeezed = inflate(shape, grow, soften, pin)
        except pathops.PathOpsError as error:
            sys.exit(f"{base_path}: glyph {name}: {error}")
        if squeezed:
            squeezed_glyphs.append(name)
        advance, _ = hmtx[name]
        shift = 0.0
        if advance:  # zero-advance marks must stay zero-advance, and stay where they are
            # Keep `spacing` of the whitespace on each side, measured from the facing edges. A
            # negative side is deliberate (a sign tucking under its consonant) and is kept as is.
            # Growth moved each edge out by `grow`, which the shift and the advance absorb.
            left, right = facing_edges(shape, band, optical if name in malayalam else 0.0)
            keep_left = left * spacing if left > 0 else left
            keep_right = (advance - right) * spacing if advance > right else advance - right
            shift = keep_left - (left - grow)
            advance = round(right + grow + shift + keep_right)
        shifts[name] = shift
        glyf[name] = to_glyph(fat.transform(1, 0, shear, 1, shift, 0))  # x += y * tan(lean), then the shift
        glyf[name].recalcBounds(glyf)
        hmtx[name] = (advance, glyf[name].xMin)

    traced = json.loads(Path(traced_path).read_text()) if traced_path else {}
    ligatures, mid_forms = swap_in_traced(font, traced, shear)

    pad = math.ceil(grow)
    hhea, os2 = font["hhea"], font["OS/2"]
    hhea.ascent += pad
    hhea.descent -= pad
    os2.sTypoAscender += pad
    os2.sTypoDescender -= pad
    os2.usWinAscent += pad
    os2.usWinDescent += pad

    rename(font, base_family, lean)
    font.save(out_path)
    print(f"built {out_path}: grow={grow:.0f} soften={soften:.0f} pinhole={pin:.0f} units @ {upm} upm, lean {lean} deg; "
          f"{len(squeezed_glyphs)} glyphs had a counter held open as a pinhole; "
          f"{nudged} boolean ops needed a nudged radius; {len(traced)} traced glyphs, {len(ligatures)} new ligature, "
          f"{len(mid_forms)} flourishes limited to word starts; "
          f"{language_fixes} features restored to Malayalam language systems")
    return shapes, pin, set(traced), ligatures, mid_forms, shifts


def shape_text(font_path, text, language=None):
    font = hb.Font(hb.Face(hb.Blob.from_file_path(font_path)))
    buffer = hb.Buffer()
    buffer.add_str(text)
    buffer.guess_segment_properties()
    if language:
        buffer.language = language
    hb.shape(font, buffer)
    return [font.glyph_to_string(info.codepoint) for info in buffer.glyph_infos]


def collapse(glyphs, ligatures):
    """What the base's shaping becomes once each ligature's component run is replaced by it."""
    rules = sorted(((tuple(seq), name) for name, seqs in ligatures.items() for seq in seqs), key=lambda r: -len(r[0]))
    out, i = [], 0
    while i < len(glyphs):
        for components, name in rules:
            if tuple(glyphs[i:i + len(components)]) == components:
                out.append(name)
                i += len(components)
                break
        else:
            out.append(glyphs[i])
            i += 1
    return out


def plain_inside_words(glyphs, mid_forms, letters):
    """A flourish keeps its big form only when no Malayalam glyph comes right before it."""
    return [mid_forms[g] if g in mid_forms and i and glyphs[i - 1] in letters else g
            for i, g in enumerate(glyphs)]


def verify(base_path, out_path, shapes, pin, lean, traced_names, ligatures, mid_forms, shifts):
    """Check the artifact on disk, not the intent in memory."""
    from proof import MIXED, STRESS, TITLE  # the same text the proof sheets show

    base, out = TTFont(base_path), TTFont(out_path)
    failures = []
    if out.getGlyphOrder() != base.getGlyphOrder() + list(ligatures) + list(mid_forms.values()):
        failures.append("glyph order is not the base's order plus the new glyphs")
    if base.getTableData("cmap") != out.getTableData("cmap"):
        failures.append("cmap is no longer byte-identical to the base")
    letters = malayalam_glyphs(out)
    seen_big, seen_plain = set(), set()
    for line in "\n".join((TITLE, STRESS, MIXED)).splitlines():
        expected = plain_inside_words(collapse(shape_text(base_path, line), ligatures), mid_forms, letters)
        # Shape untagged AND tagged as Malayalam: renderers that tag the text (libass, Pango, a web
        # page with lang="ml") select a different language system, and both must give the same result.
        for language in (None, "ml"):
            got = shape_text(out_path, line, language)
            seen_big |= set(got) & set(mid_forms)
            seen_plain |= set(got) & set(mid_forms.values())
            if expected != got:
                failures.append(f"shaping changed for {line!r} (language={language}):\n"
                                f"      base {expected}\n      now  {got}")

    out_set = out.getGlyphSet()
    unshear = -math.tan(math.radians(lean))
    min_open = 0.8 * math.pi * (pin / 2) ** 2
    bridged = []
    for name, shape in shapes.items():
        if (name in traced_names and name not in mid_forms) or is_empty(shape):
            continue  # a traced glyph is a new drawing, not the base's counters grown
        original = counters(shape)
        grown = mid_forms.get(name, name)  # a flourish's base outline lives on as its mid-word form
        # Undo the sideways shift, then the lean, to lay the built glyph back over the base shape.
        upright = glyph_shape(out_set, grown).transform(1, 0, 0, 1, -shifts[name], 0).transform(1, 0, unshear, 1, 0, 0)
        final_holes = counters(upright)
        for index, counter in enumerate(original):
            # Point-in-path, not a boolean op: a surviving hole can coincide with its counter.
            reach = dilate(counter, 3)
            open_area = sum(h.area for h in final_holes if reach.contains(h.firstPoints[0]))
            if open_area < min(min_open, 0.8 * counter.area):
                failures.append(f"{name}: counter {index} closed up (open area {open_area:.0f} < {min_open:.0f})")
        if len(final_holes) > len(original):
            bridged.append(name)
    for name in traced_names:
        if is_empty(glyph_shape(out_set, name)):
            failures.append(f"traced glyph {name} came out empty")

    # The proof text must exercise both outcomes, or the check above proves nothing about the rule.
    for flourish, plain in mid_forms.items():
        if flourish not in seen_big or plain not in seen_plain:
            failures.append(f"proof text never shows {flourish} both at a word start and inside a word")

    print(f"verify: {len(shapes)} glyphs, {len(bridged)} with an aperture bridged into a new pinhole")
    review = Path("proofs") / f"{Path(out_path).stem}.bridged.txt"  # glyphs worth a look by eye
    review.parent.mkdir(exist_ok=True)
    review.write_text("\n".join(bridged) + "\n")
    if failures:
        sys.exit("VERIFY FAILED:\n  " + "\n  ".join(failures))
    print("verify: OK - every base counter is still open; HarfBuzz shapes the proof text exactly as the base does"
          + (f", except the added {', '.join(ligatures)}" if ligatures else "")
          + (f"; {', '.join(mid_forms)} keep their flourish only at word starts" if mid_forms else ""))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="base/BalooChettan2-ExtraBold.ttf")
    parser.add_argument("--license", default="base/BalooChettan2-OFL.txt", help="the base font's OFL text")
    parser.add_argument("--out", default=f"dist/{FAMILY}-Regular.ttf")
    parser.add_argument("--traced", default="traced/glyphs.json", help="trace.py output; pass '' to skip")
    # Defaults are tuned against the traced poster letters: condensed (their ത is as wide as it is
    # tall; Baloo's is 1.6x wider), body ~600 units tall, near-uniform ~180-unit strokes, a forward
    # lean of about 9 degrees, fairly sharp crotches, letters that nearly touch.
    # 0.80 is the most squeeze the many-stroked letters (ഞ ണ ഭ മ്മ) take before they clot; at 0.68,
    # which would match the traced widths, they turn into blobs.
    parser.add_argument("--x-scale", type=float, default=0.80, help="horizontal squeeze applied before growth")
    parser.add_argument("--y-scale", type=float, default=0.94, help="vertical scale, so growth lands on the traced body height")
    parser.add_argument("--grow", type=float, default=0.019, help="outward growth, em")
    parser.add_argument("--soften", type=float, default=0.006, help="crotch rounding radius, em")
    parser.add_argument("--pinhole", type=float, default=0.035, help="minimum counter diameter, em")
    parser.add_argument("--spacing", type=float, default=0.3,
                        help="fraction of the base font's side-bearing whitespace to keep (1 = same gaps)")
    parser.add_argument("--optical", type=float, default=1.0,
                        help="Malayalam glyphs: 0 spaces them by their box, 1 by their edge at body height")
    parser.add_argument("--lean", type=float, default=9.0, help="forward lean, degrees")
    args = parser.parse_args()
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    built_shapes, pin_units, traced_set, new_ligatures, new_mid_forms, outline_shifts = build(
        args.base, args.out, args.grow, args.soften, args.pinhole, args.spacing, args.lean, args.traced,
        args.x_scale, args.y_scale, args.optical)
    verify(args.base, args.out, built_shapes, pin_units, args.lean, traced_set, new_ligatures, new_mid_forms,
           outline_shifts)
    # The OFL requires the licence and original copyright notice to travel with the font.
    shutil.copy(args.license, Path(args.out).parent / "OFL.txt")
