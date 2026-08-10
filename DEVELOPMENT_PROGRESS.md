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
