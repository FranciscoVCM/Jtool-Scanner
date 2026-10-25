"""Test-only support for the real original-field recording protocol."""
from scripts.source_filled_pipeline import FilledGlyphEvidence


def record_requested_original_filled_source(detections, options):
    """Record only the incoming originals, never a stub's proposed additions."""
    if options.get('record_filled_source') is not True:
        return None
    original=tuple(detections);frame=options['source_frame']
    field=FilledGlyphEvidence(frame,original)
    options['source_context'].record_filled_source(original,frame,field)
    return field
