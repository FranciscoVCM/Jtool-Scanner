# JTool Scanner — next-thread handoff

Updated 2026-10-01. Continue in the existing repository at
`C:\Users\corvo\Documents\Jtool Scanner`; do not create another repository,
branch, clone or worktree.

## New human-review intake (BATCH_89)

BATCH_90 now ships the source-only deferred-component retry. Read the latest
DEVELOPMENT_PROGRESS.md and USER_REVIEW_WORKFLOW.md. Say_7 improves 275/302 →
302/302 exact, 47 → 3 errors, with no missing/wrong-direction full spikes.
Its two source/reference omissions remain pending and one mini alias remains;
do not call it perfect. Thirteen ordinary cases were regenerated, only Say_7
changes, and all sixteen regenerated exact-control maps/reports are identical.
The new ignored `71-screen-after-intake-and-deferred-fix.md` under
`.artifacts/user-review-20261001/` contains all human notes with conservative
current evidence. Sixty canonical rooms still have older-code snapshots, not
new certification. The paragraphs below describe the intake baseline/probe;
their “not shipped” wording is historical and superseded by BATCH_90.

All 71 reviews, twelve JMaps and four new images have arrived. Do not ask the
user to repeat them or reopen the archive. Read USER_REVIEW_WORKFLOW.md and
ignored `local_corpus/user-reviewed-20261001/USER_REVIEWS.md`; the same directory
contains verified copies, PROVENANCE.json and reference manifests. The new
ignored `.artifacts/user-review-20261001/71-screen-user-review.md` joins the
complete human review coverage to cached output. It is not independent whole-
corpus certification; the older blank USER_REVIEW.csv is superseded.

`compare-maps` retains strict scoring and adds solid-area comparison. Both Lap
Backwards references and Say_2 match exactly. Say_7 has 47 strict errors but
equivalent terrain; CN3_7 has major terrain loss. A forced offline neutral-
component probe recovers all 82 reference Say_7 full spikes but is not shipped.
Two visible down spikes at (352,32)/(320,64) are absent from the provisional
reference; retain source evidence and await human confirmation, not score hacks.

New development cases: Say_7/CN3_7/ATK2. Keep LapBackwards_2 and Say_1/4/9
separate from tuning; maintain prior reserved CN3_30/NANG_138 checks. The older
handoff below remains useful history, but its request for missing user reviews
is superseded. No all-71 acceptance or universal recognition claim.

## Verified checkpoint

- Before this handoff, `main` was clean and equal to `origin/main` at
  `3b0b910` (`docs: record edge profile scale stress`). This handoff and its
  BATCH_88 progress note are the only intended additions in the next commit.
- The scanner app is already running at `http://127.0.0.1:8765/`; root and
  `/api/health` returned HTTP 200. Loaded-source fingerprint:
  `02b404a4fd48e404ae2481ce783e44b63e555bf3be71b224e2ccd94b076e23da`.
- The latest completed all-71 scan/control checkpoint is BATCH_84/BATCH_87;
  there have been no scanner-code changes since that output fingerprint
  `0308d520c4c1252d60e31820b5813da161010d96cb014ad65f8ba0f65f0410fb`.

## Active objective and safe next step

The active bounded objective is shared block/full-spike/minispike
classification and arbitration that improves source-supported geometry across
different visual families, while preserving true overlaps, all prior gains,
16 exact controls and a no-tuning transfer case. It is not complete and does
not promise universal accuracy. Read these before more implementation:

1. `.artifacts/native-conflicts-20260923/GOAL_PLAN.md` (ignored local plan)
2. `CROSS_TILESET_PLAN.md`
3. the latest BATCH_84–88 entries in `DEVELOPMENT_PROGRESS.md`
4. `.artifacts/native-conflicts-20260923/regions-v1.json`

The BATCH_88 traces for CN3_27/CN3_92 are map-and-metadata-equivalent to
ordinary scans. Bypassing the warm-room route did not change CN3_27's frozen
region (7/12 exact, 5 shifted, 5 extras) and caused 37 additions/33 removals
whole-room. A scalar block-origin peak policy would move 127/149 whole-room
blocks. Both are rejected; do not turn either into a production rule or repeat
the prior scalar/greedy phase experiments. The ignored details are under
`.artifacts/native-conflicts-20260923/batch88-*`.

The current source review provisionally finds the four listed CN3_27 post
blocks visible, the left inner spike present at likely `(88,48)` rather than
the current `(80,48)`, and all eight listed CN3_92 blocks on visible solid
material. The CN3_27 8px spike phase is awaiting the user's confirmation; the
two CN3_92 blocks at `(512,128)` and `(544,128)` share a ledge whose separate
boundaries are less distinct. Do not treat these judgments as exact-map
certification.

The user says they have written visual reviews for about 30/71 rooms. The
current ignored `USER_REVIEW.csv` at
`.artifacts/native-conflicts-20260923/current-71-stable-v1/USER_REVIEW.csv`
still has blank review fields. Ask the user where their notes are or accept
them in manageable batches; do not make them repeat the reviews. Use their
observations to establish complete source-backed structures, separate
development from no-tuning evaluation, and measure true recovery as well as
false detections. Do not rescan all 71 just to resume; reuse compatible
checksummed outputs and review only where evidence requires it.

## Corpus distinctions

- FTFA-1–4 have tracked source images, corrected JMaps and JTool reference
  renders; FTFA remains a strict exact control.
- Lap Around-01–12 have sources, historical scans and ignored current
  scanner-generated reconstructions, but no per-ordinal corrected JMaps or
  verified reference JTool renders. A few Lap source/JTool/Blend triplets exist
  but cannot safely be assigned to those twelve ordinals.
- Many other exact reference/JTool fixtures exist, including Irkara,
  CN3-16/18, NANG-128/135/138, F189, CN2-5 and Partysu3. The CN3_27/CN3_92
  panels in the BATCH_88 review are renders of current detections, not
  independent corrected references.
- JMaps and user labels are offline evaluation material only. Never consult
  room names, hashes, fixed coordinates, palettes or reference answers in the
  production detector; never repair generated maps to improve scores.
- CN3_NR2's down shapes at `(16,512)` and `(48,512)` were explicitly confirmed
  by the user as visual effects, not spikes. Preserve them as negatives.

## Engineering and publication guardrails

Keep all 71-screen statuses conservative; “accepted” or unchanged maps do not
mean exact. Inspect complete changed maps, not only convenient crops. Do not
delete spikes because boxes overlap blocks: real embedded geometry exists.
Require a positive-recovery path and cross-family transfer, not just false
positive suppression. Run focused tests during iteration and affected broad
tests plus all 16 exact controls before publication; measure representative
runtime with map/metadata parity. Keep private notes, copied conversation
images, local artifacts, generated outputs and `.codex-notes` out of commits.
The user has asked for meaningful progress to be committed and pushed; stage
only intentional tracked code/tests/docs and verify the staged file list.
