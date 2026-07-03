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
```

The screenshot scanner has three layers:

- high-confidence save and warp detection, enabled by default
- conservative color-object detection for apples, water, and walljumps, enabled with `--include-color-objects`
- experimental block/full-spike/mini-spike geometry detection, enabled with `--include-geometry`

Current fixture scan status:

- saves: all Irkara fixture saves are detected and matched
- warps: all fixture warps are detected except the heavily cyan-tinted warp in screen 54
- color objects: apples are reliable on current examples; water and walljumps are conservative, and blue tile art can still create water false positives
- geometry: the opt-in detector produces useful block and full-spike candidates; mini-spike recall is improving on mini-heavy fixtures but still noisy
- not yet handled: platforms, jump refreshers, gravity arrows, save variants beyond normal saves, and unknown gimmicks

The scanner writes partial `.jmap` files from image detections. Those are meant
as diagnostics for now, not final playable conversions.

Detection overlays are SVG files that place colored boxes directly over the
source screenshot. They are useful for checking whether a miss is caused by room
cropping, object recognition, snapping, or evaluation tolerance. Use
`--overlay-labels` on smaller examples; dense precision screens are usually
clearer without labels.

Start-save policies:

- `auto`: bottom-left region, then left side, then bottom side, then nearest bottom-left
- `bottom-left`: nearest save to the bottom-left corner
- `left`: leftmost save, ties prefer lower saves
- `bottom`: lowest save, ties prefer left saves
- `index:N`: use the Nth save after top-to-bottom, left-to-right sorting
- `nearest:X,Y`: use the save nearest a coordinate
- `none`: do not change existing start objects
