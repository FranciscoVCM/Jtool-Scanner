# JTool `pat_default` sprite assets

The PNGs in this directory are copied unchanged from JTool's `pat_default`
skin or from its matching default GameMaker sprite frames. The app uses the
original sprite dimensions and origins; it also reproduces the skin's
`killer_idle_color` value for spikes, fruit and killer blocks.

`walljumpR.png` and `walljumpL.png` have a counterintuitive mapping: JTool
places `walljumpR.png` on the left side of a grid cell and `walljumpL.png` on
the right. JTool Scanner therefore maps them to its user-facing Left Vine and
Right Vine names by visible position.

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
