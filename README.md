# JTool Scanner

Early prototype for turning IWBTG-style screenshots into JTool maps.

The first usable layer is the `.jmap` core:

- parse JTool `.jmap` files
- export valid `.jmap` files
- move the kid start object to a chosen save
- render a quick SVG preview for visual checks
- render source-screenshot detection overlays for scanner debugging
- scan fixture manifests once per image while producing both metrics and previews

Run from this folder:

```powershell
python -m jtool_scanner.cli summary "C:\Users\corvo\Downloads\jtool 1.3.1\irkara needle 49.jmap"
python -m jtool_scanner.cli normalize-start "C:\Users\corvo\Downloads\jtool 1.3.1\irkara needle 49.jmap" out\irkara-49-normalized.jmap --start-policy auto
python -m jtool_scanner.cli render out\irkara-49-normalized.jmap out\irkara-49-normalized.svg
python -m jtool_scanner.cli dataset-summary fixtures\irkara\manifest.json
python -m jtool_scanner.cli inspect-image fixtures\irkara\irkara-58-game.png
python -m jtool_scanner.cli inspect-image fixtures\irkara\irkara-58-game.png --overlay out\irkara-58-overlay.svg --overlay-labels
python -m jtool_scanner.cli scan-image fixtures\irkara\irkara-58-game.png out\irkara-58-scan.jmap --preview out\irkara-58-scan.svg --overlay out\irkara-58-overlay.svg
python -m jtool_scanner.cli scan-fixtures fixtures\irkara\manifest.json --out-dir out\fixture-scans --overlays
python -m jtool_scanner.cli scan-fixtures fixtures\irkara\manifest.json --include-color-objects --grid-step 8 --tolerance 24 --out-dir out\color-object-scans
python -m jtool_scanner.cli scan-fixtures fixtures\block_spike\manifest.json --include-geometry --grid-step 8 --tolerance 24 --out-dir out\block-spike-scans
python -m jtool_scanner.cli scan-fixtures fixtures\block_spike\manifest.json --include-color-objects --include-geometry --grid-step 8 --tolerance 24 --out-dir out\block-spike-scans --overlays --report-json out\block-spike-scans\report.json
python -m jtool_scanner.cli analyze-report out\block-spike-scans\report.json --group full_spikes --limit 8
python -m jtool_scanner.cli scan-fixtures fixtures\block_spike\manifest.json --pair irkara-nr-partysu3 --include-color-objects --include-geometry --grid-step 8 --tolerance 24 --summary
```

## Conversion and correction workflow

The scanner can now place a versioned correction project between image
detection and `.jmap` export. This is the data model the later visual app will
edit; it is usable from the CLI now and avoids baking false positives into the
map permanently.

Create a project from a screenshot. Color and geometry scanning are enabled by
default for this command:

```powershell
python -m jtool_scanner.cli project-create screen.png out\screen.jscan.json --jmap out\screen.jmap --preview out\screen.svg --diagnostic-preview out\screen-ids.svg
```

Inspect all candidates, or only candidates near a suspicious location:

```powershell
python -m jtool_scanner.cli project-summary out\screen.jscan.json
python -m jtool_scanner.cli project-summary out\screen.jscan.json --list --near 320,448 --radius 48 --include-disabled
```

Apply one or more corrections in a single command:

```powershell
python -m jtool_scanner.cli project-edit out\screen.jscan.json `
  --disable obj-0042 `
  --move obj-0071:336:448 `
  --set-type obj-0090:walljump_right `
  --replace-type water:water_2 `
  --add 352:448:mini_spike_up `
  --start-save obj-0114 `
  --preview out\screen.svg `
  --diagnostic-preview out\screen-ids.svg
```

Export the corrected map:

```powershell
python -m jtool_scanner.cli project-export out\screen.jscan.json out\screen-final.jmap --preview out\screen-final.svg
```

`project-import` can turn any existing `.jmap` into the same editable format.
This is useful for comparing scanner output with the hand-built examples:

```powershell
python -m jtool_scanner.cli project-import existing.jmap out\existing.jscan.json
```

Each object has a stable ID, map coordinates, JTool type, enabled state,
scanner kind/score, source-image box, and original detected state. Disabling an
object is non-destructive, so it can be restored later. Manual additions,
overlapping objects, type/orientation changes, bulk water changes, exact start
positions, and selecting one save among many are all preserved in the project.
The clean SVG represents the exported JTool map; the diagnostic SVG adds object
IDs and red dashed outlines for disabled candidates.

The correction format already accepts every official JTool 1.3.5 object type,
including killer blocks and jump refreshers. Those can be added or corrected
manually now; scanner recognition for them will be trained when suitable screen
examples are added.

The screenshot scanner has three layers:

- high-confidence save and warp detection, enabled by default
- conservative color-object detection for apples, water, walljumps, and gravity flippers, enabled with `--include-color-objects`
- experimental platform/miniblock/block/full-spike/mini-spike geometry detection, enabled with `--include-geometry`

Current eight-room stress-fixture status (24px evaluation tolerance):

- exact color objects: all 19 visible saves, 9 warps, 4 apples, 35 water objects, 13 directional walljumps, 8 gravity flippers, and 3 platforms match with no excess detections; catharsis-style dark gray water is conservatively mapped to JTool water 2
- fixture truth includes the six visible K3 saves, three secondary warps, and one F189 up-flipper omitted from the original practice ports, so genuine screenshot objects are not counted as scanner noise
- regular geometry: blocks, full spikes, mini spikes, and platforms have complete recall across the manifest; all 919 blocks match with 1,039 detections (88.5% precision), including 154/154 F189 blocks with 164 detections
- miniblocks: CN3-16 matches 501/501 with 563 detections and CN3-18 matches 374/374 with 459 detections; all 875 match with 1,022 detections (85.6% precision)
- CN3 objects: both rooms match all saves, warps, visible water, directional walljumps, full spikes, and mini spikes; stretched source spikes are represented by aligned mini-spike runs and walljump strips recover their backing miniblocks
- active saves: green-centered saves are treated as the active state of the same save object
- full-spike precision: all 652 fixture spikes match with 799 detections (81.6% precision); CN3-16 is 30/30 with 43 detections and CN3-18 is 50/50 with 60 detections after separating partial-occlusion recovery from broad axis support and pruning incompatible local orientations
- mini-spike precision: all 209 fixture mini spikes match with 287 detections (72.8% precision); a final color-independent triangle-fill and structural-support pass reduces CN3-16 to 62 detections for 54 truth and CN3-18 to 68 for 54 truth
- remaining precision work is concentrated in geometry hypotheses: full spikes have 799 detections for 652 truth, mini spikes 287 for 209, blocks 1,039 for 919, and miniblocks 1,022 for 875
- not yet handled: jump refreshers and unknown game-specific gimmicks

`scan-image` still writes a direct diagnostic `.jmap`. For maps intended for
editing or play, use `project-create`, correct the stable project, and finish
with `project-export`.

Detection overlays are SVG files that place colored boxes directly over the
source screenshot. They are useful for checking whether a miss is caused by room
cropping, object recognition, snapping, or evaluation tolerance. Use
`--overlay-labels` on smaller examples; dense precision screens are usually
clearer without labels.

For one-off `inspect-image` and `scan-image` runs, overlays are colored by
object group. For `scan-fixtures --overlays`, the manifest `.jmap` is used as
truth: matched detections are green, unmatched detections are red, and missed
truth objects are yellow dashed boxes.

For faster scanner tuning, use `scan-fixtures --pair FIXTURE_ID --summary` on one
or two representative fixtures first, then run the full manifest with
`--summary --overlays --report-json out\...\report.json` before committing.
Omitting `--out-dir` keeps the run metrics-only, which is quicker and avoids
rewriting preview files.

The JSON report includes the run settings, aggregate totals, per-fixture
metrics, artifact paths, unmatched detections, and missed truth objects. Use the
unmatched/missed coordinate lists to tune scanner thresholds against concrete
false positives instead of comparing screenshots by hand.
It also records the detection chosen for every matched truth object, including
its scanner kind and score, so recovery-path true/false yield can be measured.
`analyze-report` summarizes those lists by object group, fixture, type, score,
nearest-distance bucket, snap offset, grid residue, and representative examples.

Start-save policies:

- `auto`: bottom-left region, then left side, then bottom side, then nearest bottom-left
- `bottom-left`: nearest save to the bottom-left corner
- `left`: leftmost save, ties prefer lower saves
- `bottom`: lowest save, ties prefer left saves
- `index:N`: use the Nth save after top-to-bottom, left-to-right sorting
- `nearest:X,Y`: use the save nearest a coordinate
- `none`: do not change existing start objects
