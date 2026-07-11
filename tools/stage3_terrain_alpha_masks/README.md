# Stage3 Terrain Alpha Masks

`tools/run.py stage-alpha-mask-editor` creates per-rect mask PNGs here.
The old `stage3-alpha-mask-editor` command name is kept as a compatibility alias.

White pixels are treated as transparent by `stage-terrain-composer`; black
pixels are kept opaque. Mask filenames include the rect group, index, and source
coordinates so they stay tied to the exact source rectangle they were edited for.

Use `--stage 3` for these masks. The old `stage3-terrain-composer` command name
is kept as a compatibility alias.
