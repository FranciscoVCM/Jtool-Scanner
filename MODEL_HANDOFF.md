# JTool Scanner: model-to-model handoff

**Start here when taking over the project.** Checkpoint: 2026-11-21.
This is a continuation guide, not a new task or a claim of scanner completion.
The existing Windows checkout is `C:/Users/corvo/Documents/Jtool Scanner`,
branch `main`. Reuse it. Do not clone, create a worktree, or clean the
checkout as part of resuming. Since 2026-11-21, larger changes go on a
named branch in this same checkout (the user's request) and are merged into
`main` after validation. Check `git branch --show-current` when resuming.

## Current checkpoint (keep this block current; newest state only)

- **Agent:** Claude Code took over from Codex on 2026-11-21 (Codex's last
  session ended mid-step; no tracked files were left modified).
- **Interrupted Codex step, now recovered:** v2082 rail-end reserve
  preflight. `preflight-rail-reserve-v2082.py` (private, under
  `.artifacts/general-recognition-20261014/`) rendered six original +
  ordinary-terrain contact sheets for 29 rooms without reading the held
  rule. Claude reviewed all six sheets and **closed it with no compatible
  reserve** (details under "Resume here"). The script was edited after
  its first four sheets; that earlier version is lost (those four are
  native-grid CN3 rooms).
- **Policy change:** quality now outranks speed; see
  [PERFORMANCE_POLICY.md](PERFORMANCE_POLICY.md) (2026-11-21).
- **Validation (2026-11-21):** full `unittest discover` at `e5a342e`:
  1,896 tests in 50 min, 1 failure. `test_only_qualified_source_selectors_are_enabled`
  had a stale allowlist that omitted three later qualified releases
  (`779dda7`, `3c287b9`, `72eeba1`). The allowlist is now fixed. The
  activation and feature-profile tests pass (19/19). At `13bf72b` the
  full serial suite passes 1,896/1,896 (49 min). The new parallel runner
  passes 1,896/1,896 in 8 min, and the fast tier passes 1,711 in 25 s.
  The app was not running, so the loaded fingerprint is unverified.
- **Branch `tooling-fast-tests`:** adds `scripts/run_tests.py` (parallel
  runner plus fast tier), `scripts/skin_render.py` and
  `scripts/skin_benchmark.py` (synthetic cross-skin benchmark using the
  private 473-skin archive). This is evaluation tooling only; the
  scanner's behaviour is unchanged.
- **Direction (user, 2026-11-21):** fix mistakes that recur across many
  screens first, using the benchmark, the reference maps and
  `local_corpus/user-reviewed-20261001/USER_REVIEWS.md` together. The most
  frequent families: impossible overlaps (blocks in spike formations,
  spikes on blocks, saves, warps or numbers, minis inside spikes), phantom
  spikes in gaps, missed half-hidden spikes, and minis used where full
  blocks belong.
- **Held-improvement ledger draft:** private
  `HELD_IMPROVEMENT_LEDGER_DRAFT_v2083.md`, built from audit216 prose
  only. Its receipts are not yet re-authenticated.
- **Uncommitted work:** none beyond what the latest commit describes.
  Private session receipts: `.artifacts/claude-session-20261121/`.
- **Next action:** see "Resume here" below.

## Switching agents (Claude Code ⇄ Codex)

Only one agent works in this checkout at a time.

**Incoming agent, before any edit:** read this file, the top of
`NEXT_THREAD_HANDOFF.md` and `.codex-notes/MODEL_RESUME_LOCAL.md`; run
`git status --short --branch`, `git rev-parse HEAD`, `git ls-remote origin
refs/heads/main`, `git worktree list`; list the newest files in
`.artifacts/general-recognition-20261014/` (the folder holds >13k files,
so sort by time instead of listing it whole) and compare them to the
checkpoint above. Anything newer than the checkpoint is unfinished work:
classify it as complete, partial or failed before continuing, and record
that here.

**Outgoing agent, before a planned switch or at each meaningful
checkpoint:** update the checkpoint block above (state, completed,
remaining, validation actually run with results, uncommitted files), the
top of `NEXT_THREAD_HANDOFF.md`, and the private index. Commit reviewed
public files only.

**If an agent stopped unexpectedly:** do the incoming steps, read the
diffs and partial outputs, and decide from evidence. Do not assume an
unrecorded result succeeded or failed.

**Rules for both agents:**

- Commits use the repository owner's existing Git identity (check
  `git config user.name`/`user.email` and the result with
  `git log -1 --format='%an <%ae> | %cn <%ce>'`). No AI author,
  co-author or generated-by trailers.
- Stage explicit paths only; never `git add -A`/`git add .`. Before
  committing, `git check-ignore -v .codex-notes/MODEL_RESUME_LOCAL.md`
  must report a rule, and `git ls-files -- .artifacts .codex-notes
  local_corpus` must print nothing.
- Private evidence (`.artifacts/`, `.codex-notes/`, `local_corpus/`,
  screenshots, JMaps, review indexes, transcripts) never goes to GitHub.
- Tests and gates depend on private local evidence. If some is missing,
  stop and ask for it. Never regenerate, guess, or replace it, and never
  weaken or skip a test or gate to work around its absence.
- Do not report an experiment, test run or release as successful
  without its receipt. Preserve failed and interrupted receipts.

## Reading order and authority

1. Read this file for scope, present state, and the next decision.
2. Read the top of [NEXT_THREAD_HANDOFF.md](NEXT_THREAD_HANDOFF.md) and
   [DEVELOPMENT_PROGRESS.md](DEVELOPMENT_PROGRESS.md). Their lower entries
   are historical, even when they say “latest” or name a worker PID.
3. In the same workspace, open the ignored
   `.codex-notes/MODEL_RESUME_LOCAL.md`. It locates the exact goal plan,
   current 71-room audit, source receipts, former failures, and unrun
   next experiment. The public Git repository intentionally lacks that
   private data. With a different checkout, ask for an authorized copy of
   required evidence rather than silently filling in missing comparisons.
4. Use [README.md](README.md) for commands, [HANDOFF.md](HANDOFF.md) for the
   long-form architecture and corpus inventory, and
   [CROSS_TILESET_PLAN.md](CROSS_TILESET_PLAN.md) for dated research decisions.
   [PERFORMANCE_POLICY.md](PERFORMANCE_POLICY.md) overrides older timing caps.

For what runs now, trust current source, tests, manifests, Git, live app
health, and authenticated results over prose. For object truth, prefer
explicit human corrections and the original source; a corrected JMap
is an evaluation reference, not an inference input. Do not reopen the
whole historical transcript or the copied image archive.

## Product and architecture

The app converts IWBTG-style fangame screenshots into editable JTool maps.
Load an image, choose Standard or Experimental source geometry, scan, review
**Source** (original), **JTool** (typed reconstruction), and **Blend**
(aligned overlay), correct the draft, save a `.jscan.json` project, then
export a `.jmap`. Do not overwrite users' existing projects on rescan.

- `jtool_scanner/scanner.py`: capture framing, native and compact room
  normalization, candidates for terrain/hazards/color objects, arbitration
  and source-based recovery. A `ScanResult` carries typed objects, their
  provenance and scores, framing, gameplay flags, and structural warnings.
- `scripts/source_*.py`: reusable pixel sampling, material, geometry,
  ownership and recovery evidence. Some are deliberately offline.
  `jtool_scanner/runtime_sources.py` lists the transitive runtime helper
  files. A helper in Git is not necessarily called by the scanner.
- `jtool_scanner/app.py` and `jtool_scanner/web/`: localhost HTTP and
  the correction UI. `correction.py` stores stable object IDs and edit
  history and generates the review views; `jmap.py` handles map I/O.
- `jtool_scanner/corpus.py`, `benchmark.py`, and
  `scripts/corpus_case_comparison.py`: resumable scans, strict JMap scores
  and read-only checked before/after comparison. Evaluate references only
  after scanning. Do not treat structural warnings as object truth.

The editor/map layer represents full and mini blocks and spikes (four
directions), killer terrain, platforms, water variants, vines/walljumps,
saves, warps, cherries, gravity flippers, jump refreshers, starts and
other objects in `constants.py`. A supported map object does not imply
reliable detection on every skin. Native `(x,y)` starts at the room's
top-left and increases right/down; it is not screenshot-pixel position.
The typical room is 800×608 with 32px full tiles and 16px mini tiles.
Respect genuine 800×600 bottom clipping and fractional capture transforms.
Unknown/cropped/padded pixels are not evidence for background or objects.

## Current goal and status

**General recognition and source-complete geometry** is the working name
of the 2026-10-28 replacement goal. Its anchor is
`791b05edc13ba217350600d5719e6524f5d3d7dc`; that is not today's HEAD.
The goal was `usageLimited` when this handoff was first written and
was then explicitly resumed. It is **active and unfinished**, not
completed, user-paused, replaced, or marked blocked. Recheck platform
status when resuming; do not create a replacement if the panel is absent.

The purpose is transferable recognition across unfamiliar sprite art,
tilesets, backgrounds, lighting and capture scale. The 71 scenes supply
evidence and help prioritize real errors. Perfect universal scanning is
the long-term direction, not a promise made by this milestone.

Preserve the full completion contract, not the easiest successful subset:

1. Ship new gains in at least **three canonical rooms** across at least
   **two materially different visual families**, including at least one
   compatible prospectively reserved positive success. A qualifying
   room has at least two real corrections, at least 25% fewer frozen
   actionable errors, no source-positive loss and no new known negative.
2. Recover/correct at least **eight independent real objects across two
   rooms** and correct/remove at least **four false conflicts or background
   objects**. Do not count repeated passes, old gains, or equivalent
   block/miniblock tessellation as new physical recoveries.
3. Preserve the original 41 protection groups, 601 source miniblocks,
   139 terrain footprints, CN3-7 mask, rail/phase/hollow/compound,
   ordered metadata and genuine occlusions. Protect all 16 exact controls,
   including FTFA at least 926/928 with no extras/shifts/wrong directions;
   Flames at least 254 exact and no more than 42 extras, 19 misses, 20
   shifts or 2 wrong directions. Run focused checks, independent
   whole/every-delta visual QA and final complete unittest discovery.
4. Measure valid quiet serial AC whole-scan cost in dense, sparse and
   heavier affected rooms, at least two samples per mode per source,
   same source/options/selectors/dependencies and complete outputs.
   Since 2026-11-21 quality has priority: up to +50% for verified
   improvement, +50–100% for big documented gains, above +100% only as
   an opt-in mode (see PERFORMANCE_POLICY.md). Keep past judgments as
   originally measured.
5. Produce **final stable 71+16** outputs and a conservative 71-room audit.
   Use authenticated equivalent outputs only where justified; never
   turn unknown positions into exact matches or "approved."
6. Verify publication on existing `main`, local HEAD equals live
   `origin/main`, clean state, private exclusion, local HTTP 200 and
   loaded/disk fingerprint parity. Verify affected app modes before
   claiming a detector release.

## Progress as of this handoff

| Evidence | What it establishes |
| --- | --- |
| Audit 216 | All 71 rows have current-at-review evidence, zero historical-only pending and **zero whole-room approvals**. They span revisions, not a final stable-build corpus. |
| Goal ledger | Records 53 measured recoveries, 24 false-label corrections, and only **NANG-11 and NANG-139** as qualifying canonical rooms to date. These are ledger measurements, not a blanket claim that every result is live or that another gate passes. |
| Runtime | Last scanner behavior change is `72eeba1`: observed-original-cell guard prevents synthetic compact padding from voting as killer terrain in **Source** mode. Standard mode unchanged for that release. Loaded fingerprint at the verified checkpoint: `f87030612bdd65f2b17d7a75b4a6041a0c8260a6aca08e5afba1472f691608b7`. Later helpers are offline. |
| Tests | Last complete suite recorded **1,794** passing at an earlier checkpoint, not full discovery for this revision. Recent scoped results: 32 visibility and 16 original-detection metadata tests, then four whole-pixel aperture tests. |
| Older releases | Source-specific hollow spikes, Say-1 horizontal SAVE adjustments and fruit-edge conflicts have qualified releases. Gravity-arrow recovery has a separate release and scope. See dated entries for exact boundaries; none fixes all visuals. |

Recent causal work:

- **Rail bodies:** three current paired Source results in audit 210 retained
  seven previous private recoveries (NANG-138r six, CN3-19 one) and withheld
  CN3-21's known slanted spike compound falsely proposed as a block. Seven
  recoveries are not newly shipped. Audit 211's 34 occupied controls found
  no qualifying new transfer. `scripts/source_rail_ends.py` is offline.
- **Partial spikes:** audit 212 reproduced four real prior private additions
  each in Golden2 and Golden5. Frozen compatible Golden3 was **318→319**,
  with only the real half-hidden UP(16,64). Three misses became two, but
  one correction falls short of the two-correction gate. The other two
  reached visible geometry but failed body appearance. Do not tune on
  that reserve or call it unqueried again.
- **Original pixel squares:** audit 213 shows a point outside an occluder
  can still sample a physical square crossing it. Excluding those squares
  explains four of ten Golden5 body phase failures, preserving the four
  passes with the same appearance thresholds. These phases are not new
  detections. Dotkid2 instead fails before body: four possible parent
  walls are not verified, and four other true targets have no parent
  under this solver. Keep its separate two private RGB-bracketing
  recoveries distinct. `scripts/source_partial_aperture.py` is offline.
  Audit 214 then tested the fallback across four complete saved domains:
  197 pending keys through 161 parents, eight old recoveries preserved,
  two alternate phases passing, zero added or lost keys.
- **Other holds:** confirmed false saves in NANG-128 and Halls3 have
  different producers; no marker suppression was shipped from these
  diagnostics. Don't delete real saves or genuine half-hidden spikes
  because they overlap a competing object.

## Resume here

**2026-11-21 (current):** the v2082 rail-end reserve preflight is closed
without a query. Across 29 rendered rooms the only different-art striped
lane with visibly missing bodies is CN3_Secret1, and its upstream rail-body
transfer already qualified 0/167 windows (audit216), so rail-ends cannot
reach it. NANG rooms are the same family as NANG-138r, and Entrance1's rail
is already 36/36. Private note: `RAIL_RESERVE_PREFLIGHT_RESUME_v2082.md`.
Keep `scripts/source_rail_ends.py` offline. Audit216 remains current.

Next step, chosen with quality now prioritised: build a **held-improvement
ledger** from audit216 and its receipts. List each private, source-verified
recovery or removal that never shipped (for example CN3-26 body phase,
CN3-29 false gap spikes, CN3-25 false LEFT, Say-3/Say-9/CN3-7 markers,
rail-body recoveries, the hollow sampling candidate). For each, record its
mechanism, rooms and families, verified gains, and the exact blocker (a
protection failure, a missing maintained port, timing, or a reserve
failure). Then requalify the strongest ones as a group, under the
2026-11-21 budget and every unchanged correctness gate, instead of
searching for more single-room offline mechanisms. Do not rewrite old
verdicts. A blocker that was a protection failure still blocks.

Earlier context, retained as history below:

The frozen v2075 **offline replay finished**. No outputs changed. Both
Halls4 misses are present in the exact 29-key packet and have verified
parents. Each passes all nine visibility phases, but geometry rejects
all nine because fewer than two original edges are observable after
mask projection. Appearance never runs for those cases. CN3-19 also
does not enter the fallback, so it does not establish active false-shape
protection for the new rule. Preserve the old failed reserve verdicts.

Audit215 binds the v2078 passive trace. Across both nine-phase fans
the definite wall covers most of one slope and a neighboring possible
wall envelope covers the base. Ignoring the mask does not establish
independent spike ownership. No detector/output change or recoveries.

Audit216 closes nominal signed-RGB tip transects: one of three reviewed
Golden5 positives qualifies; both confirmed false fragments are outside
the effective CN3-19 pending domain. No reserve query or runtime change.
Next, use original source plus ordinary output to preflight a different-art
positive transfer for the separate v2053 rail-end terrain repair. Freeze
source truth and a genuine compatible reserve before querying the rule.
No release without actual caller verification, source QA, protections
and timing.

Work in bounded causal batches: authenticate current source and output →
freeze truth and reserve → trace actual candidate stage → try a few distinct
original-RGB hypotheses → protect real/false/unknown scenes → run focused
tests and actual callers → independently review whole scene and each delta
→ checkpoint and publish. A true overlap, a larger triangle with its tip
visible, a nonunique solid packing, game HUD text and a decorative visual
effect are different cases. Preserve previously documented user labels.
Recurring open failures include false spikes inside real solid tiles,
wrong directions in compound formations, missed partially visible full
spikes, miniblock/full-size confusion, occasional 16px vine offsets,
false or missing platforms, save/start alignment, warps mistaken for
terrain, and water extent. Keep these as distinct causes rather than
adding a global overlap veto or new per-skin color list.
If a worker is active, poll its existing handle/PID and don't change the
checkout or read live JSON. A timeout is not a failure. Preserve all old
terminal, interrupted and failed receipts.

## Tools and data locations

Use Python 3.12 where available. Pillow is a runtime dependency; pytest is
optional for the documented pytest workflow; unittest comes with Python.
Optional Tesseract supplies OCR, but deterministic fixture and corpus runs
disable it or pass known text. Don't make private NumPy experiments a new
runtime dependency without an explicit maintained qualification.

```powershell
python -m pip install Pillow
python -m jtool_scanner.cli app
(Invoke-WebRequest http://127.0.0.1:8765/ -UseBasicParsing).StatusCode
Invoke-RestMethod http://127.0.0.1:8765/api/health
python scripts/run_tests.py --fast            # iteration, under a minute
python scripts/run_tests.py                   # full suite, parallel; required before merge
python -m unittest discover -s tests -v       # serial equivalent (~50 min)
python -m jtool_scanner.cli benchmark fixtures/regressions/unseen-rooms/ftfa/manifest.json .artifacts/ftfa-check
python -m jtool_scanner.cli scan-corpus path/to/manifest.json .artifacts/corpus-check --resume
python scripts/corpus_case_comparison.py path/to/completed-before path/to/completed-after
```

Use complete raw and explicit feature profiles for both sides of a
comparison. Current profile schema 6 records 12 switches; do not backfill
unrecorded old switches as false. Match source/crop/options/selector and
exports, edit history, ordered metadata and typed multiplicities. Numeric
deltas are not accuracy; inspect Source/JTool/Blend too.

Tracked fixtures live under `fixtures/`. FTFA-1 through FTFA-4 are the
strict golden-room corpus. Lap Around-01 through -12 are individually
identified; corrected JMaps supplied later exist locally and support
provisional exact comparison, not the permanent tracked FTFA gate.
CN3, Irkara, NANG and the other auxiliary cases protect specific
mechanisms. The canonical 71, permanent fixtures and exact 16 overlap
but are not interchangeable. The big image archive and source indexes
are not needed at every startup. Keep `.artifacts/`, `.codex-notes/`,
`local_corpus/`, private reviews, images, JMaps/projects, generated
outputs and transcript out of Git. Preserve unique user corrections and
source identities. Commit and push only reviewed explicit public files
at meaningful checkpoints; docs-only commits don't require an app restart.
