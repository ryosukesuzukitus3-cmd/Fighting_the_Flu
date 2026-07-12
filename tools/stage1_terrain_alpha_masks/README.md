# Stage 1 terrain alpha masks

`tools/run.py stage-alpha-mask-editor --stage 1` creates optional per-rect masks here.
The Stage 1 atlas already contains source alpha, so masks are only needed for manual silhouette overrides.

Mask files follow `{group}_{index:02d}_x{x}_y{y}_w{w}_h{h}.png` and must match the source rect size.
