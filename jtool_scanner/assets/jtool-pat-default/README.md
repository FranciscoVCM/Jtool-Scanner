# JTool `pat_default` sprite assets

The PNGs in this directory are copied unchanged from JTool's `pat_default`
skin or from its matching default GameMaker sprite frames. The app uses the
original sprite dimensions and origins; it also reproduces the skin's
`killer_idle_color` value for spikes, fruit and killer blocks.

`walljumpR.png` and `walljumpL.png` are the matching default GameMaker
frames from `source.gmx/sprites/images` and occupy opposite halves of a grid
cell.  Keeping those source frames (rather than a recoloured skin substitute)
preserves the green vine artwork shown by JTool's default object palette.
The upstream save IDs are counterintuitive: ID 16 is `oWalljumpL` with
`walljumpL.png` on the right half, while ID 17 is `oWalljumpR` with
`walljumpR.png` on the left half. The scanner keeps those IDs and sprites
together so exported maps match JTool; the UI presents them as Left Vine and
Right Vine according to the upstream facing direction.

`apple-frame0.png`, `save-frame0.png`, `gravity-up.png`, `gravity-down.png`,
and `save-flip.png` are the corresponding single default frames from
`source.gmx/sprites/images`; the apple and save skin files are animated strips.
The upstream mini-killer-block default is only a 1x1 placeholder, so that one
object intentionally keeps the app's generated preview instead of embedding a
misleading sprite.

JTool is Copyright (c) 2015 Patrick Traynor and is distributed under the MIT
License. The license text is reproduced in `LICENSE`.

The upstream project used for verification is:
https://github.com/patrickgh3/jtool
