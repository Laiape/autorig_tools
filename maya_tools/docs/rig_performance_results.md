# Autorig and Edward performance implementation

Parent: `maya_tools/how_it_works.md`. Research and requirements:
`maya_tools/docs/rig_performance_plan.md`.

This record concerns the regional v002 lineage and its captured workload. The
later 2026-10-15 artist snapshot is a different scene: its hot cache matched CPU
in the tested frame/key-edit scope, while uncached GPU differed in the collars.
Do not generalize either result to every Edward version. Current decisions:
`maya_tools/docs/rig_performance_criteria.md` and
`maya_tools/docs/rig_optimization_roadmap_20261015.md`.

Build startup and crash corrections, optional audit behavior, model cache and
all-character build timings are documented in `maya_tools/docs/build_performance_results.md`.

## Delivered behavior

Edward's working scene is `maya_tools/assets/Edward/scenes/Edward_working_v002.mb`.
The original v001 is preserved. Rebuild data uses `Edward_v068.skc` and
`wrinkles/Edward_v002.wrinkles.json`. Open through `scripts/open_edward.py` to
resolve textures in the current checkout and start with Cached Playback off.

Wrinkles modify the original displayed head. No second full-face output is
created. The graph displaces 2,638 of 11,475 vertices (22.99%); compression uses
3,866 vertices (33.69%) including two exact smoothing support rings. Runtime
flow/mask/rest arrays are compact; full editing fields remain on the settings
node for presets and SKC. Full topology, UVs and input/output normal processing
still cross the Maya/Bifrost conversion boundary: this is not a regional mesh
island with a different vertex order.

Integer arrays store indices plus one so index zero survives native Maya save.
Local controls, authored Depth 1.2, CompressionStart 0 and region settings are
preserved. Compact editing regenerates support rather than silently dropping
newly assigned vertices. Empty support, Undo, replacement and native reopen pass.

Test Rig now switches Animation / Review / Export through explicit transactions.
Animation displays the low mesh and routes the high output to primary geometry;
Review and Export restore final wrinkles. Garment consumers receive primary high
geometry through an owned world-space adapter. Mode changes do not rebuild the
graph every frame. Export disables Cached Playback. Wrinkle Regions exposes an
explicit regional migration action; existing presets remain compatible.

SKC export temporarily exposes primary skin outputs and original garment-driver
connections, then restores all connections and artist state. Without this step,
Maya's skin API missed the eight high-head layers behind the Bifrost output.
The complete export preserves eight high and four low head skins.

## Evidence and practical limits

Interactive Maya 2026 / API 20260303, RTX 5060 Laptop GPU, OpenGL VP2, 1,319 x 797
perspective viewport, smooth shading, textures/shadows off. The workload is a
48-frame sequence of ten complete body/face combinations, with real time curves,
one warm pass and three measured passes; the first eight frames of each pass are
excluded (120 samples). These are currentTime plus forced-refresh wall times,
not isolated GPU times or a guarantee for another PC or an actual production shot.

- Animation, Parallel GPU: median 30.78 ms, p95 36.60 ms, max 39.15 ms,
  variation 8.75%. Passes the 41.67 ms budget for 24 FPS; the preferred 33.33 ms
  p95 headroom target is not yet reached.
- Review with visible dense wrinkles: median 91.38 ms, p95 117.26 ms.
- Review with visible regional wrinkles: median 84.95 ms, p95 97.99 ms.
  The observed p95 reduction is 16.4%; full-quality live geometry remains costly.
- Cached regional Review measured median 16.77 ms and p95 18.81 ms with complete
  cache coverage. It is **not quality-approved**: key/depth/mode invalidation
  comparison found up to 0.0152533 cm deviation, above the 0.0001 cm requirement.
  Keep it off for accepted Review and Export; timing alone cannot approve it.

DG and Parallel CPU were also measured in separate passes. Animation was about
159 ms median in DG and 34 ms in Parallel CPU; GPU benefit is scene-dependent.
The broad source inventory (constraints, 106 motionPaths, layered skins and matrix
nodes) does not establish their critical-path cost. Existing matrix architecture
and layered deformation were retained where quality tests passed.

Early reference measurements were discarded because the duplicate wrinkle face
had a hidden `deformers_GRP` ancestor. The reference was made visible before final
comparison. Both variants use identical Smooth Mesh Preview settings. A noisy
startup run was also rejected. Temporary animation preparation/cleanup now
materializes CPU inputs before GPU partition and restores the evaluation graph
after removing curves. Unsafe per-node GPU audit queries are excluded from the
interaction benchmark; native GPU evidence is captured separately.

The separate 24-frame Profiler captures show zero Bifrost compute events in
Animation and 24 in Review. A small VP2 subscene update remains, so "skipped"
means the heavy geometry computation, not every bookkeeping event. Review's
Maya-to-Bifrost translation accounts for roughly 45 ms per frame in the diagnostic
capture. Inclusive event times overlap and cannot be summed as frame time.

## Quality and reconstruction

- Ten poses, forward/reverse, DG/Serial/Parallel: 300 mesh samples across high
  head, low head, body and collars; same topology/world transforms, max vertex
  error **0**. Head motion exceeds 7 cm, ruling out an unchanged-pose false pass.
- Actual working MB reopen: max error **0** across the same pose definitions.
- Two clean builds from frozen current inputs: max difference **0**.
  Native scene reopen after rebuild: max difference **4.55e-13** scene units.
  No missing test channels. Batch-only Node Editor information warnings concern
  UI metadata; the geometry comparison passes.
- Twenty-three regression tests cover IK/FK, spine, head/neck/eyes, feet, contact,
  native correctives, bake validation, regions/presets/SKC, UI, package policy and
  benchmark state restoration. Targeted tests were rerun after the export fix.

Approved lightweight evidence is stored under
`maya_tools/assets/Edward/review/performance_20261014/`. Raw pose arrays, native
profile recordings and regenerable frozen packages remain local. Reproduce with
`scripts/run_rig_regressions.py`, `run_edward_trials.py` and
`validate_performance_package.py` in an owned trial process, not an unsaved artist
scene. Publish packages require a clean, visible, animated C/Animation report,
matching scene hash when declared, the frame budget, two builds and native reopen.

## Rejected replacements and next priorities

The 3,082-vertex low head was tested as an independent collar driver. It changed
collar2 by up to 1.1575 cm and collar3 by 2.0368 cm; the trial was rolled back.
A full primary intermediate mesh bridge did not improve conversion time and was
removed. Cached Playback failed the strict geometry gate and is not the default.

1. Focus further work on the measured Maya/Bifrost conversion boundary. A compiled
   regional deformer or adapter could avoid transferring full topology, UVs and
   normals every frame; compare against the preserved exact Bifrost source before
   replacing it. Shader microdetail is suitable only for folds that do not affect
   silhouette or exported/contact geometry.
2. If high-head demand in Animation remains important for a shot, derive a collar
   contact proxy from the same high neck/chin vertices, weights and relevant
   correctives. The generic low head already failed; validate contact and held-out
   jaw/neck combinations before rerouting garments.
3. For locked shots, test explicit baked geometry delivery with source/settings/
   topology/frame hashes and a rebake requirement after edits. Do not reuse the
   failed interactive cache result as final geometry approval.
4. Profile textured VP2, hair (41,208 vertices), shadows and final-camera workload
   separately. Optimize draw settings or skins only when their measured cost
   justifies it; do not merge the eight layers or remove matrix nodes by count.

Nini's separate keepout work is preserved as
`maya_tools/assets/Nini/scenes/Nini_dress_chains_v004.ma`: 12 chains of six joints,
72 joints total, smooth weights and native matrices/MayaMuscle nodes. Its saved
portability test found 759 moved vertices, no project module imports, no unknown
nodes and zero DG/Parallel deviation. The independent skirt test is saved under
`maya_tools/assets/KeepOutSkirt/scenes/` for continuing work on another PC.
