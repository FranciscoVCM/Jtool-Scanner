# Human reviews and independent reference maps

## Evidence, not scanner answers

Manual reviews and corrected JMaps are supervised engineering/evaluation
labels. Updating hand-written image-processing rules is not unsupervised
machine learning. Reference maps must never be scanner inputs, lookup-table
answers, or a reason to hard-code coordinates, filenames or room palettes.

Correct rooms are useful controls, not wasted annotations: exact comparison
reveals small errors hidden by a convincing preview and protects later changes.
Human “perfect”, unchanged output and fewer warnings are not exact proof.
Compare source, standalone detected JTool view, and independent expected view;
use a blend to investigate alignment, not as the only evidence.

## Offline comparisons and equivalent terrain

Evaluate a previously generated map without rescanning:

```powershell
python -m jtool_scanner.cli compare-maps detected.jmap corrected.jmap --report-json out\comparison.json --fail-on-error
```

The exact multiset comparator retains type, origin, direction and duplicates.
Player start is excluded by the existing policy; infinite jump is checked.
Other metadata should be reviewed separately, not assumed certified.

`solid_occupancy` additionally measures the union of 32px blocks and 16px
miniblocks inside the viewport. It distinguishes missing/extra solid pixels
from valid alternative overlapping-block decompositions. Duplicate blocks and
four minis covering a full block have equivalent occupancy but still produce
strict tuple errors. Hazards, spikes, platforms and water are excluded. Equal
terrain does not certify an entire room or relax `--fail-on-error`.

For a confirmed 800×600 capture, the supplementary visible-area test is:

```powershell
python -m jtool_scanner.cli compare-maps detected.jmap corrected.jmap --viewport 0,0,800,600
```

This option changes evaluation clipping only, not scanner normalization or
whole-map exact scoring. A full bottom block starting at y=576 legitimately
extends eight pixels beyond a 600px capture. Do not move its origin merely to
fit a full sprite into the screenshot. Default JTool geometry remains 800×608.
Resized or nonuniformly stretched screenshots require source/cell-boundary
evidence; their file dimensions alone do not establish native viewport height.

## 2026-10-01 intake and baseline

The ignored `local_corpus/user-reviewed-20261001/` directory preserves all
71 named-room human reviews, twelve user JMaps, and four source/scan images.
There are no missing named reviews. LapBackwards_1 belongs to the 71; ATK2 and
LapBackwards_2 are additional cases. Original files were not altered. Verified
hashes and explicit source mappings are recorded in local PROVENANCE.json and
reference-manifest.json. Raw notes and supplied images/maps remain local-only;
code pushes do not back them up. Preserve this directory in an external backup.

Eleven existing current-scanner outputs were checksum-verified and evaluated
against the newly supplied maps, without redundant scans. Strict counts exclude
the player start. LapBackwards_2 was freshly scanned using its source alone.

| Case | Exact / expected | Extras | Misses | Shifted | Wrong direction |
|---|---:|---:|---:|---:|---:|
| CN3_7 | 181 / 299 | 38 | 94 | 20 | 4 |
| LapBackwards_1 | 250 / 250 | 0 | 0 | 0 | 0 |
| LapBackwards_2 | 260 / 260 | 0 | 0 | 0 | 0 |
| Say_1 | 300 / 303 | 0 | 1 | 2 | 0 |
| Say_2 | 289 / 289 | 0 | 0 | 0 | 0 |
| Say_3 | 278 / 278 | 2 | 0 | 0 | 0 |
| Say_4 | 320 / 320 | 1 | 0 | 0 | 0 |
| Say_5 | 275 / 275 | 1 | 0 | 0 | 0 |
| Say_6 | 264 / 265 | 2 | 1 | 0 | 0 |
| Say_7 | 275 / 302 | 20 | 14 | 0 | 13 |
| Say_8 | 285 / 285 | 1 | 0 | 0 | 0 |
| Say_9 | 279 / 283 | 1 | 2 | 0 | 2 |

These are scores against provisional user references, not a claim that every
reference tuple is unambiguous in its source. CN3_7 solid-area IoU is 0.626140:
62,976 expected solid pixels are absent, with zero extra solid pixels. Its
terrain problem is therefore not merely alternative block packing. Say_7
solid occupancy is exactly equivalent, but 47 exact errors remain, almost all
spike hypotheses. Separate these causes rather than call both a color failure.

The ignored `.artifacts/user-review-20261001/71-screen-user-review.md` joins
all human notes with cached evidence. It replaces reliance on historical
acceptance labels, but is not a fresh independent whole-corpus visual audit.

## Efficient, generalizable development

### First shared detector repair: deferred source components

The first bounded implementation preserves source components rejected only
because the early full-spike hypothesis count is inflated. It retries the
same acceptance test after source/material pruning, using the cached field.
No thresholds, palettes, room IDs or coordinates were added. Early accepted
fields stay on their existing path; final exterior/paired-mini safeguards still
run. The retry does not scan image pixels again.

The ordinary Say_7 scan improves from 275/302 to 302/302 exact, with strict
errors falling from 47 to three: zero misses/shifts/wrong directions, three
extras. Two are source-visible down spikes absent from the provisional user
map, at (352,32)/(320,64); confirmation is pending and the map is unmodified.
One unwanted mini remains. The entire changed source/JTool/blend was reviewed;
this room is not declared perfect.

Thirteen source-only ordinary cases were regenerated: eleven canonical rooms
and ATK2/LapBackwards_2. Only Say_7 changes (27 added/30 removed tuples); all
metadata stays equal. All sixteen separately regenerated protected maps and
exact reports are unchanged, including FTFA's known 926/928 baseline. Tests:
329 geometry/arbitration tests with 90 subtests, and 50 integration/evaluation
tests with 34 subtests. The cached list-only retry costs about 22 microseconds
per call in a local 10,000-call probe; this is not an end-to-end latency claim.

Updated ignored audit:
`.artifacts/user-review-20261001/71-screen-after-intake-and-deferred-fix.md`.
It explicitly distinguishes the eleven freshly regenerated canonical rooms
from the sixty preceding-code snapshots. The latter are not current-code
certification. Most previously reported water, terrain, marker, hollow-spike
and unfamiliar-sprite failures remain. This ordering fix does not replace the
existing bright/low-chroma component predicate with universal color invariance.

Trace proposal, shape classification, coordinate normalization and arbitration
separately. Establish full contiguous source-backed structures with positives
and nearby negatives. Measure recovery and false detections, not object totals.
Declare development and no-tuning evaluation cases before changing rules.
These historically exposed families are not truly unseen holdouts.

Use deterministic synthetic fixtures now to isolate touching triangles,
partial occlusion, native object size, capture clipping and brightness/palette
invariance. Render with known geometry and existing sprites/textures, not
AI-generated shapes with uncertain coordinates. Validate gains on separate real
screens. Semantics-dependent objects cannot be arbitrarily recolored while
pretending labels stayed valid.

Retain original RGB evidence for water, killer blocks, vines and markers.
Palette-relative material masks and shared geometry/edge evidence are a better
experiment than duplicating the full pipeline on a grayscale screenshot.
Grayscale alone cannot remove patterned backgrounds or resolve every sprite;
isoluminant RGB boundaries can disappear. Require accuracy and runtime evidence
before any broad representation change. No universal arbitrary-tileset accuracy
claim is justified by the present corpus.

Floor text must not emit geometry, but true terrain behind a label must remain.
Partially embedded/offscreen spikes are legitimate; overlapping bounding boxes
alone must not cause deletion. Unsupported Dotkid miniwarps are not ordinary
misses. Unknown water should map to gray only when independent region/texture
evidence establishes actual water, not merely an unfamiliar color.

The highest-value next additional references are one difficult filled-spike
polarity room, one hollow/touching-triangle room, and one translucent-water
room, with a complete structure and explicit negative/distractor markings.
Prefer those to many more near-identical already-good maps. Full room JMaps
are welcome but small precise regions can be sufficient and cheaper to author.

### Second shared repair: phase-independent solid recovery

CN3_7's independent map exposes a 32px-lattice assumption: long columns and
ledges at half-cell offsets are omitted even when their dark material is visible.
The outlined-room path now samples complete 16px interior material quadrants,
packs supported 32px rectangles without a global 32px origin phase, and merges
missing strips without removing existing solids. The material threshold and
room eligibility are unchanged and room-relative; this is not universal palette
invariance. Existing rectangle packing prevents speculative residual corners.

Recovery runs after the complete spike/marker pipeline, including outer capture
consensus. The first integration changed other objects in CN3_8 and was rejected;
the successor preserves all non-block objects. Cached candidates are merged
without another pixel pass. No reference map, room ID or fixed answer origin is
read by the detector.

CN3_7 gains 61,440 solid pixels: missing area falls from 62,976 to 1,536, IoU
0.626140 to 0.990881, with zero extra solid area and no loss of prior terrain.
Strict matching improves 181/299 to 234/299. Alternate overlapping block origins
still count as strict tuple discrepancies; do not describe 99.1% terrain coverage
as 99.1% whole-room accuracy. Hollow-spike clusters, missing minis, floor-label
aliases and false vines remain. Keep full source/JTool/blend review and the
independent area comparison together.
