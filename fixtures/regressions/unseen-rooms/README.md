# Unseen Room Regression Corpus

These screenshots capture two initially unseen tilesets supplied during manual
application testing. Source images are retained alongside the scanner output
that exposed each failure. FTFA rooms also include hand-authored JTool
references.

## FTFA

- `screen-1` through `screen-4` contain warm brick terrain, full spikes, saves,
  apples, and water.
- `screen-4` includes both default and brick-skin JTool reference renders.
- Each room includes the hand-authored `.jmap` used for exact evaluation.
- The structural warm-terrain profile is expected to produce no solid
  block/full-spike overlaps.

## Lap Around

- `screen-01` through `screen-12` contain dark grayscale brick terrain and
  bright full-spike silhouettes.
- `screen-01` includes a grayscale warp.
- `screen-02` includes two saves.
- `screen-03` and `screen-11` include lit saves that must remain saves rather
  than outline warps.
- Save/start selection follows the normal bottom-left, left, then bottom
  preference once all saves have been detected.

The `*-scan-before.png` files are diagnostic history, not expected output.

The FTFA `manifest.json` is also the first strict golden-room benchmark. Run:

```powershell
python -m jtool_scanner.cli benchmark fixtures\regressions\unseen-rooms\ftfa\manifest.json out\benchmarks\ftfa
```

The runner produces a self-contained HTML dashboard and exact coordinate/type
metrics. Lap Around and follow-up rooms need one hand-corrected `.jmap` each
before they can join the exact gate; their saved screenshots remain useful
visual regression references until then.

## Follow-up

`follow-up/` preserves six manual application retests as source, JTool, and
blend triplets. Examples 1-3 revisit FTFA alignment and half-width water;
examples 4-5 cover isolated Lap Around orientation/alignment errors; example 6
is the low-contrast particle-water room. The last room is intentionally kept as
a cross-tileset stress case: cyan tile ornaments must not become warps, banner
text and particles must not become terrain, and submerged spikes need real
terrain-face support.
