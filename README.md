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
```

Start-save policies:

- `auto`: bottom-left region, then left side, then bottom side, then nearest bottom-left
- `bottom-left`: nearest save to the bottom-left corner
- `left`: leftmost save, ties prefer lower saves
- `bottom`: lowest save, ties prefer left saves
- `index:N`: use the Nth save after top-to-bottom, left-to-right sorting
- `nearest:X,Y`: use the save nearest a coordinate
- `none`: do not change existing start objects
