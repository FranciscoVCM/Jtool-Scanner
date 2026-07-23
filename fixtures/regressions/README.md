# Unseen-screen regressions

These screenshots were first scanned through the correction workspace and then
retained to cover failures found during real use.

- `infinite-jump-particle-water.png`: bright background particles and banner
  text must not become geometry; the outlined save and purple warp stay
  distinct.
- `infinite-jump-particle-water-before-fix.png`: correction-workspace blend
  showing the former banner-text geometry false positives.
- `brick-save-impostors.png`: red brick tiles must not be recovered as saves
  or interpreted as miniblocks.
- `brick-save-impostors-before-fix.png`: correction-workspace blend showing
  the former save and miniblock false positives.
- `brick-full-block-reference.png`: JTool reference confirming that the large
  brick tile is one 32px block rather than four 16px miniblocks.
- `brick-focused-jtool-before-profile.png` and
  `brick-focused-blend-before-profile.png`: the remaining broad geometry noise
  before warm 32px terrain reconciliation.
- `brick-focused-source-rescaled.png`: the later full-resolution source used
  to verify warm-room spike pruning and centered 16px-wide water recovery.
- `brick-focused-source.png`: the exact source crop used to verify component
  spike silhouettes, submerged spike formations, narrow water, and the 8px
  bottom-edge terrain offset.
- `brick-focused-jtool-after-profile.png` and
  `brick-focused-blend-after-profile.png`: correction-workspace references
  after save-impostor and broad geometry reconciliation.
