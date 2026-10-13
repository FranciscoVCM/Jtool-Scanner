"""Explicit transitive source-geometry runtime files for code identity checks."""
from pathlib import Path

SOURCE_GEOMETRY_MODULES = (
    'source_contours', 'source_glyph_prototypes', 'source_block_prototypes',
    'source_evidence_context', 'source_local_background', 'source_full_pose',
    'source_material_evidence', 'source_material_patterns', 'source_material_ownership',
    'source_occupancy', 'source_geometry_pipeline', 'source_terrain_agreement',
    'source_rectangle_prototypes', 'source_sampling', 'source_hollow_glyphs',
    'source_hollow_pipeline',
)


def source_geometry_files():
    root = Path(__file__).resolve().parent.parent
    paths = [root/'scripts'/(name+'.py') for name in SOURCE_GEOMETRY_MODULES]
    for path in paths:
        if not path.is_file():
            raise RuntimeError(f'Missing source geometry runtime dependency: {path.name}')
    return tuple(paths)
