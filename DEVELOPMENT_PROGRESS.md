# Development progress

This file records measured implementation checkpoints for the generalized
scanner review. It is deliberately limited to repository and fixture facts;
private conversation archives and ignored image material remain outside Git.

## Checkpoint: 2026-08-10

### Repository and runtime baseline at review start

- Local branch: `main`.
- Review started at `8ac66a0` (`feat: generalize scanner across held-out
  tilesets`), with the cached `origin/main` ref at `acc6883`.
- The first two review checkpoints were subsequently committed and pushed;
  the current branch tip is recorded in the Git history rather than repeated
  in this historical baseline section.
- Working tree was clean before this checkpoint.
- The documented app command is `python -m jtool_scanner.cli app`; the local
  app is healthy at `http://127.0.0.1:8765/api/health` (HTTP 200).
- The full suite passed before this checkpoint: 302 tests, `OK`.
- After the change and its regression test were added, the full suite passed:
  303 tests in 536.421 seconds, `OK`.

### Golden-room benchmark

The FTFA benchmark was rerun with the repository's exact workflow and
`grid_step=8`, geometry and color scanning enabled.

| run | exact | false positives | missed | shifted | wrong direction |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline before this checkpoint | 924/928 | 0 | 2 | 2 | 0 |
| after save-anchor correction | 926/928 | 0 | 2 | 0 | 0 |

The remaining misses are the weak lower-right and left-edge boundary slivers
in FTFA screen 1. `tests/test_unseen_regressions.py` explicitly protects the
decision not to promote the weak lower-right sliver to a block. FTFA therefore
continues to meet the current strict benchmark threshold without false
positives.

### Generalized change in this batch

Warm/outlined terrain marker reconciliation now prefers a candidate with a
full support cell at the candidate origin over an equally supported candidate
that only obtains its support by straddling adjacent cells. This removes the
8-pixel phase drift seen in scaled FTFA screen captures while retaining the
existing terrain-overlap and side-support safeguards. A synthetic regression
test covers the adjacent-cell tie topology.

### Representative fixture baseline

The Irkara color-object workflow remains stable after the change:

- saves: 23/23 matched, 30 detected;
- warps: 8/11 matched, 8 detected;
- water: 506/520 matched, 506 detected;
- walljumps: 7/7 matched, 20 detected;
- apples and gravity objects: no truth cases in this manifest.

The 71-screen giant-review manifest and its local review ledger remain
available for staged visual review. Their current ledger labels are review
bookkeeping, not authoritative corrected JMaps; Lap Around still lacks
corrected JMaps and is not an exact benchmark. A previous full geometry scan
of the large block/spike manifest exceeded the operational command timeout,
so it is not treated as a completed measurement.

## Next review focus

The next batch should use a small, explicitly measured group from the
unrecognized/reverse tileset families (CN3-16/CN3-18 and NANG-128/NANG-128r)
and compare source, current JTool reconstruction, and blend output. Candidate
rules must be palette-relative and shape/terrain-supported rather than keyed to
screen names or absolute colors. Existing FTFA exact results, the Lap/CN3/NANG
fixture scans, and the object-specific regression tests remain gates for every
subsequent change.

No claim is made here that all 71 screens are complete. Each later checkpoint
must include the changed rule, the measured before/after result, affected
fixtures, and any remaining visual uncertainty.

## Checkpoint: compact vertical-spike support (2026-08-10)

The compact-room detector previously accepted bright neutral seams as vertical
mini-spikes when they had no playable support-cell phase. The shared compact
rule now requires an up/down mini-spike to align with the corresponding native
full-tile support edge. Occluded horizontal mini-spike recovery remains a
separate path because its support geometry is different.

Measured fixture results:

| fixture | before mini result | after mini result | other result |
| --- | --- | --- | --- |
| `nang128` | 61 detected, 17 matched, 18 truth | 17 detected, 17 matched, 18 truth | 68/68 blocks, 38/38 full spikes unchanged |
| `nang138` | 55 detected, 54 matched, 58 truth | 55 detected, 54 matched, 58 truth | 105/105 blocks, 26/26 full spikes unchanged |
| `nang135` | no mini truth; 76/77 blocks | unchanged | 86/86 killer blocks unchanged |
| giant `NANG_128r` source | 127 total detections | 127 total detections | adaptive reverse-palette path unchanged |

The FTFA exact benchmark remains 926/928 exact, with zero false positives,
zero shifted objects, and the same two protected boundary misses. The focused
compact support regression passes. The full suite also passes after this
batch: 304 tests in 600.394 seconds, `OK`.

## Checkpoint: miniblock primary full-spike noise (2026-08-10)

Dense 16px-cell rooms were still receiving low-confidence horizontal and
boundary full-spike candidates from late recovery stages. A final, relative
shape gate now runs only when both conditions hold: the full-spike profile is
mini-dense and the detected terrain independently has miniblock-dominant cell
topology. It measures directional triangle-side coverage, so the rule does
not depend on CN3 colors or screen names and does not route mini-spike-heavy
Irkara rooms or compact NANG rooms through the gate.

With the gate disabled versus enabled, the focused geometry measurements were:

| fixture | full spikes before | full spikes after | matched truth before | matched truth after |
| --- | ---: | ---: | ---: | ---: |
| `cn3-16` | 69 | 35 | 26 | 26 |
| `cn3-18` | 82 | 47 | 42 | 42 |

The gate removes false candidates while retaining the same matched CN3 truth
objects. `irkara-nr-partysu3` remains unchanged at 118 detected / 90 matched
full spikes, and `nang128` and `nang138` remain at 38/38 and 26/26 full-spike
matches respectively. Their object-specific block, mini, save, warp,
water, walljump, killer-block and refresher results remain unchanged.

The exact FTFA benchmark remains `926/928 exact; 0 false positives; 2 missed;
0 shifted; 0 wrong direction`. The new directional gate regression and the
existing CN3 and compact-room geometry regressions pass. The complete suite
passes at 305 tests in 561.600 seconds (`OK`). This checkpoint is ready to be
committed and pushed as a single coherent batch.

## Checkpoint: sparse residual terrain texture arbitration (2026-08-10)

The red textured CN3-26 and CN3-27 rooms exposed a different failure mode:
the supported-material learner underfit a 32px lattice into a small set of
residual 16px cells, after which late mini-spike recovery promoted the same
texture diagonals to hundreds of hazards. The generalized guard compares the
raw 32px lattice to the learned profile and declines the profile only when its
residual 16px material is both sparse/disconnected and substantially smaller
than the raw lattice. Connected mixed-material mini-block corridors remain on
the existing expansion path.

Measured giant-review outputs after the guard:

| screen | block detections | mini-block detections | mini-spike detections |
| --- | ---: | ---: | ---: |
| `CN3_26` | 139 | 0 | 5 |
| `CN3_27` | 156 | 0 | 5 |

Before the guard, the same scans produced 35/26 blocks and 113 mini-spikes
for CN3-26, and 42/46 blocks and 655 mini-spikes for CN3-27. Saves, apples,
water, vines, warps and full-spike candidates remain present in the guarded
outputs. The focused synthetic sparse-texture regression and the existing CN3
miniblock, compact-support and directional-gate regressions pass. FTFA exact
remains `926/928`, and the complete suite passes at 306 tests in 582.168
seconds (`OK`).

The next review group should compare this arbitration against CN3-25, the
adjacent CN3-28/29 family, and one connected residual-material room before
considering any threshold change. No screen name, filename, or absolute
palette is used by the rule.

## Checkpoint: compact downsampled active-save recovery (2026-08-10)

NANG-128 remained the one tracked compact-room save miss. Its active save is
partly covered by the player, and the 19x13 source capture is downsampled
before it is padded into the standard viewport. The generic layout recovery
therefore measured 19 green / 10 yellow samples, just below its 18/12 yellow
budgets, even though the same layout and title-band evidence were present.

The recovery now uses a compact-room-only yellow budget of 9 total and 9 in
the body. The room profile is already identified from the 19x13 aspect ratio;
full-size and unknown rooms retain the original thresholds. This is a
relative scale adjustment, not a NANG-specific color or coordinate rule.

Measured results:

| check | result |
| --- | --- |
| `nang128` save | 1/1 matched at `(160, 416)` (previously 0/1) |
| `nang138` save | 1/1 unchanged |
| all other tracked game fixtures | no new save detections |
| focused save regressions | pass |
| FTFA exact benchmark | `926/928 exact; 0 false positives; 2 missed; 0 shifted; 0 wrong direction` |

The complete suite passes at 307 tests in 584.690 seconds (`OK`). The next
review group remains the connected CN3-28/29/30 residual-material family and
the compact CN2-5 geometry, not another save-threshold expansion.

## Checkpoint: neutral-room material clustering (2026-08-10)

The compact CN2-5 jump-refresher room has a noisy neutral background whose
pixels satisfy the broad neutral terrain predicate. The previous fallback
therefore emitted 428 blocks and 65 full spikes, although the tracked JMap
contains 323 blocks and 32 full spikes. A room-local two-cluster pass now
learns patch color profiles from the neutral cells and keeps the cluster with
the stronger combined edge/saturation evidence only when the cluster centers
are separated and the score margin is meaningful. Ambiguous rooms retain the
old candidates rather than guessing a material.

Measured fixture results:

| fixture | before | after |
| --- | --- | --- |
| CN2-5 blocks | 428 detected, 318 matched | 391 detected, 318 matched |
| CN2-5 full spikes | 65 detected, 28 matched | 81 detected, 31 matched |
| CN2-5 mini spikes | 10 detected, 2 matched | 10 detected, 2 matched |
| CN2-5 jump refreshers | 6 detected, 6 matched | 6 detected, 6 matched |

The gate is relative to each room's learned color/texture clusters; it does
not encode CN2 colors, coordinates, or a fixed tileset. The focused synthetic
material-cluster regression passes, FTFA exact remains `926/928` with the same
two protected boundary misses, and the complete suite passes at 308 tests in
584.785 seconds (`OK`).

## Checkpoint: compact palette-shifted save headers (2026-08-10)

NANG-135 still missed its visible active save after the compact yellow budget
change. Its green/yellow body survives downsampling, but the pale `SAVE`
header is tinted enough that the generic bright-neutral header predicate sees
zero bright samples. On the already recognized 19x13 path, the layout recovery
now uses the broader pale-header predicate while retaining the same dark-band,
body-color, ratio, rarity, and clustering gates. Full-size and unknown rooms
retain the strict header predicate.

Measured compact results:

| fixture | save result |
| --- | --- |
| `nang128` | 1/1 at `(160, 416)` |
| `nang135` | 1/1 at `(160, 448)` (previously 0/1) |
| `nang138` | 1/1 unchanged |
| all other tracked game fixtures | no new save detections |

Focused save tests pass, FTFA exact remains `926/928` with the same two
protected boundary misses, and the complete suite passes at 309 tests in
591.788 seconds (`OK`).

## Checkpoint: dense spike-pocket cloud-warp veto (2026-08-10)

The Say-9 review source contains a white cloud-shaped foreground sprite at
`(384, 224)` that is not a warp. Its silhouette is intentionally the same
shape as the filled cloud portal family, so color and normalized topology
alone cannot separate the two. The impostor is embedded in a dense five-sided
spike pocket. Every accepted filled-cloud warp in the reviewed CN3/Halls/
Redcube corpus has four or fewer strong neighboring 32px spike cells.

The filled-cloud detector now performs a palette-independent local check of
the surrounding 3x3 full-tile neighborhood and vetoes only candidates with
more than four independently accepted strong spike triangles. The rule is
relative to the existing triangle/block arbitration: it does not use Say-9's
coordinates, filename, tileset colors, or a screen-specific exception.

The new threshold regression covers both the five-neighbor veto and the
four-neighbor keep path. Say-9's false warp is removed while the reviewed
filled-cloud warp controls remain present; FTFA exactness and all existing
object-specific guards remain required gates for this batch.

## Checkpoint: neutral-shadow white-player ambiguity (2026-08-10)

The CN3-19 and CN3-21 source screens contain a white player skin whose cloud
silhouette is visually indistinguishable from the filled-cloud warp sprite.
The previous shape-only detector emitted false warps at `(672, 288)` and
`(328, 408)`. Their distinguishing evidence is not a screen name or absolute
coordinate: the lowest-luminance fifth of each bright component is a bright,
nearly neutral-gray shadow, unlike the darker or chromatically contrasted
shadow of the accepted filled-cloud portal controls.

The bright-cloud detector now treats that neutral-bright shadow as an
ambiguous foreground sprite and declines to emit a warp. Darker and
chromatic shadows still use the existing topology and enclosure rules. The
synthetic regression covers neutral, chromatic, and dark shadow paths; the
CN3-16/CN3-18 true cloud controls and FTFA benchmark remain required gates.

Measured after the change:

- CN3-19: the false filled-cloud warp at `(672, 288)` is absent from the
  regenerated JMap.
- CN3-21: the false filled-cloud warp at `(328, 408)` is absent from the
  regenerated JMap.
- CN3-16 and CN3-18: their true filled-cloud warp detections remain present.
- F189 remains `154/154` blocks, `85/85` full spikes, and `8/8` gravity
  flippers matched; no new color-object detections appeared.
- FTFA remains `926/928 exact; 0 false positives; 2 missed; 0 shifted; 0
  wrong direction`.

## Checkpoint: bright outlined-terrain ambiguity gate (2026-08-10)

CN3-25, CN3-26, and CN3-27 are a bright red outlined tileset family whose
32px cells contain repeated diagonal/triangular decoration. The previous
generic geometry pass could interpret those interior motifs as playable
16px mini-spikes or mini-blocks, even though the source screens contain no
such objects. CN3-26 previously produced 10 mini-spikes and CN3-27 produced
122 mini-spikes plus 58 mini-blocks; CN3-25 had already reached zero mini
objects but remained part of the same ambiguity family.

The scanner now learns a room-local bright outlined-terrain profile from
brightness contrast and lattice sparsity. In that profile, ambiguous
16px terrain silhouettes are declined while ordinary full-size blocks and
spikes and all supported colour objects remain available. The rule is
palette-relative and morphology-based; it does not use a CN3 filename,
screen coordinate, fixed colour, or one-off object list. Dense mini-spike
controls such as Partysu3 and Irkara-51/59 do not enter the gate.

Measured grid-8 project results after the change:

| screen | objects | mini-blocks | mini-spikes |
| --- | ---: | ---: | ---: |
| `CN3_25` | 279 | 0 | 0 |
| `CN3_26` | 292 | 0 | 0 |
| `CN3_27` | 352 | 0 | 0 |

Source/JTool/blend review confirms that saves, apples, water, vines, full
blocks, and full spikes remain represented. The bright-room focused tests
pass. Protected fixture scans retain the established CN3-16/CN3-18,
F189, NANG, CN2-5, Partysu3, Irkara-51, and Irkara-59 behavior, and the
FTFA golden-room benchmark remains `926/928 exact; 0 false positives; 2
missed; 0 shifted; 0 wrong direction`. Full geometry/material placement in
these three giant-review screens is still not a corrected-JMap result and
requires later review.

## Checkpoint: bright chromatic platform arbitration (2026-08-10)

CN3-28, CN3-29, and CN3-30 use a bright teal room with several red, beige,
and blue solid materials. The permissive neutral-platform edge detector was
mistaking spike edges, terrain lips, and the floor-number glyphs for JTool
platforms: the prior project outputs contained 6, 10, and 5 platform objects
respectively. The source review shows these screens' relevant geometry is
blocks/miniblocks and spikes; the cherries are ordinary apple detections and
the visible floor numbers are not objects.

Platform arbitration now uses a room-relative bright-room gate. It
requires a compact horizontal-bar edge pattern (multiple strong rows or a
clipped top-and-bottom enclosure) before retaining a platform candidate in
that room class. Dark rooms and bright neutral platform controls retain the
existing detector. The rule is based on room luminance/chroma and patch
morphology, not CN3 names, fixed colors, coordinates, or a platform list.

Measured grid-8 project results after the change:

| screen | objects | platforms | apples |
| --- | ---: | ---: | ---: |
| `CN3_28` | 345 | 0 | 3 |
| `CN3_29` | 345 | 0 | 5 |
| `CN3_30` | 427 | 0 | 5 |

The multicolour block/miniblock and spike detections remain available in the
source/JTool/blend review. The morphology regression passes; known platform
fixtures (`irkara-89`, `k3-ex-hades`, and `irkara-71`) retain their prior
platform matches. FTFA remains `926/928 exact; 0 false positives; 2 missed;
0 shifted; 0 wrong direction`. These three giant-review screens still lack
corrected authoritative JMaps, so exact geometry recall is not claimed.

## Checkpoint: bright-room platform and water-negative review (2026-08-10)

CN3-31, CN3-92, and CN3-93 were reviewed as a connected family. CN3-31's
bright neutral brick room was producing 33 platform objects from brick/spike
edges; the room-luminance version of the platform-bar gate removes those
impostors while preserving the white/black blocks, spikes, vines, and saves.
The gate remains morphology-based and leaves dark-room platform fixtures
unchanged.

The water-negative audit also confirms the earlier water failure is no longer
present in the current workflow: CN3-92's cyan background and CN3-93's purple
material emit no water objects. Their ordinary blocks, miniblock candidates,
spikes, saves, warp, and green supports remain available for later exact
geometry review. In particular, purple material is not routed to water merely
because its hue is blue/purple; the scanner's water decision remains based on
room-relative shape and profile evidence.

Measured grid-8 project results:

| screen | objects | platforms | water |
| --- | ---: | ---: | ---: |
| `CN3_31` | 292 | 0 | 0 |
| `CN3_92` | 355 | 0 | 0 |
| `CN3_93` | 112 | 0 | 0 |

Known bright and dark platform fixtures retain their previous matches, and
FTFA remains `926/928 exact; 0 false positives; 2 missed; 0 shifted; 0 wrong
direction`. These giant-review screens still lack corrected authoritative
JMaps, so this is a classification/no-false-positive checkpoint rather than
an exact geometry claim.

## Checkpoint: Bathhouse background/water separation (2026-08-10)

CN3-Bathhouse1 was reviewed separately because its light-blue room background,
cyan water regions, and uncommon pink/orange trigger-like square are visually
close in colour. The current source/JTool/blend workflow keeps the blue room
background as background, retains the cyan water detections, and deliberately
does not emit the unusual pink square as water. This follows the safe
water-negative policy used for similarly ambiguous trigger colours; it is not
a colour-name or coordinate exception.

The grid-8 project contains 12 water-2 detections in the visible cyan regions,
two saves, three left-walljumps, and the surrounding blocks/spikes. The pink
square remains unclassified by design. Full geometry/material placement still
needs later review because no corrected authoritative giant-review JMap exists
for this screen. FTFA remains `926/928 exact; 0 false positives; 2 missed; 0
shifted; 0 wrong direction`, and the protected water/background fixture scans
remain unchanged.

## Checkpoint: Dotkid ring state and trigger-safe review (2026-08-10)

CN3-Dotkid1 through CN3-Dotkid5 were reviewed as a stateful family. Each
source contains the large visibility ring around the dotkid player; all five
grid-8 projects detect that marker and export `dotkid:1` in the JMap metadata.
The ring is not emitted as a gameplay object. Trigger-like colour around the
save in Dotkid2 and the save-edge colours in Dotkid3 likewise remain
unclassified rather than becoming extra saves, water, or geometry.

The existing application path already carries the metadata through correction
projects, the web map-settings checkbox, and JMap export. The source/JTool/
blend review confirms the object scans remain bounded by the visible terrain,
spikes, and saves; exact geometry still needs corrected authoritative maps for
these giant-review screens. The dotkid ring tests and full suite remain green,
and FTFA stays at `926/928 exact; 0 false positives; 2 missed; 0 shifted; 0
wrong direction`.

## Checkpoint: Entrance save-count audit (2026-08-10)

CN3-Entrance1, CN3-Entrance2, and CN3-Entrance3 were regenerated with the
current grid-8 colour/object and geometry workflow. The source/JTool/blend
review confirms one, two, and three visible `SAVE` sprites respectively, and
the current JMaps emit exactly one, two, and three save objects. In particular,
the earlier report of many extra saves on Entrance3 is not reproducible in the
current scanner; no filename, coordinate, or screen-specific save suppression
was added. The family still has ordinary terrain/spike geometry that needs a
corrected authoritative JMap before exact recall can be claimed.

| screen | objects | saves | current artifact |
| --- | ---: | ---: | --- |
| `CN3_Entrance1` | 294 | 1 | `.artifacts/bright-review/CN3_Entrance1-current4.jmap` |
| `CN3_Entrance2` | 348 | 2 | `.artifacts/bright-review/CN3_Entrance2-current4.jmap` |
| `CN3_Entrance3` | 334 | 3 | `.artifacts/bright-review/CN3_Entrance3-current4.jmap` |

The protected scanner tests and FTFA benchmark remain unchanged at
`926/928 exact; 0 false positives; 2 missed; 0 shifted; 0 wrong direction`.

## Checkpoint: Golden save/warp arbitration review (2026-08-10)

CN3-Golden1 through CN3-Golden7 were reviewed as one dark-brown/orange
tileset family. The current source/JTool/blend outputs do not reproduce the
earlier concern that dark blocks are being exported as saves: the current
JMaps contain exactly the visible labeled red `SAVE` sprites (1, 1, 0, 1, 1,
2, and 2 respectively). No Golden screen emits a warp object in this run.
The narrow gray panel-like material is classified as a platform candidate on
the screens where its shape passes the existing platform morphology gate;
ordinary dark terrain remains block geometry. No filename, coordinate, or
Golden-specific palette exception was added.

| screen | objects | saves | warps | platforms |
| --- | ---: | ---: | ---: | ---: |
| `CN3_Golden1` | 332 | 1 | 0 | 0 |
| `CN3_Golden2` | 375 | 1 | 0 | 2 |
| `CN3_Golden3` | 395 | 0 | 0 | 1 |
| `CN3_Golden4` | 389 | 1 | 0 | 1 |
| `CN3_Golden5` | 374 | 1 | 0 | 0 |
| `CN3_Golden6` | 403 | 2 | 0 | 1 |
| `CN3_Golden7` | 352 | 2 | 0 | 1 |

These screens still lack corrected authoritative giant-review JMaps, so the
checkpoint establishes classification and no-false-save/no-false-warp
evidence rather than exact geometry recall. FTFA remains `926/928 exact; 0
false positives; 2 missed; 0 shifted; 0 wrong direction`; the held-out
`k3-ex-hades` scan remains at 6/6 saves and 1/2 platforms.

## Checkpoint: Halls1–3 portal and water audit (2026-08-10)

CN3-Halls1, Halls2, and Halls3 were regenerated and reviewed against their
sources and blends. Halls1 retains 59 water-2 cells in the visibly cyan
regions, one save, eight apples, and two portal-like warp silhouettes. Halls2
retains its left save, one apple, and one portal-like warp without turning the
dark-purple background into water. Halls3 retains two saves, one portal-like
warp, and the up/down gravity arrows while its bright starry gradient remains
background. The current blend does not reproduce the earlier block-versus-
warp/save failures for this subfamily; no Halls-specific rule was introduced.

| screen | objects | saves | warps | water-2 | apples |
| --- | ---: | ---: | ---: | ---: | ---: |
| `CN3_Halls1` | 383 | 1 | 2 | 59 | 8 |
| `CN3_Halls2` | 109 | 1 | 1 | 0 | 1 |
| `CN3_Halls3` | 177 | 2 | 1 | 0 | 0 |

Exact corrected JMaps are not present for these giant-review screens, so the
remaining work is geometry fidelity rather than a justified global
classification change. FTFA and the held-out fixture measurements remain
unchanged.

## Checkpoint: Halls4-7 background, refresher, and vine audit (2026-08-10)

The remaining Halls screens were regenerated as a held-out tileset family.
Halls4 emits no jump refreshers and does not turn its light-blue background
into water. Halls5 likewise keeps the cyan sky as background, with one save
and one portal silhouette. Halls6 separates the muted-green terrain blocks
from the narrow repeated vine strip (two left-vine objects), and preserves the
two-cell blue hazard as water-2. Halls7 keeps the starry gradient out of the
water detector while retaining its save, portal, vine, and panel-like
platforms. The app already exposes these directional objects as Left Vine and
Right Vine; no screen-specific rename or palette exception was needed.

| screen | objects | saves | warps | water-2 | vines | refreshers |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `CN3_Halls4` | 235 | 1 | 1 | 0 | 0 | 0 |
| `CN3_Halls5` | 109 | 1 | 1 | 0 | 0 | 0 |
| `CN3_Halls6` | 86 | 1 | 1 | 2 | 2 | 0 |
| `CN3_Halls7` | 110 | 1 | 1 | 0 | 2 | 0 |

These screens still lack corrected authoritative giant-review JMaps, so the
review records classification evidence and the absence of the reported
background/refresher false positives without claiming exact geometry recall.

## Checkpoint: fragmented-save fallback and FTFA preservation (2026-08-11)

The generalized red-body/header recovery path was exercised against the
terrain-occluded save in `cn3-18`. It still recovers the left save while the
existing cross and active-layout paths retain the other two saves. The
fallback now requires a scale-normalized distributed red-fragment morphology;
an otherwise similar candidate dominated by one large terrain component is
not promoted to a save. This is a palette- and resolution-independent shape
gate, not a filename, room, coordinate, or tileset exception.

The change was checked against the held-out FTFA golden room immediately
afterward. FTFA returned `926/928 exact; 0 false positives; 2 missed; 0
shifted; 0 wrong direction`, restoring its prior strict baseline. The focused
tests cover the CN3-18 recovery, rejection of FTFA terrain, the floor-number
active-save negative, the muted-header fallback, and save/warp miniblock
coexistence. The protected four-room scan remains at 10/10 saves, 4/4 warps,
5/5 water cells, 4/4 walljumps, and 8/8 gravity flippers matched; its known
geometry over-detection/missed-cell totals are unchanged.

## Checkpoint: NR, Redcube, and Secret texture review (2026-08-11)

The next source/JTool/blend batch was regenerated from the preserved local
giant-review sources. NR1 visibly contains two saves and the fresh project
emits two; NR2 contains one labeled save and emits one, without promoting the
repeated orange/red terrain to save objects. Redcube1 and Redcube2 each retain
one save, while Redcube3 retains its three saves, one mini-spike-up marker,
two warps, and no apple detections. The red terrain and the `?`, `??`, and
`???` artwork remain out of the apple/block object classes where the current
source/blend review indicates they are not gameplay sprites.

Secret1's gradient remains background and its striped U-shaped material
remains blocks. Three recovery-only downward spikes that landed inside the
striped material were removed by a generalized repeated-horizontal-edge-band
gate; the eight isolated red triangles remain. The gate is palette- and
scale-normalized and is protected by a synthetic morphology test plus the
existing NANG and FTFA regressions. These giant-review screens still have no
corrected authoritative JMaps, so the results establish classification and
negative evidence rather than exact geometry recall.

| screen | fresh objects | saves | notable retained types |
| --- | ---: | ---: | --- |
| `CN3_NR1` | 207 | 2 | blocks, spikes, water, vines, player |
| `CN3_NR2` | 447 | 1 | blocks, spikes, vines, player |
| `CN3_Redcube1` | 192 | 1 | blocks, spikes, warp, player |
| `CN3_Redcube2` | 208 | 1 | blocks, spikes, warp, player |
| `CN3_Redcube3` | 227 | 3 | blocks, spikes, mini-spike, warps, player |
| `CN3_Secret1` | 25 | 0 | 17 blocks and 8 full spikes; no water |

FTFA remains `926/928 exact; 0 false positives; 2 missed; 0 shifted; 0
wrong direction`. The protected four-room measurement remains 10/10 saves,
4/4 warps, 5/5 water, 4/4 walljumps, and 8/8 gravity flippers matched, with
the prior geometry precision/recall totals unchanged.

## Checkpoint: follow-up-2 Cyan and Lap visual review (2026-08-11)

The preserved follow-up-2 triplets were regenerated through the current
project-create/source/JTool/blend workflow. Cyan retains its infinite-jump
message as metadata/background, one save, 224 water-2 cells, and the
surrounding blocks and spike shapes; its 10 geometry-review warnings remain
visible for later human correction. Lap retains the two visible saves, 155
blocks, and 74 full spikes in the dark-brick/white-spike reconstruction; its
19 unsupported-spike warnings identify review locations rather than silent
object loss. Neither triplet has a corrected authoritative JMap, and the
follow-up-2 Lap image still cannot be safely assigned to a Lap Around ordinal.

The blends show no justified new generalized classifier rule in this pass.
The material is preserved locally under ignored `.artifacts/follow-up-2/` and
remains part of the visual review corpus, not a strict exact benchmark.

## Checkpoint: CN3_26 duplicate red-body arbitration (2026-08-11)

The preserved `CN3_26` source was regenerated after the giant-review save
audit found three red-body candidates even though the source visibly contains
only two SAVE sprites. The extra candidate was a red terrain/triangle region
with a pale-looking area above it but weak localized dark header detail. The
fragmented red-body fallback now requires at least 20% dark header evidence
(up from 10%) in addition to its scale-normalized distributed morphology and
pale header gate. This is a visual-header evidence rule, not a screen,
coordinate, filename, or tileset exception.

Before the gate, `CN3_26` emitted saves at `(32,96)`, `(464,424)`, and
`(448,448)`; after it, only `(32,96)` and `(448,448)` remain. The new
synthetic regression covers a fragmented red body with pale but weak header
detail, while the existing muted-header and `cn3-18` recovery tests remain
green. The exact FTFA benchmark is unchanged at `926/928 exact; 0 false
positives; 2 missed; 0 shifted; 0 wrong direction`.

The protected four-room scan also retains all high-value object matches:
10/10 saves, 4/4 warps, 5/5 water cells, 4/4 walljumps, and 8/8 gravity
flippers. Its geometry totals remain 866/875 mini blocks, 244/244 blocks,
249/260 full spikes, and 181/184 mini spikes matched; these remain review
metrics rather than exact golden-room claims.

## Checkpoint: Say-family refresher and warp negative audit (2026-08-11)

Say_1 through Say_9 were regenerated in one current15 batch and compared with
their preserved source screens and JTool previews. The sources show only the
listed SAVE sprites, terrain blocks, and spikes; the white cloud in Say_9 is a
foreground decoration rather than a warp. The current projects emit the
expected save counts (2, 2, 2, 1, 1, 1, 1, 2, 1), zero type-21 warps on all
nine screens, and zero type-22 jump refreshers on all nine screens. The prior
first-pass report's 142 Say refreshers and Say_9 cloud warp are therefore stale
diagnostic output, not current detections.

No new screen-specific filter was justified: the existing refresher shape and
cloud/terrain arbitration already reject these negative controls while
preserving the true refresher and warp fixtures elsewhere. Full terrain
geometry remains visual-only because these giant-review screens have no
corrected authoritative JMaps. The current15 JMaps, SVG previews, and blends
are preserved under ignored `.artifacts/say-review/current15/`, and the local
review ledger records each screen's evidence and unresolved geometry status.

## Checkpoint: neon outlined-terrain cloud arbitration (2026-08-11)

CN3_7, CN3_8, and CN3_9 were regenerated as the original unfamiliar green
outlined-tileset controls. Each source contains a white cloud-shaped
foreground/player sprite that matched the generic filled-cloud warp silhouette
under the previous rule. Their lowest-luminance shadow sits only 17–23
luminance points from the local background ring, unlike the retained portal
controls in CN3-16/18 (42–53 points). The filled-cloud detector now treats
low shadow/background contrast as ambiguous, using local ring measurements
instead of absolute palette or screen coordinates.

The current17 projects remove the false warp from all three screens while
retaining their visible saves, neon blocks, spikes, and vines. Floor numbers
7, 8, and 9 remain background text. A synthetic regression covers both the
player-like low-contrast case and a high-contrast portal case; the existing
neutral-shadow, dense-enclosure, CN3-16, and FTFA controls remain required.
These screens still lack corrected giant-review JMaps, so the checkpoint is a
source/JTool/blend classification result rather than an exact geometry claim.

## Checkpoint: dark grayscale save recovery and reverse-tileset audit (2026-08-11)

The reconnect resumed from a clean `a68073e` checkout with all 71 ignored
ledger rows and the prior public checkpoints intact. The next source/JTool/
blend batch regenerated `LapBackwards_1`, `CN3_19`, and `CN3_21` under ignored
`.artifacts/reconnect-batch/current20/`.

LapBackwards_1 contains two grayscale SAVE signs and one warp. The original
dark-brick template found the upper sign but classified the lower sign's cell
as a block. The scanner now keeps its original binary pass and adds a brighter
relative-threshold pass gated by a broken, label-like upper band. The gate
recovers both saves at `(384,64)` and `(64,384)` while rejecting the nearby
warp silhouette at `(544,224)`. This is a palette/contrast-normalized rule,
not a coordinate or screen exception.

CN3_19 retains its two saves and emits no warp for the two white player-like
silhouettes. CN3_21 retains its two saves, all four visible gravity flippers
(two up and two down), and no warp for its white player-like silhouettes. The
fresh object counts are 248, 160, and 292 respectively; the local review
ledger records their current20 JMaps, previews, blends, evidence, and lack of
corrected giant-review JMaps.

Validation: `tests.test_unseen_regressions` ran 30 tests in 193.736 seconds
with `OK`; the documented FTFA benchmark remains `926/928 exact; 0 false
positives; 2 missed; 0 shifted; 0 wrong direction`. The two FTFA misses are
the established lower-boundary blocks, not save or warp regressions. The
complete unittest discovery run also passed: 323 tests in 412.983 seconds.

## Checkpoint: outlined-cloud player veto on CN3-25 through CN3-27 (2026-08-11)

CN3_25, CN3_26, and CN3_27 were regenerated as the next unfamiliar red
outlined-tileset batch. Each source contains a small white player-like cloud
silhouette that satisfied the outlined-cloud warp topology. The candidate's
shadow is bright, neutral gray, matching the already-established ambiguous
player evidence for filled clouds. The outlined-cloud path now applies the
same palette-relative neutral-shadow and local-background contrast veto; it
does not use a screen name, coordinate, floor number, or tileset exception.

The current22 projects emit zero warps on all three screens while retaining
the visible saves (2, 2, and 4), apples (4, 0, and 9), vines, water-2, and
outlined terrain. Floor numbers 25, 26, and 27 remain background text. The
true filled-cloud warp controls remain present in current23 CN3_16 and
CN3_18, one each. These giant-review screens still lack corrected
authoritative JMaps, so this is a classification/no-false-warp checkpoint,
not an exact geometry claim. The local ignored ledger records current22
JMaps, previews, blends, evidence, and unresolved geometry status.
The focused cloud regressions passed, the exact FTFA benchmark remains
`926/928 exact; 0 false positives; 2 missed; 0 shifted; 0 wrong direction`,
and the complete unittest discovery run passed 324 tests in 609.557 seconds.

## Checkpoint: CN3-28 through CN3-30 chromatic cherry review (2026-08-11)

CN3_28, CN3_29, and CN3_30 were regenerated in current24 after the outlined
cloud batch. Their mixed brown, beige, blue, and gray terrain remains in the
block/miniblock and spike classes; the bright-room platform gate emits no
platform impostors; and the visible cherry counts are 3, 5, and 5. The floor
numbers 28, 29, and 30 and the small white player silhouettes remain
background/non-gameplay material, with zero warp or refresher detections.

No additional generalized rule was justified by this visual review: the
current chromatic morphology and platform gates already separate the object
families without relying on these floor numbers or coordinates. Current24
object totals are 344, 344, and 426. The local ignored ledger records each
source/JMap/reconstruction/blend review and the remaining lack of corrected
authoritative giant-review JMaps, so these are classification/placement
checkpoints rather than exact geometry claims.

## Checkpoint: NANG-128/135/138 compact reverse-palette review (2026-08-11)

NANG_128, NANG_135, and NANG_138 were regenerated in current25 through the
same source/JMap/reconstruction/blend workflow. The compact/downsampled save
paths now retain NANG_128's two green saves and NANG_135's tinted-header save;
the white spiral warp remains a warp and the dense killer-block fields remain
killer blocks. NANG_138 retains its one spiral warp and all twelve visible
blue jump refreshers, with no false save promotion.

The measured current25 object totals are 128, 165, and 210. Star, narrator,
and other decorative material remains outside gameplay classes. This batch
confirms the existing compact scale/header and refresher-shape rules on a
reverse palette; it did not justify a new screen-specific rule. The local
ignored ledger records current25 JMaps, previews, blends, evidence, and the
absence of corrected authoritative giant-review JMaps.

## Checkpoint: NANG reverse tileset controls (2026-08-11)

NANG_128r, NANG_135r, and NANG_138r were regenerated in current26 as the
reverse-metal tileset controls. The orange/green trigger squares in NANG_128r
remain outside save and vine classes; its killer blocks, spikes, and spiral
warp remain. NANG_135r retains its labeled save, spiral warp, and killer-block
field while stars remain decorative. NANG_138r retains all three blue jump
refreshers and its spiral warp, with no false save or vine promotion.

The current26 object totals are 127, 154, and 188. These results show the
existing shape/relative-palette rules transferring to the reverse family;
they did not justify a new screen-specific rule. The ignored ledger records
the source/JMap/reconstruction/blend evidence and the absence of corrected
authoritative giant-review JMaps.

## Checkpoint: CN3 NR1/NR2 and Redcube1 review (2026-08-11)

CN3_NR1, CN3_NR2, and CN3_Redcube1 were regenerated in current31. NR1
retains both visible saves, cyan water strips, and patterned terrain without
false cloud/cherry objects. NR2 retains its one labeled save and orange/yellow
terrain without promoting its player-like cloud or background texture. The
Redcube1 source retains its labeled save and two visible filled-cloud warp
silhouettes; the question-mark art remains background and red patterned
terrain is not routed to cherries.

Current31 totals are 204, 446, and 191. These rooms have no corrected
authoritative giant-review JMaps, so the ledger records classification and
negative evidence rather than exact geometry recall.

## Checkpoint: Zero_Final unfamiliar blue/cyan baseline (2026-08-11)

Zero_Final was regenerated in current30 from the preserved source and reviewed
against the clean JTool reconstruction and source/blend overlay. The current
scanner retains one outlined SAVE, the cyan lower-region water as 212
water-2 cells, and the neon blocks/spikes; the deep-blue star field and
glowing `You can infinity jump` text remain background. No warp or spurious
color object is emitted. The source/blend review still exposes eleven
structural geometry warnings (unsupported or overlapping spike candidates),
and the optional OCR path did not infer `infinitejump` from this glowing text;
these remain explicit follow-up items rather than silently asserted matches.

Current30 emits 370 objects (`1:97,3:21,4:7,5:3,6:27,7:1,8:1,12:1,15:212`)
and has no corrected authoritative giant-review JMap. This is a measured
unfamiliar-tileset baseline and geometry/OCR limitation record, not an exact
benchmark claim.

## Checkpoint: NANG-139r/140 decoration and refresher review (2026-08-11)

NANG_139r and NANG_140 were regenerated in current29. NANG_139r retains its
reverse spiral warp and killer-block field while question-mark art, panels,
stars, and the player remain outside gameplay classes. NANG_140 retains its
labeled save, all four blue jump refreshers, and one spiral warp while its
stars, orange trigger, question-mark art, and player remain non-gameplay.

Current29 totals are 147 and 194. This completes the bounded NANG family
review without adding another screen-specific exception; the ignored ledger
records the source/JMap/reconstruction/blend evidence and the lack of
corrected authoritative giant-review JMaps.

## Checkpoint: NANG-130/130r/131r refresher and gravity audit (2026-08-11)

NANG_130, NANG_130r, and NANG_131r were regenerated in current27. The
familiar and reverse metal rooms both keep their blue jump refreshers in the
jump-refresher class (3, 3, and 2 respectively) rather than gravity flippers;
their spiral warps remain warps, while triggers, stars, and decorative
material remain outside gameplay classes. NANG_130 retains its save and
NANG_130r retains its reverse-palette save.

Current27 totals are 122, 261, and 173. This is a negative-control audit of
the existing refresher/gravity and spiral-warp rules; no new screen-specific
rule was justified. The ignored ledger records each source/JMap/reconstruction
/blend result and the absence of corrected authoritative giant-review JMaps.

## Checkpoint: NANG-137/137r/139 trigger and warp review (2026-08-11)

NANG_137, NANG_137r, and NANG_139 were regenerated in current28. The
familiar and reverse trigger-like colored squares in 137/137r remain outside
save/vine gameplay classes, while their spiral warps and killer blocks remain
detected. NANG_139 retains its labeled save, two-piece spiral warp, and
killer-block field; its question-mark art and panels remain decorative.

Current28 totals are 114, 114, and 147. This confirms the existing
trigger-vs-save, reverse-palette, and spiral-warp rules on another family
without adding a screen-specific exception. The ignored ledger records the
source/JMap/reconstruction/blend evidence and the absence of corrected
authoritative giant-review JMaps.

## Checkpoint: CN3 Redcube2/Redcube3 and Secret1 reconnect-safe review (2026-08-11)

CN3_Redcube2, CN3_Redcube3, and CN3_Secret1 were regenerated in current32
after a client reconnect. Redcube2 retains its visible labeled save and
bottom-right filled-cloud warp without promoting the red patterned terrain or
question-mark art. Redcube3 retains all three visible saves, the red-orb and
bottom-right cloud warp candidates, and the red patterned terrain without
cherry promotion; one small mini-spike remains a geometry-review item.
Secret1 does not classify its rainbow gradient as water, and the bottom-right
red spike is emitted as one full spike rather than two mini-spikes. The
remaining spike/terrain differences are recorded as review items rather than
new screen-specific rules.

Current32 totals are 207, 226, and 25. None of these rooms has a corrected
authoritative giant-review JMap, so this is a source/current/blend
classification checkpoint and negative-result record, not an exact benchmark
claim. The ignored review ledger contains the current32 artifact paths and
object counts. The reconnect did not lose the prior pushed commits or the
current progress; only this durable log entry and its ignored ledger rows
were pending publication.

## Checkpoint: NANG_11 compact-room negative review (2026-08-11)

NANG_11 was regenerated in current33. The scanner ignores the Floor/TNT/
narrator interface and retains the central labeled save, but it misses the
visible white spiral warp and emits one full-spike plus one platform geometry
false positive. The source is a small centered room inside a screenshot whose
overall aspect ratio is close enough to be inferred as a 25x19 room; the
resulting full-frame scaling is the likely cause of the warp miss. This is a
general compact-room normalization gap, not evidence for a NANG-specific
object rule, and no speculative code change was made without a tracked
authoritative map.

Current33 emits 20 objects (`1:17,3:1,12:1,13:1`). The ignored ledger now
points row 57 at the current33 source/JMap/reconstruction/blend artifacts and
records the unresolved room-size issue for a future generalized pass.

## Checkpoint: neutral gray outline-warp recovery (2026-08-11)

The outline-warp detector now seeds a second, deliberately narrow palette
family for middle-luminance low-saturation strokes. This is a topology-first
generalization: it recovers the gray spiral in NANG_11 without relying on its
room, game, or background colors, while retaining the existing normalized
size, nested-run, and background gates. A read-only audit across all 71
giant-review sources found only the expected NANG_11, NANG_130, and NANG_138
neutral spiral candidates. No neutral false positives were found in the
audited FTFA, Lap, Irkara, or CN3-neon material.

NANG_11 current34 now emits one warp (`1:16,3:1,12:1,13:1,21:1`); its compact
room-size inference and two geometry mismatches remain explicitly unresolved.
The focused warp regressions pass, the full suite passes **325 tests in
632.571 seconds**, and the exact FTFA benchmark remains `926/928 exact; 0
false positives; 2 missed; 0 shifted; 0 wrong direction`. The app was
restarted on this source and its health endpoint returned HTTP 200.

## Checkpoint: continuation baseline and 71-row artifact audit (2026-08-11)

The continuation started from clean synchronized commit `a318e5d`. The app
health endpoint returned HTTP 200. The complete unittest suite passed **325
tests in 606.099 seconds**, and the exact FTFA benchmark remained
`926/928 exact; 0 false positives; 2 missed; 0 shifted; 0 wrong direction`.

The ignored giant-review ledger contains 71 unique source identities and 71
current source/JMap/reconstruction/blend records. Two stale Dotkid4/5 preview
paths were corrected to their existing targeted current artifacts; no source,
fixture, JMap, or implementation file was changed by that bookkeeping.

## Checkpoint: neutral-outline held-out NANG validation (2026-08-11)

NANG_11, NANG_130, and NANG_138 were regenerated together in current35 after
the neutral gray outline-warp change. NANG_11 retains one gray spiral warp,
one save, and the same documented full-spike/platform geometry issues.
NANG_130 retains one spiral warp, its save, and three jump refreshers; NANG_138
retains one spiral warp and all twelve jump refreshers. Their object counts
and anchor coordinates match the preceding current34/current27/current25
outputs, so the new palette seed adds the intended neutral recognition without
changing the held-out NANG object families.

The ignored ledger now points rows 57, 60, and 67 at current35. No corrected
authoritative giant-review JMaps exist for these rooms, so this is a measured
held-out classification checkpoint rather than an exact geometry claim.

## Checkpoint: low-contrast platform material-support arbitration (2026-08-11)

NANG_11 exposed one remaining low-contrast platform false positive: a neutral
terrain edge matched the thin-bar morphology but had block-material support
`0.070`. A read-only audit of all 71 current outputs found no other platform
detection below that value; all eight tracked authoritative platform truths
were at least `0.106`. The low-contrast platform path now requires a relative
block-support score of `0.08`, while bright-outline and textured platform paths
remain unchanged.

Measured results: NANG_11 drops from 20 to 19 objects and removes its false
platform; all five Irkara-71 platforms remain; the known K3 and Irkara-89
geometry differences are unchanged. Focused platform tests pass, the complete
suite passes **325 tests in 416.991 seconds**, FTFA remains `926/928 exact; 0
false positives; 2 missed; 0 shifted; 0 wrong direction`, and the restarted
app returns HTTP 200. Current36 is the persisted NANG_11 source/JMap/
reconstruction/blend checkpoint; one unsupported full-spike and compact-room
normalization remain unresolved.

## Checkpoint: NANG_11 isolated support audit and reconnect recovery (2026-08-11)

The reconnect preserved the synchronized `a9258a5` commit, the app source, and
the 71-row ignored review ledger; no implementation progress was lost. A
compact diagnostic reproduced NANG_11's remaining full-spike false positive:
the raw support recovery is `(416,232)` and common-room alignment moves it to
`(416,224)`. Its 32px patch has edge density `0.309`, block score `0.302`,
triangle side coverage `0.875`, and triangle base coverage `0.312`; the source
crop is a red brick terrain tile with no visible spike. The false candidate is
therefore a compact-room/terrain-texture interaction, not a missing commit.

A read-only audit of preserved current outputs found 220 analogous
support-shaped rows across 46 source identities. Many legitimate CN3, Golden,
Halls, Say, and fixture candidates occupy the same block/triangle-score range,
so a global block-score or side-coverage veto would remove real geometry. No
screen-specific rule was added. The durable next target is generalized compact
room localization or a topology-aware texture discriminator, protected by the
FTFA exact benchmark and the existing CN3-16/CN3-18 geometry regressions.

## Checkpoint: filled red-portal component gate (2026-08-11)

Embedded-room normalization exposed a palette-independent failure mode in the
haloed-red warp detector: fragmented red brick X-texture could satisfy the
old `0.50` component-fill floor after rescaling. The detector now requires a
filled red component of at least `0.60`, while retaining the existing halo
patch topology gate. A read-only audit of all tracked red-orb examples found
17 detections with observed fills from `0.708` through `0.882`, so the new
floor preserves the corpus; the two compact NANG_11 brick fragments fall
below it and are removed. The exact FTFA benchmark remains `926/928 exact;
0 false positives; 2 missed; 0 shifted; 0 wrong direction`.

## Checkpoint: conservative embedded-room localization (2026-08-11)

The scanner now has a high-precision automatic profile for a centered,
near-square gameplay island embedded in a larger screenshot. It requires a
large detached activity component, repeated strong boundaries on both axes,
and a decisive grid score; explicit room boxes and source grids still take
precedence. A tracked FTFA screen that initially triggered the prototype is
protected by the size/centering gates and continues through the legacy path.

NANG_11 is the only hit across the 71 giant-review sources and all FTFA source
screens. Its current39 source/JMap/reconstruction/blend workflow now infers
room `(316,199,356,356)`, grid `9x9`, one save, one gray spiral warp at
`(432,336)`, and 14 terrain blocks, with no full-spike or red-halo false
positive. This is a visual checkpoint, not an exact-map claim: the giant
review still has no corrected NANG_11 JMap.

Validation: the complete unittest suite passed **327 tests in 624.038
seconds**, the exact FTFA benchmark remains `926/928 exact; 0 false positives;
2 missed; 0 shifted; 0 wrong direction`, and the restarted app returns HTTP
200 on the latest source fingerprint.

## Checkpoint: CN3 Halls and Bathhouse material-family review (2026-08-11)

The source/current/blend triplets for `CN3_Halls1` through `CN3_Halls7` and
`CN3_Bathhouse1` were reviewed after the reconnect from the current ignored
ledger outputs. These rooms deliberately span several unfamiliar material
families: white marble, cyan and blue tiled rooms, green tiles, brown brick,
dark space/metal, and the blue patterned Bathhouse tiles. The existing
palette-relative terrain learner continues to recover the main solid-cell
layouts across those changes rather than depending on a fixed tileset color.

The visible color-object families also remain coherent in this batch: labeled
saves and spiral warps are retained where present; Halls1 retains its water,
apples, and warp family; Halls6 retains its water, vine/walljump material,
save, and warp; and the reverse/neutral material paths do not promote the
backgrounds to gameplay objects. The blend overlays show that the remaining
differences are primarily dense full/mini-spike placement and local terrain
edge geometry. Because none of these giant-review screens has a corrected
authoritative JMap, those differences remain visual review items rather than
grounds for a screen-specific rule or an exact claim.

This batch therefore produced a measured negative result: no safe new
cross-corpus threshold was justified. The FTFA exact benchmark, tracked CN3
geometry regressions, and color-object fixtures remain the gates before any
future spike/material arbitration change.

## Checkpoint: Say dual-material tileset review (2026-08-11)

The `Say_1` through `Say_9` source/current/blend triplets were reviewed as a
second unfamiliar-material family. Their rooms combine a dark blue brick
material with large smooth purple foreground regions, while the spike sprites
remain bright and neutral. The current output continues to learn the solid
layout without a fixed blue/purple color rule; the two labeled saves in Say1,
the two in Say2, and the visible save variants in the remaining Say rooms are
retained in the expected locations. The blend views do not show a systematic
loss of the purple foreground as a separate tileset.

The residual overlay differences are predominantly dense spike orientation and
partial/full-spike geometry. They recur across the same material family and
are not isolated to a brightness or reverse-palette branch, but the giant
review set has no corrected JMaps for measuring them exactly. No new color or
screen-specific geometry rule was added; the existing FTFA benchmark and CN3/
NANG fixture gates remain protected.

## Checkpoint: coherent water-anchor preservation (2026-08-11)

The supported-cell terrain fallback could absorb a real water column when its
room-local material family matched the learned terrain. The fallback now keeps
only a high-confidence, full-width, internally smooth water cell: both 16px
halves must have a similar local color profile and the full cell must have low
edge density. Narrow half-cell texture remains eligible for the existing
terrain reclassification path. The rule is palette-relative and does not use a
screen name, absolute color, or coordinate exception.

Measured results:

| case | water result | other gate |
| --- | --- | --- |
| `CN3_Entrance2` current regeneration | 3 visible water cells retained (the prior fallback removed all 3) | 353 editable objects; 2 saves; no new object family |
| `irkara-54` | 405/475 matched, 405 detected, 100.0% precision | prior baseline was 344/475; saves remain 3/3 |
| `irkara-51` | 4/4 matched, 4 detected, 100.0% precision | unchanged protected water case |
| `irkara-52` | 4/4 matched, 4 detected, 100.0% precision | unchanged protected water case |
| `irkara-71` | 26/37 matched, 26 detected, 100.0% precision | unchanged held-out result |
| `cn3-18` | 5/5 matched, 5 detected, 100.0% precision | saves, warp, walljumps, miniblocks, and mini-spikes remain at prior results |

The focused anchor distinction regression passes. The complete unittest suite
passes **328 tests in 623.470 seconds**, and the exact FTFA benchmark remains
`926/928 exact; 0 false positives; 2 missed; 0 shifted; 0 wrong direction`.
The giant-review Entrance2 result is still a source/current/blend visual
checkpoint rather than an exact claim because corrected giant-review JMaps are
not available. The remaining Irkara54 and Irkara71 misses are unresolved
geometry/material coverage, not justification for a coordinate-specific rule.

## Checkpoint: coherent textured-water field preservation (2026-08-11)

The first water-anchor rule preserved smooth full-width cells but still let the
supported-cell terrain arbitration erase textured water tiles when both halves
of a cell were high-edge. A second palette-independent path now preserves such
a cell only when it has at least two neighboring water candidates within the
local lattice, both 16px halves independently meet the water-density floor,
and neighboring profiles remain coherent. An isolated or half-width repeated
texture does not qualify from adjacency alone.

Measured results:

| case | water result | gate result |
| --- | --- | --- |
| `irkara-54` | 472/475 matched, 472 detected, 100.0% precision | previous geometry result was 405/475; color-only baseline is 472/475 |
| `irkara-51` | 4/4 matched, 4 detected, 100.0% precision | unchanged |
| `irkara-52` | 4/4 matched, 4 detected, 100.0% precision | unchanged |
| `irkara-71` | 26/37 matched, 26 detected, 100.0% precision | unchanged |
| `cn3-18` | 5/5 matched, 5 detected, 100.0% precision | unchanged |

The read-only giant-corpus audit also leaves `CN3_Entrance2` at three water
cells, `Zero_Final` at 212, and the cyan-background negatives `CN3_92` and
`CN3_93` at zero. The focused field/half-density regression passes. The
complete unittest suite passes **329 tests in 625.292 seconds**, and FTFA
remains `926/928 exact; 0 false positives; 2 missed; 0 shifted; 0 wrong
direction`. No corrected giant-review JMaps exist, so the giant-room results
remain visual/classification checkpoints rather than exact-map claims.

## Checkpoint: colored warp center-fill tolerance (2026-08-11)

The colored ring warp detector rejected one genuine portal when capture scaling
and an adjacent decoration filled just over the old 22% center threshold. The
center-fill gate now allows up to 24% while retaining the existing square-box,
dark-core, hollow-center, density, and score checks. This is a small
palette-independent capture tolerance, not a screen or coordinate exception.

Measured results:

| fixture | warp result | control |
| --- | --- | --- |
| `irkara-nr-flames` | 2/2 matched, 2 detected, 100.0% precision | recovered the lower-right ring at `(752,528)` while retaining `(32,24)` |
| `irkara-53` | 1/1 matched, 1 detected | no duplicate colored/outline warp |
| `irkara-57` | 1/1 matched, 1 detected | no extra warp despite dense minispike texture |
| `irkara-59` | 1/1 matched, 1 detected | no extra warp in the minispike-heavy room |

The focused colored-warp and filled/elongated-impostor regressions pass. FTFA
remains `926/928 exact; 0 false positives; 2 missed; 0 shifted; 0 wrong
direction`; the complete suite passes **330 tests in 623.079 seconds**, `OK`.

## Checkpoint: neutral bright outlined-room arbitration (2026-08-11)

The white/gray `irkara-89` tileset exposed a general ambiguity in the
supported-cell material learner: sparse 32px outlined cells produced 88
residual 16px `mini_block` detections even though the authoritative map has no
miniblocks. A new neutral outlined-room gate uses only room-local brightness,
contrast, saturation, and sparse cell morphology. It shares the existing
bright outlined decoration veto and does not use a filename, coordinate, or
screen-specific exception.

Measured results:

| fixture | result | control/remaining issue |
| --- | --- | --- |
| `irkara-89` | false miniblocks `88 -> 0`; `0/0` miniblock truth; 11/98 blocks matched; 1/1 platform matched | one apple remains missed, two warp detections and two platform detections remain; these are separate geometry/object follow-ups |
| `cn3-16` | 501/501 miniblocks matched, 563 detected; 4/4 saves; 1/1 warp | true 16px room remains on the normal miniblock path |
| `irkara-nr-flames` | 2/2 warps, 3/3 apples, 16/16 water; zero miniblocks | colored held-out control unchanged |

The focused gate/material/miniblock regressions pass. FTFA remains
`926/928 exact; 0 false positives; 2 missed; 0 shifted; 0 wrong direction`,
and the complete unittest suite passes **331 tests in 628.941 seconds**, `OK`.

## Checkpoint: fragmented neutral apple contour (2026-08-11)

The same pale outlined family also split the monochrome apple at
`irkara-89` into several disconnected dark strokes, so the existing
component-sized outline-apple gate could not see it. A fallback now scans
complete 32px cells only after the pale-room gate, requiring normalized apple
contour support and precision plus local dark-pixel density, edge, border, and
center-shape bounds. It is palette-relative and does not depend on a sprite
filename or coordinate.

Measured results:

| fixture | apple result | controls |
| --- | --- | --- |
| `irkara-89` | improved from 0/1 to 1/1 matched, exactly 1 detected at `(128,368)` | miniblocks remain 0; the prior warp/platform/terrain discrepancies remain separately documented |
| `irkara-nr-flames` | 3/3 matched, 3 detected | colored apple path unchanged; 2/2 warps and 16/16 water remain |

The focused fragmented-outline, compact-contour, and color-object regressions
pass. FTFA remains `926/928 exact; 0 false positives; 2 missed; 0 shifted; 0
wrong direction`, and the complete unittest suite passes **333 tests in
657.967 seconds**, `OK`.

## Checkpoint: clustered neutral contours and fragmented-warp arbitration (2026-08-11)

The first implementation of the pale-room apple recovery used a complete
8-pixel room grid. It recovered the target apple, but made the full suite too
slow. The fallback is now component-clustered: it evaluates only compact groups
of nearby dark outline fragments after the existing pale-room gate, then applies
the same normalized contour, density, edge, border, and center-shape tests.
This keeps the rule palette-relative and general while avoiding a room-wide
search. The fragmented outline-warp branch also now requires a near-square
merged box (normalized width/height ratio at most 1.18); the single-component
route retains its broader aspect-ratio range. This rejects a wide decorative
label join without using a filename, coordinate, or screen-specific exception.

Measured results:

| fixture | result | control/remaining issue |
| --- | --- | --- |
| `irkara-89` | apples 1/1 (1 detected), warps 1/1 (1 detected), miniblocks 0/0 (0 detected) | platforms 1/1 (3 detected), blocks 11/98, full spikes 112/113; these remain geometry follow-ups |
| `nang138` | blocks 105/105, full spikes 26/26, saves 1/1, warps 1/1, refreshers 12/12 | mini-spikes 54/58 (55 detected), the existing measured discrepancy |
| `irkara-nr-flames` | colored warp/apple/water controls remain 2/2, 3/3, and 16/16 | no regression from neutral paths |
| `cn3-16` | 501/501 miniblocks remain matched (563 detected) | normal dense-miniblock path preserved |

The focused apple and warp regressions pass. The complete unittest suite passes
**334 tests in 1150.026 seconds**, `OK`. The exact FTFA benchmark remains
`926/928 exact; 0 false positives; 2 missed; 0 shifted; 0 wrong direction`;
the misses are still the lower-right/left-edge blocks in FTFA screen 1, not a
new regression.

## Checkpoint: normalized 71-screen review status ledger (2026-08-11)

The ignored `.artifacts/giant-review/review-ledger.csv` was re-audited after
the reconnect. All 71 canonical source records still have their source,
current JMap, preview, and blend paths; no screen identity or generated output
was lost. The original thematic `visual_status` labels and evidence are
preserved, and two explicit columns now provide the required durable review
vocabulary: `review_status` (`accepted`, `needs-more-work`, or `unresolved`)
and `status_basis`.

The current ledger contains 58 accepted visual object-class audits, 13 screens
with documented geometry/appearance follow-ups, and no unresolved artifact or
identity rows. “Accepted” means the source/current/blend object-class review
found no unexplained discrepancy; it does not turn a visual-only room into an
exact benchmark when a corrected giant-review JMap is absent. The 13 follow-up
rows are `Zero_Final`, `CN3_31`, `CN3_92`, `CN3_Bathhouse1`, `CN3_Dotkid1`
through `CN3_Dotkid5`, `CN3_Entrance2`, `CN3_Redcube3`, `CN3_Secret1`, and
`NANG_11`. Their existing `remaining_issue` text remains the authoritative
next-step record. This ledger update is local and ignored; no private corpus or
generated artifact is staged.

## Checkpoint: neutral outlined-square block recovery (2026-08-11)

The authoritative `irkara-89` fixture exposed a second neutral-tileset gap:
many 32px square outlines were placed on 8px phases and shared edges with
triangle outlines, so the generic classifier preferred spikes and returned
only 11/98 blocks. A neutral-family fallback now measures normalized straight
border sides on the existing 8px phase, requires both horizontal and vertical
support, and vetoes saves, warps, water, walljumps, and other reliable anchors.
It is gated by room-local brightness, saturation, contrast, and sparse-cell
morphology; no filename, coordinate, sprite color, or tileset name is used.
Chromatic bright rooms (including FTFA screens 2 and 4) do not enter this
branch.

Measured results:

| fixture | block result | controls |
| --- | --- | --- |
| `irkara-89` | improved from 11/98 matched (14 detected) to 72/98 matched (77 detected; 93.5% precision) | saves 1/1, apples 1/1, warps 1/1, water 14/14, walljumps 9/9; full spikes remain 112/113 |
| `nang138` | 105/105 blocks, 26/26 full spikes, 12/12 refreshers | saves 1/1, warp 1/1, mini-spikes remain 54/58 |
| FTFA exact benchmark | unchanged at `926/928 exact; 0 false positives; 2 missed; 0 shifted; 0 wrong direction` | screens 2 and 4 retain their exact block counts |

The focused neutral-square/anchor tests pass. The complete unittest suite passes
**335 tests in 1391.577 seconds**, `OK`. The remaining Irkara-89 block misses
are primarily clipped boundary cells and cells whose square outline is heavily
overlapped by a spike; those remain a separate measured follow-up rather than
being hidden by a broad permissive threshold.

## Checkpoint: clipped neutral outlined-block recovery (2026-08-11)

The neutral square pass now treats a patch at the room boundary as a clipped
observation: it requires the visible straight side(s) rather than demanding a
border that cannot be present outside the capture. Interior patches still
require both a horizontal and vertical side, so the relaxation is geometric
clipping tolerance, not a palette or coordinate exception.

The Irkara-89 scan improved to **79/98 blocks matched, 84 detected (94.0%
precision)**. Saves, apples, warps, water, walljumps, platforms, and full-spike
measurements remain unchanged (`1/1`, `1/1`, `1/1`, `14/14`, `9/9`, `1/1`, and
`112/113` respectively). FTFA remains `926/928 exact; 0 false positives; 2
missed; 0 shifted; 0 wrong direction`, and NANG138 remains exact for blocks,
full spikes, saves, warps, and refreshers. The complete unittest suite passes
**335 tests in 675.556 seconds**, `OK`.

## Checkpoint: one-tile boundary contour projection (2026-08-11)

Some clipped neutral squares left their strongest contour one partial tile
inward. The recovery now projects that already-qualified evidence to the
nearest room boundary only within one tile, retaining the same anchor veto and
deduplication rules. This is a capture-clipping generalization and does not
name a screen or coordinate.

The Irkara-89 scan now reports **81/98 blocks matched, 86 detected (94.2%
precision)**. Saves, apples, warps, water, walljumps, platforms, and full
spikes remain `1/1`, `1/1`, `1/1`, `14/14`, `9/9`, `1/1`, and `112/113`.
NANG138 remains exact for blocks, full spikes, saves, warps, and refreshers;
FTFA remains `926/928 exact; 0 false positives; 2 missed; 0 shifted; 0 wrong
direction`. The complete unittest suite passes **335 tests in 687.094 seconds**,
`OK`. This closes the current neutral-outlined-block iteration; the remaining
17 Irkara-89 misses are overlapping/partial shapes requiring a separate
evidence pass.

## Checkpoint: jump-refresher/mini-spike coexistence (2026-08-11)

The NANG138 compact-room review exposed a shared arbitration mistake rather
than a tileset-specific recognition gap. Four genuine 16px upward mini-spikes
at `(192,432)`, `(288,432)`, `(448,464)`, and `(544,464)` occupy the same 32px
cells as blue jump-refreshers. The generic anchor pass treated every nearby
mini-spike as marker noise and removed them after the compact geometry pass.

Geometry arbitration now allows mini-spikes to coexist with jump-refreshers
as an object-class rule. It does not name a room, palette, coordinate, or
sprite. The focused NANG138 regression and the existing compact support-phase
regression pass.

The exact fixture workflow now reports NANG138 mini-spikes at **58/58 matched,
59 detected (98.3% precision)**, while blocks remain 105/105, full spikes
26/26, saves 1/1, warp 1/1, and jump-refreshers 12/12. One unrelated compact
mini-spike false positive remains at `(544,128)` and is retained as the next
measured discrepancy rather than hidden by a room-specific filter.
