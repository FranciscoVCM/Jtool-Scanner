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

The screenshot scanner has three layers:

- high-confidence save and warp detection, enabled by default
- conservative color-object detection for apples, water, and walljumps, enabled with `--include-color-objects`
- experimental block/full-spike/mini-spike geometry detection, enabled with `--include-geometry`

Current fixture scan status:

- saves: all Irkara fixture saves are detected and matched
- warps: all Irkara fixture warps are detected and matched, including the cyan-tinted screen 54 warp
- color objects: apples are reliable on current examples; pale/cyan water is matched on current fixtures; catharsis-style dark gray water is conservatively mapped to JTool water 2; walljump vines are recovered with some extra candidates on light green/white rooms
- geometry: the opt-in detector produces useful block and full-spike candidates; outline-heavy rooms get a structural block-recovery pass, ambiguous and block-like full-spike candidates are filtered with outline gates, and block-like mini-spike noise is trimmed but still high on mini-heavy fixtures
- not yet handled: platforms, jump refreshers, gravity arrows, save variants beyond normal saves, and unknown gimmicks

The scanner writes partial `.jmap` files from image detections. Those are meant
as diagnostics for now, not final playable conversions.

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
