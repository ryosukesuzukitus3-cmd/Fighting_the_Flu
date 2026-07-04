# Roadmap Memory

Last updated: 2026-07-04

## Current State

- Stage3 is broadly finished for the current pass.
- Stage3 authored layout was committed directly to `main` as `9963291 Tune stage3 layout`.
- The Stage3 designer/tooling PR was merged and cleaned up.

## Next Recommended PR

1. Generalize `stage-designer` / composer workflow beyond Stage3.
   - Goal: make the Stage3 production workflow usable for Stage2 first.
   - Prefer a practical first step over a sweeping rewrite.
   - Expected shape: stage-specific background, rect definitions, mask directory, and terrain layout can be selected or inferred.
   - Preserve Stage3 behavior while enabling Stage2 authoring.

## PR Sequence After Generalization

1. Stage2 visual asset and block set introduction.
   - Cyber tone from the selected concept direction.
   - Background and terrain should separate clearly.
   - Avoid overly strong/bright background colors that compete with gameplay.
2. Stage2 placement and gameplay pass.
   - Use the designer to build explicit blocks, props, events, enemies, gates, and rewards.
   - User may tune balance directly in JSON/tool.
3. Stage1 visual asset and block set introduction.
   - Organic blood-vessel direction.
   - Keep gore restrained.
   - Include red blood cell flavor and blood clot/gate language.
4. Stage1 placement and gameplay pass.
5. Stage4 route/道中 visual and terrain pass.
6. Stage4 final boss room and final presentation pass.

## Sequencing Rationale

- Stage2 comes first because its hard cyber/fortress material language is closest to Stage3's tooling path, making it the best proving ground for generalization.
- Stage1 should come after Stage2 because it needs a more organic asset language and should not inherit a hard block look by accident.
- Stage4 should come last because route, boss room, and final presentation are more tightly coupled and likely to cause more rework if started before the tooling is stable.
