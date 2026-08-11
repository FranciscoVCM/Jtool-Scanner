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
