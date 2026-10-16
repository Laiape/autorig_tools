# Edward all-PRX bake comparison

Parent: `maya_tools/how_it_works.md`. Date: 2026-10-16.
Scope: apply the two belt experiments to every PRX garment output for manual
artist review. These are experimental comparison scenes, not approved changes
to normal CREATE RIG or the production deformation graph.

## Input and coverage

A fresh native snapshot preserves the current modified artist scene and its
filename, frame, selection and modified flag. Work uses the active nested
runtime in an owned standalone Maya process. The current original and the two
earlier belt reviews are kept recoverable.

All 23 PRX outputs are included, totaling 37,791 vertices: body garments,
belts, straps, collars and boot accessories. Every changed source has only
its PRX in the direct supported deformer stack and no downstream worldMesh
consumer. Driver/bind inputs are recorded separately for each PRX. In particular,
the belt corrective/padding branch is not redirected onto other garments.

The control bank has 75 scalar channels across both sides, body/limb FK,
spine, local chest, local hip, neck/head, jaw and lip corners. There are 150
independent capture poses and 173 separate intermediate/combined held-out poses.
Global translation, rotation and authored scale add three validation cases.
This finite FK bank does not establish arbitrary-pose, IK or scale equivalence.

## Both methods

The blendshape scene uses one native shared blendShape with 23 base geometry
indices and 119 active pose weights. Each geometry stores its own matching
topology/deltas; unaffected bases omit zero target data. The node successfully
handles all outputs, so no structural fallback to separate nodes is required.
SDKs drive the captured targets and a native global-motion matrix follows the
master control. There is no live PRX dependency in the candidate history.

The skin scene contains 23 independently fitted linear skinClusters. Candidate
joints come from the bounded earlier garment-specific influence sets. The fit
uses only the current capture bank and allows at most eight nonzero weights per
vertex. The held-out bank is excluded from fitting. These skin approximations
do not alter any original weights, authored corrective target or wrinkle field.

Both methods operate on copies of the complete evaluated garment output. All
original PRX outputs remain available through a general comparison selector.
Other original rig geometry and animator controls are retained in the files.

## Validation and timing

The fixed equivalence threshold is 0.0001 cm. All 326 cases are evaluated
forward and reverse on every output and both alternatives: 29,992 mesh
comparisons. Position, face-vertex normals, topology, UV data/assignments,
materials/assignments and edge smoothness are checked separately from timing.
Native reopen probes repeat representative captures, held-out combinations,
ankle motion and global changes in both focused files. The scene saves retain
852 joints and the original PRX comparison option.

The quality arrays and per-output results are authoritative; a structurally
valid shared deformer does not imply equivalent deformation. Exact production
acceptance still requires all quality and persistence gates, including the
normal rebuild/data round-trips. No production replacement is approved here.

Capture-pose positions for all shared-blendshape outputs are within tolerance
(maximum 0.000010790 cm), although three meshes fail the normal threshold.
Held-out combined-pose positions fail for both methods: the maximum is
27.024249 cm for blendshape-only and 2.427529 cm for fitted skins. Skin capture
poses reach 4.198400 cm. These are approximate review copies, not exact bakes.
Per-output and global-motion failures are retained in the summary/row data.

Separate interleaved timing measures standalone DG CPU edits to nine body/limb
channels while forcing the 23 garment outputs. Eight warmups are discarded per
pass. Each candidate has three passes, with nine interleaved PRX references.
Median/p95/max, pass drift and raw samples are retained. These are not viewport
playback, full-rig FPS, GPU or cache measurements.

Median / p95 ms for this diagnostic cohort: original PRX 78.950 / 89.438;
shared blendshape 4.204 / 6.025; fitted skins 15.808 / 18.531. Reference pass
medians span 77.627-81.438 ms. Speed does not override the failed quality gate.

## Manual review

The outer experiment folder is
`maya_tools/assets/Edward/experiments/all_prx_bakes_20261016_v001/`.

- `Edward_all_PRX_BLENDSHAPE_COMPARE_v001.ma` starts with all 23 shared-blendshape
  copies visible.
- `Edward_all_PRX_SKIN_COMPARE_v001.ma` starts with all 23 fitted-skin copies
  visible.

Select `Edward_PRX_Review` and change `deformationVariant` between Original_PRX
and Shared_BlendShape or SkinClusters. Both files start in FK. The GUI loader
preserves the previous free control values/frame when it updates the two owned
review windows, and selects the new comparison control for convenience.

Before updating either window, its exact current belt review is exported to
`Edward_belt_BLENDSHAPE_before_all_PRX_v001.ma` or
`Edward_belt_SKIN_before_all_PRX_v001.ma`. This retains any test keys, weight
edits or sculpts. Only the explicitly owned belt-review windows are eligible;
the original artist window is excluded by process and source-path guards.

## Evidence and reproduction

The experiment folder retains `snapshot.json`, `manifest.json`, sampled mesh/
joint arrays, fitted weights, full quality rows/summaries, timing samples,
reopen results and previous/current review-window receipts. Compact per-output
results, source/scene/code hashes and decisions are indexed by
`docs/validation/all_prx_bakes_20261016/summary.json`.

The opt-in outer scripts are `edward_all_prx_trial.py`,
`edward_all_prx_bakes.py`, `edward_all_prx_validate.py`,
`edward_all_prx_benchmark.py`, `edward_all_prx_save.py`,
`edward_all_prx_open_existing.py` and `finalize_edward_all_prx_evidence.py`.
They are experiment tooling and never run during normal rig creation.
