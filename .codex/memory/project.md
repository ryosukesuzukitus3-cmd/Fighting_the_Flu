# Project Memory

## Development Posture

- The user values quality and game feel over rigidly minimizing code changes. Small scoped fixes are good, but do not treat "minimal diff" as a hard constraint when the underlying model is limiting the work.
- When the user questions a structure or asks "is this the right design?", examine the data model before offering local patches.
- For visual/gameplay work, screenshots and captures are important review artifacts. PRs that affect appearance should include before/after or relevant captures when practical.
- The user often directly edits stage JSON. Treat uncommitted stage JSON changes as user work unless explicitly told otherwise.

## Stage Authoring Direction

- Stage3 established the preferred stage production direction:
  - explicit placed terrain pieces as the source of truth;
  - stage-designer palette workflow;
  - terrain atlas rects plus alpha masks;
  - events/enemies editable in the same designer flow;
  - visual composition should match concept art, not just satisfy collision geometry.
- Do not simply copy Stage3's visual style to other stages. Reuse the production workflow, while giving each stage its own materials and silhouette language.

## Tooling Preferences

- Keep `stage-designer` useful for direct user editing. Ergonomics matter because the user will tune placements manually.
- If a tool behavior is keyboard-layout sensitive, prefer checking text/unicode input as well as physical key constants.
- Overlay/debug visuals should be hideable when they interfere with visual inspection.

## Collaboration Notes

- If a memory file or organization change seems useful, suggest it before restructuring `.codex/memory/`.
- Keep final answers concise, but mention tests/checks that were actually run.
