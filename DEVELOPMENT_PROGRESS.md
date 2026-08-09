# Development progress

This file records measured implementation checkpoints for the generalized
scanner review. It is deliberately limited to repository and fixture facts;
private conversation archives and ignored image material remain outside Git.

## Checkpoint: 2026-08-10

### Repository and runtime baseline

- Local branch: `main`.
- Local `HEAD`: `8ac66a0` (`feat: generalize scanner across held-out tilesets`).
- The local branch is one commit ahead of the cached `origin/main` ref
  (`acc6883`). No push was performed; the remote network was unavailable
  during verification.
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
