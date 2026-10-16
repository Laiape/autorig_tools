# Rig performance criteria

Parent: `maya_tools/how_it_works.md`.
Current roadmap: `maya_tools/docs/rig_optimization_roadmap_20261015.md`.
Evidence: Edward snapshot audit dated 2026-10-15, not a universal character cost.

## Decide what is being improved

State the hypothesis and affected workflow before restructuring: build time,
control manipulation, uncached playback, hot cached playback, scene size, load
time, RAM, VRAM or export. A result in one category does not prove another.
Inventory identifies candidates. It does not establish cost or quality.

Use the project skills under `.agents/skills/`: `rig-change-impact` for large
design decisions, `rig-performance-audit` for measurements, and
`rig-deformation-equivalence` for structural/deformation replacements.

## Scene and construction contract

- Shared `AutoRig.build` keeps DG lazy evaluation, cache/GPU evaluators disabled,
  undo disabled and refresh suspended throughout construction and data import.
- On successful completion, use Parallel CPU with Cached Playback OFF. This is
  a conservative starting profile, not a claim that CPU wins for every rig.
  GPU or cached profiles require geometry and invalidation evidence for that
  scene/version. Artists may explicitly change runtime settings afterward.
- Persist the profile as a hidden, locked data attribute on the character root.
  `utils/scene_evaluation.py` applies it once after opening a marked scene when
  AutoRig Tools is installed. An unmarked or unrelated scene is not changed.
  Native scene files alone cannot guarantee another machine's evaluator setup.
- Successful builds adopt the posing profile; failed builds restore the caller's
  previous evaluator flags, undo, cycle checking and refresh. Model opening
  during construction must not activate the post-open work profile.
- Do not save global preferences, rewrite every source model, add scriptNodes,
  run benchmarks, query GPU partitions, or extract vertices during normal build
  completion/startup. No per-frame Python callback or reconnection is allowed.
- Preserve authored wrinkle, skin, corrective, display, camera and animation
  settings. Evaluation setup is separate from an explicit detail-mode change.
- Record configuration overhead separately. The existing final redraw remains
  outside the settings-only measurement; do not hide a redraw in a cheap label.

## Comparable timing

- Identify the loaded checkout. Preserve an unsaved artist scene in a versioned
  native snapshot before trials. Use a disposable process for risky exports and
  experiments. Never replace the only authored scene or silently discard edits.
- Fix scene/input/code hashes, Maya/API/plugin versions, hardware, frame range,
  units, actual time unit/FPS, camera, viewport dimensions, Smooth Mesh Preview,
  shading and visible DAG ancestors. Record both enabled and unavailable states.
- Use an animated workload covering every affected module and side. Resolve
  actual channels, check IK/FK switches, and verify nonzero motion. Cache semantic
  discovery during preparation; exclude preparation from timed evaluation.
- Compare DG, Parallel CPU, Parallel GPU and hot Cached Playback separately.
  Use Serial to investigate discrepancies. A cached result must be compared to
  the accepted CPU/DG geometry, not only to possibly incorrect uncached GPU.
- Warm the workload, discard initial frames, collect at least three clean passes
  and interleave references. Report median, p95, maximum, samples, pass medians
  and dispersion. A descriptive noise band may be the larger of reference drift
  and 5% of reference median; it is not a statistical confidence interval.
- Separate timing, profiling, geometry extraction and screenshots. currentTime
  plus forced refresh is wall time including VP2 submission, not isolated GPU
  execution. Derived FPS is 1000 / measured ms and is not a playback guarantee.
- Separate control-edit latency from temporal playback. Report cache fill/wait,
  coverage, invalidation and cold recomputation separately from hot replay.
- Do not compare absolute times across different viewport/workload cohorts.
  Stop a hung preparation or unsafe native export; preserve failure evidence.

## Interpret the evidence honestly

"Bypass" means omitting a stage, for example temporarily using a geometryFilter's
pass-through nodeState or routing its primary input directly to the consumer.
It removes both computation and the stage's deformation. It is a diagnostic
ablation until an equivalent replacement has passed independent quality tests.
Restore both driverGeometry and bind/rest connections when a trial changes PRX.

Bypassing a group changes downstream geometry and parallel scheduling. Its time
difference is marginal and nonadditive; negative savings can be real or noise.
Do not sum deltas or present them as the intrinsic cost of each algorithm.

Profiler EvaluateNode durations are inclusive CPU work. Nested and parallel
events overlap; per-module totals are not wall time, FPS or removable savings.
Attribute DAG nodes to the deepest owning module, include SDK curves owned by
that module, and keep shared/global/deformer work in separate buckets. Do not
mass-freeze a module to claim its cost without a successful controlled capture.

Native exportSelectedStrict sizes measure serialized payloads, not usable rigs,
RAM or exact incremental scene savings. Individual exports have headers and may
overlap/share data. Report bytes and MiB/KiB with scope; do not sum unrelated
exports into a percentage of the full scene. Separate external textures/XGen
data and missing paths. Whole-process RAM is not per-component RAM.

## Geometry and artist intent

- Map all consumers before changing a driver: proximityWrap, uvPin, Bifrost,
  follicles, garments, live targets and export. Hidden geometry can still be
  demanded; a zero envelope/mask or hidden output does not prove skipped work.
- Keep primary deformation, attachments and final wrinkles directional. Adding
  an intermediate driver mesh does not guarantee lower conversion/readback cost.
  Preserve each consumer's correct topology, bind geometry and coordinate space.
- Preserve sequential facial skin order, DQ methods/masks, bindPreMatrix, actual
  weights, corrective aliases/indices/deltas, rest fields and authored settings.
  maxInfluences is a setting, not proof of the weights currently stored.
- Use default max vertex error <= 1e-4 scene units for equivalent same-topology
  changes. Validate world transforms, forward/reverse poses, held-out combined
  expressions, both sides, global/nonuniform scale, lips/eyelids and clothing.
  For approximate LODs, declare separate surface/contact/visual tolerances first.
- Check actual wrinkle displacement outside timing. A frozen neutral output
  cannot validate detail. Test depth/mask/pose edits and mode re-enable behavior.
  Neutral preparation may reset published wrinkleDepth defaults to zero. Apply
  declared active-detail settings after neutral preparation and verify actual
  nonzero displacement before accepting a wrinkle comparison.
- A change in where existing correctives are applied is an artistic change even
  when every new prototype agrees. Compare against the original separately and
  report the difference before adopting a candidate.
- Before accepting a structural replacement, require native reopen, relevant
  preset/SKC round-trips and two reproducible builds from the same inputs.
- Include evaluated normals, UVs/material assignments and joint matrices when
  preserving appearance. Equivalent positions alone can miss a shading change.
- Remove only proven static exact-zero skin columns when studying unused
  influences; retain tiny nonzero weights. Reject driven weight arrays and
  verify retained native weights/DQ masks exactly. Fewer influences can still
  regress: benchmark native-reopened scenes as well as the post-edit state.
- For a new static imported skin, prefer omitting exact-zero source influences
  at initial bind over deleting them afterward. Keep existing bindings and
  driven/all-zero/incomplete records unchanged. Preserve every nonzero value,
  including tiny weights, and validate the resulting full build against an
  explicit opt-out. Normal creation must not require a forced save/reopen.
- SKC exports default to lossless nonzero native weights and DQ values. Do not
  round weights or threshold small positive values in a preservation workflow.
  `SkinManager.export_skins(..., lossless=False)` is explicit legacy compact
  encoding, not an equivalent-data guarantee.
- In-place Bifrost may hide native polygon skins behind a plugin DAG output.
  Capture original routes/presets first, expose only owned native skin outputs
  during weight export, and restore all connections on success or exception.
  Count expected skin layers in the exported data. Preserve already matching
  skin order during replacement; unnecessary reordering can move correctives.
- A hot-cache warmup that fails to finish is a failed repetition, not a sample
  to discard while advertising the successful hot rows. Keep the failure record
  and leave that profile unapproved until its stability is established.

## Edward findings that guide priorities

The artist snapshot contained 18 modules, 58 skins and 23 PRX. Its conservative
Parallel CPU result was 40.81 ms/f without wrinkles and 154.30 ms/f with them.
Hot cache measured 20.62/23.20 ms/f OFF/ON and matched CPU in 11 frame jumps and
two key edits on 26 outputs. That limited success does not approve all shots,
all settings edits, or the different regional v002 scene's earlier failed cache.
Uncached GPU differed in collar3 by 0.136349 units and collar2 by 0.000709.

Additional body/facial/wrinkle driver meshes had no stable speed advantage over
the simpler direct prototype. Routing body correctives to the visible body and
all body PRX changed the original body by up to 1.827831 units; originally only
the belt consumed that corrective branch. Constant target weights may be
intentional garment padding, not necessarily broken pose activation.

The four low-head skins add stored data, but bypassing the hidden branch did
not establish a runtime gain. Hair/curve visibility and low display did not show
a stable improvement in this cohort. Keep a useful LOD; do not remove it by rule.
Jaw, eyelid and eyebrow have the largest attributed module CPU work, while
group skin/PRX bypasses identify further investigation candidates. None of
those ablations is an accepted replacement. Bifrost translation warrants a
targeted prototype; another full intermediate mesh is not a demonstrated fix.

## Acceptance record

The exact follow-up is in `rig_exact_optimization_results_20261015.md`: all 60
outputs including 47 clothing/accessory meshes; exact native pose results;
11.88% less OFF frame time after reopen, no proven ON gain. The native skin
export failure and cache hang are retained. These results do not certify a
full CREATE RIG rebuild, untested scale modes or another character.

For each significant candidate save: hypothesis; baseline and candidate hashes;
consumer map; preserved/intentional behavior; timing protocol and references;
quality and invalidation scope; native persistence checks; noise/limitations;
decision (accept, reject, inconclusive); retained source and rollback path.
No improvement inside noise, quality failure or missing channels is a pass.
Build time, posing and playback budgets are separate. Animation playback p95
target is 1000 / shot FPS ms, preferably 33.33 ms headroom at 24 FPS; these are
project targets, not measurements already achieved by every character.

API references for the runtime configuration:
[evaluator](https://help.autodesk.com/cloudhelp/2026/ENU/Maya-Tech-Docs/CommandsPython/evaluator.html),
[evaluationManager](https://help.autodesk.com/cloudhelp/2026/ENU/Maya-Tech-Docs/CommandsPython/evaluationManager.html),
and [MSceneMessage](https://help.autodesk.com/cloudhelp/2026/ENU/MAYA-API-REF/py_ref/class_open_maya_1_1_m_scene_message.html).
