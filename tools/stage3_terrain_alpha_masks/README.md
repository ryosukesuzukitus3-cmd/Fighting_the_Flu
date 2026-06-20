# Stage3 Terrain Alpha Masks

`tools/run.py stage3-alpha-mask-editor` creates per-rect mask PNGs here.

White pixels are treated as transparent by `stage3-terrain-composer`; black
pixels are kept opaque. Mask filenames include the rect group, index, and source
coordinates so they stay tied to the exact source rectangle they were edited for.
