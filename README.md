# JTool Scanner

Early prototype for turning IWBTG-style screenshots into JTool maps.

The first usable layer is the `.jmap` core:

- parse JTool `.jmap` files
- export valid `.jmap` files
- move the kid start object to a chosen save
- render a quick SVG preview for visual checks

Run from this folder:

```powershell
python -m jtool_scanner.cli summary "C:\Users\corvo\Downloads\jtool 1.3.1\irkara needle 49.jmap"
python -m jtool_scanner.cli normalize-start "C:\Users\corvo\Downloads\jtool 1.3.1\irkara needle 49.jmap" out\irkara-49-normalized.jmap --start-policy auto
python -m jtool_scanner.cli render out\irkara-49-normalized.jmap out\irkara-49-normalized.svg
python -m jtool_scanner.cli dataset-summary fixtures\irkara\manifest.json
python -m jtool_scanner.cli inspect-image fixtures\irkara\irkara-58-game.png
python -m jtool_scanner.cli scan-image fixtures\irkara\irkara-58-game.png out\irkara-58-scan.jmap --preview out\irkara-58-scan.svg
python -m jtool_scanner.cli scan-fixtures fixtures\irkara\manifest.json --out-dir out\fixture-scans
python -m jtool_scanner.cli scan-fixtures fixtures\block_spike\manifest.json --include-geometry --grid-step 8 --tolerance 24 --out-dir out\block-spike-scans
```

The screenshot scanner has two layers:

- high-confidence save and warp detection, enabled by default
- experimental block/full-spike/mini-spike geometry detection, enabled with `--include-geometry`

Current fixture scan status:

- saves: all Irkara fixture saves are detected and matched
- warps: all fixture warps are detected except the heavily cyan-tinted warp in screen 54
- geometry: the opt-in detector produces useful block and full-spike candidates across the new stress fixtures, but it is still noisy and mini spikes need more work
- not yet handled: water, walljumps, platforms, apples, and unknown gimmicks

The scanner writes partial `.jmap` files from image detections. Those are meant
as diagnostics for now, not final playable conversions.

Start-save policies:

- `auto`: bottom-left region, then left side, then bottom side, then nearest bottom-left
- `bottom-left`: nearest save to the bottom-left corner
- `left`: leftmost save, ties prefer lower saves
- `bottom`: lowest save, ties prefer left saves
- `index:N`: use the Nth save after top-to-bottom, left-to-right sorting
- `nearest:X,Y`: use the save nearest a coordinate
- `none`: do not change existing start objects
