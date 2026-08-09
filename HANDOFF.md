# JTool Scanner Project Handoff

## 1. Purpose and target workflow

JTool Scanner turns screenshots of *I Wanna Be the Guy* fangame rooms into
editable JTool maps. The practical target is a useful one-click draft that
needs only small corrections. The longer-term target is approximately 99%
accuracy on unseen rooms, with irreducible visual ambiguity handled by the
correction interface rather than hidden behind false confidence.

The intended user workflow is:

1. Open or capture a PNG of a fangame room.
2. Let the scanner locate/normalize the room, infer its grid, and detect
   JTool-compatible objects.
3. Compare the source with the exact JTool-style export preview using Source,
   JTool, and Blend views.
4. Correct misses, false positives, coordinates, orientations, water choices,
   and start-save selection.
5. Save the editable `.jscan.json` project when the work should remain
   revisable;
6. export a valid `.jmap` and open it in JTool.

JTool remains the target runtime. This project does not attempt to clone its
gameplay engine.

## 2. Repository and current state

- Local repository: `C:\Users\corvo\Documents\Jtool Scanner`
- GitHub: `https://github.com/FranciscoVCM/Jtool-Scanner`
- Branch: `main`
- Implementation baseline documented here:
  `e73ce972f9c1cc2823dd11e52fd2cd29e7657fc7`
- Baseline commit: `Recognize outlined terrain across neon rooms`
- The working tree was clean and the baseline matched live `origin/main`
  before this handoff was added.

The repository has one application package, `jtool_scanner`, plus tracked
fixtures and tests. There is no packaging metadata or lockfile; run commands
from the repository root so Python can import the package directly.

## 3. Architecture and important modules

| Path | Responsibility |
|---|---|
| `jtool_scanner/cli.py` | Command-line entry point for the app, JMap utilities, scans, correction projects, fixture evaluation, report analysis, and exact benchmarks |
| `jtool_scanner/app.py` | Local HTTP server and JSON/PNG/JMap API boundary |
| `jtool_scanner/web/` | Browser correction interface (`index.html`, `app.js`, `app.css`) |
| `jtool_scanner/scanner.py` | Room normalization, OCR hook, object detection, structural reconciliation, recovery, pruning, and scan provenance |
| `jtool_scanner/correction.py` | Versioned `.jscan.json` model, stable object IDs, edit history, project import/export, clean preview, and source blend |
| `jtool_scanner/jmap.py` | JTool 1.3.5 parsing and serialization |
| `jtool_scanner/codec.py` | JTool compact-number encoding/decoding |
| `jtool_scanner/constants.py` | Room dimensions and official object IDs/names |
| `jtool_scanner/save_picker.py` | Automatic and explicit starting-save policies |
| `jtool_scanner/image.py` | PNG decoding and in-memory RGB image representation |
| `jtool_scanner/geometry.py` | Boxes, distances, snapping, and geometric helpers |
| `jtool_scanner/render_svg.py` | Exact JTool-style map rendering |
| `jtool_scanner/render_overlay.py` | Source-image detection/truth overlays |
| `jtool_scanner/evaluation.py` | Tolerance-based fixture matching and aggregate metrics |
| `jtool_scanner/report_analysis.py` | False-positive/miss diagnostics grouped by type, score, grid residue, and other features |
| `jtool_scanner/benchmark.py` | Exact golden-room comparison, localized reviews, baseline regression gate, and HTML dashboard |

The scanner returns a `ScanResult` containing the normalized room, detected
objects, OCR text/settings, and structural warnings. It can produce a direct
diagnostic JMap, but maps intended for editing or play should pass through a
`CorrectionProject`.

## 4. Implemented map and scanner capabilities

The JMap/correction layer accepts every official object ID currently listed in
`constants.py`:

- blocks and miniblocks;
- full spikes and minispikes in all four orientations;
- apples/cherries;
- normal and flipped saves;
- platforms;
- water 1, water 2, and water 3;
- left and right walljumps/vines;
- killer blocks and mini killer blocks;
- bullet blockers;
- player start;
- warps/goals;
- jump refreshers;
- upward and downward gravity flippers.

The map model also preserves infinite jump, dotkid, save type, border type,
player X scale, and player gravity metadata.

Scanner detection is narrower than the editable/exportable vocabulary. Its
implemented detection includes:

- saves, including green/active and alternate visual states;
- multiple warp visual families;
- apples;
- three water choices, including conservative Catharsis-style gray-water
  mapping to water 2;
- directional walljumps;
- gravity flippers;
- platforms;
- full blocks and miniblocks;
- full spikes and minispikes in every orientation;
- killer blocks;
- jump refreshers;
- room crop/grid inference and normalization;
- optional Tesseract OCR for infinite-jump text;
- structural warnings that do not require a reference JMap.

Unknown game-specific gimmicks are intentionally excluded. Objects supported
by the correction model but not reliably detected can be added manually.

## 5. Room normalization and start selection

The canonical JTool room is 800×608 pixels, or 25×19 cells at 32 pixels per
cell. Detection can use 8/16/32-pixel placement.

- Smaller source rooms are centered.
- Odd horizontal space is biased left.
- Odd vertical space is biased down.
- Larger rooms keep the leftmost 25 columns and bottommost 19 rows.
- Common 19×13 rooms are inferred automatically.
- Ambiguous rooms can use `--source-grid COLSxROWS`.

Automatic player-start selection prefers:

1. bottom-left region;
2. left side;
3. bottom side;
4. nearest save to the bottom-left.

The UI and CLI support explicit alternatives (`bottom-left`, `left`, `bottom`,
`index:N`, `nearest:X,Y`, and `none`). The exported player start is placed at
the selected save's exact coordinate.

## 6. Graphical correction interface

Start the graphical workspace with:

```powershell
python -m jtool_scanner.cli app
```

The app accepts:

- a PNG for scanning;
- a `.jmap` for import and editing;
- a `.jscan.json` correction project for continued work.

The interface provides:

- select/move, add, and erase/disable tools;
- 1/8/16/32-pixel snapping;
- object palette for the supported JTool types;
- object type and coordinate editing;
- enabled/disabled export state;
- duplication;
- starting-save selection;
- bulk water replacement;
- infinite-jump setting;
- geometry, color-object, and OCR scan toggles;
- candidate layers with text and confidence filters;
- structural-review warnings;
- undo and redo;
- downloadable correction projects;
- final `.jmap` export.

Disabling a scanner candidate is non-destructive. Stable object IDs, original
detection coordinates/types, source boxes, scores, manual additions, edit
history, metadata, and start selection are preserved in the correction
project.

## 7. Source, JTool, and Blend review

The center canvas has three authoritative review modes:

- **Source:** normalized fangame screenshot;
- **JTool:** clean render of the map that will be exported;
- **Blend:** source and JTool render overlaid for alignment review.

The clean JTool preview and downloaded JMap use the same conversion path. The
preview is therefore the pre-export authority, not a separate approximation.

Diagnostic previews can include stable object IDs and disabled candidates.
Blend and diagnostic views also show source-independent warnings such as:

- unsupported spikes;
- overlapping opposite orientations;
- saves embedded in terrain;
- other structurally contradictory geometry.

The CLI equivalent is:

```powershell
python -m jtool_scanner.cli project-create screen.png out\screen.jscan.json `
  --jmap out\screen.jmap `
  --preview out\screen.svg `
  --diagnostic-preview out\screen-ids.svg `
  --blend-preview out\screen-blend.svg
```

Use `project-summary`, `project-edit`, and `project-export` for scripted
corrections. Use `project-import` to convert an existing JMap into the same
editable project format.

## 8. Fixture scans, exact benchmarks, and tests

There are two distinct real-image evaluation workflows.

### Tolerance-based fixture scans

`scan-fixtures` evaluates a manifest at a configurable positional tolerance.
It can generate scan JMaps, previews, truth-aware overlays, and JSON reports.
Matched detections are green, unmatched detections red, and missed truth
objects yellow/dashed.

Use one representative pair while tuning:

```powershell
python -m jtool_scanner.cli scan-fixtures `
  fixtures\block_spike\manifest.json `
  --pair irkara-nr-partysu3 `
  --include-color-objects `
  --include-geometry `
  --grid-step 8 `
  --tolerance 24 `
  --summary
```

Then run the complete manifest:

```powershell
python -m jtool_scanner.cli scan-fixtures `
  fixtures\block_spike\manifest.json `
  --include-color-objects `
  --include-geometry `
  --grid-step 8 `
  --tolerance 24 `
  --out-dir out\block-spike-scans `
  --overlays `
  --report-json out\block-spike-scans\report.json

python -m jtool_scanner.cli analyze-report `
  out\block-spike-scans\report.json `
  --group full_spikes `
  --limit 8
```

Omit `--out-dir` for faster metrics-only iteration.

### Exact golden-room benchmarks

`benchmark` requires a source PNG and authoritative corrected JMap. It compares
exact type, orientation, X/Y coordinate, and duplicate count. Infinite jump is
checked as map metadata. Player start is intentionally excluded because it is
a correction policy.

```powershell
python -m jtool_scanner.cli benchmark `
  fixtures\regressions\unseen-rooms\ftfa\manifest.json `
  out\benchmarks\ftfa
```

Each room is scanned once. Output includes:

- copied source;
- `detected.jmap`;
- detected and expected SVGs;
- source/detection blend;
- exact error overlay;
- localized `review.svg`;
- localized source review crops and Source/Detected/Expected panels;
- `report.json`;
- self-contained `index.html`.

Gate a candidate against a deliberately retained baseline:

```powershell
python -m jtool_scanner.cli benchmark `
  fixtures\regressions\unseen-rooms\ftfa\manifest.json `
  out\benchmarks\candidate `
  --baseline out\benchmarks\baseline\report.json `
  --fail-on-regression
```

The command exits nonzero if an established room gains exact errors or loses
exact matches. `--pair ID` selects one or more rooms for quick iteration.

### Automated tests

The repository contains eleven test modules covering JMap encoding, correction
projects, app APIs, scanner/color behavior, geometry, evaluation, report
analysis, exact comparisons, structural review, and unseen-room regressions.

The complete intended runner is:

```powershell
python -m pytest -q
```

`pytest` must be installed to collect the free-function benchmark tests.
Most class-based tests can also be run with:

```powershell
python -m unittest discover -s tests -v
```

The bundled runtime initially lacked `pytest`; installing `pillow pytest`
completed the documented environment. The latest isolated full run completed
`308 passed, 46 subtests passed in 562.90s (0:09:22)` with
`python -m pytest -q -p no:cacheprovider`. The temporary directory override is
only needed on this Windows host because its default pytest temp root is not
writable; it is not a scanner workaround.

## 9. Verified FTFA golden corpus

FTFA is currently the strict golden-room corpus. Its manifest is:

`fixtures/regressions/unseen-rooms/ftfa/manifest.json`

All four rooms are individually identifiable:

| ID | Source | Corrected JMap | Expected JTool render | Historical reconstruction |
|---|---|---|---|---|
| FTFA-1 | `screen-1-source.png` | `screen-1.jmap` | `screen-1-jtool.png` | `screen-1-scan-before.png` |
| FTFA-2 | `screen-2-source.png` | `screen-2.jmap` | `screen-2-jtool.png` | `screen-2-scan-before.png` |
| FTFA-3 | `screen-3-source.png` | `screen-3.jmap` | `screen-3-jtool.png` | `screen-3-scan-before.png` |
| FTFA-4 | `screen-4-source.png` | `screen-4.jmap` | `screen-4-jtool-default.png` | `screen-4-scan-before.png` |

FTFA-4 also has `screen-4-cropped-source.png` and the alternate
`screen-4-jtool-brick.png` render. Local current/review output is indexed in
`.codex-notes/IMAGE_CORPUS_INDEX.md`; generated exact benchmark dashboards are
under ignored `out/benchmarks`.

The rooms cover warm brick terrain, full spikes, saves, apples, water,
boundary crops, phase alignment, and multiple JTool visual skins. FTFA-4 has a
saved exact run at 249/249 after correcting reference-map inconsistencies.

The current unmodified FTFA gate reports `924/928 exact`, with zero false
positives, two misses, and two shifted saves. The remaining four mismatches are
known coordinate/reference issues and are retained as review items rather than
silently relaxed.

## 10. Verified Lap Around corpus

Lap Around-01 through Lap Around-12 are individually identifiable:

- source:
  `fixtures/regressions/unseen-rooms/lap-around/screen-NN-source.png`;
- historical scanner result:
  `screen-NN-scan-before.png`;
- local current reconstruction:
  `.artifacts/lap-current/NN.png`.

The corpus exercises grayscale brick terrain, bright spike silhouettes, a
grayscale warp, multiple saves, lit saves, spike orientation, coordinate
phase, and normal start-save selection. Local structural reviews exist for
rooms 01, 02, 03, 05, and 11. Local save crops and montages are preserved
under `.artifacts`.

Lap Around is not yet a strict exact benchmark because corrected JMaps are
still missing for all twelve rooms. Do not present its visual regressions as
exact scores. The tracked follow-up-2 Lap triplet cannot safely be assigned to
a specific Lap Around ordinal.

## 11. Other verified real-image cases

### CN3 and CN3 neon

- **CN3-16:** source/JTool/JMap triple; 501 miniblocks, 54 minispikes, saves,
  and a warp.
- **CN3-18:** source/JTool/JMap triple; 374 miniblocks, 54 minispikes, water,
  walljumps, saves, a warp, and stretched-object approximations.
- **CN3 neon 7, 8, and 9:** tracked source and `app-before` images. They test
  dark interiors and hollow spikes surrounded by bright outlines. Detection
  must use contrast/geometry rather than memorizing green.

### NANG

- **NANG-128:** centered 19×13 room with 13 killer blocks; orange triggers
  remain ignored.
- **NANG-135:** centered 19×13 room with 86 killer blocks; stars remain
  ignored.
- **NANG-138:** centered 19×13 room with 12 jump refreshers and dense
  minispikes; stars remain ignored.

Each has a tracked source, JTool render, corrected JMap, and manifest entry.

### F189, CN2-5, Irkara, and Partysu3

- **F189:** five upward and three downward gravity flippers.
- **CN2-5:** seven jump refreshers with irregular 4/8/16-pixel geometry.
- **Irkara 51:** minispikes, water, walljumps, and saves.
- **Irkara 59:** minispike-heavy sparse-block layout.
- **Irkara Partysu3:** dense 16-pixel miniblock/minispike stress case.
- **Irkara 71:** principal committed platform example, also containing water
  and saves.
- **Irkara Flames:** useful water/apple/solid-geometry example.

Primary object routing:

| Object | Verified examples |
|---|---|
| miniblock | CN3-16, CN3-18, Partysu3 |
| minispike | CN3-16, CN3-18, Partysu3, Irkara 51, Irkara 59 |
| killblock | NANG-128, NANG-135 |
| jump refresher | CN2-5, NANG-138 |
| gravity flipper | F189 |
| save | Irkara corpus, CN3-16/18, alternate red-cross reference |
| warp | Irkara corpus, CN3/NANG cases, blue-cloud/purple-ring/white-outline references |
| water | Irkara 51/52/54/71, Flames, CN3-18, FTFA-4 |
| walljump | Irkara 51, CN3-18 |
| platform | Irkara 71 |

## 12. Follow-up visual-review corpora

`fixtures/regressions/unseen-rooms/follow-up` contains six tracked
source/JTool/blend triplets:

- `example-N-source.png`;
- `example-N-jtool-before.png`;
- `example-N-blend-before.png`;

for `N = 1..6`.

Examples 1–3 revisit FTFA alignment and half-width water. Examples 4–5 cover
Lap-style orientation/alignment failures. Example 6 is the low-contrast
particle-water cross-tileset case.

`fixtures/regressions/unseen-rooms/follow-up-2` contains two more tracked
triplets:

- cyan source/JTool/blend;
- Lap source/JTool/blend.

The cyan/Lap labels and roles are verified by filenames and exact historical
hash matches. The follow-up-2 Lap triplet cannot safely be assigned to a
specific Lap Around ordinal.

## 13. Installation, startup, and health verification

Use a current Python 3 environment. The repository has been exercised with
Python 3.12. Install the runtime/test dependencies explicitly because there is
currently no requirements file:

```powershell
python -m pip install pillow pytest
```

Tesseract is optional. If it is installed and discoverable on `PATH`, PNG
commands can use it for infinite-jump text. Use `--ocr-text` for deterministic
input or `--no-ocr` to disable it.

From the repository root:

```powershell
python -m jtool_scanner.cli app
```

Expected address:

`http://127.0.0.1:8765/`

Verify the page instead of assuming the process started:

```powershell
$response = Invoke-WebRequest http://127.0.0.1:8765/ -UseBasicParsing
$response.StatusCode
```

Expected result: `200`.

The API also exposes:

`http://127.0.0.1:8765/api/health`

with `{"ok": true}`.

Only one app process may bind the port. On Windows the server uses exclusive
address binding so a second process fails instead of splitting requests.

## 14. Scanner-design principles

1. Prefer geometry, topology, repeated structure, edge shape, and neighboring
   support over hard-coded colors or room coordinates.
2. Generalize across palettes, brightness, saturation, backgrounds, and
   recolored variants.
3. Avoid screen-specific patches except as short-lived diagnostics.
4. Treat a detection as a hypothesis; use structural reconciliation and the
   correction project rather than silently baking uncertain candidates into
   the final map.
5. Determine spike orientation from triangle/silhouette geometry first and
   support topology second.
6. A spike normally touches the exposed face of supporting terrain.
7. Large block/spike overlap, unsupported spikes, and contradictory
   orientations are review signals.
8. Saves and apples normally sit above or between terrain, not inside it.
9. A block texture must not turn into many saves, warps, apples, refreshers,
   water tiles, or miniblocks.
10. Text, floor numbers, overlays, stars, triggers, particles, and unrelated
    sprites should remain ignored.
11. Do not infer water from a solid background or gradient.
12. Distinguish warp shape from the kid sprite and decorative rings.
13. Preserve legitimate off-grid 8/16-pixel placement and object phase.
14. Use overlapping fixed-size JTool objects for source extents that JTool
    cannot stretch. An 80-pixel strip uses positions 0, 32, and 48; a stretched
    spike can use aligned minispikes.
15. For ambiguous water behavior, choose the closest visual JTool type and
    expose correction. Catharsis water maps conservatively to water 2.
16. Validate every general rule against all established fixtures, not only the
    room that motivated it.
17. When 16px and 32px material hypotheses coexist, arbitrate with supported
    topology and tracked fixture truth; never suppress a dense miniblock field
    merely because it looks visually busy.

## 15. Known limitations and generalization risks

- Scanner accuracy is substantially better on established fixtures than on
  arbitrary unseen tilesets.
- Palette, brightness, outline style, background gradients, and texture can
  still alter segmentation and classification.
- Geometry precision remains harder than recall, especially for blocks,
  miniblocks, full-spike hypotheses, and minispikes.
- New rooms can still produce false saves, warps, water, refreshers,
  miniblocks, or gravity flippers.
- Saves, warps, refreshers, flippers, platforms, and walljumps have multiple
  game-specific sprite families.
- Water type and gameplay behavior cannot always be inferred from a still
  screenshot.
- Custom gimmicks are not representable in standard JTool and should usually
  be ignored.
- OCR is advisory; game fonts and video overlays vary.
- Dotkid metadata is preserved by the project/JMap model and exposed in the
  web UI. Automatic detection is intentionally conservative and currently
  targets the large visibility-ring convention verified by the five CN3
  dotkid screens; unrelated dotkid visual families may still need manual
  selection.
- Bullet blockers, mini killer blocks, and flipped saves are editable/exportable
  types but are not established automatic-scanner corpora.
- Lap Around cannot be used as an exact gate until corrected JMaps exist.
- Ignored baseline reports are not durable CI gates unless intentionally
  preserved.
- The scanner is large and rule-dense. Changes should be localized,
  regression-tested, and justified with diagnostic yield rather than new
  unmeasured thresholds.

## 16. Remaining work and recommended next steps

1. Create hand-corrected JMaps for Lap Around-01 through Lap Around-12, then
   add a manifest and promote the set to an exact benchmark.
2. Choose and preserve a known-good FTFA benchmark report for
   `--baseline --fail-on-regression`; generated `out` directories alone are
   not durable.
3. Curate the broader named CN3/NANG conversation sources into a local corpus
   manifest. Promote only small, reviewed golden cases to Git unless Git LFS or
   another storage policy is chosen.
4. Preserve unique `.jscan.json` projects that contain manual corrections not
   reproducible from source plus current code.
5. Add packaging/dependency metadata for Pillow, pytest, and optional
   Tesseract setup.
6. Add CI that runs the full test suite and a deliberately bounded exact
   benchmark.
7. Continue improving source-independent segmentation and feature grouping
   across unseen palettes instead of adding coordinate-specific fixes.
8. Measure rule changes across all fixture manifests and exact FTFA rooms
   before accepting them.
9. Extend exact goldens for CN3/NANG/object families where the corrected JMaps
   already exist.
10. Expand dotkid detection only when another visually distinct, reviewed
    marker family is available; keep the existing visibility-ring rule
    conservative.

## 17. Image-corpus policy and verified counts

### Permanent tracked material

There are **127 images committed locally and on GitHub**. Local `HEAD` and live
`origin/main` had identical image sets during the audit. The committed corpora
include:

- 28 block/spike/object-stress images;
- 20 Irkara images;
- 79 regression images, including FTFA, Lap Around, CN3 neon, follow-ups,
  and focused before/after cases;
- 26 corrected/reference JMaps;
- three fixture manifests.

Tracked fixtures, manifests, tests, and documentation are the durable source of
truth.

### Ignored local artifacts and generated output

`.artifacts` contains current reconstructions, correction projects, reports,
overlays, diagnostic crops, scripts, contact sheets, and montages. `out`
contains generated scan and benchmark output. Both trees are ignored.

Most scan JMaps, SVGs, blends, overlays, review crops, reports, and benchmark
dashboards are reproducible from tracked inputs and code. Historical UI
captures and hand-edited `.jscan.json` projects may not be byte-for-byte
reproducible and require separate preservation decisions.

Do not commit generated output merely because it exists. Promote a generated
file only when it has been reviewed and selected as a durable reference.

### Historical conversation images

There are **327 historical conversation images preserved locally and indexed**
under `.codex-notes/conversation-images`.

- **163 have confident semantic identities.**
- **164 remain preserved but semantically opaque.**

The archive and its manifests are intentionally ignored. Do not commit:

- copied conversation images;
- image-audit reports;
- the private transcript;
- `.codex-notes` generally.

The local provenance indexes are:

- `.codex-notes/IMAGE_CORPUS_INDEX.md`;
- `.codex-notes/image-corpus-index.csv`.

They should remain present and ignored.

### Missing and uncertain references

The historical audit found 43 referenced original paths that no longer exist.
They are not 43 demonstrated lost images:

- **34 of 43 missing original references are strongly accounted for** by
  renamed committed Irkara and block/spike fixture material;
- **eight initial concept/reference screenshots remain uncertain**;
- `Zero_Final` is known to correspond to the missing `test1.png`, but no
  surviving copy was found.

FTFA-1 through FTFA-4 are individually identifiable. Lap Around-01 through
Lap Around-12 are individually identifiable. The follow-up-2 Lap triplet is
verified as a Lap review set but cannot safely be assigned to a specific Lap
Around ordinal.

### Preservation priorities

Preserve permanently:

1. all tracked fixtures, JMaps, manifests, tests, and documentation;
2. unique raw source screens that exist only in the conversation archive;
3. unique hand-edited `.jscan.json` correction projects;
4. a selected known-good benchmark baseline if it becomes a regression gate;
5. the image-corpus indexes and an external backup of the ignored historical
   archive.

Do not use `.artifacts`, `out`, a private Codex transcript, or temporary
clipboard paths as the sole durable home of irreplaceable source material.

## 18. Recent relevant commits

From newest implementation baseline backward:

- `e73ce97` — Recognize outlined terrain across neon rooms
- `12ac0ac` — Align fruit previews with JTool coordinates
- `8d56cd1` — Preserve spike phase in cropped room captures
- `dde158b` — Add source-independent scan review
- `b183296` — Add localized scanner mismatch reviews
- `93b2bbc` — Prefer visible spike outlines in ambiguous water
- `658396e` — Align spikes to adjacent terrain support
- `1bdd2f2` — Align warm spike component phases
- `054b23b` — Reconcile block phases and spike orientation
- `4ad0f59` — Preserve spike orientation and separate opposite pairs
- `9360d79` — Recover boundary-clipped spike runs
- `4f5f434` — Add exact golden-room benchmark workflow
- `bd81656` — Improve unseen room alignment and spike orientation
- `8dc7f12` — Generalize unseen room geometry reconciliation
- `c3739e7` — Recognize warm and grayscale room structures
