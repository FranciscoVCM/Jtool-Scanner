# Crimson Needle 3 neon rooms

Regression screenshots for floors 7, 8, and 9.

- `floor-XX-source.png` is the fangame screenshot.
- `floor-XX-app-before.png` is the JTool Scanner result before outlined-terrain
  reconciliation.

These rooms use dark block interiors and hollow spikes enclosed by bright
colored outlines. Tests intentionally identify that representation through
brightness contrast and geometry rather than the green hue.

Floor 7 also protects against emitting miniature objects from the sharp
triangular holes inside glowing full-spike sprites. Existing coarse locations
bound source tests; they are not reference answers or blanket overlap vetoes.
