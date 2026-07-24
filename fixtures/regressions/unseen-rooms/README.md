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
