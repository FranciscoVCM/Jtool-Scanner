"""Experimental source identity/size agreement; no reference maps or app binding.

Only NEW full proposals are adjudicated. Original source evidence must positively
support a competing glyph before incomplete terrain evidence can disprove a full.
"""
from __future__ import annotations

from jtool_scanner.terrain_material import cell_quad, pack_textured_rectangles
from jtool_scanner.spike_shape import VERTICES
from scripts.source_glyph_prototypes import SourceGlyphLibrary, _contains
from scripts.source_block_prototypes import SourceBlockLibrary


def _footprint(key):
    kind, x, y = key
    size = 16 if kind == 2 else 32
    return {(px, py) for py in range(y, y+size) for px in range(x, x+size)}


def agree_new_fulls(image, room, detections, proposed, rejected, cells, flat_cells=()):
    """Return proposals and source proofs, without mutating original detections.

    ``cells``/``flat_cells`` must come from independent original-source evidence.
    Newly proposed objects must never be added to ``detections`` as teachers.
    ``rejected`` contains prior source-disproved objects; this rule adds no old
    object removals and does not interpret unknown pixels as empty space.
    """
    proposed, rejected, cells, flat = set(proposed), set(rejected), set(cells), set(flat_cells)
    existing = {(d.type_id, d.x, d.y) for d in detections}
    fulls = {k for k in proposed-existing if k[0] == 1}
    disagreement = {k for k in fulls if not cell_quad(k[1:]) <= cells}
    if not disagreement:
        return proposed, dict(new_full_source_disagreement=[], original_source_size_preserved=True)
    spikes = [(d.type_id, d.x, d.y) for d in detections if 3 <= d.type_id <= 10]
    library = SourceGlyphLibrary(image, room, spikes)
    owner_cache = {}

    def quarter_owners(x, y):
        if (x, y) in owner_cache:
            return owner_cache[x, y]
        points = [(x, y), (x+16, y), (x+16, y+16), (x, y+16)]
        faces = [library.raw.raw.edge(points[i], points[(i+1)%4]) for i in range(4)]
        if all(n >= 9 and not unknown for n, unknown in faces):
            owner_cache[x, y] = []
            return []
        owners = []
        for kind, sx, sy in sorted(set(spikes)):
            size = 16 if kind > 6 else 32
            if max(x, sx) >= min(x+16, sx+size) or max(y, sy) >= min(y+16, sy+size):
                continue
            for direction in (3, 4, 5, 6):
                key = direction+(4 if size == 16 else 0), sx, sy
                proof = library.support(*key)
                if not proof['passed']:
                    continue
                polygon = [(sx+u*size/32, sy+v*size/32) for u, v in VERTICES[direction]]
                core = sum(_contains(polygon, px+.5, py+.5)
                           for py in range(y+4, y+12) for px in range(x+4, x+12))
                if core >= 16:
                    owners.append(dict(key=key, source_proof=proof, core_owned_pixels=core,
                                       competing_raw_rectangle_faces=faces))
        owner_cache[x, y] = owners
        return owners

    polygons = []
    for anchor in library.anchors:
        kind, x, y = anchor['key']
        size = anchor['size']
        direction = kind-4 if kind > 6 else kind
        polygons.append([(x+u*size/32, y+v*size/32) for u, v in VERTICES[direction]])
    texture = SourceBlockLibrary(library, {k[1:] for k in existing if k[0] == 1}, cells-flat, polygons)
    abstained, proofs = set(), []
    for key in sorted(disagreement):
        supported = cell_quad(key[1:]) & cells
        owners = [dict(native=c, owners=quarter_owners(*c)) for c in sorted(cell_quad(key[1:])-cells)]
        competitor = any(row['owners'] for row in owners)
        proof = texture.support(*key[1:]) if competitor else None
        abstain = competitor and not proof['passed']
        if abstain:
            abstained.add(key)
        proofs.append(dict(key=key, supported_source_quarters=sorted(supported),
                           missing_source_quarters=sorted(cell_quad(key[1:])-cells),
                           explicit_source_glyph_owners=owners,
                           unknown_alone_does_not_disprove_terrain=not competitor,
                           original_source_whole32_proof=proof, abstained=abstain))
    retained = proposed-abstained
    recoverable = {c for k in abstained for c in cell_quad(k[1:]) & cells}
    packed = pack_textured_rectangles(recoverable)
    covered = {c for p in packed for c in cell_quad(p)}
    recovered = {(1, x, y) for x, y in packed} | {(2, x, y) for x, y in recoverable-covered}
    occupied = {p for k in (existing-rejected) | retained if k[0] in (1, 2) for p in _footprint(k)}
    recovered = {k for k in recovered if not _footprint(k) <= occupied}
    return retained | recovered, dict(new_full_source_disagreement=proofs,
                                     source_supported_quarter_repacking=sorted(recovered),
                                     original_objects_not_removed_by_new_full_qualification=True,
                                     no_unknown_as_absence_or_overlap_only_deletion=True)
