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

## Active follow-on: cross-family recognition/arbitration (2026-09-09)

The new goal requires measured recognition/classification/arbitration gains in
at least two visual families, not another isolated placement correction.
Baseline is the verified `9590334` implementation and its completed 26-case
`component-origin-fixed` run. Do not repeat that baseline unnecessarily.

Initial development pair: CN3-27 (red lattice terrain on a light background)
and CN3-Golden5 (gold patterned terrain on a dark background). Say, Zero and
NANG variants are reserved as untuned evaluation cases for this batch; exact
FTFA and all twelve block/spike controls remain protected. The partition is
prospective, not a claim these images have never been seen historically.

Fresh observational traces of both development rooms reproduce their current
baseline JMaps exactly. In CN3-27, support spikes pruned at (656,96) and
(664,96) are reintroduced by `_recover_raw_full_spike_support`. The exact-origin
block arbitration removes other aligned conflicts but leaves these offset
hypotheses. In Golden5, the hypothesis at (464,64) is pruned and restored by
`_recover_pruned_full_spikes`; the left-facing hypothesis at (432,64) is pruned
again, then reintroduced by `_reconcile_bright_filled_full_spikes`.
Primary hypotheses also survive in both rooms. Local source/blend review
shows terrain-overlapping false spikes; bounding-box overlap alone is not a
safe rejection rule. Existing exact-origin arbitration deliberately exempts
primary spikes because prior Irkara evidence includes true shifted spikes.

Next bounded experiment: investigate source-supported terrain/triangle
arbitration for offset conflicts and restored candidates. Establish explicit
regional truth and profile positive/negative shape and material evidence before
changing production decisions. Preserve genuine adjacent/overlapping geometry
and Irkara counterexamples. Do not disable whole recovery stages or blindly
extend exact-origin suppression to bounding-box overlap.

Evidence: `traces/CN3_27/conflict-summary.md` and
`traces/CN3_Golden5/conflict-summary.md`, with full events and instrumented JMaps
under the existing cross-tileset artifact directory. No detector changes have
yet been made for this follow-on goal, and no accuracy gain is claimed.

### Offset-conflict profiling checkpoint

Reusing the current immutable outputs, source-relative directed-contour and
contrast profiling took about three seconds across the 26 cases; this is
diagnostic runtime, not an end-to-end scan benchmark. A broad partial-overlap
rule (at least half the bounding box covered by blocks, weak directed contour
and weak local separation) would remove nine exactly correct reference spikes
in Flames, Hades and CN2-5. Reject that rule; preserve those counterexamples.

Requiring complete block-union coverage instead produces a research-only final
map counterfactual: twelve candidates removed in CN3-27, six in CN3-31, three
in Halls2 and eight in Irkara-89. Irkara-89 false positives fall 35 to 27 while
202 exact, 11 missed, 24 shifted and one wrong orientation remain unchanged.
All other exact-control reports are unchanged. Golden5 has no removals under
this rule; its partial-overlap issue is not solved by this experiment.

CN3-31 (monochrome brick) is added to development for this full-coverage branch;
source inspection shows candidate origins inside continuous terrain. Explicit
regional annotations, complete changed-region visual review, production
integration, targeted regression tests and controlled runtime checks are still
required. A block detection is not itself truth, and no whole-room approval
or deployed recognition gain is claimed. Keep Golden5's diagnosis as an open
partial-coverage follow-up rather than weakening protection to force a gain.

Local evidence: `offset-conflicts.json`, `offset-shadow/comparison.json` and
the profiling/evaluation scripts in `.artifacts/cross-tileset-20260908/`.

### Candidate implementation and visual exceptions

Localized source/triangle panels are preserved as `offset-shadow/*/review.svg`
and PNG renders. CN3-27's twelve proposed triangles are wrong hypotheses in
the inspected source. CN3-31 has four clear terrain-interior false positives,
but two candidates at (128,224) and (160,296) lie on sloping boundaries and are
ambiguous. Halls2's up candidate at (160,128) is near a genuine up triangle.
Do not count removing those three uncertain candidates as an improvement.

Independent side profiles show strong single slopes on both CN3-31 boundary
cases, and a supported nearby same-direction triangle for the Halls2 case.
The production candidate therefore requires complete block-union coverage,
weak minimum contour and local contrast, neither individual side strongly
supported, and no strong nearby same-direction triangle. It runs once after
the final capture merge/refit, so early recovery inputs remain unchanged.
No filenames, palettes or diagnostic coordinates are production inputs.

Sixteen focused tests and 26 subtests pass, including seven new tests for
union coverage/gaps, duplicate blocks, real triangles, single-side evidence,
nearby alternatives and cropped boundaries. The fresh 26-case run under
`terrain-arbitration-candidate/` and selected existing geometry regressions are
running; their results are not yet verified. Controlled end-to-end runtime
measurement and updated final visual audit are still required. Do not mark
this goal complete or publish an accuracy claim from the earlier shadow alone.

### Verified full-run result and next work

The fresh 26-case run is complete. Actual output changes agree exactly with
the reviewed negative annotations: twelve CN3-27, four CN3-31 and two Halls2
false hypotheses removed, with all three ambiguous hypotheses preserved.
Irkara-89 false positives improve 35 to 27 without changing exact matches,
misses, shifts or wrong orientations. Fifteen other exact reports and every
other primary map are unchanged. `verify_terrain_candidate.py` checks full
object multisets, the explicit annotations and the exact comparison reports.
The new mixed-age audit is `71-screen-terrain-checkpoint.md`; no full-room
acceptance is inferred from these regional gains.

The ABBA comparison completed all eight scans with exact agreement against
the appropriate saved output. Median baseline/candidate times were
185.459/193.726 seconds for CN3-27 (+4.46%) and 246.953/225.183 seconds for
CN3-31 (-8.82%). Individual scans varied substantially. The new stage itself
took 1.675-1.795 seconds and 0.745-0.759 seconds respectively, under 1% of
the corresponding baseline medians. This is bounded local overhead evidence,
not a speedup or a guarantee about every screen. The complete record is
`timings/b543a235ec284ffbb5f54fe3ac8ba6c9/results.json`.

Final validation passed 52 focused/app/correction/corpus tests (62 subtests),
six capture-lattice tests (six subtests), and the earlier fourteen selected
geometry regressions. The polarity/color/scale preservation test is included.
These 72 tests are targeted coverage, not a full repository suite claim.

Next ranked work after this bounded goal:

1. Golden5's partial-coverage aliases: distinguish a genuine exposed triangle
   from repeated tile texture and boundary fragments. Preserve the nine exact
   partial-overlap counterexamples and uncertain CN3-31 slopes. Do not simply
   relax the complete-coverage rule.
2. Recovery provenance: investigate why rejected candidates are restored
   without stronger independent evidence, and whether shared evidence can
   prevent the false restoration earlier without suppressing real recoveries.
3. Candidate misses in unfamiliar sprite/material families: choose new
   source-supported positives and retain genuinely cold examples for transfer
   evaluation. This precision improvement has not increased candidate recall.

The rule adds neither a screen identity nor a palette requirement, but its
limits remain important: it relies on full-block hypotheses, cannot resolve
all partial occlusions, does not reconstruct missing objects, and preserves
uncertainty where a nearby or single-sided triangle is plausible. It is not
a universal tileset recognizer or a complete solution for the 71 screens.

### Follow-on completion evidence

| Goal requirement | Verified result |
|---|---|
| Recurring failure across visual families | Red lattice and monochrome brick false triangle hypotheses over terrain; traced restored/retained offset conflicts, with Golden5 partial-overlap counterexamples kept open |
| Shared implementation | Source-relative contour/contrast arbitration after final merge; no filename, palette, coordinate or reference-map lookup |
| Reviewed gains in at least two families | 12 CN3-27 and 4 CN3-31 false hypotheses removed; two additional Halls2 removals; explicit annotations and current blends reviewed |
| Preserve uncertainty and exact controls | Three uncertain hypotheses kept; eight Irkara-89 extras removed without losing exact matches; fifteen other exact reports unchanged, including FTFA; corrected NANG-128r unchanged |
| Untuned evaluation | Say-1, Say-9, Zero_Final and both NANG primary variants unchanged; no tuning from those outcomes |
| Runtime and regressions | Eight paired timing scans reproduce saved maps; stage overhead measured; 72 targeted tests pass |
| Reproducibility and audit | Complete versioned reports, source/annotation comparisons, 71-row mixed-age audit and ranked next work preserved; publication verified separately in Git |

The bounded goal can close after the tested files are committed/pushed and
the live app/remote state are verified. Broader recognition recall, the open
partial-overlap cases and full 71-screen correctness remain project work.

## Active follow-on: observable partial-terrain slopes

Baseline is published `e527d59` and the complete `terrain-arbitration-candidate`
report. Development remains Golden5, CN3-27, CN3-31, Halls2 and neon-9;
sixteen exact-reference cases are controls. Say, primary NANG and Zero are
separate no-tuning evaluations for this experiment, not historically unseen
screens. NANG-128r is an established placement regression control.

The candidate masks predicted terrain while sampling the two proposed slopes.
It interprets absent edges only with at least four exposed samples per side,
weak whole-patch evidence and weak exposed luminance/color separation. Strong
individual slopes, nearby supported triangles, insufficient exposure and
isoluminant color boundaries are preserved. Complete-coverage arbitration is
unchanged. Neither full-block hypotheses nor aggregate brightness alone decide
whether an exposed triangle exists.

The causal disagreement is measurable in Golden5: the restored left hypothesis
at (432,64) passes the bright-fill gate with density contrast 0.539 and luma
contrast 45.612, while both exposed slopes have five samples, zero edge hits
and zero separation. At the genuine left triangle (480,64), exposed edge
coverage is 1.0 on both sides. The adjacent right hypothesis (464,64) remains
uncertain because the genuine neighboring triangle supplies exposed contrast;
do not weaken safeguards to force its removal.

Applying the production candidate to frozen maps proposes 41 source-reviewed
removals in Golden5, one each in CN3-27 and CN3-31, and one in the untuned
Zero_Final evaluation. Sixteen exact-control extras are also removed: Arcfoxp1
one, Irkara-89 one, Flames three and Hades eleven, without changing their exact,
missed, shifted or orientation totals. These are final-map counterfactuals,
not yet freshly verified production results or whole-room acceptance.

The nine exact partial-overlap counterexamples survive: some have one hidden
slope and insufficient observable evidence, others retain measurable exposed
contrast/edges. New synthetic tests cover four directions, three scales,
inverted polarity, color variation and isoluminant visible triangles. A cheap
necessary angular condition avoids most nearby-patch statistics while leaving
the full nearby safeguard intact; proposed removals remain unchanged. The
standalone added stage takes about 0.30s in Golden5 and 0.41s in Hades in this
probe, not an end-to-end timing claim.

Local research: `partial-terrain-research/` under the existing cross-tileset
artifact directory, including explicit `reviewed-regions.json`, paginated
source/hypothesis crops, recovery features and frozen-map comparisons.
The new full run is `exposed-terrain-candidate/`; do not invalidate its active
implementation identity with edits or commits. Fresh output verification,
current blends, end-to-end timing and conservative 71-row audit update remain
required before publication and goal completion.

### Fresh-run verification

All 26 actual scans match the predeclared deltas: sixty reviewed false
hypotheses removed, no additions or other tuple changes. Exact matches, misses,
shifts and wrong directions are preserved in all sixteen controls. Arcfoxp1
extras improve 18 to 17, Irkara-89 27 to 26, Flames 46 to 43, and Hades 31 to 20.
Twelve other exact reports are unchanged. FTFA retains 926/928 exact with zero
extras/shifts/wrong directions. NANG-128r is unchanged. Say and NANG evaluation
maps are unchanged; Zero_Final improves by one source-reviewed extra without
tuning on that outcome.

The complete actual-map verifier also preserves the nine documented true
partial-overlap spikes and the unresolved Golden5 nearby candidate. All 26
artifacts passed a final cache-integrity/resume check. Eighty-one targeted tests
passed; this is not a full-suite result. The four changed primary blends were
reviewed and retain major room errors. `71-screen-exposed-checkpoint.md` gives
all 71 rows with mixed-age scope; no historical accepted label is renewed.

Controlled end-to-end timing is active under
`partial-terrain-timings/a34e276d5f8c4c7298ac489e3b8a361c/`; publication waits for
that gate. The next project work should address surviving ambiguous conflicts
and missing-object recall/placement, not repeatedly loosen this negative-evidence
rule. This change rejects unsupported protrusions; it cannot invent an object
never proposed or recognize arbitrary non-triangular custom spike sprites.

### Completion evidence for partial-terrain milestone

| Requirement | Verified result |
|---|---|
| Shared recognition/arbitration gain | Current production removes 41 Golden5, one CN3-27 and one CN3-31 false hypotheses, plus sixteen extras in four exact controls; no screen identity or palette lookup |
| Independent recovery evidence | Golden5's restored false candidate passes whole-patch bright-fill scores but has no observable slope support; real triangles and the ambiguous neighboring case remain protected |
| Protected controls and evaluation | All sixteen controls preserve exact/miss/shift/orientation totals; nine named partial-overlap positives retained; FTFA and corrected NANG-128r preserved; untuned Zero_Final loses one reviewed extra, Say/NANG unchanged |
| Current review and audit | All sixty removals source-reviewed, actual tuple deltas match exactly, four changed primary blends inspected; complete mixed-age 71-row audit with no whole-room approval |
| Regression tests | 82 targeted tests and 149 subtests pass, including real fixture positives at two capture scales and isoluminant synthetic triangles; not a full suite claim |
| Runtime | Eight serial ABBA scans reproduce frozen maps; Golden5 medians 50.413/53.123s (+5.38%), CN3-31 112.469/113.815s (+1.20%); new-stage cost 0.326-0.355s and 0.115-0.124s, no speedup claimed |
| Reproducibility | Complete versioned 26-case run and checksum-verified cache reuse; explicit annotations, comparisons and timing records retained locally |

The code/test/documentation checkpoint is ready to commit and push, followed
by live remote/HEAD, clean-tree and app checks. Only after those checks may this
bounded goal close. The full scanner project and remaining room errors do not.

Publication verification subsequently succeeded for implementation commit
`8b7f5cfbec6cf8892b85091586c47155fa88600c`: local HEAD equaled live
`origin/main`, Git status was clean, and the app returned HTTP 200. The tested
package fingerprint is unchanged. This bounded milestone is verified; its
historical pending-validation entries above are superseded. Missing-object
recall/placement and surviving conflicts remain the next project work.

## Active milestone: independent positive recall (2026-09-10)

Resume from published `28c60cb` and the complete exposed-terrain baseline,
not from the earlier prototype maps. Development roles were declared before
tuning: Halls2, CN3-31 and Golden5; CN3-27/neon-9 and sixteen exact maps are
regression cases. NANG-128r is the established origin control. Say-1, Say-9,
primary NANG-128 and Zero_Final are no-tuning evaluations for this change,
not historically unseen images.

Current observational traces reproduce the baseline JMap multisets. Halls2
has correctly proposed triangles discarded by geometry deduplication or
shifted away by normalization. CN3-31 has real triangles lost to source-scale
deduplication/block arbitration and final source/canonical consensus, despite
surviving in the canonical pass. Thus the target is discarded positive evidence,
not merely moving an already emitted final object.

The candidate adds independent directed-material proposals only after final
consensus and the existing negative-evidence arbitration. It requires both
complete localized slopes, strong source-relative contrast, an unambiguous
orientation/origin, and at least three independent nearby material witnesses
with agreeing contrast polarity. New proposals cannot bootstrap more proposals.
Occupied neighborhoods are left to existing conflict/placement workflows.
No names, palette identities, coordinates or reference answers enter production.

Portable tests exposed blur-fringe position ambiguity on flat triangles.
The addition-only localization score uses gradient strength relative to local
luminance spread, while established refit/veto scores remain unchanged. A
water-overlaid CN3-27 hypothesis was also found to have uncertain placement;
it is excluded, not counted as an improvement. Completely visible contours
are required for new objects; partial/isoluminant/ambiguous evidence abstains.
This still cannot recognize arbitrary custom sprite shapes or start a room
with no reliable material witnesses. Existing color-specific detectors remain.

The frozen-map candidate proposes 34 source-reviewed additions: Halls2 six,
CN3-31 two, CN3-27 eighteen, neon-9 six, and Flames two. Both Flames additions
match its unchanged committed reference. Other exact reports and all four
no-tuning evaluation maps are unchanged in the counterfactual. These counts
are not yet freshly verified production results or whole-room accuracy.

A follow-up synthetic counterexample confirmed that shifted hypotheses of two
physical spikes could masquerade as four witnesses. Nearby support now requires
spatially independent objects, not merely different origin tuples. This prevents
that bootstrap and recovers two additional Halls2 objects by discarding redundant
nearby hypotheses before selecting material witnesses. All thirty-four proposed
positions were source-reviewed, including the initial lost rightward Halls2 spike.

Partial truth deliberately retains ten additional known misses: 44 reviewed
positive positions are absent from the baseline final maps, and the candidate
recovers 34 while abstaining on ten. This selected development set is not a
whole-room recall estimate. All fifteen reviewed Halls2/CN3-31 positives appear
in intermediate trace stages; only eight are recovered by this candidate.
Candidate coverage and final retention must not be conflated. Full primary-room
extra/shift/direction/size totals remain unknown without complete truth; exact
reference controls supply those separate error counts where available.

Evidence is under `.artifacts/cross-tileset-recall-20260910/`: declared roles,
observational traces, explicit positive/negative/uncertain regions, current
counterfactual maps and small source-review pages. The earlier stopped candidate
run is retained; `candidate/` is now regenerating the stricter implementation
with immutable keys. Do not edit package code or commit during this run.
Fresh deltas/blends, exact controls, affected regressions, serial end-to-end
timing, the conservative 71-row audit and publication remain completion gates.

### Positive-recall validation complete

The ordinary 26-case production run now reproduces all 34 annotated additions
exactly, with no removed, relocated, retyped or otherwise changed objects.
These actual results supersede the prototype/pending entries above. Current
source/JTool/blend review covers all five changed cases. Substantial room errors
remain; no historical accepted label is renewed.

| Evidence | Verified result |
|---|---|
| Real positive-recall gains | Halls2 +6, monochrome CN3-31 +2, red-textured CN3-27 +18, green-outline neon-9 +6, Flames +2 exact-reference spikes |
| Candidate versus final recall | All fifteen reviewed Halls2/CN3-31 positives occur in intermediate baseline traces, but none in the final baseline; eight are now retained. Across the selected 44 known missing positions, 34 are recovered and ten remain missing; this is not whole-room recall |
| Exact controls | Flames exact matches 250 to 252, misses 23 to 21; 43 extras, 20 shifts and two wrong orientations unchanged. Fifteen other reports unchanged. FTFA remains 926/928 exact with zero extras/shifts/wrong directions |
| Protected cases | Previous sixty reviewed false hypotheses remain absent; preceding terrain gains, nine named true occlusions, NANG-128r's eighteen corrected origins and all unchanged object tuples remain protected |
| Reserved evaluation | Say-1, Say-9, primary NANG-128 and Zero_Final unchanged, without tuning from their outcomes; these are historically exposed, not truly unseen data |
| Tests | 153 distinct targeted tests and 247 subtests pass on the final implementation, including capture consensus, floor text, saves, vines, platforms, overlap guards, app/correction and corpus support; not a full-suite run |
| Current audit | `71-screen-recall-checkpoint.md` contains all 71 rows with explicit fresh versus historical evidence and no whole-room approval |

Eight serial ABBA timing scans reproduced the appropriate saved maps. Median
end-to-end times were Halls2 43.667 to 45.523s (+4.25%) and CN3-31 108.424 to
109.249s (+0.76%). The new recovery stage itself took 0.867-0.888s. This is a
modest measured latency cost, not a speedup or universal latency bound; the
entire Halls2 end-to-end difference cannot be attributed to that stage alone.
No duplicate whole-room scanner pass was added. Timing followed completion of
the affected test run, with no competing scheduled test/corpus work.

Focused regression setup now scans only the fixture rooms actually requested
by selected assertions, sharing each result per test class as before. All eleven
fixture paths, scan options and assertions are retained. Two dedicated tests
protect lazy loading, cache reuse/reset and normal unknown-attribute behavior.
This is a test-workflow improvement, not a production scan-speed claim.

The immutable production run, explicit annotations, actual regional metrics,
five current blend reviews, test XML and serial timings are retained under
`.artifacts/cross-tileset-recall-20260910/`. Package fingerprint:
`b9dbd80714bae9b86d69931a14feb7710b1e5b0458f6a2ef67c42f1345f033aa`.
Publication, live remote equality and clean-tree checks are the remaining
handoff gates; their final result belongs in the local `CHECKPOINT.md` and Git.

### Recommended next bounded work

Trace the ten explicitly retained misses before weakening this recovery rule:
six Halls2, one CN3-31, two CN3-27 and one neon-9. Separate competing existing
hypotheses, partially hidden contours and mistaken source/canonical arbitration.
Try an evidence-aware retention or conflict-resolution change only when two
visual families show a common cause. The current addition-only rule deliberately
does not relocate nearby hypotheses or use incomplete/isoluminant luminance
evidence. Preserve those abstentions unless stronger independent evidence is
available, along with every new positive and all prior negative controls.

Sparse rooms without reliable witnesses, arbitrary non-triangular custom
sprites, dense small-object clusters, remaining type/direction/placement errors
and truly unfamiliar tilesets remain open. Additional examples should target
those gaps rather than duplicate solved palettes. The bounded positive-recall
milestone is not a claim of perfect 71-screen or universal recognition.

## Current priority: full-corpus revalidation (2026-09-11)

The user's new goal supersedes the suggestion to immediately tune the preceding
ten spike misses. First revalidate all 71 canonical screens, especially the 61
historical-only rows, and use their failures to rank shared detection causes.
The detailed local plan is `.artifacts/corpus-revalidation-20260910/GOAL_PLAN.md`.
Completion requires both full fresh review/final-current outputs and substantive
shared gains across at least two previously historical visual families; an audit
alone does not complete the goal.

All 71 frozen-baseline outputs now exist and passed integrity reuse. Eight rooms
are individually reviewed; do not conflate generation with review. The partial
audit already confirms major Entrance and engraved-metal CN3 failures, including
mini/full geometry confusion, missing short vines, missed gravity arrows, Roman
floor-text impostors and missed real portals. These findings are hypotheses and
regional evidence, not a selected implementation batch or full-room counts.
Review the remaining families before committing to the next detector change.
