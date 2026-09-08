# Cross-tileset milestone

## Objective and completion requirements

Establish a reproducible, versioned cross-tileset baseline; trace representative
failures through candidate generation, classification, placement and arbitration;
rank the next development work; and demonstrate one measured generalized
improvement against separate evaluation families while protecting FTFA and relevant
fixtures. Completing this milestone does not mean all 71 rooms are accurate.

Generalization is the primary objective. The 71-screen corpus supplies observed
failures and regression examples, not authoritative exact truth for every room.
No filenames, screen coordinates, room palettes or manual reference objects may
be used as production detection rules. Reference JMaps are evaluation-only.

## Versioned baseline

The initial baseline is pinned to commit
`115bb2d245233a7a511f533d132a26423b7e3886`, package fingerprint
`02f438e14175b2ddb5284d476c5a0442f957f773b1823f9cac2437ee8ce4b964`.
All 26 cases completed. After interruption, 23 verified completed cases were
reused and only the remaining three were scanned. The run records Python/Pillow
versions, input/settings/reference hashes, original scan revision, artifact
checksums, scan durations and raw detections.

Local manifest: `.artifacts/cross-tileset-20260908/manifest.json`.
Local report: `.artifacts/cross-tileset-20260908/baseline/report.json`.
Historical and partial reports remain in `baseline/runs/`.

| Role for the next experiment | Cases |
|---|---|
| Development | CN3-9, CN3-27, CN3-31, CN3-Golden5, CN3-Halls2 |
| Separate evaluation families | Say-1, Say-9, NANG-128, NANG-128r, Zero_Final |
| Protected reference controls | FTFA-1 through FTFA-4 and all twelve block/spike fixture pairs |

These images have historical development exposure. The partition is a prospective
experiment boundary, not a claim of previously unseen data. New examples from
the user can provide a stronger cold evaluation later; they are not needed to
continue now. Baseline durations were collected under varying concurrent load
and are not a controlled latency benchmark.

FTFA remains 926/928 exact with zero extras, shifts or direction errors; the two
known boundary blocks remain missed. The exact comparator also makes important
control limitations visible: Irkara-89 has 100/113 exact full spikes, 29 extra
full spikes, 12 shifted full spikes and one wrong orientation. CN3-18 has one
extra mini-up spike at (496,416) as well as the known offscreen water miss.
These are baseline errors, not evidence that this workflow changed detection.
Use the report's exact results rather than older tolerance-based shorthand.

## Diagnosis already established

Halls2's missing right spike is not an initial classification failure:

1. The 32px patch at (248,184) is classified right-facing, score 0.7596,
   direction margin 0.4502, outline separation 0.6865; acceptance returns true.
2. `_normalize_full_spike_detections` moves it to (248,192), following the
   fixed transverse-axis snap. The neighboring left spike is shifted similarly.
3. `_prune_full_spike_shape_noise` removes the shifted support candidates.
4. The existing final refit recovers the left spike from a different incorrect
   candidate; the right spike remains missing.

The observational trace yields exactly the same final JMap as the uninstrumented
scan. Local evidence: `traces/CN3_Halls2/events.json` and `summary.md` under the
cross-tileset artifact directory. It covers selected patch/classifier/acceptance
decisions and list-returning stages, not every internal decision in the scanner.

A counterfactual source-score guard recovers the right spike, but its eight
phase decisions also change downstream geometry elsewhere in Halls2. It is
not yet a production fix or a proven room-wide improvement. Four FTFA outputs
are unchanged; initial Irkara-89 metrics are unchanged despite moving another
already-inexact spike. Complete regional review and further controls before
accepting or rejecting this approach. Keep the rejected or inconclusive evidence.

The stricter research guard additionally requires strong directed slopes at the
original position, weak slopes at the forced snap and strong absolute local
inside/outside contrast separation. In eight manually reviewed Halls2 positions,
exact presence improves from 1/8 to 8/8. This is a selected regional measurement,
not whole-room recall or precision. Its complete output still changes 22 added
and 29 removed spike tuples, and visible errors remain elsewhere in the room.
Irkara-89 now has zero proposals and an unchanged map, rejecting the earlier
wrong-position movement. NANG-128, NANG-128r and Zero_Final also have unchanged
maps. These no-effect checks protect cases but do not demonstrate recognition
gains on a different tileset. The guard remains outside production pending
broader changed-region review and evidence of transfer.

### Second trace: classified component size lost during placement

The NANG-128r observational trace also reproduces its ordinary final JMap
exactly. The adaptive compact component stage recognizes all eighteen visible
minispikes, but passes each component to an origin helper that subtracts half
a 32px object. These are 16px objects, so they are emitted eight pixels up and
left of their source-supported origins and survive arbitration there.
This is a different placement mechanism from transverse snapping, not an
absence of unfamiliar-palette candidates. It does not prove that all current
tileset failures are placement failures.

The implementation candidate makes the helper's native object size explicit
and passes 16 for classified minispikes, retaining the 32px default for other
callers. No color/classification threshold changes. A manually reviewed list
of eighteen NANG-128r minispike origins improves from 0/18 exact to 18/18 exact;
all non-minispike tuples remain unchanged. NANG-128 is unchanged. Whole-room
accuracy is still not established. Synthetic real connected-component tests
cover four orientations, both sizes, three capture scales and two brightness
combinations. The full 26-case comparison completed: only these eighteen
minispike positions changed. All other maps and all sixteen exact-reference
reports are unchanged, including FTFA 926/928 exact with no extras, shifts or
direction errors. The expanded targeted suite passed 103 tests and 74 subtests.

NANG-128r has now been inspected for diagnosis and is not an untouched holdout
for this fix. Say and Zero remain separate no-tuning evaluation families;
report their outcomes separately. Neither unchanged outputs nor synthetic
variants establish universal unseen-tileset recognition.

## Ranked development work

1. **Preserve image-supported positions through normalization.** Highest current
   causal confidence: a strong correctly classified object is demonstrably moved
   and lost. Compare original and snapped evidence, study partial-contour aliases,
   and preserve existing snapping where it is supported. Measure missing/extra/
   shifted/direction errors separately. Do not simply disable normalization.
   The independently diagnosed native-component-size correction is now verified:
   it fixes the coordinate contract without the phase experiment's room-wide
   recovery interactions. Retain the phase experiment as follow-up.
2. **Trace and reduce competing block/full-spike/minispike hypotheses.** The
   corrected controls show many extras and shifts. Identify whether the evidence
   was wrong at classification or became wrong in later recovery/arbitration.
   Keep real object coexistence; an overlapping bounding box is not sufficient
   grounds for deletion. This rank reflects measured error burden; individual
   root causes still need traces.
3. **Separate unfamiliar-material proposal failures from profile routing.** Trace
   NANG variants and other evaluation families before attributing misses to color.
   Measure raw candidate coverage in reviewed regions. Favor shared cached shape,
   contrast and local material evidence; retain color semantics where needed.
   Do not add a second full grayscale scan without measured runtime/accuracy value.
4. **Revisit marker origins and false-positive distractors with bounded examples.**
   Saves, vines, platforms, floor text and spike-like decorations remain protected
   concerns. Use current source evidence rather than stale whole-room acceptance
   labels. Save/start and vine origin conventions need explicit coordinate tests.

Ranking is provisional and should change when new traces contradict it. Do not
spend repeated iterations changing thresholds after a hypothesis is falsified.

## Acceptance and workflow gates

- Complete the remaining representative traces before claiming the diagnostic
  requirement is fulfilled. Record the stage and evidence, including unknowns.
- Establish explicit reviewed-region truth for visual-only improvement claims;
  do not substitute warning counts or object totals for accuracy.
- Develop against the declared development cases; evaluate against the separate
  families and the relevant protected controls. Report no-effect outcomes too.
- Compare both exact truth and visual changed regions. Photometric transforms
  must preserve the semantics being evaluated; color-dependent objects cannot
  all be recolored without reconsidering their labels.
- Verify instrumented and ordinary scanner outputs agree before relying on traces.
- Run targeted tests during iteration, then FTFA and affected fixture controls
  before publishing. Broaden tests when the changed pipeline scope warrants it.
- Keep generated/private artifacts ignored, record progress and commit/push
  coherent changes. Maintain app health for user testing.
- Complete the milestone only after the new generalized improvement is implemented,
  measured and protected. Baseline infrastructure and a promising experiment alone
  do not satisfy the goal.

## Milestone verification (2026-09-09)

| Requirement | Verified evidence |
|---|---|
| Versioned reproducible baseline | 26 complete cases; input/code/runtime/settings hashes, immutable artifacts and checksums; interrupted baseline resumed; all 26 fixed-run cases checksum-verified and reused in a final resume check |
| Representative causal traces | Halls2 candidate accepted, snapped and pruned; NANG-128r mini component classified then shifted by the wrong native-size contract and retained; both instrumented final JMaps equal ordinary baselines |
| Ranked next work | Placement/phase, competing geometry hypotheses, unfamiliar-material proposal/profile routing, then marker origins and distractors; size-contract correction completed first based on stronger causal evidence |
| Implemented measured generalized improvement | Explicit native-size origin conversion; eighteen visually annotated NANG-128r minispikes corrected without any other tuple changing in that room; real-component tests protect size/scale/direction/brightness invariants |
| Separate-family evaluation | Say-1, Say-9, Zero_Final and all five development room outputs unchanged; NANG-128 unchanged; NANG-128r disclosed as diagnosed, not an untouched holdout |
| Protected exact controls | All sixteen exact reports unchanged, including all FTFA and block/spike fixture pairs; no reference objects used as scanner inputs |
| Tests and app | 103 targeted tests and 74 subtests passed; local app restarted with size fix, HTTP 200 |

Local detailed evidence is under `.artifacts/cross-tileset-20260908/`:
`baseline/report.json`, `traces/`, `component-origin-focus/reviewed-minispikes.json`,
`component-origin-fixed/report.json` and `component-origin-fixed/comparison.md`.
`71-screen-origin-checkpoint.md` records all 71 screens with explicit mixed-age
coverage; no old accepted label is treated as fresh full-room verification.

This closes the bounded evidence-and-improvement milestone after publication,
not the broader scanner project. The origin fix generalizes the placement
contract for classified mini components; it does not expand the adaptive
detector's existing white-triangle recognition domain. The phase guard remains
unpublished because its downstream changes need further review. New cold
examples, family-level recognition gains, and complete 71-room accuracy remain
future work. No universal detection or performance improvement is claimed.
