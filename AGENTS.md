# Autorig project guidance

## Git publishing

Standing user instruction: commit and push completed project changes to
`https://github.com/Laiape/autorig_tools.git` unless the user says otherwise.
Follow `.cursor/rules/git-publishing.mdc`. On this machine the active checkout
is `C:/proyectos/auto-rig/autorig_tools`; the parent is a separate repository
that ignores this checkout and must not be used to infer its Git status.

For every rig creation/build/adaptation request, follow the existing module
class and native scene hierarchy described in
`.cursor/rules/rig-module-structure.mdc`. Inspect `arm_module.py` or the closest
existing module; use the shared builder, per-module mechanics/skin/control
groups and a populated `_ENV` skeleton under `rig_GRP/skeletonHierarchy_GRP`.
The flower settings controller uses an F drawing.

For guide placement and fitting, read `.cursor/rules/rig-guide-placement.mdc`.
Use actual anatomical mesh loops and the artist's component selections for
joint centers and facial curves; paired lip/eyelid CV[0] starts at world +X.

Read `how_it_works.md` and the affected area's index before changes. Product
code/docs are English ASCII; user chat is Spanish. Preserve existing local
edits and resolve the loaded Maya checkout before editing runtime code.

For rig systems, deformation, build/startup, LOD or caching changes read
`maya_tools/docs/rig_performance_criteria.md`. Current priorities and accepted
scene startup behavior are in `maya_tools/docs/rig_optimization_roadmap_20261015.md`.
Persistent Cursor rules are under `.cursor/rules/rig-*.mdc`.

Use project skills when applicable:

- `.agents/skills/rig-change-impact/SKILL.md`: large changes and impact estimates.
- `.agents/skills/rig-performance-audit/SKILL.md`: comparable measurements.
- `.agents/skills/rig-deformation-equivalence/SKILL.md`: quality and persistence.

Keep expensive profiling/benchmarks outside normal CREATE RIG. Preserve lazy DG
construction; successful builds adopt the conservative scene evaluation profile.
Do not equate bypassed deformation, inclusive CPU, file payloads and frame time.
GPU/cache acceptance is scene/version/coverage specific and needs a quality gate.
