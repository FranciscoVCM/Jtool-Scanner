"""Experimental original-source full-block pose repair; no default app binding.

Requires a unique nearby whole-frame texture match, preservation of known solid
pixels, source-proved empty old margins and protected glyph/nonterrain exclusions.
Material inputs must be independent original-source evidence, never answer maps.
"""
from __future__ import annotations

from math import sqrt

from jtool_scanner.spike_shape import VERTICES
from scripts.source_block_prototypes import SourceBlockLibrary
from scripts.source_glyph_prototypes import SourceGlyphLibrary, _contains
from scripts.source_local_background import SourceLocalBackground


def _footprint(key):
    type_id, x, y = key
    size = 16 if type_id == 2 else 32
    return {(px, py) for py in range(y, y+size) for px in range(x, x+size)}


def refit_full_poses(image, room, detections, proposed, rejected, source_material, *, source_context=None):
    """Return source-supported proposals, removals and isolated diagnostics.

    Original detections are only source locators, not a declaration of truth.
    Newly proposed objects never teach appearance or background. Preserve all
    original minis/nonterrain; remove only source-disproved full poses with a
    unique positively supported alternative. Unknown evidence causes abstention.
    """
    proposed, rejected = set(proposed), set(rejected)
    terrain = set(map(tuple, source_material.get('accepted', [])))
    flat = set(map(tuple, source_material.get('source_flat_accepted_cells', [])))
    textured = terrain-flat
    existing = {(d.type_id, d.x, d.y) for d in detections}
    anchors = [d for d in detections if d.type_id not in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20)]
    spikes = [(d.type_id, d.x, d.y) for d in detections if 3 <= d.type_id <= 10]
    if source_context is not None:
        source_context.validate(image, room, spikes)
    labels = set(source_material.get('selected_clusters', []))
    tips = source_material.get('tip_votes', {})
    backs = source_material.get('background_back_votes', source_material.get('back_votes', {}))
    bg = {int(c) for c, votes in tips.items()
          if votes >= 3 and votes/(votes+backs.get(int(c), backs.get(str(c), 0))) >= .75}
    centers = [tuple(c[n] for n in ('r', 'g', 'b')) for c in source_material.get('cluster_centers', [])]
    if not labels or not bg:
        return proposed, rejected, dict(texture_pose_proofs=[], texture_pose_abstention='no independent material roles')
    distance = lambda a, b: sqrt(sum((u-v)**2 for u, v in zip(a, b)))
    foreground, background = [centers[i] for i in labels], [centers[i] for i in bg]
    separation = min(distance(f, b) for f in foreground for b in background)
    library = (SourceGlyphLibrary(image, room, spikes) if source_context is None else
               source_context.glyph_library(image, room, spikes))
    polygons = []
    for anchor in library.anchors:
        type_id, x, y = anchor['key']
        size = anchor['size']
        direction = type_id-4 if type_id > 6 else type_id
        polygons.append([(x+u*size/32, y+v*size/32) for u, v in VERTICES[direction]])
    texture = SourceBlockLibrary(
        library, {(d.x, d.y) for d in detections if d.type_id == 1}, textured, polygons)
    known = {p for x, y in terrain for p in _footprint((2, x, y))}
    local_background = SourceLocalBackground(library, lambda value:
        min(distance(value, c) for c in background) < .5*min(distance(value, c) for c in foreground))
    background_proofs, bg_cache, membership = [], {}, {}

    def background_patch(x, y):
        key = x, y
        if key in bg_cache:
            return bg_cache[key]
        values = []
        for py in range(y, y+8):
            for px in range(x, x+8):
                if not (0 <= px < 800 and 0 <= py < 608):
                    return False
                sx = int(room.x+(px+.5)*room.width/800)
                sy = int(room.y+(py+.5)*room.height/608)
                if not (0 <= sx < image.width and 0 <= sy < image.height):
                    return False
                values.append(image.pixel(sx, sy))
        for value in values:
            if value not in membership:
                f, b = min(distance(value, c) for c in foreground), min(distance(value, c) for c in background)
                membership[value] = b < .5*f
        mean = tuple(sum(v[c] for v in values)/64 for c in range(3))
        proof = local_background.predict(x+4, y+4, .25*separation)
        mean_error = distance(mean, proof['prediction']) if proof['valid'] else float('inf')
        result = sum(membership[v] for v in values)/64 >= .95 and proof['valid'] and mean_error <= .25*separation
        background_proofs.append(dict(native=[x, y, 8, 8], source_proof=proof, mean_error=mean_error,
                                      unchanged_mean_error_limit=.25*separation, background_passed=result))
        bg_cache[key] = result
        return result

    def anchor_overlap(x, y):
        return any(max(x, a.x) < min(x+32, a.x+32) and max(y, a.y) < min(y+32, a.y+32) for a in anchors)

    proofs, new, retired = [], set(), set()
    for old in sorted(existing-rejected):
        if old[0] != 1:
            continue
        _, x, y = old
        if x % 16 or y % 16 or anchor_overlap(x, y):
            continue
        extent = _footprint(old)
        old_positive = extent & known
        if extent <= known:
            continue
        old_proof = texture.support(x, y)
        if old_proof['passed']:
            continue
        candidates = []
        for dx in (-16, 0, 16):
            for dy in (-16, 0, 16):
                nx, ny = x+dx, y+dy
                if (nx, ny) == (x, y) or not (0 <= nx <= 768 and 0 <= ny <= 576) or anchor_overlap(nx, ny):
                    continue
                cells = {(nx, ny), (nx+16, ny), (nx, ny+16), (nx+16, ny+16)}
                if len(cells & textured) < 2:
                    continue
                candidate_proof = texture.support(nx, ny)
                if not candidate_proof['passed']:
                    continue
                candidate = 1, nx, ny
                target = _footprint(candidate)
                if not old_positive <= target:
                    continue
                exclusive, empty = extent-target, []
                for bx in range(x, x+25, 4):
                    for by in range(y, y+25, 4):
                        patch = {(px, py) for py in range(by, by+8) for px in range(bx, bx+8)}
                        if not patch <= exclusive or patch & known:
                            continue
                        if any(_contains(poly, px+.5, py+.5) for poly in polygons for px, py in patch):
                            continue
                        if background_patch(bx, by):
                            empty.append([bx, by, 8, 8])
                if empty:
                    candidates.append(dict(old=old, new=candidate, source_texture_cells=sorted(cells & textured),
                        unmasked_source_full_texture=candidate_proof, old_unmasked_source_full_texture=old_proof,
                        visible_empty_source_patches=empty, all_old_source_foreground_pixels_retained=True,
                        protected_glyph_polygons_not_background=True))
        if len(candidates) != 1:
            continue
        row = candidates[0]
        new.add(tuple(row['new']))
        retired.add(old)
        proofs.append(row)
    new_pixels = {p for key in new for p in _footprint(key)}
    redundant = {key for key in proposed-existing if key[0] == 2 and _footprint(key) <= new_pixels}
    # A positively disproved old pose must not re-enter through the proposal set.
    # This removes only the exact fulls proved retired above, not overlaps/minis.
    return (proposed-redundant-retired) | new, rejected | retired, dict(texture_pose_proofs=proofs,
        original_source_full_texture_teachers=texture.teachers,
        original_source_full_texture_model_count=len(texture.models),
        only_new_mini_duplicates_removed=sorted(redundant), local_original_background_proofs=background_proofs,
        **{'no_existing_mini_deletion_or_new_witnesses=True': True})
