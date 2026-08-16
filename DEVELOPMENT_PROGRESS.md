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

## Checkpoint: exact full/mini duplicate arbitration (2026-08-11)

The remaining NANG138 mini-spike discrepancy was an exact same-origin,
same-direction duplicate: a high-confidence full down-spike and a weaker
16px down-mini were both emitted at `(544,128)`. A confidence-gap rule now
removes only a weaker mini fully contained at the accepted full-spike origin;
it is independent of room identity, palette, or tileset and leaves mixed-scale
neighboring geometry untouched.

NANG138 now reports **58/58 mini-spikes matched with 58 detections (100%
precision)**, alongside 105/105 blocks, 26/26 full spikes, 1/1 save, 1/1 warp,
and 12/12 jump-refreshers. The focused compact regressions pass; FTFA remains
the strict golden-room gate at `926/928 exact` pending the same two known
screen-1 misses.

## Checkpoint: compact borderline mini-spike recovery (2026-08-11)

NANG128 had one authoritative down-mini at `(560,384)` whose neutral-triangle
score was `0.5698`, just below the compact pass floor, while its supported
same-direction neighbor at `(544,384)` scored `0.6162`. The compact detector
now admits a narrow `0.56` borderline band; the existing vertical support,
cluster, and final arbitration gates still decide whether it survives. Generic
room thresholds and horizontal recovery are unchanged.

NANG128 improved from **17/18 matched (17 detected)** to **18/18 matched (18
detected)**. NANG138 remains **58/58 matched (58 detected)**, and its blocks,
full spikes, saves, warp, and refreshers remain exact. Held-out scans of
CN2-5, CN3-16, CN3-18, and NANG135 showed no new mini-spike regression; their
pre-existing geometry totals remain documented. FTFA remains `926/928 exact`.

## Checkpoint: NANG135 compact-block arbitration negative result (2026-08-11)

The fresh baseline remains **336 tests in 474.837 seconds, OK**, with FTFA at
`926/928 exact; 0 false positives; 2 missed; 0 shifted; 0 wrong direction`.
NANG135 currently matches 73/77 solid blocks with 76 detections and matches all
86 killer blocks. The four block misses are a mixture of half-step candidate
competition and visually ambiguous red/brick patches; two authoritative blocks
also overlap killer sprites in the map.

A bounded native-phase arbitration experiment was measured against NANG135,
NANG128, NANG138, and the focused geometry suite. Preferring native 32px
candidates exposed additional ambiguous red/brick patches, while preserving
every emitted killer backing candidate added false blocks. The experiment was
rejected and all code/test edits were removed. No screen-specific exception or
permissive threshold was retained; NANG135 remains an explicit follow-up until
stronger visual evidence can separate real blocks from the same-looking
texture and hidden overlaps.

## Checkpoint: four visual giant-review screens re-audited (2026-08-11)

The current source/reconstruction/blend triplets for `CN3_Dotkid4`,
`CN3_Dotkid5`, `CN3_Secret1`, and `CN3_Redcube3` were reviewed directly. The
Dotkid screens retain their detected dotkid rings and saves but still have
substantial unfamiliar-tileset geometry differences. `CN3_Secret1` keeps the
rainbow gradient as background and emits the visible spike field, but its
bottom-right red geometry remains one full spike rather than two mini-spikes.
`CN3_Redcube3` retains the three visible saves, red orb/warp candidates, and
red patterned terrain without promoting the terrain to cherries; one small
mini-spike remains a visual geometry review item.

All four remain `needs-more-work` in the local ledger because no corrected
giant-review JMaps exist. This batch produced no safe generalized scanner
hypothesis and changed no implementation or fixture; these are visual review
records, not exact-map claims.

## Checkpoint: three unfamiliar-tileset visual audits (2026-08-11)

Direct source/blend review of `CN3_31`, `CN3_92`, and `CN3_Bathhouse1` confirms
that their current ledger entries still describe the remaining risk. `CN3_31`
has bright-neutral white/black terrain whose block-versus-background geometry is
not yet stable. `CN3_92` retains the cyan field as water/background and the
brown/green terrain and controls, but the terrain lattice remains visually
ambiguous. Bathhouse1 retains the blue geometry and cyan background/water
separation; its pink trigger-like square and several overlapping structures
still need review.

None has a corrected giant-review JMap, so this batch supplies visual evidence
only. No implementation or fixture change was justified, and all three remain
`needs-more-work` in the ignored local ledger.

## Checkpoint: preserve dense adjacent-up mini-spikes through block arbitration (2026-08-11)

The Partysu3 fixture supplied a falsifiable regression for the generic
minispike/block arbitration. Its authoritative map contains adjacent upward
minispikes at `(640,560)`, `(656,560)`, and `(672,560)`. The existing dense
adjacent-up recovery already recognized all three from local silhouette,
block-like backing, and a same-row 16px anchor, but the later block arbitration
discarded the high-confidence `(672,560)` candidate because its backing block
scored higher. Arbitration now preserves that object-class/topology pattern
without naming a screen, palette, coordinate, or tileset. A focused regression
test protects the precedence rule.

Measured results:

| fixture | mini-spikes | controls |
| --- | --- | --- |
| `irkara-nr-partysu3` | improved from 73/76 matched (114 detected) to **74/76 matched (115 detected)** | saves 2/2, warps 2/2, blocks 90/90, full spikes 94/95 |
| full 12-pair fixture workflow | aggregate improved from 272/288 matched (341 detected) to **273/288 matched (342 detected)** | color classes remain exact; NANG128/NANG138 remain exact |
| FTFA strict benchmark | unchanged at **926/928 exact; 0 false positives; 2 missed; 0 shifted; 0 wrong direction** | no benchmark regression |

The focused geometry suite passes **229 tests in 103.226 seconds**, and the
complete unittest suite passes **337 tests in 517.038 seconds**, `OK`. The
remaining Partysu3 mini-spike misses and false positives are still recorded as
geometry follow-ups; this checkpoint does not claim exact recovery of the full
fixture.

## Checkpoint: three giant-review re-audits and Irkara-89 held-out review (2026-08-11)

The current source/JMap/reconstruction/blend artifacts for `Zero_Final`,
`CN3_Entrance2`, and `NANG_11` were rechecked directly from the preserved
sources and rasterized embedded blends. `Zero_Final` still retains one save and
212 cyan lower-region `water_2` cells while treating the deep-blue star/text
field as background; its eleven structural warnings remain geometry review
items. `CN3_Entrance2` still retains both visible saves and the three coherent
water cells; its 109 unsupported-spike warnings and one overlapping-opposite
spike warning are not evidence for a safe tileset rule without a corrected
JMap. `NANG_11` still isolates the centered 9x9 room, retains one save and one
gray spiral warp, and emits fourteen terrain blocks; its remaining terrain
shape judgment is visual-only.

As a held-out exact check, `irkara-89` was regenerated and reviewed with its
current source/blend. It remains at **81/98 blocks matched (86 detected)**,
**112/113 full spikes matched (141 detected)**, and exact save, warp, apple,
water, and walljump classes. The remaining block misses are predominantly
clipped, spike-overlapped, or visually blank/ambiguous truth cells; broadening
outline projection would add unsupported terrain and was not retained.

This batch changed no scanner code or fixtures. The three giant-review rows
remain `needs-more-work` because corrected authoritative JMaps are absent, and
the Irkara-89 discrepancies remain an explicit exact-fixture follow-up. The
existing 71-row ledger still has all source/JMap/preview/blend paths present;
no new exception or hidden discrepancy was introduced.

## Checkpoint: CN2-5 and CN3-16 bounded geometry re-audit (2026-08-11)

The current fixture workflow and source/JTool references were rechecked for
`cn2-5-jumprefresh` and `cn3-16` using their native screenshot scaling. CN2-5
matches six of seven authoritative jump-refreshers with no unmatched
detections. The remaining truth entry at `(624,160)` is visibly absent from
the correctly scaled game screenshot (the corridor is empty) even though the
JTool reference draws the icon there. This is a source/JMap discrepancy, not
evidence for a broader refresher detector rule, so no code change was retained.
Its other geometry totals remain 315/318 blocks, 29/32 full spikes, and 3/3
mini-spikes.

CN3-16 still has exact saves, warp, miniblocks, and mini-spikes; its remaining
full-spike result is 27/30 matched with 35 detections. The three misses sit in
bright, overlapping geometry where the current candidate projections already
produce extra spikes. Broadening those projections without corrected geometry
would trade a small recall gain for unsupported objects on this and held-out
tilesets, so no generalized change was justified.

This was a read-only visual/exact audit. No fixture, scanner, or ledger row was
altered; the generated reports and crops remain ignored local evidence.

## Checkpoint: continuation baseline and refreshed CN2-5/CN3-16 audit (2026-08-11)

The continuation re-read the authoritative 71-screen task and established a
fresh baseline at `5d8348f`. Local `main` equals `origin/main`, the working
tree is clean, the application returns HTTP 200, and all 71 ledger rows still
have source, current-JMap, preview, and blend paths. The complete unittest
discovery run passed **337 tests in 515.518 seconds**, `OK`. The exact FTFA
benchmark remains **926/928 exact; 0 false positives; 2 missed; 0 shifted; 0
wrong direction**; both misses are the established screen-1 boundary blocks.

The two bounded fixture audits were regenerated from the current scanner:

| fixture | result | interpretation |
| --- | --- | --- |
| `cn2-5-jumprefresh` | blocks 315/318 (391 detected), full spikes 29/32 (80), mini-spikes 3/3 (11), refreshers 6/7 (6) | the seventh truth refresher at `(624,160)` is absent from the correctly scaled game screenshot but present in the JTool reference; precision is already 100% for the six emitted refreshers, so no detector broadening is justified |
| `cn3-16` | saves 4/4, warp 1/1, miniblocks 501/501, mini-spikes 54/54, full spikes 27/30 (35) | the remaining full-spike misses coexist with extra bright overlapping candidates; relaxing the existing projection/arbitration would add unsupported geometry |

This continuation produced no safe generalized scanner hypothesis and changed
no implementation, fixture, or authoritative map. The refreshed reports are
ignored local evidence; the existing ledger statuses remain authoritative for
the giant-review corpus.

## Checkpoint: full fixture and 71-screen completion audit (2026-08-11)

The complete 12-pair `fixtures/block_spike/manifest.json` workflow was rerun
with color objects, geometry, grid step 8, tolerance 24, overlays, and a JSON
report. Its aggregate exact-fixture measurements are:

| class | matched / truth | detected |
| --- | ---: | ---: |
| saves | 22/22 | 24 |
| warps | 12/12 | 12 |
| apples | 4/4 | 4 |
| water | 35/35 | 35 |
| walljumps | 13/13 | 13 |
| gravity flippers | 8/8 | 8 |
| platforms | 2/3 | 4 |
| miniblocks | 866/875 | 998 |
| blocks | 1455/1486 | 1587 |
| full spikes | 709/748 | 885 |
| minispikes | 273/288 | 342 |
| killer blocks | 99/99 | 99 |
| jump refreshers | 18/19 | 18 |

The fresh report is metric-identical to the prior post-change fixture report;
the remaining geometry discrepancies are unchanged and documented by family.
NANG128 and NANG138 remain exact across their covered classes, F189 keeps all
eight gravity flippers, CN3-16/18 retain their exact color/object controls,
Partysu3 retains its dense mini-spike result, and the FTFA gate remains
`926/928 exact`.

The 71-row ignored ledger has unique ordinals 1–71, nonempty source/JMap/
preview/blend/evidence fields, 58 `accepted` rows, 13 `needs-more-work` rows,
and zero `unresolved` or identity-missing rows. The 13 follow-ups explicitly
name their remaining geometry/appearance uncertainty; none is silently
treated as an exact map. Lap Around remains visual-only because corrected JMaps
are absent, and the CN2-5 refresher discrepancy remains a source/JMap mismatch.

`HANDOFF.md` was refreshed to reflect the current 926/928 FTFA result, the
337-test baseline, and the continuation commits. This final audit changed no
implementation code, fixtures, JMaps, or ignored local corpora.

## Checkpoint: named Irkara control refresh (2026-08-12)

The committed Irkara manifest was refreshed for the two explicitly protected
minispike controls. `irkara-51` retains 3/3 saves, 1/1 warp, 4/4 water cells,
and 4/4 walljump truth (with six walljump detections, the existing precision
follow-up); its geometry remains an exact-fixture review metric. `irkara-59`
retains 2/2 saves, 1/1 warp, and 403/412 minispikes with 403 detections. No
new object family or palette-specific rule appeared. Together with the fresh
12-pair block/spike workflow, these controls preserve the named Irkara,
Partysu3, CN3, NANG, F189, and CN2-5 gates without implementation changes.

## Checkpoint: profiled-room save anchor arbitration (2026-08-13)

The profiled terrain paths had a recurring point-object phase error: saves in
scaled outlined rooms could remain eight pixels below or beside the native
JTool origin because the final support-cell lattice was added after the first
marker reconciliation. The scanner now reruns the existing
support-cell/terrain arbitration after the profile's final terrain cells are
available. This is a palette-relative support rule, not a global coordinate
shift and not a screen-specific exception.

Measured save origins after the change are canonical for the profiled Irkara
controls: `irkara-51`, `irkara-52`, `irkara-59`, `irkara-71`, and `irkara-89`
now match their authoritative JMaps at the previously observed +8 phase
positions. FTFA remains unchanged at `926/928 exact; 0 false positives; 2
missed; 0 shifted; 0 wrong direction`; CN3-18's non-profile residual phase is
unchanged and remains a separate follow-up rather than evidence for a global
shift.

The complete 12-pair block/spike workflow remains metric-identical: saves
`22/22` matched with `24` detections, and all color classes retain 100% recall
and their previous precision. The focused unseen-regression module passes 31
tests, the correction/image suite passes 57 tests, and both pass with the new
bright-outlined-room regression. The generated report is preserved locally at
`.artifacts/goal-continuation/block-spike-save-anchor/report.json`.

The next bounded review should target platform precision/recall on the
unrelated bright/outlined families (especially `irkara-89`, `irkara-71`,
`k3-ex-hades`, and CN3 panel-like rooms) without weakening the FTFA gate or
the exact Irkara-71 platform result.

## Checkpoint: bright-room platform edge-span arbitration (2026-08-14)

Bright outlined rooms exposed a platform-specific false-positive shape that
was not addressed by the earlier bar-presence gate. In `irkara-89`, two
terrain lips produced three adjacent strong horizontal edge rows at the
bottom of a platform-sized patch, while the true platform exposed an enclosed
top/bottom edge pattern. The bright-room morphology gate now requires strong
rows to span the patch, or to touch both patch boundaries; a short cluster at
one boundary is rejected. The rule uses only relative edge morphology and is
not keyed to the Irkara palette or coordinates.

The authoritative platform controls now measure:

| fixture | before | after |
| --- | --- | --- |
| `irkara-89` | 1/1 matched, 3 detected | **1/1 matched, 1 detected** |
| `irkara-71` | 5/5 matched, 5 detected | **5/5 matched, 5 detected** |
| `k3-ex-hades` | 1/2 matched, 1 detected | **1/2 matched, 1 detected** |

The complete 12-pair workflow improves the aggregate platform precision from
`2/4` to **`2/2` detections matched (100%)**, with recall unchanged at `2/3`.
All color classes remain exact; the two removed Irkara-89 platform impostors
also release two previously suppressed terrain cells, improving that pair's
block result from `81/98` to `83/98` matched. The FTFA exact benchmark remains
`926/928 exact; 0 false positives; 2 missed; 0 shifted; 0 wrong direction`.

The full unseen-regression module passes **31 tests in 712.517 seconds**. The
remaining authoritative platform miss is the dark textured Hades platform at
`(144,448)`; its screenshot/JMap evidence is insufficient for a permissive
threshold change without introducing terrain-edge candidates. CN3 platform
outputs remain visual-review evidence where corrected maps are absent; the
bright CN3-28 through CN3-31 impostor family remains fully gated.

## Checkpoint: dark relative platform recovery (2026-08-14)

The remaining Hades platform miss was caused by screenshot scaling: the brown
platform at `(144,448)` exposes a strong vertical enclosure and one long
horizontal edge, so it falls just below the generic two-edge-row threshold.
The detector now has a separate relative route for dark enclosed bars. It
requires a tall vertical edge, low block occupancy, a low-texture lower
neighbor, low saturation, and a patch luminance no more than eight levels
above the room average. This keeps the route palette-independent and rejects
the brighter continuous gray terrain edge found in NANG-11 and the Irkara
controls.

Measured result:

| check | result |
| --- | --- |
| `k3-ex-hades` platforms | **2/2 matched, 2 detected** (including `(144,448)`) |
| full 12-pair workflow | **3/3 matched, 3 detected**; all color classes unchanged |
| FTFA exact benchmark | **926/928 exact; 0 false positives; 2 missed; 0 shifted; 0 wrong direction** |
| full unseen regressions | **32 tests in 425.773 seconds, OK** |
| correction/image suite | **57 tests in 287.368 seconds, OK** |

The 71-source morphology audit found no additional dark-relative candidates
outside the already gated CN3 terrain-edge family. The remaining fixture
platform classes are now exact; giant-review platform rows without corrected
JMaps remain visual evidence rather than new truth labels.

## Checkpoint: explicit clipped-vine phase aliases (2026-08-14)

Repeated sparse-vine strips can expose the same sprite at two adjacent 16px
phases. The scanner now deduplicates the primary walljump route before using
that repeated evidence, then reconciles only an explicit opposite-side alias
within the 8px screenshot phase tolerance. A repeated right-facing strip at
the image's left boundary is normalized to the observed off-screen
`(-16,left)` JTool origin only when it belongs to a vertical repeated group.
Unpaired interior vines are deliberately left unchanged.

The authoritative clipped controls now report exact walljump origins and
directions for CN3-18: `(-16,336)`, `(-16,368)`, `(-16,416)`, and
`(-16,448)`, all type `walljump_left`. Irkara-89's paired left-edge aliases
also normalize to `(0,112,left)` and `(0,144,left)`; its unpaired interior
phase ambiguity remains visible for review. The full fixture workflow retains
walljump `13/13` recall and `13` detections, while CN3-18 mini-block recall
improves by three matched cells through the corrected backing origin.

Protected measurements remain green: FTFA is `926/928 exact; 0 false
positives; 2 missed; 0 shifted; 0 wrong direction`; the full unseen module
passes **33 tests in 474.237 seconds**, and the correction/image suite passes
**57 tests in 184.936 seconds**. The two additional low-confidence Irkara-89
full-spike candidates introduced by the corrected backing phase are retained
as an explicit geometry review item; no truth spike was lost.

## Checkpoint: mini-cell save phase arbitration (2026-08-14)

The 16px terrain path exposed one remaining save phase drift in CN3-18. A
high-confidence fragmented save at `(224,88)` overlapped the first mini-cell
row, while `(224,80)` had a complete 32px support row with no terrain overlap.
The final pipeline now applies a palette-independent mini-cell support check
to saves at most one 8px phase away. It requires two full supporting 16px
cells and never shifts a marker without that evidence.

CN3-18 now emits `(224,80)` with kind
`save_red_body_header_fragmented_mini_terrain_aligned`; its other saves and
all exact CN3-16/Irkara saves remain unchanged. The full 12-pair workflow is
metric-identical to the preceding vine checkpoint; FTFA remains `926/928
exact; 0 false positives; 2 missed; 0 shifted; 0 wrong direction`. The full
unseen module passes **33 tests in 331.102 seconds**, and the correction/image
suite passes **57 tests in 181.994 seconds**. The lower CN3-18 save `(768,376)`
remains an explicit source/JMap phase review item because no full mini-cell
support row justifies moving it.

## Checkpoint: preserve bright-platform morphology contracts (2026-08-14)

The first complete post-checkpoint unittest run exposed one compatibility
regression in the bright-platform helper: the production six-row span rule had
also changed the helper's established synthetic three-row contract. The
helper now keeps that general morphology contract by default, while the final
bright-room impostor prune opts into `require_span=True`. This preserves the
Irkara terrain-edge rejection without weakening the platform detector's
palette-independent production gate.

Validation after the split: **341 tests in 613.688 seconds, OK**. The focused
bright-room and dark-platform regression pair also passes (**2 tests in
273.348 seconds**). No fixture, JMap, or generated artifact was changed.

## Checkpoint: terrain-backed vine phase arbitration (2026-08-14)

The recurring vine error was not a tileset color failure alone: repeated
green strips could be sampled at an adjacent 8/16px phase while a geometry
scan already contained the canonical terrain column. Geometry-enabled scans
now use that local evidence only when the current interior x-column has no
nearby block or miniblock support and a neighboring phase does. Eight-pixel
shifts preserve the facing; sixteen-pixel shifts flip the upstream JTool vine
ID. Clipped edge origins and open-background vines remain unchanged.

The same-side repeated-strip candidate now wins over a weaker opposite-side
alias before terrain arbitration, preventing a y-phase regression in the
Irkara-89 lower vine. Irkara-89 now matches all nine walljumps exactly,
including `(416,128,left)`, `(256,512,right)`, `(416,544,left)`,
`(416,576,left)`, and `(640,376,left)`. CN3-18 remains exact at all four
off-screen left origins, and the Irkara-51 right vine at `(224,128)` is
recovered from its prior `(208,128)` phase. The unresolved Irkara-51 extras
remain a separate visual/geometry review item.

Validation: the unseen-regression module passes **33 tests in 942.384
seconds**, and the strict FTFA benchmark remains **926/928 exact; 0 false
positives; 2 missed; 0 shifted; 0 wrong direction**. The two FTFA misses are
the established screen-1 edge blocks.

## Checkpoint: wider terrain-supported vine phase window (2026-08-14)

The same support rule exposed one Irkara-51 candidate 24px from its canonical
column, caused by a combined half-cell and screenshot sampling phase. The
terrain arbitration window now considers ±8, ±16, and ±24px candidates, still
requiring an unsupported current column and at least one nearby detected
terrain cell. The 24px case flips the upstream JTool vine ID; no coordinate or
screen name is used.

Irkara-51 now emits the supported right-vine `(224,128,right)` and left-vine
`(672,400,left)` origins. Its unsupported extra vine candidates remain
visible for a separate precision review rather than being silently deleted.
The new regression passes **1 test in 320.626 seconds**; the prior strict
FTFA and 12-pair measurements are unchanged.
The complete post-change suite is green when run by module: **342 tests**
(`34 + 286 + 22`), with no fixture or JMap modifications.

## Checkpoint: paired mini-silhouette full-spike recovery (2026-08-14)

The green/white Irkara-51 room exposed a generalized scale failure: many real
32px spikes survived only as two adjacent 16px directional silhouettes. The
later mini-dense profile cleanup then removed the full spike and left false
mini-spike objects. Geometry scanning now pairs adjacent same-direction
half-cell silhouettes and promotes them only when the independent 32px patch
has a strong matching direction, outline, side coverage, edge density, and a
non-block-dominant center. The recovery is palette- and tileset-independent;
it does not use fixture names or JMap coordinates.

On Irkara-51 this raises full-spike matches from `29/63` to `46/63` and reduces
mini-spike output from `43` detections (32.6% precision) to `15` (14/15 matched,
93.3% precision), while saves, warps, water, and walljumps remain unchanged.
The full 12-pair block/spike workflow is unchanged in its protected aggregate
totals (`709/748` full spikes, `273/288` mini spikes, `22/22` saves,
`13/13` walljumps, `8/8` gravity, `18/19` refreshers, and exact color-object
recall). FTFA remains `926/928 exact; 0 false positives; 2 missed; 0 shifted;
0 wrong direction`.

The Irkara-51 regression now protects both recovered full-spike examples and
the preservation of a genuine mini-spike. The complete module suite still
needs to be rerun after this checkpoint before it is considered final.

## Checkpoint: late recovery of unfamiliar mini-spike silhouettes (2026-08-15)

Several green/white and reverse-palette rooms expose genuine 16px spikes to
the primary shape classifier, but later room-scale cleanup removes them when
there is no matching terrain anchor. The final pipeline now performs one
late, palette-independent reconsideration of those raw candidates. It keeps
only strong down, right, and up silhouettes whose independent 32px footprint
does not look like a full spike. A separate low-score paired-down veto removes
two 16px halves when their 32px footprint has a strong full-down shape,
without touching high-confidence mini pairs such as Partysu3 and Irkara-51.

The generalized rule raises the actual ten-pair Irkara manifest from the
previous `425/460` matched mini spikes (`436` detections) to `434/460`
matched (`444` detections), improving precision slightly from 97.5% to 97.7%.
Irkara-52 specifically improves from `8/21` matched (`12` detections) to
`16/21` matched (`16` detections) with no false mini-spike output in its
recovered group. Full-spike totals remain `529/796` matched (`717`
detections), unchanged by the late placement. The protected twelve-pair
block/spike workflow remains `273/288` matched mini spikes and all prior
object-family totals; it emits one additional unmatched CN3-18 mini candidate
(`343` detections versus `342` previously). FTFA remains `926/928 exact; 0
false positives; 2 missed; 0 shifted; 0 wrong direction`.

The new Irkara-52 regression and the existing Irkara-51 paired-spike
regression pass together. The complete post-change module suite passes **343
tests** (`35 + 286 + 22`), with no fixture or JMap modifications.

## Checkpoint: silhouette-centered vine phase recovery (2026-08-15)

The green/white Irkara-52 room exposed a second generalized vine failure. A
single sprite can be split into two ordinary green components one 32px cell
apart, or two opposite half-cell aliases can straddle the true 8px phase. The
scanner now probes the three intervening phases only when the candidate patch
has a palette-relative edge profile and the expected side bias. Existing
repeated-strip candidates veto the split recovery, and recovered phases are
protected from later terrain-column arbitration. No fixture name, palette, or
coordinate is used by the rule.

Irkara-52 now matches all three authoritative walljumps exactly: `(16,416,
right)`, `(112,528,right)`, and `(272,320,left)`, improving the prior `2/3`
walljump match to `3/3` with no extra vine. Irkara-51 keeps its supported
`(224,128,right)` and `(672,400,left)` phases; Irkara-89 remains exact at
`9/9`, and CN3-18 remains exact at `4/4`. The complete ten-pair Irkara
workflow now reports `7/7` walljump recall with the existing 15 detections;
precision remains an explicitly tracked follow-up because the corpus contains
known extra visual candidates.

The protected twelve-pair block/spike workflow is unchanged (`13/13`
walljumps, `22/22` saves, `35/35` water, `8/8` gravity, `3/3` platforms), and
the strict FTFA gate remains `926/928 exact; 0 false positives; 2 missed; 0
shifted; 0 wrong direction`. The complete selected module suite passes **344
tests in 670.562 seconds**, with no fixture or JMap modifications.

## Checkpoint: dark sparse outlined-room platform gate (2026-08-15)

The dark purple outlined Irkara-49 and Irkara-49-warp rooms exposed a broad
platform failure: the generic low-contrast and textured routes interpreted
terrain lips as 57 platform objects (28 and 29 respectively), even though
those rooms contain no platform sprites. Irkara-71 and K3-EX-Hades provide
filled/darker controls with real platforms, so the correction is deliberately
room-relative rather than a fixture or coordinate exception.

The scanner now applies a dark-sparse gate only when the room luminance is at
most 45 and the room's filled bright share is at most 0.14. A candidate must
then retain a 24-pixel horizontal run, a three-pixel vertical run, a low
center and block occupancy, and a low below-edge score. The gate preserves all
non-platform detections and leaves filled dark controls on the existing route.

On the ten-pair Irkara manifest this reduces platform detections from `62` to
`5`, while the five true Irkara-71 platforms remain exact: aggregate platform
precision and recall are now both `100%` (`5/5` matched). K3-EX-Hades remains
exact at `2/2`; the targeted block/spike controls remain exact at `3/3`
platforms and `9/9` walljumps. All other Irkara aggregate object totals are
unchanged. FTFA remains `926/928 exact; 0 false positives; 2 missed; 0
 shifted; 0 wrong direction`. The new regression test passes, and the complete
 selected module suite passes **345 tests in 790.763 seconds**, with no fixture
 or JMap modifications.

## Checkpoint: clipped edge-vine origin recovery (2026-08-15)

An edge-clipped walljump component can contain only a short vertical column.
Centering that shortened box assumes a full 32px sprite and moved the
Irkara-51 left-edge vine from its JTool origin `(0,240)` to `(0,232)`. The
scanner now uses the component top only when the candidate is at the left edge,
is at most 8 map pixels wide, and is shorter than 28 map pixels. Complete
sprites and repeated-strip/clipped aliases retain their existing center or
phase rules; the logic does not use a fixture name or coordinate.

Irkara-51's edge vine now lands at `(0,240,left)`; the existing Irkara-52
split/phase recoveries, Irkara-89 repeated strips, and CN3-18 edge-clipped
aliases remain unchanged. The two focused regressions pass. The complete
selected module suite passes **346 tests in 824.307 seconds**, with no fixture
or JMap modifications.

The accompanying save-phase audit remains a negative result rather than a
global shift: the existing support/profile paths correct the known FTFA,
Irkara-51/52/71/89, and upper CN3-18 phases, while unprofiled Irkara-49/54
and the lower CN3-18 save still show isolated +8 origins. K3-EX-Hades also
contains intentional 8px-phase saves where blindly preferring a full support
cell would move the marker in the wrong direction. A future save change must
therefore use sprite/layout evidence and preserve these phase-sensitive
controls; no blanket `y -= 8` rule was added.

## Checkpoint: dark sparse SAVE-header phase recovery (2026-08-15)

The dark, mostly empty Irkara-49 and Irkara-49-warp rooms exposed a bounded
SAVE-origin error: the warm body component rounded eight map pixels below the
JTool origin even though the pale `SAVE` header was still visible above it.
The scanner now performs a room-relative correction only when the sampled room
is very dark (brightness at most 45) and sparse (filled share at most 0.14), a
pale header occupies enough of the expected header band, and the proposed
change is no more than one 8-pixel phase. The correction is represented as
`save_dark_header_aligned`; normal saves, terrain-supported saves, FTFA, and
phase-sensitive K3 layouts do not take this path.

Both Irkara-49 and Irkara-49-warp now have their two SAVE markers at the exact
authoritative coordinates `(256,64)` and `(384,544)`. The Irkara-71 control
remains exact at `(384,96)` and `(544,544)`, and the existing dark-sparse
platform gate remains exact at five platforms with no platform detections in
the two outlined rooms. The full ten-pair Irkara scan remains `23/23` matched
saves, `7/7` matched walljumps, and `5/5` matched platforms; no fixture or JMap
was changed.

Validation is green: the focused SAVE/platform pair passes 2 tests in
401.067 seconds; the complete unittest discovery run passes **347 tests in
931.515 seconds**, `OK`; and the strict FTFA benchmark remains **926/928
exact; 0 false positives; 2 missed edge blocks; 0 shifted; 0 wrong
direction**, with every FTFA save still exact. The rule is intentionally
limited to independent header evidence in dark sparse rooms; residual +8
phase cases in Irkara-54 and lower CN3-18 remain measured follow-up work
rather than justification for a global vertical shift.

## Checkpoint: palette-relative SAVE-header phase recovery (2026-08-15)

The previous dark-sparse correction isolated the recurring eight-pixel SAVE
phase error but did not generalize to bright cyan or photographic backgrounds.
The raw palette detector centers the colored body, while some tilesets tint the
white `SAVE` title so strongly that an absolute pale-color test cannot see it.
The scanner now finds a short, contiguous local-luminance-contrast run above
an ordinary palette-body candidate and uses that run as the sprite-origin
anchor. It requires at least three text-like rows, a minimum local signal
share, and a one-phase (8 map pixel) limit. The correction runs after terrain
arbitration for ordinary candidates, so supported terrain markers retain their
existing provenance; the dark-sparse absolute-header path still runs before
terrain arbitration.

This recovers all three Irkara-54 saves exactly at `(32,64)`, `(192,544)`,
and `(576,544)`, including the cyan-tinted right-hand header that is not
recognized by the old absolute-pale predicate. It also corrects the lower
CN3-18 save from `(768,376)` to its authoritative `(768,368)` without moving
the upper `(224,80)` or center `(384,256)` saves. Dark Irkara-49/49-warp
remain exact, and the rescaled brick control retains its original
`save_terrain_aligned` provenance at `(480,544)`.

The complete unittest discovery run passes **348 tests in 1005.062 seconds**,
`OK`. The strict FTFA gate remains **926/928 exact; 0 false positives; 2
missed edge blocks; 0 shifted; 0 wrong direction**, with every FTFA save exact.
The ten-pair Irkara workflow remains `23/23` matched saves, `7/7` matched
walljumps, and `5/5` matched platforms; no fixture or JMap was modified.
This is header-evidence phase recovery, not a general vertical offset: terrain,
fragmented, active-layout, and intentionally phase-sensitive K3 save paths
remain protected and are not rewritten by the ordinary rule.

## Checkpoint: dark textured paired upward mini-spike recovery (2026-08-15)

The dark textured `k3-ex-hades` room exposed eight authoritative upward
mini-spikes that the ordinary luminance-edge classifier could not retain.  A
new palette-relative fallback learns each 16px patch's background from its
border, requires a centered foreground silhouette that grows toward the lower
edge, and accepts it only when the same-row silhouette appears in an adjacent
cell.  The room gate is based on local brightness, saturation, and neutral
chroma rather than a fixture name; bright/neon, compact, cyan, and warm rooms
do not enter this route.

The K3 result improves from `0/8` matched upward mini-spikes to `8/8` with
exact coordinates `(400,16)`, `(416,16)`, `(464,16)`, `(480,16)`,
`(544,112)`, `(560,112)`, `(224,496)`, and `(240,496)`, with no other mini
spike output in that room.  The complete 12-pair block/spike workflow improves
aggregate mini-spikes from `273/288` matched (`343` detected) to `281/288`
matched (`351` detected); all eight added detections match truth and every
other aggregate object total is unchanged.  The exact FTFA gate remains
`926/928 exact; 0 false positives; 2 missed; 0 shifted; 0 wrong direction`.

The CN2-5 refresher discrepancy remains a deliberate negative result: its
JMap-only `(624,160)` entry is absent from the source screenshot, while all
six visible refreshers remain exact.  No fixture, JMap, or ignored corpus
artifact was modified.

## Checkpoint: bound dark-textured mini-spike recovery (2026-08-15)

The paired low-contrast mini-spike fallback now has a cheap structural
precondition: it runs only when the scan already contains at least twelve
full-spike detections.  This is the hazard-field context that motivated the
K3 rule, and it prevents the 1185-cell palette-relative probe from running on
ordinary color-only and synthetic scans.  The K3 screen still recovers all
eight authoritative upward mini-spikes at exact coordinates.

The complete unittest discovery run passes **349 tests in 1650.616 seconds**,
`OK`.  The strict FTFA gate remains **926/928 exact; 0 false positives; 2
missed edge blocks; 0 shifted; 0 wrong direction**.  The documented
12-pair block/spike workflow remains unchanged for every category except the
intended K3 mini-spike recovery: saves 22/22, warps 12/12, apples 4/4,
water 35/35, walljumps 13/13, gravity flippers 8/8, platforms 3/3,
mini-blocks 869/875, blocks 1457/1486, full spikes 709/748, mini-spikes
281/288, killers 99/99, and refreshers 18/19.  No fixture or JMap was
modified.

## Checkpoint: compact relative platform recovery (2026-08-16)

The preserved `CN3_Entrance2` source/blend review shows a real small brown
platform at map approximately `(80,464)`, while the current regeneration had
only seven striped-terrain platform impostors and omitted that sprite.  Its
signature is not a useful absolute color rule: after screenshot scaling it is
a 24px-plus horizontal / 12px-plus vertical enclosure with one strong edge
row, low chroma, low block occupancy, and luminance at least ten units below
the room.  Its neighboring 16px-shifted material profile is also separated by
at least ten normalized profile units.  The scanner now has a dedicated
compact-relative route with these palette-relative constraints, deferring
neighbor profiling until the cheap shape gates pass.

`CN3_Entrance2` now emits the recovered platform at `(80,464)` (score about
`.753`) in addition to the seven pre-existing candidates; no fixture source or
JMap was changed.  The same route produces no candidates in the tracked
`*-game.png` fixture corpus, including the similarly shaped F189 terrain edge,
because its neighboring material is continuous.  The sampled giant-review
controls `CN3_Entrance1`, `CN3_Entrance3`, `CN3_Halls6`, `CN3_Halls7`,
`CN3_19`, `CN3_25`, `CN3_28`, `CN3_29`, `CN3_30`, `CN3_31`, and `NANG_11`
also produce no compact-relative candidates.  Existing exact platform controls
remain unchanged: K3 `(512,336),(144,448)`, Irkara-71's five platforms,
Irkara-89 `(704,288)`, and no platform in F189.

The new pure-route regression test passes.  The complete 12-pair fixture
workflow remains unchanged at platforms **3/3 matched and 3 detected**, with
saves 22/22, warps 12/12, apples 4/4, water 35/35, walljumps 13/13, gravity
8/8, killers 99/99, mini-blocks 869/875, blocks 1457/1486, full spikes
710/748, mini-spikes 281/288, and refreshers 18/19.  The strict FTFA benchmark
remains **926/928 exact; 0 false positives; 2 missed edge blocks; 0 shifted;
0 wrong direction**.  Full unittest discovery passes **351 tests in 1748.175
seconds**, `OK`.  No fixture, JMap, or ignored corpus artifact was modified.

## Checkpoint: platform-edge full-spike coexistence (2026-08-16)

K3-EX-Hades exposed a late arbitration error in a mixed platform/hazard
layout.  A low-confidence full spike immediately touching a platform edge was
being discarded as platform overlap, while a stronger triangle whose body
actually occupied the platform's 16px band was correctly rejected.  The
coexistence rule now uses only normalized map geometry: horizontal edge
contact, no body overlap, and a full-spike confidence ceiling.  It does not
change platform detection or permit embedded triangles.

The K3 full-spike result improves from **108/113 matched with 132 detections**
to **109/113 with 133 detections**.  Across the complete 12-pair workflow,
full spikes improve from **709/748 to 710/748** and **887 to 888 detections**;
all other category totals remain unchanged, including platforms at **3/3
matched and 3 detected**.  The complete unittest discovery run passes
**350 tests in 1676.974 seconds**, OK.  The strict FTFA gate remains
**926/928 exact; 0 false positives; 2 missed edge blocks; 0 shifted; 0 wrong
direction**.  No fixture or JMap was modified.

## Checkpoint: bright relative platform-impostor arbitration (2026-08-16)

The compact-platform recovery exposed a complementary failure mode in the
same unknown dark tileset: white striped terrain edges were emitted as seven
platforms in `CN3_Entrance2`, even though the source contains one small brown
platform.  A late arbitration pass now removes only platform detections whose
32x16 patch is simultaneously much brighter than the room, densely filled,
center-heavy, and supported by at least three long horizontal edge rows.  It
does not weaken candidate generation and explicitly preserves the bright
outline, textured, dark-relative, and compact-relative bar routes.

In the source/current review, `CN3_Entrance2` changes from seven platform
impostors to the single visually supported `(80,464)` platform.  The sampled
giant controls retain or remove only visually consistent material: Entrance1
retains two bars, Entrance3/Halls6/Halls7/CN3-19/NANG-11 retain none,
CN3-25 retains three, and CN3-28 through CN3-31 remain at zero.  The source
review also records that Entrance1 contains additional partially occluded
brown bars not yet recovered; those remain visual follow-up work rather than
being promoted to exact truth without a corrected JMap.

The complete 12-pair fixture workflow is unchanged from the prior checkpoint:
platforms **3/3 matched and 3 detected**, saves 22/22, warps 12/12, apples
4/4, water 35/35, walljumps 13/13, gravity 8/8, killers 99/99, mini-blocks
869/875, blocks 1457/1486, full spikes 710/748, mini-spikes 281/288, and
refreshers 18/19.  FTFA remains **926/928 exact; 0 false positives; 2 missed
edge blocks; 0 shifted; 0 wrong direction**.  Full unittest discovery passes
**352 tests in 1666.249 seconds**, `OK`.  No fixture, JMap, or ignored corpus
artifact was modified.

## Checkpoint: preserve repeated-strip vine origins (2026-08-16)

The Halls7 source/current/blend review isolated a recurring 16px horizontal
alias.  The visible green strip at source pixels approximately `x=512..529`
can be represented by either a left vine at map `(400,y)` or a right vine at
`(416,y)`.  The repeated-cadence silhouette consistently scored the left
shape phase slightly higher, but the later terrain-column reconciler moved it
to the same-column `(416,right)` alias.  That made the JTool origin and
direction wrong even though the rendered green pixels looked similar.

Terrain-column alignment now leaves high-confidence left-facing
`*_repeated_strip` detections on their shape-derived phase, alongside the
existing split/phase exceptions.  Right-facing repeated strips remain eligible
for terrain support because the authoritative Irkara89 control contains a
stronger same-column right/left alias at one phase.  Ordinary clipped or
isolated vines still use the terrain support reconciler.  This is a
morphology/provenance rule, not a screen coordinate or palette rule: the
repeated cadence and the established terrain alias together choose the JTool
origin.

The current Halls7 scan changes from `(416,288,right),(416,320,right)` to the
source-supported `(400,288,left),(400,320,left)`.  Halls6 remains the ordinary
terrain-aligned `(224,160,left),(224,192,left)` result.  Protected Irkara51,
Irkara52, and CN3-18 vine coordinates remain unchanged.  The complete tracked
12-pair block/spike workflow is unchanged: saves 22/22, warps 12/12, apples
4/4, water 35/35, walljumps 13/13, gravity 8/8, platforms 3/3, mini-blocks
869/875, blocks 1457/1486, full spikes 710/748, mini-spikes 281/288, killers
99/99, and refreshers 18/19.  FTFA remains **926/928 exact; 0 false
positives; 2 missed edge blocks; 0 shifted; 0 wrong direction**.

The regression suite now includes a pure terrain-alias test proving that a
repeated-strip vine at `(400,288)` is not moved to `(416,288)` merely because
the neighboring terrain column is populated.  No fixture or JMap was
modified; Halls7 remains visual evidence rather than exact benchmark truth.

The first full-suite run intentionally caught one collateral Irkara89
direction/phase regression in this rule; the right-facing terrain-alias path
was restored and the pure test was expanded to cover both directions.  The
corrected complete discovery run passes **353 tests in 1572.166 seconds**,
`OK`.

Post-correction exact gates were rerun at `grid_step=8`: the selected
`irkara-89`, `cn3-18`, and `irkara-nr-partysu3` controls retain their prior
walljump totals and all matched color/geometry totals, and the strict FTFA
benchmark remains **926/928 exact; 0 false positives; 2 missed; 0 shifted; 0
wrong direction**.

## Checkpoint: palette-relative partial platform recovery (2026-08-16)

The Entrance1 source/blend review exposed a second form of unknown-tileset
platform failure: several brown platform sprites retain only a short
horizontal contour and a vertical edge, so the complete-bar routes cannot
classify them.  A new partial-relative route uses only transferable evidence:
low-saturation room material, a compact low-fill patch, short horizontal and
vertical remnants, a candidate darker than the room, opposing candidate/room
chroma direction, and distinct neighboring material profiles.  It does not
name a tileset or use a screen coordinate.  The expensive neighbor-profile
sample is deferred until the cheap shape and palette-relative gates pass.

On the preserved giant-review source, Entrance1 retains its two previously
recognized bars `(192,16)` and `(256,336)` and now adds the visually supported
partial bars `(160,96)`, `(48,480)`, and `(288,528)`.  The lower gray partial
bar near `(144,464)` remains unresolved because it has no reliable opposing
chroma signal; the possible `(416,400)` fragment remains uncertain without a
corrected JMap.  Entrance2 remains the single supported `(80,464)` bar after
the bright-striped-terrain veto, and Entrance3 remains platform-free.

Held-out controls remain clean after late pruning: F189 and CN3-18 emit no
platforms; K3 emits exactly `(512,336),(144,448)`; Irkara-71 emits its five
authoritative platforms; and Irkara-89 emits only `(704,288)`.  The complete
12-pair fixture workflow remains unchanged: platforms **3/3 matched and 3
detected**, saves 22/22, warps 12/12, apples 4/4, water 35/35, walljumps
13/13, gravity 8/8, mini-blocks 869/875, blocks 1457/1486, full spikes
710/748, mini-spikes 281/288, killers 99/99, and refreshers 18/19.  The
strict FTFA gate remains **926/928 exact; 0 false positives; 2 missed; 0
shifted; 0 wrong direction**.  The pure regression test requires opposing
room/candidate chroma and rejects an otherwise similar blue terrain patch.
No fixture, JMap, or ignored corpus artifact was modified.

## Checkpoint: unknown material-family negative audit (2026-08-16)

The current source/current/blend triplets for `CN3_31`, `CN3_92`, and
`CN3_Bathhouse1` were regenerated after the partial-platform checkpoint.
These three screens cover bright neutral brick, cyan-background brown/green
terrain, and blue patterned terrain with cyan water.  They do not share a
falsifiable missing-object signature that can safely justify another global
threshold: `CN3_31` emits three labeled saves, three vines, and zero platform
impostors; `CN3_92` keeps its cyan field as background and emits one warp; and
`CN3_Bathhouse1` retains two saves, thirteen water-2 cells, and three vines
while rejecting the pink trigger-like decoration as water.

The remaining differences are dense block/spike placement and material-edge
geometry without corrected giant-review JMaps.  The three current projects,
JMaps, previews, and blends are preserved under
`.artifacts/goal-continuation/material-family-review/`, and their ledger rows
now point to those outputs.  No implementation change was justified by this
cross-family audit; promoting any of the ambiguous terrain edges would risk
the strict FTFA gate and the exact platform/water controls.  This is an
explicit negative result, not an assertion that the three screens are exact.

## Checkpoint: weak marker-adjacent mini-spike arbitration (2026-08-16)

`CN3_Redcube3` provided a bounded false-positive case rather than evidence
for a new tileset rule.  Its source crop shows a real right-side SAVE at
`(736,224)` and no playable mini-spike at the diagonal `(752,240)` position;
the old scan nevertheless emitted `mini_spike_up` there with score `0.337`.
The generalized arbitration now suppresses only mini-spike candidates at
most 24 map pixels from a save/warp marker when their confidence is at most
`0.40`.  It is applied during geometry-anchor conflict resolution and does
not mention Redcube3, a palette, or a screen coordinate.

Two pure tests protect both sides of the boundary: the weak diagonal edge
loses to the save marker, while a strong candidate at the same position
(score `0.78`) remains coexistent.  Held-out scans retain the genuine nearby
mini-spike group in NANG138, including the authoritative down spike at
`(176,224)`, and the many genuine Irkara59 mini-spikes near saves/warps.
`CN3_Secret1` remains a negative control with no mini-spike promotion; its
bottom-right red geometry and gradient remain visually unresolved.

The regenerated Redcube3 project drops from 226 to 225 objects (three saves,
two warps, and no weak marker-adjacent mini-spike); its source/JMap/preview/
blend outputs are preserved under
`.artifacts/goal-continuation/marker-mini-spike-review/`.  The complete
12-pair workflow remains unchanged: saves 22/22 matched (24 detected), warps
12/12, apples 4/4, water 35/35, walljumps 13/13, gravity 8/8, platforms
3/3, mini-blocks 869/875, blocks 1457/1486, full spikes 710/748,
mini-spikes 281/288, killers 99/99, and refreshers 18/19.  FTFA remains
**926/928 exact; 0 false positives; 2 missed edge blocks; 0 shifted; 0
wrong direction**.  No fixture or JMap was modified; the giant-review rows
for Redcube3 and Secret1 now point to the regenerated ignored artifacts.
The complete unittest discovery run passes **356 tests in 1560.826 seconds**,
`OK`.

## Checkpoint: CN3 Dotkid material-family phase audit (2026-08-16)

The five CN3-Dotkid screens were regenerated together as a held-out material
family: green/brown terrain, pale spike edges, dark paths, a dotkid ring,
and one or more SAVE markers.  All five current projects export `dotkid:1`
and preserve the visible save class without promoting the trigger-like save
colour as a second object.  Their dense block/spike geometry remains visual
review material because no corrected giant-review JMaps exist.

The latest vine-origin work also provides a useful negative control.  The
source shapes in Dotkid4 and Dotkid5 are broad filled green terrain, not a
confirmed sequence of the narrow canonical walljump sprites; the current
scan therefore emits no walljump strips, whereas an older targeted artifact
had many such candidates.  This avoids carrying a green-material impostor
forward as a generalized vine rule.  Dotkid3's prior edge-warp candidate at
`(0,192)` is not reproduced and is now explicitly uncertain; the source does
not provide a corrected map to decide whether it was a warp or a player-like
decoration.  The current save origins are `(704,96)`, `(96,512)`, and
`(544,384)` for Dotkid3–5 respectively, each eight pixels above the older
review artifact's phase.

The five source/JMap/preview/blend triplets are preserved under
`.artifacts/goal-continuation/dotkid-phase-review/`, and ledger rows 29–33
point to them.  No implementation change was justified by this audit: there
is no shared, falsifiable missing-object signature, and inventing one would
risk the FTFA vine/platform gates.  The existing 12-pair fixture totals and
the strict FTFA result remain the protected controls from the preceding
checkpoint.

## Checkpoint: flag and embedded-room audit (2026-08-16)

The latest grid-8 source/JMap/blend regeneration of `Zero_Final`, `NANG_11`,
and `CN3_Entrance2` is behaviorally unchanged from their previous review
checkpoint.  Zero_Final still yields one outlined SAVE, 212 water-2 cells,
the same block/spike geometry, and no warp or false color object.  An
OCR-enabled retry still returned empty recognized text, so the visible
“You can infinity jump” banner remains an unresolved flag-detection case
rather than justification for a phrase-specific detector.  NANG_11 still
localizes the centered 9x9 island, keeps one save and the gray spiral warp at
`(432,336)`, and rejects the surrounding Floor/TNT/narrator UI.  Entrance2
still keeps two saves, three water-2 cells, and only the supported partial
platform at `(80,464)`.

The regenerated triplets are preserved under
`.artifacts/goal-continuation/flag-room-review/`, and ledger rows 1, 35, and
57 point to those outputs.  This batch supplies a negative result across
three different room/profile paths: no shared missing-object signature was
found, and no implementation change was made.  Zero_Final’s flag remains a
candidate for a future general text/flag subsystem, not a tileset rule.

## Checkpoint: water-tinted apple corpus audit (2026-08-16)

The current scanner was rechecked against the three preserved apple-heavy
screens after an older report appeared to show a missing Halls1 apple.  That
report was stale: the current palette-relative water route detects both
Halls1 water-tinted apples at `(64,248)` and `(48,464)` with the
`apple_water_tinted` kind, alongside the six ordinary apples.  It also keeps
all nine visible apples in CN3_27 and all four in CN3_25, while the existing
neutral-cloud and terrain arbitration continues to reject player-like cloud
silhouettes and background material.

The regenerated source/JMap/preview/blend triplets are preserved under
`.artifacts/goal-continuation/apple-family-review/`, and ledger rows 19, 21,
and 44 now point to them.  This is a held-out confirmation of the existing
relative-color/contour rule across cyan water, red outlined terrain, and
bright mixed rooms; no new threshold or screen-specific exception was
needed.  The 12-pair fixture and FTFA gates remain the protected controls.

## Checkpoint: CN3 Halls2-Halls7 visual corpus regeneration (2026-08-16)

The six Halls screens were regenerated together at the documented grid step
of 8 with color objects, geometry, source/JMap previews, and source/output
blends.  The six current triplets are preserved under
`.artifacts/goal-continuation/halls-review/`, and ledger rows 45-50 now point
to those current artifacts.  All 71 ledger rows still have existing source,
JMap, preview, blend, evidence, and explicit review-status paths; the status
distribution remains 58 accepted and 13 needs-more-work.

This batch did not justify a new scanner rule.  Halls2 changed from the older
artifact by recovering five material-relative partial-block candidates and a
weak right mini-spike on visible edge/partial-tile motifs, while retaining its
SAVE, warp, and background rejection.  Source crops support those candidates
as plausible edge geometry, but there is no corrected giant-review JMap to
call them exact, so the ledger records them as visual-only/uncertain rather
than adding a screen-specific exception.  Halls3 retained two saves, one
warp, and directional gravity objects; its save origins remain phase-shifted
from the older visual artifact.  Halls4 and Halls5 retained their SAVE/warp
classes and rejected background water/refresher impostors.  Halls6 retained
the two terrain-aligned left vines and two-cell water hazard, and Halls7
retained the SAVE, warp, two panel-like platforms, and two source-supported
left vines from the preceding vine-phase checkpoint.  No corrected JMaps
exist for these visual-only screens, so dense spike/block geometry remains
explicitly unresolved rather than being overfit.

The strict FTFA rerun remains **926/928 exact; 0 false positives; 2 missed
edge blocks; 0 shifted; 0 wrong direction**.  The complete tracked fixture
workflow was then completed with the exact grid-8 settings (the first overlay
run exceeded the command timeout; the authoritative retry omitted only
optional overlays).  The current aggregate is saves 22/22 matched (24
detected), warps 12/12, apples 4/4, water 35/35, walljumps 13/13, gravity
8/8, platforms 3/3, mini-blocks 869/875 (1001 detected), blocks 1457/1486,
full spikes 710/748, mini-spikes 281/288, killers 99/99, and refreshers
18/19.  No implementation files changed in this checkpoint; the last complete
unittest result remains 356 tests in 1560.826 seconds, `OK`.

## Checkpoint: CN3 Redcube1-3 and Secret1 material audit (2026-08-16)

Redcube1, Redcube2, Redcube3, and Secret1 were regenerated as one red/
rainbow-material batch under `.artifacts/goal-continuation/
redcube-material-review/` (Redcube1-2) and the existing
`marker-mini-spike-review/` directories (Redcube3/Secret1).  Ledger rows
53-56 now reference current JMaps, SVG reconstructions, and SVG source/blend
outputs; all 71 ledger rows continue to have valid paths.

The source review confirms a stable shared negative result.  Redcube1 keeps
one labeled SAVE, two bright filled-cloud warps, and red patterned terrain;
Redcube2 keeps one SAVE and one warp; Redcube3 keeps three labeled SAVEs,
the red haloed orb and the bright cloud warp.  Question-mark art and the red
terrain are not promoted to cherry, water, or other color-object classes.
Redcube2's current SAVE origin is `(32,96)` instead of the older visual
artifact's `(32,104)`, but no corrected JMap exists to choose between those
phases.  Secret1 remains a useful held-out negative control: its rainbow
gradient, pink striped U-shaped terrain, red directional spikes, and white
cloud-like decoration produce no water or mini-spike promotion.  The weak
Redcube3 candidate beside the right SAVE remains suppressed, while genuine
nearby mini-spikes in Irkara59 and NANG138 remain retained.

No shared invariant failed in a way that justifies another threshold change:
the red patterned terrain, marker labels, clouds, and rainbow background are
already separated by the existing local-shape/material arbitration.  Dense
geometry remains visual-only without corrected giant-review JMaps, so no
screen-specific geometry correction was added.  The prior FTFA, 12-pair
fixture, and full-suite gates remain the protected controls.

## Checkpoint: NANG compact/reverse corpus regeneration (2026-08-16)

NANG_128, NANG_128r, NANG_130, NANG_130r, NANG_131r, and NANG_135 were
regenerated together at grid step 8 with current source/JMap/reconstruction/
blend outputs under `.artifacts/goal-continuation/nang-reverse-review/`.
Ledger rows 58-63 now point to those triplets and retain explicit visual-only
status where corrected giant-review JMaps are unavailable.

The batch confirms the shared palette-relative arbitration across normal and
reverse rooms.  NANG_128 retains both compact green saves, the white spiral
warp, and eight killer blocks, and additionally recovers two visible right
mini-spikes at `(320,288)` and `(320,304)`.  NANG_128r continues to reject the
orange/green trigger squares while retaining its reverse terrain, 13 killer
blocks, and spiral warp.  NANG_130 retains its SAVE, neutral-outline warp,
three blue refreshers, and trigger/star rejection while recovering ten compact
down-spikes and three compact up-spikes from visible runs.  NANG_130r and
NANG_131r retain their reverse SAVE/warp/refresher classes without promoting
triggers, stars, or gravity flippers.  NANG_135 retains its compact SAVE,
spiral warp, and 86 killer blocks; its current save origin is `(160,440)`
instead of the older visual artifact's `(160,448)`, with no corrected JMap to
choose the phase.

The new mini-spike recoveries are treated as evidence of the existing compact
shape route, not as a NANG-specific rule.  NANG138, Irkara59, CN2-5, and the
strict FTFA benchmark remain held-out controls; no protected regression or
shared false-positive signature justified another implementation change.

## Checkpoint: CN3 neon and cyan unrecognized-material regeneration (2026-08-16)

CN3_7, CN3_8, CN3_9, CN3_16, and CN3_18 were regenerated together at grid
step 8 under `.artifacts/goal-continuation/cn3-unrecognized-review/`.
Ledger rows 12-16 now reference the current JMaps, reconstructions, and
source/blend SVGs.  The source review covered the neon floor-number screens,
the cave/cyan tileset, bright cloud silhouettes, repeated vines, water-3, and
the dense stacked mini-spike geometry.

The three neon screens retain their four/three/three labeled SAVE objects and
the observed left-vine strips while keeping floor numbers, clouds, and glow
background out of gameplay classes.  CN3_16 remains stable except for one
older mini-spike at `(768,288)` that is no longer emitted beside a SAVE/right
wall edge; a source crop shows no canonical spike there.  CN3_18 is unchanged:
three saves, the bright cloud warp, four right-vine strips, and five water-3
cells remain, with stretched spikes represented as stacked minis.  This is a
held-out confirmation that the palette-relative material and cloud/number
arbitration generalizes from neon green to cyan cave imagery without a
screen-specific rule.  No corrected giant-review JMaps exist for exact dense
geometry, so the remaining mismatch is explicitly visual-only.

## Checkpoint: Say1-Say4 purple material regeneration (2026-08-16)

Say_1 through Say_4 were regenerated together at grid step 8 under
`.artifacts/goal-continuation/say-purple-review/`; ledger rows 2-5 now point
to current JMaps, reconstructions, and source/blend SVGs.  Direct source review
shows the expected purple terrain, dense white spikes, and two/two/two/one
SAVE markers with no warp or refresher sprites.

Say_1 is byte-for-class stable.  Say_2 keeps both saves and rejects the old
mini-spike at `(384,192)`; current terrain arbitration places the SAVE/start
origins at `(320,224)` and `(704,416)`.  Say_3 keeps both saves while moving
both origins eight pixels up/right from the older visual artifact.  Say_4
keeps its single SAVE and rejects the old `(416,256)` mini-spike, placing the
SAVE/start at `(32,64)`.  These phase differences are recorded as visual-only
uncertainty because no corrected giant-review JMaps exist; they do not justify
a global save shift, and the K3/Irkara controls continue to demonstrate why a
blanket correction would be unsafe.  No generalized implementation change was
made.

## Checkpoint: CN3 platform/vine material batch (2026-08-16)

CN3_19, CN3_21, CN3_25, CN3_26, and CN3_28 were regenerated together at grid
step 8 under `.artifacts/goal-continuation/cn3-platform-vine-review/`; ledger
rows 17-20 and 22 now point to the current JMaps, reconstructions, and
source/blend SVGs.  The source crops and regenerated blend show that CN3_19
contains one real dark horizontal platform bar at `(128,96)`, beneath the
terrain/spike enclosure.  The prior bright-room veto removed it because its
three strong horizontal edge rows were internally bounded but did not span six
sample rows.  The other four screens retain their source-supported saves,
apples, vines, gravity objects, and compact geometry without platform
promotion; CN3_28 remains at zero platforms but has one visible green
right-vine strip that the current scan still misses and is now explicitly
marked needs-more-work in the ledger.

The generalized platform change adds an optional enclosure morphology gate:
bright-room candidates must have either a broad top/bottom span or three strong
rows bounded away from the lower terrain edge.  A lower-edge run alone remains
an impostor.  The synthetic regression covers the CN3_19-shaped internal bar
and rejects a lower-edge-only run.  This is deliberately palette-independent
and uses no screen name or coordinate.

Measured controls after the final rule: CN3_19 platform recall changed from
`0` to `1` source-supported platform; CN3_28, CN3_29, CN3_30, and CN3_31 remain
at zero platform detections.  Irkara-89 retains exactly its one matched
platform (and its prior block result), K3 retains both platform matches, and
FTFA remains `926/928 exact; 0 false positives; 2 missed; 0 shifted; 0 wrong
direction`.

The complete 12-pair fixture workflow was rerun with grid step 8 and tolerance
24.  Its final aggregate is saves `22/22` matched (24 detected), warps
`12/12`, apples `4/4`, water `35/35`, walljumps `13/13`, gravity `8/8`,
platforms `3/3` (3 detected), mini-blocks `869/875` (1001 detected), blocks
`1457/1486` (1590 detected), full spikes `710/748`, mini-spikes `281/288`,
killers `99/99`, and refreshers `18/19`.  No protected fixture regression was
observed.  The remaining giant-review geometry is still visual-only where
corrected JMaps are absent.  The complete unittest suite then passed **357
tests in 1811.266 seconds**, `OK`.

## Checkpoint: palette-relative dark-vine recovery (2026-08-16)

The next unrecognized-material batch adds a generalized dark-vine morphology
route.  It does not learn screen names, fixed room colours, or coordinates.  A
candidate must be a narrow vertical connected component with a 32-pixel-scale
height, green opponent-space dominance over its local ring, and sufficient
relative contrast.  The component is snapped to the 16-pixel sprite phase;
terrain support is then aggregated across the whole component so intermittent
occlusion cannot move individual cells by 16 pixels or flip their orientation.
Existing bright, repeated, split, and clipped-edge vine detections are passed
as anchors, so the adaptive route fills a genuinely missing dark strip instead
of displacing an established exact edge phase.

The source/JTool/blend review and regenerated projects are under the ignored
`.artifacts/goal-continuation/cn3-platform-vine-review/` batch directory:

- `CN3_28` changed from zero detected vines to two source-supported right-vine
  cells at `(512,368)` and `(512,400)`.
- `CN3_29` changed from zero detected vines to two cells for each of the two
  visible dark strips: left-facing `(480,128)`/`(480,160)` and right-facing
  `(768,128)`/`(768,160)`.
- `CN3_30` changed from zero detected vines to three left-facing cells at
  `(64,144)`, `(64,176)`, and `(64,208)`.

These three screens have no corrected authoritative giant-review JMaps, so the
new detections are source-supported visual improvements rather than exact
benchmark claims.  CN3-18 remains an exact protected control after the route's
edge-anchor guard: the full scan emits its four left-edge vines at
`(-16,336)`, `(-16,368)`, `(-16,416)`, and `(-16,448)`.  Halls7 retains its
stronger repeated-strip detections, and the neon CN3-8/CN3-9 material does not
produce dark-vine candidates.  The synthetic geometry tests cover shared
terrain phase and yielding to an existing clipped edge vine.

Measured gates after this change are unchanged: the complete block/spike
workflow reports saves `22/22`, warps `12/12`, apples `4/4`, water `35/35`,
walljumps `13/13`, gravity `8/8`, platforms `3/3`, killer blocks `99/99`, and
refreshers `18/19` matched; FTFA remains `926/928 exact` with zero false
positives, shifts, or wrong directions and the same two boundary misses.  The
full unittest discovery run passes **359 tests in 1879.360 seconds**, `OK`.

At this checkpoint the CN3-21, Golden1, and NR2 strips were still source-visible
follow-up candidates rather than exact truth; the next checkpoint records their
current regenerated outputs.  Corrected giant-review JMaps remain absent, so
the follow-up detections are never treated as exact truth or screen-specific
exceptions.

## Checkpoint: dark-vine follow-up screens (2026-08-16)

The three follow-up candidates from the prior checkpoint were regenerated and
reviewed from current source/JMap/blend outputs.  The same palette-relative
component route, with no new screen-specific rule, now records the following
source-supported cells:

- CN3_21 adds the dark strip in the center-right block cavity as left-facing
  cells `(480,64)` and `(480,96)`, while retaining its eleven established
  right-facing vine cells, two saves, and four gravity flippers.
- CN3_Golden1 adds the green strip at the left of the middle cavity as
  right-facing cells `(96,256)` and `(96,288)`, while retaining its single SAVE
  and rejecting warp/cloud promotions.
- CN3_NR2 adds the lower-center strip as left-facing cells `(352,480)` and
  `(352,512)`, while retaining its SAVE and orange/yellow structural terrain.

Source-versus-blend crops show the sprite side and terrain adjacency agree for
all three orientations.  None of these screens has a corrected authoritative
giant-review JMap, so the cells are visual evidence rather than exact truth.
The ignored ledger now points to the regenerated projects and records the
confidence and limitation explicitly.

Held-out controls remain clean: the selected FTFA screen is `233/235 exact`
with zero false positives, shifts, or wrong directions and the same two
boundary-block misses; the two-pair CN3-18/Irkara-89 control scan retains
walljumps `13/13`, saves `4/4`, apples `1/1`, water `19/19`, and platforms
`1/1` matched.  No implementation change was required after the published
dark-vine route; this was a source/current-output completion and evidence
checkpoint.

## Checkpoint: platform and water arbitration across three materials (2026-08-16)

The pending source/JTool/blend review was completed from freshly regenerated
grid-step-8 projects under the ignored
`.artifacts/goal-continuation/platform-water-review/` directory.  This batch
does not add a scanner rule; it records measured evidence across unrelated
white-brick, striped-cave, and cyan-room materials and keeps visual uncertainty
separate from exact truth because these giant-review screens still lack
corrected authoritative JMaps.

- `CN3_31` retains three source-visible SAVE sprites and three green vines, and
  emits zero independent platforms.  The earlier bright-room gate's
  33-impostor-to-zero result is consistent with the current white/black terrain;
  no platform is promoted merely from a bright horizontal edge.
- `CN3_Entrance2` retains two saves, one source-supported brown platform at
  `(80,464)`, three coherent `water_2` cells, and its established vines.  The
  partial platform survives because local support and enclosure agree rather
  than because of the room name or palette.
- `CN3_Bathhouse1` retains two saves, three vines, and thirteen bounded
  `water_2` cells.  The broad cyan room background and pink decorative/
  trigger-like region remain background, and no platform is emitted.

The regenerated counts are respectively `293`, `347`, and `145` objects.  The
ignored review ledger now points at these current JMaps, reconstructions, and
PNG blends and records all three as `needs-more-work` for remaining visual
geometry only; no screen-specific correction was introduced.

Held-out platform controls were rerun with the documented bundled Python
runtime, grid step 8, and tolerance 24: Irkara-71 remains platforms `5/5`
matched with saves `2/2`, while K3 Ex-Hades remains platforms `2/2` and saves
`6/6`.  Irkara-71's existing water limitation (`26/37`) and extra warp
detections are unchanged and unrelated to this platform arbitration audit.
The live application remains healthy at HTTP 200.  No implementation code or
tracked fixture changed in this checkpoint.

## Checkpoint: generalized red-body SAVE header phase recovery (2026-08-16)

The five CN3-Dotkid screens were regenerated after extending the late,
palette-relative SAVE-header reanchor to the unanchored
`save_red_body_header` family and its terrain-aligned form.  The rule still
requires an already recognized SAVE body, an independent local-contrast header
run, and a movement of at most one 8-pixel phase.  It does not use a screen
name, room palette, absolute coordinate, or blanket vertical shift.

- `CN3_Dotkid1`: `(360,568)` -> `(360,560)` and provenance becomes
  `save_header_aligned`.
- `CN3_Dotkid2`: `(48,408)` -> `(48,400)` and provenance becomes
  `save_header_aligned`.
- `CN3_Dotkid3`, `CN3_Dotkid4`, and `CN3_Dotkid5` remain unchanged at
  `(704,96)`, `(96,512)`, and `(544,384)` respectively because their existing
  terrain support already agrees with the header phase.

The source/current/blend triplets are under the ignored
`.artifacts/goal-continuation/dotkid-header-phase-review/` directory and the
ignored ledger now points to them.  Dotkid rings remain `dotkid:1`, trigger-like
colours stay out of the SAVE class, and broad filled green terrain is not
promoted to walljumps.  Corrected giant-review JMaps are still unavailable, so
these are visual improvements rather than exact giant-review claims.

Validation: the new synthetic header-phase regression and the existing muted
and fragmented SAVE tests pass; current exact scans retain CN3-18 saves at
`(224,80)`, `(384,256)`, `(768,368)` and Irkara-89 at `(352,544)`.  The FTFA
benchmark remains `926/928 exact; 0 false positives; 2 missed; 0 shifted; 0
wrong direction`, and the complete unittest discovery run passes **360 tests
in 1979.562 seconds**, `OK`.  No protected fixture or implementation behavior
outside this header-evidence family regressed.

## Checkpoint: neutral-material water and mini-spike negative controls (2026-08-16)

`CN3_92`, `CN3_Redcube3`, and `CN3_Secret1` were regenerated and reviewed from
current source/JMap/reconstruction/blend outputs under the ignored
`.artifacts/goal-continuation/neutral-material-review/` directory.  This is a
measured negative-result batch across a cyan field, dark red patterned terrain,
and a rainbow-gradient room; no palette-only detector rule was justified.

- `CN3_92` retains one bounded filled-cloud warp, the brown/green terrain and
  spikes, and zero water cells.  The large cyan corridors are spatially a
  continuous background field, not bounded water evidence, so broad color
  promotion would be unsafe.
- `CN3_Redcube3` retains three source-visible saves, two bounded warp
  candidates, and the dark red terrain/spikes.  The weak mini-spike candidate
  adjacent to the right SAVE remains suppressed by terrain support; genuine
  nearby mini-spike fixture controls remain protected.
- `CN3_Secret1` retains its striped enclosure and eight directional spikes but
  emits no water or mini-spikes.  The gradient and cropped red geometry are
  explicitly unresolved visual material rather than evidence for a new
  palette-specific rule.

The regenerated object totals are `351`, `225`, and `25` respectively.  All
three remain `needs-more-work` because corrected giant-review JMaps are absent;
their ignored ledger rows now point to the current PNG blends and record the
negative evidence.  No implementation code changed in this checkpoint.

## Checkpoint: reconnect-safe Zero_Final and NANG_11 held-out review (2026-08-16)

The first post-reconnect held-out batch was rechecked from the preserved source
screens and the current grid-step-8 source/JMap/reconstruction/blend outputs.
The earlier `{"detail":"Bad Request"}` transport error left no tracked partial
write; the repository checkpoint and these ignored artifacts are intact.

- `Zero_Final` remains a deliberately conservative blue/cyan result: one
  outlined SAVE, 212 coherent `water_2` cells in the lower cyan field, the
  established spike/block geometry, and no warp or false color-object promotion.
  The deep-blue particles and glowing instructional text remain background. No
  OCR text was available in this environment (`tesseract` is not installed), so
  `infinitejump` remains `0`; this is an optional OCR limitation, not evidence
  for a phrase-specific detector. Eleven structural warnings and the absence of
  a corrected giant-review JMap remain explicitly unresolved.
- `NANG_11` remains a successful embedded-room localization: the centered 9x9
  island produces 14 terrain blocks, one labeled SAVE at `(320,384)`, and one
  gray-outline warp at `(432,336)`, while Floor/TNT/narrator UI and red-brick
  halos stay outside object classes. The 14 terrain cells remain visual-review
  material because no corrected giant-review JMap exists.

The original blend-preview files in this local batch are SVG markup stored with
`.png` names. They were rasterized to explicit `*-blend-raster.png` review
copies, and the ignored ledger rows for Zero_Final and NANG_11 now point to
those actual raster files. No implementation code or tracked fixture changed.

As held-out platform controls, the current post-arbitration scan emits zero
platforms for Irkara-49, Irkara-49-warp, and Irkara-58; it preserves Irkara-71
at 5/5, Irkara-89 at 1/1, and K3 Ex-Hades at 2/2. This confirms that no new
platform threshold is justified by the Zero/NANG visual uncertainty. The live
application remains HTTP 200.

The complete tracked 12-pair block/spike fixture workflow was also rerun with
grid step 8, color objects, geometry, tolerance 24, and overlays.  It matched
all saves `22/22`, warps `12/12`, apples `4/4`, water `35/35`, walljumps `13/13`,
platforms `3/3`, gravity flippers `8/8`, killer blocks `99/99`, and matched
refreshers `18/19` (18 matched).  The broader geometry totals remain the known
stress-corpus baseline: mini blocks `869/875`, blocks `1457/1486`, full spikes
`710/748`, and mini spikes `281/288` matched.  The report is preserved under
`.artifacts/goal-continuation/reconnect-zero-nang-block-spike/`.

The complete unittest discovery run against this checkpoint passed **360 tests
in 1863.540 seconds**, `OK`.  The exact FTFA rerun remains `926/928 exact; 0
false positives; 2 missed; 0 shifted; 0 wrong direction`.
