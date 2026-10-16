# Measured rig optimization roadmap

Parent: `maya_tools/how_it_works.md`.
Criteria: `maya_tools/docs/rig_performance_criteria.md`.
Updated: 2026-10-15. Applies to shared systems, with Edward as measured evidence.

## Current decision

Start every newly built character in conservative Parallel CPU, cache OFF.
Keep authored deformation/detail settings. GPU and cache are optional measured
work profiles, not quality assumptions. Construction remains DG lazy and does
not run the interactive benchmark. Do not rewrite source models for runtime
flags that belong to the Maya session.

The shared builder now stores a root profile marker and applies it at successful
completion. A single after-open callback in AutoRig Tools restores that intent
for marked scenes. Failed builds restore prior runtime flags. No executable
scene script or per-frame callback is stored. Existing unmarked scenes can opt
in with `scene_evaluation.register(root)` followed by `scene_evaluation.apply()`
and a normal explicit scene save; no bulk migration is performed automatically.

Exact Edward follow-up is delivered in `Edward_working_v004.mb`; see
`maya_tools/docs/rig_exact_optimization_results_20261015.md`. The complete scope
includes 47 clothing/accessory meshes among 60 outputs. Conservative cleanup
preserves tested geometry/normals/joints and improves native-reopened CPU
wrinkles-OFF timing by 11.88%. Wrinkles-ON gains are inconclusive. GPU and cache
remain off by default after quality/stability failures. This bounded result does
not mark the Bifrost/backend or full-module rewrite phases complete.

The shared builder now includes eligible constant point cleanup and initial
nonzero-only skin binding, plus a scoped exact native math pass. See
`rig_exact_build_integration_20261015.md`. This prevents unused bindings at
creation rather than running the saved-copy removeInfluence tool on a live rig.
Existing skins, layers, routes and authored detail settings remain intact.
Debug comparisons can use `AutoRig.build(exact_optimizations=False)`.

## Phase 0: durable baseline and small startup cost - implemented

Changed components: `utils/scene_evaluation.py`, `utils/create_rig.py`, and
`userSetup.py`. Shared entry point covers all characters/families using AutoRig.
The profile has no character names, asset disk scan, vertex query, GPU partition
query, viewport redraw, cache fill or benchmark. Its marker is a string attribute
on the existing root, rather than another evaluation node.

Acceptance: different character names/namespaces reopen with the profile;
unmarked scenes remain unchanged; repeated registration/startup is idempotent;
construction callbacks do not override lazy DG; failure restores runtime state;
animation/frame/selection and authored geometry remain unchanged. Record actual
settings-only overhead separately from a full build or its final viewport draw.
Evidence goes in `maya_tools/docs/validation/scene_evaluation_20261015/`.

Verification: 8 native scene-profile tests and 11 build-lifecycle tests passed
in Maya 2026. With the GPU evaluator loaded, registering/applying the small
fixture took 1.21 ms; settings-only application in the open Edward artist scene
took 0.29-0.55 ms in three samples. These exclude the existing final redraw,
graph evaluation and a complete rebuild. No full-build speedup is claimed.

## Phase 1: choose work profiles per scene - measured, CPU retained

Compare Parallel CPU, GPU and cache against accepted geometry using the real
shot and control edits. Edward's current snapshot supports CPU posing (~41 ms/f
without wrinkles) and hot replay (~21/23 ms/f OFF/ON) in the tested scope. Its
uncached GPU collar error prevents making that mode the shared default.

Investigate the two collar PRX under CPU/GPU, bind/rest data and evaluation
order in an isolated copy. A requested GPU block did not establish a verified
partition or fix the error. Do not relabel that trial an approved hybrid.

Acceptance: matching topology and <=1e-4 scene-unit maximum error on relevant
outputs; held-out body/face/clothing poses; common edits and mode invalidation;
cache fill/memory reported separately. A fast hot replay does not certify
faster posing. Recheck evidence after code, topology or settings changes.

## Phase 2: make optional detail truly optional - high priority

Keep the existing explicit primary/detail routing. Validate Animation bypass
with Profiler and consumer checks, rather than zeroing Envelope. Re-enable
wrinkles without stale data and preserve the final export output.

Profile Maya-to-Bifrost and Bifrost-to-Maya transfers separately. Prototype one
conversion/compact-array/compiled-adapter change at a time against the exact
procedural result. Reuse correct-stage normals only when shading remains valid.
Consider shader microdetail only for folds that do not alter silhouette,
contact, collision or required export geometry.

Acceptance: heavy compute absent in Animation, nonzero correct detail in Final,
native reopen and preset/SKC round-trips, median/p95 gain beyond reference drift.
No measured percentage improvement is promised before the prototype exists.

## Phase 3: modules and clothing - exact cleanup delivered, deeper work pending

Inspect the dominant paths inside jaw, eyelid and eyebrow, using the saved
per-node Profiler attribution. Reduce repeated space/matrix/surface calculations
where measured critical-path work supports it. Keep controls, IK/FK, SDKs,
joint orientation, scale conventions and contact behavior intact.

Profile the 23 PRX by garment and driver. Test a smaller driver only for a costly
branch; retain the high-head source until a contact proxy actually passes. The
generic low-head collar proxy previously failed, so it is not the default.
Avoid adding body/facial/wrinkle intermediate meshes merely to reduce node
counts: the final routing audit found no stable speed advantage.

Acceptance: all affected sides/modules exercised; equivalent contact and shape;
one candidate at a time with interleaved references. Inclusive CPU and bypass
deltas locate work but are not a promised reduction in frame time.

## Phase 4: facial layers and package size - exact data cleanup delivered

Retain the low LOD when useful. Its four skins add serialized data; removing
them while hidden did not show a stable speedup. If a high-only render package
is needed, remove only low-owned geometry/deformers in a derived copy and
compare two native saves to measure real file savings.

Study skin consolidation or weight pruning only when the critical path warrants
it. High mouth uses up to 27 actual influences and low mouth up to 33, despite
a maxInfluences setting of five. DQ/local spaces and sequential layers make
blind merging/pruning a deformation change. Fit on separate poses and validate
held-out transitions before accepting a compact delivery rig.

XGen serialized payload is about 99 MiB in isolation, with overlapping stored
mesh data possible. Test an animation package without unnecessary groom data
and retain the render source. The scalp's 5,451 one-key point curves are data
cleanup candidates, not a proven FPS bottleneck. Do not delete them from the
authoring model without preserving points, topology and XGen consumers.

Acceptance: actual complete-scene file/load comparison; exact final deformation
and groom where required; no sum of overlapping exports presented as savings.

## Phase 5: regression acceptance and delivery

Use the existing Test Rig and package workflow. Store clean wall timings,
separate profiles, quality arrays and scoped decisions with input/code hashes.
Require native reopen, two builds and relevant data round-trips for structural
changes. Keep build cost, interaction latency, p95 playback, RAM and file size
as separate budgets. A quality failure rejects a speed improvement.

Scope each result to scene version, hardware, settings and workload. Preserve
rejected/inconclusive trials so future work does not repeat failed approaches.
The 2026-10-14 regional scene and the 2026-10-15 artist snapshot are different
lineages; neither one's cache result approves or invalidates the other globally.

## Historical context

`maya_tools/docs/rig_performance_plan.md` retains the research and initial phase
design. `maya_tools/docs/rig_performance_results.md` records the regional v002
implementation and its earlier cache failure. The later snapshot summary is
`maya_tools/docs/validation/edward_audit_20261015/summary.json`; full local trial
scenes, raw timings and the PDF live in the outer workspace's experiment/output
folders. The current criteria and this roadmap take precedence over older
blanket GPU/cache statements.
