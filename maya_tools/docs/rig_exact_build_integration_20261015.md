# Exact cleanup in normal CREATE RIG

Parent: `maya_tools/how_it_works.md`.
Original saved-copy study: `rig_exact_optimization_results_20261015.md`.
Policy: `rig_performance_criteria.md`.

## Automatic behavior

`AutoRig.build()` now enables exact optimizations for every character/family
using the shared pipeline. The existing CREATE RIG button hot-reloads that
module, so no additional user action or new UI is needed.

Before constructing modules, only the new character's polygon shapes are
eligible for constant point-curve cleanup. Curves must have one key, no inputs,
one point consumer, no custom metadata and no locked/referenced data. Their
current scalar values remain as native point tweaks. Time-driven curves, SDKs,
other meshes and editable artist extensions are retained.

The module pass shares only identical native lip math created by this build.
It does not modify preexisting scene nodes or replace native arithmetic. The
current jaw constructor already shares the accepted corner calculations; that
pass can therefore correctly remove zero additional nodes on a fresh build.
Build reports do not promise a fixed node reduction for every character.

During SKC import, new polygon skins bind only source influences with an exactly
nonzero saved weight. Tiny positive/negative nonzero values are retained.
Driven-weight records, empty/all-zero records and incomplete influence data
fall back to the original binding behavior. Existing skins keep their bindings,
including during weight replacement. Curves/surface mechanics are not pruned.
Facial layers, DQ masks/methods, correctives, PRX and wrinkle presets remain.

This filters the initial joint list; it never calls removeInfluence on a live
skin. The slow post-edit state found in the earlier Edward experiment is not
used as the build strategy. No forced save/reopen, automatic scene replacement,
per-frame Python, Profiler, GPU partition query or benchmark runs in CREATE RIG.

The established construction contract remains: lazy DG, undo disabled and
refresh suspended throughout creation, then Parallel CPU with cache/GPU
override OFF after success. Failure restores the caller's runtime state.
Authored detail settings stay separate from the evaluator profile.

## API and receipts

- `AutoRig.build(..., exact_optimizations=True)` is the normal default.
  `False` is a bounded comparison/debugging opt-out for this integration.
- `AutoRig.import_weights(optimize_new_bindings=True)` selects initial filtering.
- `SkinManager.import_skins(..., optimize_new_bindings=False)` retains its
  previous default for direct callers; the builder explicitly enables it.
- `share_identical_lip_math(..., nodes=created_nodes)` limits ownership. An empty
  list is a no-op; namespaces are supported.
- Build result and existing buildtiming JSON contain `optimizations`: enabled,
  static point-curve count, shared math count and per-new-skin before/after
  binding counts. There is no new standalone logging workflow.

Lossless SKC export, the in-place Bifrost export scope and preservation of an
already matching skin/corrective order were already integrated in the shared
SkinManager; they remain active. Source model/SKC files are not rewritten.

## Measured full-build comparison

Two separately owned Maya 2026 processes rebuilt Edward from the same current
model/guides/build/skin/corrective inputs, with this integration OFF and ON.
All input hashes remained unchanged. Compare this pair with itself, not with
the earlier artist snapshot's file or viewport timing cohort.

Both builds retained 60 output meshes, 852 joints and 58 skins. Across 17
semantic poses, reverse traversal and both wrinkle routes (4,080 mesh samples),
maximum world-position, vertex-normal and joint-matrix differences were zero.
Neutral preparation resets published wrinkleDepth defaults to zero in that
pose set. A separate nonzero detail probe activates depth after pose preparation
to exercise the algorithm rather than relying only on route labels. This is a
validation-only override, never a changed saved preset or build default.

The integrated build baked 5,451 constant point curves and omitted 514 exact-zero
initial bindings in 13 newly imported skins. Body bindings reduced 388 to 40.
This differs from the earlier nine-skin/474-removal saved-copy experiment because
the new import covers every eligible new polygon skin from the current inputs.
The current constructor already shared the lip math, so the final native math
pass removed zero additional nodes. Existing joints and all skin layers remain.

One sequential pair measured 31.3547 seconds OFF and 31.3521 seconds ON for the
complete build. Static model preparation took 1.8577 seconds, and math cleanup
0.0222 seconds, offset by other construction/import differences. This pair
establishes no material observed creation slowdown; it is not a statistical
speedup measurement or an interactive playback/FPS claim. The prior saved-copy
11.88% OFF playback gain is not a universal guarantee for newly built characters.

Nini (biped) and horse (quadruped) also completed normal builds with the default
enabled. These are construction checks; only Edward has the full geometric A/B
coverage in this integration record.

Native regressions: six initial-bind/scope cases, eight exact-cleanup cases,
11 build-lifecycle cases and 20 existing SkinManager integration cases pass.
They cover tiny weights, DQ masks, driven/all-zero fallbacks, existing skins,
namespaces, unrelated nodes, rollback, locked/custom point data and guarded DG.

Native Maya ASCII reopen also passes: position and vertex-normal error zero;
maximum joint-matrix element difference 2.02908e-5, below the predeclared 1e-4
threshold. 58 of 60 outputs show real motion in the exercised poses. The extra
active-detail probe compares 720 mesh samples after neutral preparation, with
manual activation and nonzero local depths/values only in private copies.
It produces 0.824651 units of actual wrinkle displacement and still has maximum
position, vertex-normal and joint-matrix difference zero between variants.
These test overrides are not written to presets, source models or built rigs.

Native source files contain two unsupported UI metadata nodes in this standalone
environment. Their data was retained using Maya ASCII rather than deleting it
to permit a binary conversion. Bifrost standalone menu/publishing-path messages
remain in the raw logs. Neither warning was treated as a numeric quality pass.

Evidence: `maya_tools/docs/validation/exact_build_integration_20261015/`.
Raw owned scene/array files remain in the outer workspace under
`tmp/edward_build_exact_integration_v002/`. The artist session was not rebuilt,
reopened or replaced during this integration.
