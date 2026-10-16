# Maya tools

Parent: `how_it_works.md`.
Vision (required): `modulos/vision/how_it_works.md`.
UI: `maya_tools/criterios-ui.md`.

Performance requirements and the phased Autorig/Edward optimization plan:
`maya_tools/docs/rig_performance_plan.md`. Persistent measurement, graph and
wrinkle/detail rules live in `.cursor/rules/rig-performance-measurement.mdc`,
`.cursor/rules/rig-evaluation-architecture.mdc` and
`.cursor/rules/rig-wrinkles-and-detail.mdc`. This policy does not implement
runtime optimizations; planned changes require measured acceptance.

Current exact Edward delivery and complete 47-piece clothing/accessory audit:
`maya_tools/docs/rig_exact_optimization_results_20261015.md`. The active runtime
is the nested `autorig_tools/` checkout. Its new native `Edward_working_v004.mb`
is a validated saved-copy cleanup; the artist scene and source models remain.
Normal CREATE RIG now includes initial-bind/static-data optimization; current
behavior and full-build evidence: `maya_tools/docs/rig_exact_build_integration_20261015.md`.
Edward belt shared/per-mesh blendshape prototypes, held-out/scale rejection and
isolated DG timings are documented in the active checkout:
`autorig_tools/maya_tools/docs/rig_belt_blendshape_trial_20261016.md`.
The all-23-PRX comparison extension is in
`autorig_tools/maya_tools/docs/rig_all_prx_bakes_20261016.md`.
The requested 23-garment DQ export in active Edward v072 is documented in
`autorig_tools/maya_tools/docs/rig_prx_dq_export_20261016.md`.

The 2026-10-15 Edward audit is stored under
`assets/Edward/experiments/driver_routing_20261015_v001/` and
`assets/Edward/experiments/full_audit_20261015_v001/`. The outer workspace's
`scripts/edward_driver_routing_trial.py`, `edward_rig_audit.py` and
`edward_final_audit.py` run versioned snapshot experiments through
`scripts/maya_trial_client.py`; `finish_edward_full_audit.py` serializes them.
`summarize_edward_audit.py` attributes inclusive native CPU events without
calling them wall time. `build_edward_audit_report.py` and
`build_edward_audit_canvas.py` generate the Spanish PDF and managed canvas.
`refine_edward_module_ownership.py` includes native SDK curves in exclusive
module ownership. `edward_module_storage_worker.py`,
`edward_model_storage_worker.py` and `inspect_edward_scalp_payload.py` measure
supplementary native payloads in disposable processes. Final geometry and
cache invalidation checks are in `edward_quality_resolution.py`;
`restore_edward_artist_state.py` restores original routes, frame and selection.
The delivered PDF is `output/pdf/edward-rig-audit.pdf` in the outer workspace.
GPU without cache differs from Parallel CPU in the two collars. Normal hot
Cached Playback matches CPU in the tested jumps and edits, with wrinkles both
off and on; this does not certify every shot or control. The attempted collar
GPU block did not establish a verified node partition or fix the discrepancy.
Native strict payload exports are not independent functional rigs or RAM
measurements. Prototype body routing changes the artistic result relative to
the original and is validated against the Direct prototype, not implicitly
approved for production. Mass-freezing the jaw stalled a diagnostic and is not
used as evidence of a module's runtime cost. No production rig modules are
changed by these experiment scripts. The original artist `.ma` is preserved.

Current engineering criteria and improvement order are in
`maya_tools/docs/rig_performance_criteria.md` and
`maya_tools/docs/rig_optimization_roadmap_20261015.md`; reusable skills are under
`.agents/skills/`. The active Maya runtime is the nested `autorig_tools/` checkout,
where `utils/scene_evaluation.py`, CREATE RIG and startup now apply the conservative
Parallel CPU/cache-OFF profile to newly built and marked reopened rigs. The older
outer runtime files were not overwritten. No source model was bulk re-saved.

## 1. Overview

Maya module named `self_module`. Load via `maya_tools/self_module.mod`.
That file lists known clone roots (`C:\proyectos_laia\autorig_tools`,
`C:\GIT\autorig_tools`). Maya skips a missing path and uses the first
folder that exists. Add a new clone as another `+` block; do not
overwrite the list. Maya finds the `.mod` when it is in
`Documents/maya/modules/` (copy of the same file) or when
`MAYA_MODULE_PATH` includes `maya_tools`. Details: `README.md`.
Live `.mod` is the source of truth.

On start (`maya_tools/scripts/userSetup.py`, deferred):

- AutoRig Tools menu (`maya_tools/scripts/ui/auto_rig_UI.py`)
- AutoRig shelf (`maya_tools/scripts/ui/auto_rig_shelf.py`)
- VS Code command ports 4434 / 7001 / 7002
- numpy install via mayapy if missing
- `proxy_locator` plugin
- MCP TCP listener on localhost port 9877 (`maya_tools/scripts/tools/mcp_listener.py`)

Autorig build: `maya_tools/scripts/utils/create_rig.py` class `AutoRig`.
Biped modules under `maya_tools/scripts/biped/autorig/`.
Quadruped modules under `maya_tools/scripts/quadruped/autorig/`.
Each module's `make` call uses `utils/module_nurbs.py` to keep its construction
NURBS curves and surfaces under its `Module_GRP`. Controller drawing keeps its
animation hierarchy. A space transform follows the original parent matrix when
needed, preserving animated evaluation and connected transform channels.
Leg impl flags on CREATE RIG: `reference` | `self`; optional `leg_solver="nodes"`.

Language of this file: English ASCII. Some existing Maya `inViewMessage`
strings are Spanish; do not bulk-rewrite them unless asked.

## 2. Layout

```
maya_tools/
|-- self_module.mod
|-- scripts/
|   |-- userSetup.py
|   |-- ui/              menu, shelf, Qt windows
|   |-- utils/           autorig core, guides, cache, curves
|   |-- tools/           skin, export, MCP, tests
|   |-- biped/autorig/   biped modules
|   |-- quadruped/autorig/
|-- plugin/              C++ collision (pluginMain.cpp)
|-- icons/
|-- assets/
|-- cache/               biped.cache during build
```

Character folders and character-specific filenames use an initial capital
(Anne, Chihuahua, Edward, Freya, Giraffe, Horse, Jamal, Maui, Mechanic,
Moana, Nini, Source, Spot, Thaiz). Technical subfolders keep their existing
names. Guide document keys, curve DAG roots, picker metadata, portable picker
payloads and source paths use the same character identity.
`maya_tools/scripts/utils/asset_names.py` normalizes new assets and names read
from existing Maya preferences. The asset tree retains current inputs and
explicitly referenced historical inputs; superseded versions, duplicate picker
exports and regenerable caches are archived outside assets under `recovery/`.
Validation: `maya_tools/scripts/tools/tests/test_asset_dependencies.py`.

## 3. Menu vs tools

UI chrome and item order: `maya_tools/criterios-ui.md`.
Where files appear: `modulos/vision/mapa_datos.md`.

Do not add a web frontend. Do not invent a second autorig entry point
outside the menu / shelf / `userSetup.py`.

Docs guide; live scripts are the source of truth.

### Joint corrective targets

Entry: AutoRig Tools > CORRECTIVES > Joint Corrective Targets.
Backend: `maya_tools/scripts/tools/joint_correctives.py`; Qt editor:
`maya_tools/scripts/ui/joint_correctives_UI.py` (PySide2/6).

Create a region on a polygon mesh, load the rig joint a patch follows, then
select vertices and add a corrective joint. Repeat for more patches.
Add/edit a target and move, rotate or scale its edit handles. Save records
local TRS deltas; Cancel restores the stored target. Targets have independent
0..1 manual weights, enable flags, solo preview, and optional attribute drivers.
Start/end map to weight 0/1, with linear or smooth interpolation, including
descending ranges. Capture the shoulder direction in its zero pose to get an
IK/FK-independent swing-angle driver (bone axis X/Y/Z, clavicle/torso reference).
That direction driver intentionally ignores axial twist.

The additional normalized linear skin layer has a neutral identity influence.
Corrective bindPreMatrix connections track each anchor's inverse world matrix.
Thus zero target weight leaves the existing mesh skin unchanged at any rig pose.
Selected-vertex masks can be replaced with uniform or radial falloff weights;
overlapping patches share normalized skin weights. Select the corrective layer
for further weight editing in Maya. Pose weights add local channel deltas:
rotations add Euler channels, scales add offsets from 1. This is a joint-based
shape basis, not exact arbitrary per-vertex sculpt reconstruction or an RBF.

All targets, masks and driver nodes are stored in the Maya scene. Runtime uses
stock DG nodes without scriptJobs, expressions or an external plugin. Save/load
and Maya Undo are supported. Adding a joint also adds zero entries to existing
targets. Delete Target removes its contributions and its owned nodes.
Tests: `maya_tools/scripts/tools/tests/test_joint_correctives.py` and
`maya_tools/scripts/tools/tests/test_joint_correctives_ui.py`, executed in mayapy.

### Pose blendshapes

Entry: AutoRig Tools > CORRECTIVES > Corrective Blendshapes > Pose Blendshapes.
Backend: `maya_tools/scripts/tools/pose_blendshapes.py`; Qt editor:
`maya_tools/scripts/ui/pose_blendshapes_UI.py`. The editor lists blendshapes on
the loaded polygon mesh and their targets. New creates a post-deformation
blendshape by default; pre-deformation is also available. Existing deformers
keep their current order, displayed in the list.

Transfer sculpt to mesh / LOD opens a modeless dialog for a saved captured
target. Load another neutral, aligned object-space mesh, choose a destination
blendshape or create a post/tangent layer, and optionally restrict selected
destination vertices or maximum match distance. Surface mapping interpolates
source deltas barycentrically, independent of vertex count/topology. At least
four paired source/destination landmarks enable affine plus Gaussian RBF
registration; inverse local Jacobians transform displacement vectors across
proportions. Collapsed landmark maps and empty displacement are rejected.
The original sculpt, controller pose and selection are preserved. SDK channels
are copied to the matching destination controller. Same-rig orientation targets
share the existing native sample rather than fitting duplicate poses; deleting
one target cannot disable a sample still used by another. Another rig uses an
independent SDK on its matching controller; optionally provide its own neutral
orientation region through the API or convert the transferred target in the editor.
Transfer provenance and topology signatures round-trip in `.skc`. Backend:
`maya_tools/scripts/tools/corrective_transfer.py`; real Maya 2024/2026 tests:
`maya_tools/scripts/tools/tests/test_corrective_transfer.py`; Qt test: `maya_tools/scripts/tools/tests/test_corrective_transfer_ui.py`.
Edward's jaw sculpt is transferred from `cabeza_high` (11,475 vertices) to
`cabeza_low` (3,082 vertices) in `Edward_v056.skc`. Its 874 affected vertices
share the jaw orientation pose; 204 vertices beyond the 1-unit match distance
remain unchanged. High-resolution geometry is unchanged at 0/15/30 degrees.
The low-resolution target, provenance and driver survive SKC restoration and
scene reopen (`Edward_research_v002.ma` in `experiments/research_application`).
The final validation also accounts for the independently updated U-lip module:
compare scenes and rebuilds using the same recorded jaw-module source hash.
Older scene geometry is not an acceptance baseline for that deliberate code change.

Post creation uses Maya's default chain insertion. Explicit `after` can insert
the blendshape into a proximityWrap driver branch when the body's worldMesh
has garment consumers, leaving the visible body unaffected. The regression
test covers a skinned body driving a wrapped garment.

Select the controller in its corrective pose and click Add. The capture dialog
shows changed Translate/Rotate channels, each attribute's declared default,
and its current full-weight value. Names are automatic, for example
`L_shoulder_RZ45_BLS`, `R_wrist_TXm2p5_RZm30_BLS`; m encodes minus, p a decimal.
Repeated names get a numeric suffix. Controller namespaces are omitted from
the alias; scene message connections preserve the actual controller identity.
Pose records also store the exact target name. Sculpt save/cancel and target
deletion preserve surviving aliases and sparse target indices. Missing aliases
can be recovered from pose metadata without changing deltas or SDK connections;
legacy records use their original record name as a fallback.

Add enters native sculptTarget editing at weight 1. Sculpt or move vertices
on the original mesh, then Save sculpt or Cancel sculpt. Cancel restores the
stored target deltas. Both restore the driver connection. Go to pose / Default
restore captured channel values or declared defaults. In controller channel
mode, SDKs interpolate linearly from default=0
to captured=1 and clamp beyond the range. Several changed channels multiply
their activation weights. Scale/custom channels are not captured.
The optional orientation driver uses `maya_tools/scripts/tools/orientation_correctives.py` and
Maya's native `poseInterpolator`. In Pose Blendshapes, load the base joint and
an upstream reference, choose its twist axis, and Create at neutral. Select
that region and a Swing, Twist or combined pose type before Add. Convert
selected target preserves its sculpt and captures its saved controller pose,
then restores the current rig pose. The relative joint/reference matrix is
stripped of translation, scale and shear; samples store quaternions. Clamped
native outputs drive the target independently of the IK/FK controller used.
Duplicate orientations and invalid references are rejected. Mirror creates
the matching right region and pose; Delete disables the owned native sample
without disturbing other sparse indices. Regions, native sample settings and
target links round-trip in `.skc`; legacy SDK records remain supported.
Tests: `maya_tools/scripts/tools/tests/test_orientation_correctives.py` in Maya 2024/2026 and
`maya_tools/scripts/tools/tests/test_orientation_correctives_ui.py` in Maya 2026. Skin import captures mesh
topology before binding stacked skins to avoid stale evaluated MFnMesh data.
Edward's jaw target `C_jaw_RX30_BLS` uses `C_jawSkinning_JNT` relative to
`C_headSkinning_JNT` (X twist) in `Edward_v055.skc`. The eight translational
lip targets retain SDKs. Approved skin weights, sculpts and wrinkle data are
unchanged. Full build/rebuild and scene reopen reproduce neutral/half/full
jaw shapes exactly. The scene and JSON validation are under
`maya_tools/assets/Edward/experiments/research_application/`.

Neutral pose resets all `_CTL` controls below the loaded mesh's character root,
including keyable numeric custom attributes, to their declared defaults in one
undo step. Visibility is preserved; locked or driven channels are skipped and
reported. Default continues to reset only the selected target's captured channels.

Post targets use tangent-space deltas so corrections follow the deformed
surface, suitable for sculpting posed shoulders in Maya. Pre targets use
native downstream deformation inversion during sculpt editing. Target editing
uses Maya's existing sculpt/transform tools; the Pose Editor is not involved.
LIVE toggles target sculpt editing and turns red while an edit is active;
clicking it again saves the sculpt and resumes its driver. Save/Cancel remain
available, and reopened editors recover the same red LIVE state.

Mirror L_ -> R_ creates an independent right target and captured-pose driver
after the left sculpt is saved. It preserves existing targets, animation
connections and the current controller pose. The matching R_ controller must
exist in the same namespace. Controller frame axes determine the pose signs;
geometry is reflected across mesh object X using undeformed vertex positions
and paired topology. Where model details differ, closest-surface interpolation
transfers the correction to the right side.
The sculpt is evaluated at neutral and authored natively so post/tangent deltas
retain the correct direction. Undo removes the entire mirrored target and driver.

Right-click the name of a saved target for Mirror shape (same target).
The sculpted side is detected automatically; if both sides contain a sculpt,
the L_/R_ target name chooses the source side. The action copies that sculpt onto the opposite side of the existing
target, replacing the destination-side correction while preserving the source
side, center line, target name, controller and driver. They do not add targets
or require an opposite controller. The separate Mirror L_ -> R_ button still
creates an independent right target. Save or cancel LIVE edits first; Maya Undo
restores the previous shape after a same-target mirror.
Both orders are verified on skinned synthetic meshes in Maya 2024 and 2026.
Live-connected source target meshes remain edited through their source geometry;
the tool does not disconnect them. Target deletion on multi-base deformers is
left to Maya. New targets, drivers, pose metadata and active edit backups are
stored in the scene. The existing JSON CorrectiveBlendshapeManager remains
pre-only; it does not export post targets or this tool's multi-channel metadata.

SkinManager's `.skc` snapshot now includes Pose Blendshapes metadata and its
owned SDK curves (keys, tangents, infinity) and multi-channel activation. Import
relinks them to existing controllers and restores editable pose records.
Target aliases are applied after target arrays are allocated, before reconnecting
aliased weight plugs. Pose metadata carries exact names even if the exported
deformer has lost its aliases. Import preserves sparse indices and does not
recreate deleted targets.
The curves and poses require a new export from the original sculpt scene;
older `.skc` files contain target deltas but not those driver networks. Arbitrary
external rig graphs are still expected to be generated by the rig build.
Branch-only blendshapes driving proximityWrap are exported with their input
geometry and original mesh data, then restored without attaching them to the
visible body. Imported mesh blendshapes use default insertion to preserve the
skin chain when garments consume their worldMesh. Shape Editor directory
bookkeeping is regenerated by Maya rather than restored through setAttr.
Build reloads keep standard-library modules loaded; reloading glob can rescan
unavailable network locations in sys.path and abort an otherwise local build.
Rig construction loads lookdevKit before creating modules that need
`floatConstant`; clean standalone Maya sessions otherwise create unknown nodes.

Tests: `maya_tools/scripts/tools/tests/test_pose_blendshapes.py` and
`maya_tools/scripts/tools/tests/test_pose_blendshapes_ui.py` and
`maya_tools/scripts/tools/tests/test_pose_blendshapes_mirror.py` with mayapy.
Same-target symmetrization is covered by
`maya_tools/scripts/tools/tests/test_pose_blendshapes_mirror_shape.py`.
Name recovery, sparse targets, global neutral pose and undo are covered by
`maya_tools/scripts/tools/tests/test_pose_names_neutral.py`; `.skc` recovery is
covered by `maya_tools/scripts/tools/tests/test_skin_manager_api.py`.
Validation also includes complete Edward reconstruction through the production
build and weight-import stages in Maya 2024 and 2026, checking captured/default
activation and sculpted target data after saving and reopening the rebuilt rig.

## 4. Repeatable rig validation

### Bake deformation to skin

Skinning > Bake Deformation to Skin fits a selected skin/wrap/blendshape/
Delta Mush stack to nonnegative normalized linear weights on a new copy.
Existing sources remain intact. Fit frames and validation frames are separate;
the default validation bank uses excluded midpoints. Maximum accepted error
checks both banks and rolls back copies/metadata before export on failure.
Results include RMS/max per pose, held-out max, units and worst per-vertex
error. Optional `bakeError` vertex colors show the error on the copy only;
scene-stored `bakeValidation` retains measurements. The optional new SKC
replaces selected stacks and removes their obsolete captured pose records,
while preserving shared deformers through a membership guard and retaining
bake provenance in scene-deformer metadata. It never overwrites an old SKC.
Implementation: `maya_tools/scripts/tools/proximity_bake.py` (legacy import path retained);
UI: `maya_tools/scripts/ui/proximity_bake_UI.py`. Tests in Maya 2024/2026:
`maya_tools/scripts/tools/tests/test_deformation_bake.py`; existing `maya_tools/scripts/tools/tests/test_proximity_bake.py` validates multi-
driver wraps and reconstruction; `maya_tools/scripts/tools/tests/test_deformation_bake_ui.py` covers Qt.
Edward's low-head candidate is saved separately as
`maya_tools/assets/Edward/experiments/research_application/Edward_research_bake_v001.ma`, with native
error colors and persisted metrics. The jaw trial reached a 2.330226 cm
held-out maximum error, so it is not used to replace the approved stack.

### Portable wrinkle regions

Correctives > Wrinkle Regions / Presets edits the existing Bifrost wrinkle
backend. Create empty regions for any neutral facial mesh, assign selected
vertices a signed fold pattern, choose direction/spacing/projection plane and
feather its boundary. Assign selected controls to a region to partition local
depth/value influence with a scale-relative falloff. Runtime remains entirely
inside the serialized Bifrost graph; there are no Python callbacks.
Presets (`.wrinkles.json`) store source rest geometry, signed fields, masks,
settings, local controller values and calibrated edge lengths. Identical source
meshes retain their calibrated rest while posed. Different topology requires
explicit normalized-bounds surface projection; variants measure new neutral
edge lengths and map matching namespaced controllers. Missing template
controls are reported and surviving masks are normalized. Source visibility
is preserved during replacement. Projected eyes/lips require artist review.
Preset provenance persists in the scene and `.skc` wrinkle snapshots.
Backend: `maya_tools/scripts/tools/wrinkle_presets.py`; UI: `maya_tools/scripts/ui/wrinkle_regions_UI.py`.
Tests: `maya_tools/scripts/tools/tests/test_wrinkle_presets.py` in Maya 2024/2026, plus Qt and existing
`maya_tools/scripts/tools/tests/test_wrinkle_skin_roundtrip.py` regression validation in Maya 2026.
Edward's current portable preset is `maya_tools/assets/Edward/wrinkles/Edward_v002.wrinkles.json`.
It keeps four expressions: inward brows and raised brows in Forehead, lowered
brows on the upper nose in Nose, and smile in Cheeks. Eyes and Chin fields are
zeroed, their local masks removed, and seven unused controller attribute pairs
removed. The 19 remaining local controls, three retained fields and rest data
are preserved. The saved scene is `maya_tools/assets/Edward/scenes/Edward_working_v005.mb`;
`Edward_v071.skc` preserves all v070 skin/corrective data and updates only wrinkles.
The earlier `Edward_v001.wrinkles.json` retains 26 local controls, including
lip-corner depth 7.4. Five historical expression
comparisons have zero geometry error after preset replacement, SKC restore
and native scene reopen. Approved skin and sculpt data are preserved when
adding preset provenance; validation JSON is under the research application
experiment folder. The final scene is
`maya_tools/assets/Edward/experiments/research_application/Edward_research_v005.ma`;
its snapshot is `maya_tools/assets/Edward/skin_clusters/Edward_v059.skc`.
The snapshot preserves all v057 data except the validated wrinkle metadata.
Two full builds with the current jaw module produce identical geometry across
ten combination poses. Scene save/reopen differs by at most 4.55e-13 cm.
The separately authorized lip-U code update is included in this validation copy;
the previously open Maya scene is untouched. The jaw module hash and comparison
reports are recorded in
`maya_tools/assets/Edward/experiments/research_application/final_validation.json`.

Test Rig > Build comparison loads meshes from one character root. Combination
poses + report evaluates a fixed bank of body/facial compound poses without
adding keys. Reports (`.rigqa.json`) retain pose values, topology signatures,
object-space vertices, missing/skipped channels, deformer diagnostics and
DG/Serial/Parallel mean/p95 timings. An optional previous report produces RMS
and maximum geometry differences only when units, poses and topology match.
Modes are also checked against each other. Locked and non-animation-driven
channels are reported rather than overridden. Animation connections, current
values, frame, selection, evaluation mode, cache enable state and undo state
are restored even on failure. Existing reports are never overwritten.
Report definitions include the complete captured neutral channel values so a
comparison cannot silently mix different pose definitions.
Interactive reports can capture the current viewport per pose; batch reports
explicitly mark viewport GPU diagnostics unavailable. Timings include pose
changes, CPU geometry reads and validation overhead; they are not playback FPS.
Full CREATE RIG writes a lightweight `.righealth.json` under the character's
`validation/` folder. Full combination-pose benchmarks are an explicit Test Rig
action. Backend: `maya_tools/scripts/tools/rig_validation.py`; tests: `maya_tools/scripts/tools/tests/test_rig_validation.py` in
Maya 2024/2026 and `maya_tools/scripts/tools/tests/test_rig_validation_ui.py` in Maya 2026.

## 5. Research extensions and validated packages

### Research extensions and validated packages

Pose Blendshapes supports native combination targets: select at least two saved
targets and Create combination. The new sculpt corrects their remaining joint
effect. Multiplication is evaluated by a native combinationShape node. Captured
controller poses, target dependencies and composite links survive SKC import.
Deleting a driver is rejected while a combination uses it. Implementation:
`maya_tools/scripts/tools/combination_correctives.py`.

Test Rig adds continuous facial contact reports, local DQ comparisons and native
Animation/Review/Export detail modes. Contact reports sample landmark separation
and forward/reverse geometry; they are not complete mesh collision tests.
DQ reports compare the existing method, LBS, DQS and a local blend while preserving
existing blend masks outside the tested region. Principal RMS extents are
thickness proxies; artists review candidates before applying them. Native detail
conditions switch rendered high/low meshes and wrinkle envelopes. Viewport
benchmarks require interactive Maya and record forced-refresh wall time plus a
native Profiler capture. They do not claim isolated GPU timings or playback FPS.
Backends: `maya_tools/scripts/tools/facial_contact_validation.py`,
`maya_tools/scripts/tools/skinning_volume.py`,
`maya_tools/scripts/tools/rig_performance.py`.

Bake Deformation to Skin can fit an LBS copy with a small native orientation
residual bank. Fit frames, withheld frames and additional expressions are measured
separately. A failed limit rolls back the candidate unless an explicit research
call keeps it for inspection. Quality alone does not prove a performance benefit.
Backend: `maya_tools/scripts/tools/hybrid_bake.py`.

Branch-only corrective drivers are restored on hidden native DAG meshes instead
of unattached blendShape nodes. Their native membership and Proximity Wrap bind
geometry remain valid for viewport evaluation and scene reopen. This resolves
the native calcTargetBindMatrix crash observed during Edward validation. Branch
pose records point to the editable hidden driver mesh. Geometry/driver semantics
are covered by `maya_tools/scripts/tools/tests/test_skin_manager_api.py`.

AutoRig Tools > Validated Rig Packages freezes code, selected model/guides/curves/
build/skin/wrinkle versions, picker resources and reports. Manifest file hashes
detect mismatched inputs. Validation requires two coherent rebuild comparisons
and native scene reopen before promotion. Rebuilds use a fresh working copy so
generated caches do not mutate the package. Backend:
`maya_tools/scripts/tools/rig_package.py`; UI:
`maya_tools/scripts/ui/rig_package_UI.py`.

Tests: `maya_tools/scripts/tools/tests/test_combination_correctives.py`,
`maya_tools/scripts/tools/tests/test_facial_contact_validation.py`,
`maya_tools/scripts/tools/tests/test_skinning_volume.py`,
`maya_tools/scripts/tools/tests/test_rig_performance.py`,
`maya_tools/scripts/tools/tests/test_hybrid_bake.py`,
`maya_tools/scripts/tools/tests/test_rig_package.py`.
Edward experiment reports are under
`maya_tools/assets/Edward/experiments/research_extensions/`.
The validated frozen release is
`maya_tools/assets/Edward/packages/Edward_v004/manifest.json`; its native scene is
`maya_tools/assets/Edward/packages/Edward_v004/publish_checks/Edward_validated.ma`.
Its `maya_tools/assets/Edward/skin_clusters/Edward_v063.skc` preserves v062 skin
and sculpt payloads while adding native branch membership and detail metadata.
Two clean package rebuilds match exactly across ten poses on high/low head and
body. Native save/reopen differs by at most 4.55e-13 cm. The local DQ trial and
hybrid bake remain separate candidates; hybrid validation failed the 0.1 cm
limit, including previously unseen facial expressions. Interactive viewport
measurements were made with GPU deformation override disabled, not isolated GPU
timings. Final evidence is
`maya_tools/assets/Edward/experiments/research_extensions/final_validation.json`.

## 6. General rig workflows

Entry: AutoRig Tools > ANIMATION > Test Rig > General rig tools. The existing
window scrolls; no separate menu or window is introduced. Backend files:
`maya_tools/scripts/tools/rig_roles.py`,
`maya_tools/scripts/tools/rig_profiles.py`,
`maya_tools/scripts/tools/rig_pose_library.py`,
`maya_tools/scripts/tools/rig_surface_contact.py`,
`maya_tools/scripts/tools/rig_migration.py`. Embedded Qt panel:
`maya_tools/scripts/ui/rig_tools_panel.py`.

### Semantic roles

Load the character root, then bind selected controls, joints, polygon transforms,
landmarks or references by role, side, module and index. A key such as
`arm/L/arm.upper.fk/0/control` identifies the function inside one character.
Native attributes and message membership survive rename, namespaces and scene
reopen. Resolution is scoped to the loaded root; duplicate or ambiguous keys
are rejected. Discover repository roles conservatively recognizes a limited
set of existing body/facial control names. Other controls, joints and meshes
need explicit bindings; it does not infer arbitrary skeleton semantics.

For example, in Maya's Python Script Editor:

```python
from maya_tools.scripts.tools import rig_roles
rig_roles.bind("Character", "myUpperArmControl", "arm.upper.fk",
               side="L", module="arm", kind="control")
rig_roles.bind("Character", "myUpperArmJoint", "arm.upper.skin",
               side="L", module="arm", kind="joint")
```

Export bindings as `.roles.json`. Import reuses existing semantic keys or
unambiguous namespace-free node hints. For different node names, Python
`rig_roles.restore(root, snapshot, node_map={semantic_key: destination_node})`
provides the explicit mapping. Save rebuild bindings as
`maya_tools/assets/<character>/rig_data/roles.roles.json`; CREATE RIG restores
that file after deformers/wrinkles, then discovers known controls. Build health
records role coverage and unbound conventionally named controls. Frozen rig
packages copy and hash the complete per-character `rig_data/` directory.

### Portable validation and pose review

Load polygon meshes in Build comparison. Validation profiles provides editable
JSON presets for body, face and hands plus a custom profile. Values use this
repository's axis conventions and scene units; adapt them for other anatomies.
Body limb cases explicitly require their semantic settings control and set
`Ik_Fk` to FK. Hand presets require five explicitly indexed digit controls.
Missing, locked, driven or ambiguous required channels invalidate the profile;
incomplete poses are skipped rather than reported as successful stress poses.

Profiles store named cases with semantic channel definitions. Optional
`transitions` reference start/end case names, sample count, `max_step`,
`max_step_change` and `reverse_tolerance`. These measure object-space vertex
steps and return-path differences, not continuous mathematical guarantees.
Optional `checks` support `distance`, `matrix_match` and `channel_range`.
Matrix matching separates position (scene units), rotation (degrees) and scale
tolerances, allowing rig-specific IK/FK or space-match assertions on bound
references. Checks may apply to specific `poses`; global checks and configured
surface contacts also run at transition samples. The tool verifies provided
match references; it does not automatically create an IK/FK matching solution.

`.rigprofile.json` files are reusable between rigs sharing the semantic schema.
`.rigqa.json` reports keep actual channels, portable definitions and semantic
mesh keys when meshes are bound. Renaming those nodes does not invalidate a
baseline. Same units, definitions and topology remain necessary for numeric
comparison. `quality_pass` aggregates required channels, assertions, transitions,
surface contacts, evaluation-mode consistency and any supplied baseline.

Pose library captures values of bound animator controls and a viewport camera
reference. Unbound/skipped controls are explicitly reported. Save/load
`.rigposes.json`, apply a pose to free controls, or review the entire library
without changing animation. Applying a pose to animated/connected controls is
rejected; report review temporarily evaluates them and restores their original
connections. Interactive reports create per-pose PNGs using temporary native
cameras and restore the previous panel camera; batch mode measures geometry.
Load a current report and baseline to create a colored difference snapshot for
the chosen pose. It uses saved pose points and topology, leaving the original
mesh and its color sets intact. Red saturates at 0.1 scene units by default;
Python accepts another limit. Maya Undo removes the snapshot.

### Corrective dependencies and surface contact

Pose Blendshapes mirror now carries a combination's complete dependency graph.
Central drivers can be shared while side drivers get independent counterparts.
Transfer sculpt to mesh / LOD transfers combined targets and their dependencies,
mapping controls by semantic role or explicit Python `controller_map`. New
combination capture message links survive controller rename; exported SKC data
uses their current names. Existing unmanaged SDK mirror conventions remain.
Incomplete dependencies and missing counterparts fail with transaction rollback.

Surface contact accepts semantic source/target meshes, selected source vertex
indices and optional target face regions. `proximity` measures unsigned gaps
for open regions; it cannot classify penetration. `closed` requires a complete
closed manifold target and classifies sampled vertices using three agreeing
ray parities. Ambiguous classifications require review. Limits use scene units.
The panel measures the current pose, selects offending vertices and appends the
check to a profile so each pose and transition can test it. This diagnoses
sampled contact; unsampled edge/triangle intersections are not certified and
there is no automatic collision correction.

### Version migration

Keep source and fresh destination rigs as separate hierarchies. Bind the same
semantic keys on both, load the source root and choose the destination in
Version migration. Preview lists transferable data and blocking issues; Apply
recomputes preflight and creates the candidate in one undo transaction.

Supported data: static numeric animator channels, native time-based animation
curves including their keys/tangents, one skin per mesh with identical topology,
exact mapped influence weights/DQ masks, and managed SDK/orientation/combination
correctives. Orientation samples retain their native driver and need compatible
joint orientation conventions. Source nodes and source animation stay intact.
Existing destination animation/deformers, missing roles, changed topology,
stacked skins, live/unmanaged targets and unsupported deformer stacks block
migration. Use the existing projection/stack tools for an explicit alternative.
Run a validation profile and review candidate shapes before saving a new rig
version. This does not overwrite scenes or automatically replace production rigs.

Validation: the eight new general-workflow test scripts under
`maya_tools/scripts/tools/tests/` cover differently named synthetic rig fixtures,
namespaces, native reopen/undo, geometry, weighted skins, motion, dependency
preservation and injected failure rollback in Maya 2024/2026. Interactive camera
capture/restoration is additionally checked in a separate Maya 2026 GUI session.

## 7. Edward photo picker

The current shared pipeline for **all characters** is documented in
`scripts/tools/CHARACTER_PICKER.md`. Picker generation uses actual built controls,
shared module guide prerequisites, per-character guide proportions and
`assets/<character>/picker/picker_profile.json`. Its entry is Animation >
Character Picker / the CharacterPicker shelf button. Thaiz has its generated
bundle and portable single-file installer under `assets/Thaiz/picker`.
CREATE RIG does not generate, embed or open the picker. Open it manually from
the menu or shelf; opening generates a bundle if it is missing.
The Edward photo workflow below remains a separately distributable reference.

The separate DWPicker photo design and individual SVG/PNG controller assets
live in `maya_tools/assets/Edward/picker/reference_workflow/`. Load instructions:
`maya_tools/assets/Edward/picker/reference_workflow/README.md`.
The loader resolves background paths, checks scene targets/namespace and
embeds the document in DWPicker. The original picker is preserved.
Facial secondary controls use light blue on L and pink on R; the same
palette is applied to their independent SVG/PNG assets and DWPicker shapes.
The supplied `edward_reference_sheet.png` provides the frontal body A-pose.
The supplied `edward_face_front.png` is preserved as the original frontal face.
Its restored 1380 x 1140 version is `edward_face_front_hd.png`.
Native viewports isolate those views, with controls aligned to each source.
Offline builder: `maya_tools/scripts/tools/build_edward_reference_picker.py`.
Native SVG renderer: `maya_tools/scripts/tools/render_edward_reference_picker.cjs`.

The native Qt picker supports Maya 2024+ through PySide2/PySide6. Entry:
`AutoRig Tools > ANIMATION > Edward Picker` or shelf `EdwardPicker`.
It uses the same DWPicker data for controller geometry and target names,
with namespaces, selection synchronization, layers, zoom and pan.
The standalone `install_edward_picker.py` installs the runtime in shared
Maya user scripts and creates a persistent shelf button. Install/use details:
`maya_tools/assets/Edward/picker/reference_workflow/README_MAYA.md`.
Qt interaction tests with a simulated Maya API are in
`maya_tools/scripts/tools/tests/test_edward_picker.py`; live Maya and Qt5
runtime verification remain outstanding.

The current Edward curve export has 310 picker targets: 127 body and 183
face. Secondary digit points cover the additional finger joints; the removed
head squash control is excluded. Export coverage is checked by the Qt tests.
