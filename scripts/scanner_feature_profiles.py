"""Fail-closed feature-profile checks for scanner experiments, not detection.

Code identity alone does not describe process-local boolean overrides. Prepare
complete profiles from authoritative runtime state and validate the declared
experimental difference BEFORE scanning. Missing old metadata is unknown, not
a reason to assume an unrecorded selector was False.
"""
from collections.abc import Mapping


SOURCE_FEATURE_SWITCHES = frozenset({
    '_SOURCE_FRAME_ARBITRATION_ENABLED',
    '_SOURCE_INTERIOR_GLYPHS_ENABLED',
    '_SOURCE_COMPOUND_CONFLICTS_ENABLED',
    '_SOURCE_DEFERRED_PLATFORMS_ENABLED',
    '_SOURCE_REJECTED_PRIMARY_RECOVERY_ENABLED',
    '_SOURCE_REPEATED_IDENTITY_ENABLED',
    '_CAPTURE_BASE_CONTEXT_ENABLED',
})


def _switch_values(values):
    if not isinstance(values, Mapping) or set(values) != SOURCE_FEATURE_SWITCHES:
        raise ValueError('A complete, explicitly recorded scanner switch profile is required')
    if any(type(value) is not bool for value in values.values()):
        raise ValueError('Every recorded scanner selector must be an actual boolean')
    return {name: values[name] for name in sorted(SOURCE_FEATURE_SWITCHES)}


def recorded_feature_profile(values):
    """Validate explicit metadata; never infer missing old runtime overrides."""
    return {'schema_version': 1, 'switches': _switch_values(values)}


def snapshot_feature_profile(scanner_module):
    """Read complete actual selector state, including monkeypatched experiments."""
    namespace = vars(scanner_module)
    enabled = {name for name, value in namespace.items()
               if name.startswith('_') and name.isupper() and name.endswith('_ENABLED')}
    if enabled != SOURCE_FEATURE_SWITCHES:
        raise ValueError('Scanner selector inventory changed; update the explicit profile schema')
    return recorded_feature_profile({name: namespace[name] for name in enabled})


def _profile_values(profile):
    if (not isinstance(profile, Mapping) or set(profile) != {'schema_version', 'switches'}
            or type(profile['schema_version']) is not int or profile['schema_version'] != 1):
        raise ValueError('Unsupported or incomplete scanner feature-profile record')
    return _switch_values(profile['switches'])


def validate_feature_comparison(baseline, candidate, *, expected_changes):
    """Require EXACT declared changes, and equality of every other selector.

    ``expected_changes`` maps each tested selector to its explicit (before,
    after) boolean pair. An empty mapping validates a code-only comparison.
    Baseline/candidate and caller metadata are not mutated. This does not check
    code/source/options/reference identity or numerical/semantic correctness;
    those remain independent, mandatory qualification checks.
    """
    before, after = _profile_values(baseline), _profile_values(candidate)
    if not isinstance(expected_changes, Mapping) or not set(expected_changes) <= SOURCE_FEATURE_SWITCHES:
        raise ValueError('Expected changes must name registered scanner selectors')
    declared = {}
    for name, pair in expected_changes.items():
        if (not isinstance(pair, (tuple, list)) or len(pair) != 2
                or any(type(value) is not bool for value in pair) or pair[0] == pair[1]):
            raise ValueError('Each tested selector needs a distinct actual-boolean before/after pair')
        declared[name] = tuple(pair)
    actual = {name: (before[name], after[name]) for name in before if before[name] != after[name]}
    if actual != declared:
        raise ValueError('Confounded or missing selector change: expected '
                         f'{sorted(declared.items())}, observed {sorted(actual.items())}')
    return {'schema_version': 1, 'untested_switches_identical': True,
            'declared_changes': {name: list(pair) for name, pair in sorted(actual.items())},
            'NOT_code_input_output_or_accuracy_qualification': True}
