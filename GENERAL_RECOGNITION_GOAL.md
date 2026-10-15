# General recognition: measured implementation and release plan

Updated 2026-10-15. This refines the unfinished active goal; it does not declare
the preceding work complete, reset its evidence, or weaken its numerical gates.
Continue in the existing `main` checkout. No new repository, clone, branch or
worktree. Preserve all source images, fixtures, JMaps and local corrections.

## Outcome

Improve source-object identity across unfamiliar textures, backgrounds,
palettes, brightness, sprite variation and capture scales. Use the 71 reviewed
screens to expose failures and measure transfer, not as an answer dictionary.
The practical milestone is a tested, deployed generalized repair with measured
positive recovery and false-conflict reduction. Neither a successful milestone
nor green unit tests establishes perfect recognition of arbitrary future games.

The central distinction is **appearance versus identity versus placement**:

- Similar color or repeated texture does not prove solid terrain.
- A triangular-looking gap between touching spikes is not automatically a spike.
- A source-supported shape at two nearby origins is not necessarily two objects.
- A 32px spike partly hidden by a wall is not necessarily a 16px minispike.
- Cropped, padded or unknown pixels are not evidence of absence.

## Starting evidence and honest status

Keep the completed B235 71-screen plus 16-control outputs as the immutable
recognition baseline. Its runtime fingerprint is
`17b98ead1d86fba9ac4f5f7e985e05a85bd71e685dd089277dc6959e63554cea`.
The latest published checkpoint before this plan is
`07d7df268fb7fcf2f0ab77269063d678ade86ea1`.

The existing filled-source research has 14 independently reviewed real full-spike
recoveries: Golden2 +3, CN3-19 +8 and CN3-21 +3. CN3-93 is unchanged. Those
research gains are not enabled in the app. Golden2's frozen 37-object structure
improves from 33 to 36 exact, with actionable errors 10 to 7. Remaining room
errors persist; no whole-room acceptance follows from this regional result.

The outlined helper's first 18-control qualification failed with 99 new
reference extras. The stricter two-slope ownership version passes that helper
qualification with zero new reference extras, but helper checks are not actual
whole-scanner controls, deployment or latency qualification.

The first Halls7 reserved evaluation **failed**. Reviewed source annotation
corrections leave its 61-object denominator and 39-error baseline unchanged;
exact matches improve 50 to 60, but errors improve only 39 to 35 (10.26%), with
six false 8px pose copies. Preserve the original labels/results and explicit
correction. Halls7 is now exposed regression evidence, never an untouched reserve
again. Do not optimize its coordinates and relabel the result a reserved success.

An exact bilinear sampler optimization is a separate checkpoint. Its affected
74-test suite, all 16 actual controls and eight serial whole-scan timing outputs
pass exact equality. Two dense and two sparse samples per mode show median
changes of -3.7% and -4.9% against the old scalar oracle in the same session.
These limited measurements are not a universal speed claim or detector gain.
Named protection qualification, review, publication and loaded-app parity must
be recorded before describing its deployment as complete.

Phase 1 qualification is now complete: 29 named source/control cases preserve
all previous groups and footprints by whole-output equality. The conservative
71-row audit has 24 current strict QA carries and 47 current-runtime pending,
with zero whole-room approvals. Publication and app verification are a separate
receipt; the recognition milestone remains unfinished.

The sampler checkpoint is now published as3e550bf. App HTTP and loaded/disk
parity remain unverified because environment permissions prevented process
control and loopback observations; do not bypass or infer the app is down.

Current late-growth research separates new-object confidence from legacy
material/pose calibration. Canonical CN3-18 actual candidate maps remove37
full32 and42 mini16 false footprints, with all79 source deltas/whole view
reviewed,4864/4864 and5376/5376 positive masks intact, frozen excess18176->0.
Hades and four mini/footprint/compact controls retain complete output equality;
39 focused prototype tests pass. This is not app activation or room acceptance.
Broad16 controls preserve complete equality, but the named cohort stops at
Halls2 with ten real marble footprints removed/8192 positive pixels lost. V3 is
REJECTED, not awaiting blind adoption. Diagnose source witness availability and
16-versus32 structure without palette/room exceptions. All41 qualification,
safe maintained per-source context integration and controlled cost remain.
The process-local instrumentation is NOT
thread-safe production integration. See the newest DEVELOPMENT_PROGRESS section
and ignored gate tracker; no reduced positive-recovery/reserved requirements.

The standalone source_growth_confidence module is a maintained research
component, not a runtime-bound feature.58 affected tests and exact numerical
port comparisons qualify its pure functions, not app deployment or cache/thread
integration. Parity with a rejected prototype is not recognition qualification.
Preserve that distinction when continuing the implementation.

## Phase 1 — close the intact implementation checkpoint

1. Verify local/live Git state and inspect the two saved sampler edits; do not
   discard or recreate them. Identify live producers before launching work.
2. Verify remaining named protections through actual targeted outputs and strict
   compatible reuse of completed current controls. Compare complete JMaps,
   ordered detection metadata, warnings, source bytes, crop/grid and options.
   All 41 fixed groups, 601 miniblocks and 139 terrain footprints must retain
   their previous achieved evidence. Identical outputs carry existing QA; they
   do not create new visual approvals.
3. Review the code and tests, update progress and the conservative audit, stage
   only explicit public paths, commit and push the qualified checkpoint.
4. Restart the local app on that tested code; require root and health HTTP 200
   and loaded-source/disk fingerprint equality. Never imply research helpers
   are active merely because they exist on disk.

Accuracy-only scans may run in two independent processes where safe. Their
durations are not latency comparisons. No runtime edits or HEAD changes while
a frozen producer is running. Reuse completed scans; no repeated baseline or
full historical-image sweep.

## Phase 2 — source-supported instance identity

Work first on the independently visible shared failure: newly proposed poses
currently compete with original objects but not adequately with each other.
Develop a source-backed distinction between a new instance, an alternate pose
of one instance, and an unresolved hypothesis.

For every miss, separate capture/scale error, absent candidate, missing usable
source witnesses, failed shape/size/direction evidence and final arbitration.
An unfamiliar tileset can fail before arbitration; an alias fix alone does not
solve that. Record candidate coverage and witness availability alongside output
accuracy. Where there are no reliable original witnesses, investigate bounded
source-contour bootstrapping, never teacher recycling from emitted hypotheses.

Use Golden2 and Halls3 development structures plus portable rendered adversaries.
Freeze thresholds and test definitions before scoring transfer. Require tests
for two genuine nearby apices, a single spike with an 8px alias, textured
internal triangles, touching opposite directions with 16px displacement,
partly occluded 32px spikes, capture-edge unknowns and genuinely different
backgrounds. Test palette, polarity, brightness and fractional scale changes.
Add paired appearance stress tests that hold geometry fixed while varying
foreground texture, background texture/gradient and contrast independently.
Measure exact typed origins and occupied terrain, not visual resemblance.
Keep color-dependent semantics intact when transforming water/killblock/flipper
examples. A geometry-only representation cannot resolve every semantically
ambiguous sprite; abstention or a review flag is preferable to confident invention.

Use immutable original-source witnesses. Competing new proposals cannot become
teachers. No lowest-coordinate winner, blanket deduplication, global overlap
deletion or universal whole-box appearance threshold: genuine compounds can
have different exterior pixels. Stub tests of arbitration are insufficient;
qualify it with real RGB source proofs and actual scanner outputs.

The first new RGB-source qualification already rejects the draft arbiter:
12 isolated alias cases pass across three palettes and four directions, but
two genuinely visible neighboring apices are both removed by its whole-box
appearance requirement. Preserve that failure. The next hypothesis must explain
visible, source-owned instance boundaries under mutual occlusion without making
whole-box similarity a prerequisite or accepting every apex-shaped texture.
Do not publish the failed arbiter as a generalization improvement.

Profile the finite hypothesis set and shared source features before binding the
consumer. The current outlined helper takes minutes and is not deployment-ready.
Retain the existing filled recoveries while addressing this cause; do not ship
a slower broad search simply to raise helper recall.

## Phase 3 — competing solid and spike explanations

Trace source-origin errors separately in canonical CN3-18, Halls3 and Golden2.
Canonical CN3-18 is not the separate tracked near-exact CN3-18 control.

- CN3-18: mountain/background falsely expanded by material-size packing.
- Halls3: false sky solids from repeated-terrain evidence.
- Golden2: real filled compounds confused with solid/opposing-direction objects.

Freeze complete positive/negative structures before testing each distinct cause.
Compare source-supported material, directed boundaries, size and competing
rectangle/triangle explanations. Source-local similarity is supporting evidence,
not permission to classify all repeated pixels as terrain. The previously tried
shadow guard loses two correct Hades phase repairs and remains rejected.

Favor shared, bounded features with retained original RGB. Explore normalized
edge/luminance channels only when a causal test supports them; do not duplicate
a full grayscale scan or throw away useful color evidence for water, killblocks,
vines and flippers. Synthetic scenes are controlled software tests with known
geometry, not proof of real unseen-tileset transfer and not model training.

## Phase 4 — frozen transfer and protected evaluation

For the next compatible mechanism, freeze a new experiment using the already
predeclared Golden5/NANG138r reserve pool. Declare eligibility and order before
scoring, retain every failure, and do not select a favorable room afterward.
These rooms have historical exposure; call them reserved for this experiment,
not unseen. Keep Halls7 as an exposed adverse regression. Protect NANG130r's
compact 19x13 frame and CN3-19/21/93 numeral negatives.

Use human JMaps only after source-only scanning for evaluation. Keep genuine
source/reference disagreements explicit. Evaluate solid occupancy separately
where overlapping editor blocks provide several equally valid arrangements.
Current Lap Around references may support targeted controls once their source
association is verified; no need to reopen all images or rescan all Lap rooms
for an unrelated change.

Preserve the complete earlier protection definitions, including:

- 601 source miniblocks and 139 Dotkid5 terrain footprints;
- Entrance1's 36/36 rail and Entrance2's 5120 positive terrain pixels;
- Halls4's 25/25 structure and 62/63 visible blocks;
- CN3-7's 168448/168448 solid mask and Golden7's 39 restorations;
- hollow recoveries, phase repairs, real occlusions and all nongeometry objects;
- confirmed NR2 effects versus real minispikes and true half-visible spikes;
- FTFA at least 926/928 exact with zero extras, shifts or wrong directions;
- Flames at least 252 exact, without increases over 42 extras, 21 misses,
  20 shifts and 2 wrong directions; other exact-control gains intact.

Do not delete objects just because they overlap: valid embedded spikes, narrow
terrain strips and mini rails exist. Review vine direction/16px side offsets,
save/start origins, platform false positives/misses and numeral impostors as
explicit regression categories, not unrelated rewrites in this batch.

## Measurement and integration contract

The original milestone minima remain mandatory in actual final scanner outputs:
at least three improved canonical rooms across two visual families, including
one successful reserved evaluation; at least eight independent real geometry
recoveries/corrections across two rooms; at least four corrections/removals of
baseline false conflicts; at least 25% fewer actionable errors and two fixes
per successful frozen structure; no positive loss or new fixed negatives.

Count misses, extras, exact typed origins, wrong size/direction and phase shifts
separately. Measure terrain-positive and excess occupancy without awarding
duplicate tilings. Keep denominators fixed. No warning-count proxy, coordinate
answer lookup, palette/room/hash branch, emitted teacher, or benchmark-driven
source-wrong correction.

For each bounded batch: inspect and freeze -> reproduce ordinary output ->
test a causal hypothesis -> focused tests and actual development scans ->
reserved/protected evaluation -> whole changed-map and every-delta source QA ->
runtime qualification -> reviewed commit/push/deploy -> audit update.

Integrate only qualified behavior. Reuse the scanner's cached RGB/coverage and
finite original-source hypotheses. Run quiet AC serial same-session whole dense
and sparse before/after scans with at least two samples per mode/source. Keep
helper and whole timing separate. Investigate persistent cost above 5%; explain
any necessary accuracy/speed tradeoff before adoption. Run relevant tests during
development and the broader affected suite at an integration checkpoint. Do not
alter code merely to hide a permissions, dependency or environment error.

## Durable work and conservative audit

Each batch has a question, fixed source structures, hypothesis budget, result
receipts and a checkpoint. After a few distinct unsuccessful hypotheses,
summarize the causal finding and change direction; do not spend hours repeating
the same failed cache or silently thinking without measurable activity.
Record process identity, current case, completed receipts and resume commands.
Poll live handles; an observation timeout is not a terminal failure. Save a
durable checkpoint promptly before poweroff/reconnect interruptions. Avoid
overlapping workers and never restart an unverified still-running producer.

Maintain a successor audit with one row for every screen: pinned baseline,
current output identity, fresh versus strict-equality-carried versus pending
review, quantified changes where labels exist, known errors, uncertainty and
next action. Passing a regional/control test is not whole-room acceptance.
Historical QA carries only with full source/options/transform/map/metadata
equality. Re-review changed rooms as a whole and every changed object.

Commit and push meaningful reviewed public code, tests, workflows and progress
notes on `main`; stage explicit paths and inspect the staged list. Private
reviews, generated outputs, local images/projects, image indexes and transcript
remain ignored. Do not stage `.codex-notes`, `.artifacts` or `local_corpus`.
Confirm live HEAD equals origin/main, clean Git, private exclusion and working
app parity at publication checkpoints. Do not promise immunity from network or
power interruptions; make recovery verifiable.

## Completion gates and evidence requests

Close the goal only when all six original gates are met: shipped generalized
repair and required gains; multi-family reserved transfer; all protections and
independent QA; controlled acceptable runtime; final stable current 71+16 audit;
reviewed pushed clean state and tested app parity. Compatible checksummed reuse
is allowed; unqualified old-code scans cannot be relabelled current.

This milestone is not complete because time/usage runs out, controls pass,
a helper improves or an audit is written. Unresolved errors stay visible and
ranked. No universal or all-71-perfect claim without corresponding evidence.
Request additional examples only for a specific missing distinction, with an
annotated crop and precise question; existing confirmed answers must not be
asked again. User reviews and harder corrected maps are valuable evaluation
evidence, not a production coordinate lookup or an automatic fitting algorithm.
