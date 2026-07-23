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
