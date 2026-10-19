# Maya tools

Parent: `how_it_works.md`.
Vision (required): `modulos/vision/how_it_works.md`.
UI: `maya_tools/criterios-ui.md`.

NURBS painting in NG, the adjacent NURBS Skin tab and an independent
drag-and-drop installer: `maya_tools/docs/ng_nurbs_bridge.md`.
The approved architecture and original audit are retained in
`maya_tools/docs/ng_nurbs_bridge_design_20261016.md`.

Performance requirements and the phased Autorig/Edward optimization plan:
`maya_tools/docs/rig_performance_plan.md`. Persistent measurement, graph and
wrinkle/detail rules live in `.cursor/rules/rig-performance-measurement.mdc`,
`.cursor/rules/rig-evaluation-architecture.mdc` and
`.cursor/rules/rig-wrinkles-and-detail.mdc`. Implemented behavior and measured
acceptance are in `maya_tools/docs/rig_performance_results.md`.

Current engineering criteria: `maya_tools/docs/rig_performance_criteria.md`.
Measured improvement order: `maya_tools/docs/rig_optimization_roadmap_20261015.md`.
Exact Edward cleanup, all 47 clothing/accessory meshes, lossless SKC and native
acceptance: `maya_tools/docs/rig_exact_optimization_results_20261015.md`.
Normal CREATE RIG integration and full-build regression scope:
`maya_tools/docs/rig_exact_build_integration_20261015.md`.
Edward belt shared/per-mesh blendshape prototypes, captured-pose success,
held-out/scale rejection and isolated DG timings:
`maya_tools/docs/rig_belt_blendshape_trial_20261016.md`.
All 23 garment PRX outputs extended to shared blendshape and fitted-skin
comparison scenes: `maya_tools/docs/rig_all_prx_bakes_20261016.md`.
Requested DQ conversion and lossless canonical garment export in Edward v072:
`maya_tools/docs/rig_prx_dq_export_20261016.md`.
Requested skin-only garment export in Edward v073, with `cinturones2` and
`pCube26` in Classic Linear and experimental bind blendShapes removed:
`maya_tools/docs/rig_skin_only_export_20261016.md`.
Edward v074 preserves that delivery and changes two mirrored low-head mouth
skin rows to repair the Auto Wide mask boundary. The previous v073 snapshot
is retained. Exact data differences, the downstream tangent-corrective stencil
and DG/Serial/Parallel preservation checks are in
`docs/validation/rig_repair_20261016/summary.json`.
Edward Maya/custom limb-module compatibility and interactive timing comparison:
`maya_tools/docs/rig_custom_solver_comparison_20261016.md`.
Chihuahua verified binary opening through Character Manager, direct binary
model delivery and measured load/redraw scope:
`maya_tools/docs/chihuahua_model_open_20261016.md`.
Chihuahua's current lightweight model, optional groom reference and explicit
SHOW GROOM action: `maya_tools/docs/chihuahua_deferred_groom_20261016.md`.
Use the project impact/audit/equivalence skills indexed in
`.cursor/skills/how_it_works.md` for large system and deformation changes.

`utils/scene_evaluation.py` stores a hidden data-only evaluation profile on each
new character root. CREATE RIG retains lazy DG construction, then adopts Parallel
CPU with cache/GPU override OFF after success; failure restores prior flags.
`userSetup.py` installs one after-open hook for marked scenes only. A repeated
startup or build does not add callbacks/nodes. No model files, global preference
files, authored detail settings or per-frame evaluation code are changed.
Saved rigs reopen with that profile when AutoRig Tools is installed; unmarked
legacy scenes remain opt-in. Tests and overhead evidence are in
`maya_tools/docs/validation/scene_evaluation_20261015/`.

## 1. Overview

Maya module named `self_module`. Run `scripts/install_maya_module.py`
from the checkout to activate. It writes an explicit checkout path to
`Documents/maya/modules/self_module.mod` and backs up the previous file.
The installer also works under uninitialized mayapy, whose `maya.cmds`
does not yet expose `internalVar`; it falls back to the user's Documents
folder without initializing Maya. Restart Maya after switching clones.
The legacy `maya_tools/self_module.mod` lists old clone locations and can
silently select outdated tools. Details: `README.md`. The installed
`.mod` is the source of truth.

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
Flower modules under `maya_tools/scripts/flower/autorig/` use `Rig_Type = 2`
in the same CREATE RIG pipeline. Asset recipe, petal release actions and native
validation: `maya_tools/scripts/flower/how_it_works.md`.
The Maya 2026 module audit is in
`docs/validation/module_audit_20261016/summary.json`: 30 module imports,
1,422 registered literal node creations, 13 full builds/native reopens and
33 of 36 regression suites passing in the initial run. The eyelid persistence
repair, Edward v074 mouth-mask revision and final 39-suite follow-up are in
`docs/validation/rig_repair_20261016/summary.json`. The reusable native type
and module-import check is `scripts/tools/tests/test_native_node_types.py`.
Its modules follow the ArmModule class/group convention. The shared skeleton
helper accepts explicit module-chain attachments for its branched `_ENV`
hierarchy under `rig_GRP/skeletonHierarchy_GRP`. The flower settings drawing is F.
Quadruped tail, spine and neck controls follow every authored guide segment in
order. `guides_manager.sample_chain_matrices` retains one control at each guide,
adds any requested extra controls inside the segments and aims frames at the
next guide. The configured control count is a minimum when there are more
guides. Spine's sagittal spacing bias applies within each segment; a two-guide
spine keeps its previous distribution. Tail FK rest offsets use parent space.
This changes the authored rest path on the next build; existing rigs and skin
bindings are not migrated in place. The downstream ribbons keep their existing
smoothing and configured skin-joint counts, so internal guide positions are
control anchors, not a promise of exact interpolating skin-joint positions.
Regression: `scripts/tools/tests/test_quadruped_guide_paths.py` exercises native
module methods with fixture guide loading and fallback controller circles,
all guide anchors, local frames, DG/Serial/Parallel poses, skin deformation,
two reproducible builds and native scene reopen. It also loads Chihuahua's
saved guide positions into the fixtures; this is not a full-character rebuild.
Quadruped builds may opt into `spine_tangents` (off by default). It adds two
endpoint-following tangent controls to the configured primary spine count,
with `tanVisibility` on the first spine control OFF by default. Chihuahua uses
three primary controls (`C_spine00_CTL`, `C_spine02_CTL`, `C_spine04_CTL`) and
two hidden tangents (`C_spine01Tan_CTL`, `C_spine03Tan_CTL`). The five ribbon
anchors and eight configured skin joints retain the previous neutral positions.
The guide settings and `.build` export both persist the optional setting.
Native regression: `scripts/tools/tests/test_quadruped_spine_tangents.py` checks
neutral agreement with the five-control layout, endpoint following, visibility,
live deformation, DG/Serial/Parallel, global scale, reproducible builds and reopen.
Chihuahua also enables `authored_guide_orientation` in its build settings.
Spine, neck, tail, jaw, paw digits and FK controls retain the authored guide
rotations; terminal frames are not replaced by their parent's orientation.
Static matrix adapters keep the ribbon/IK solver's required axes separate.
The native leg graph retains each non-planar rest offset instead of moving the
model or flattening its guide positions. The normal CREATE RIG entry uses that
graph when this optional setting is enabled. Other assets default to their
existing solver frames. This affects new builds, not existing bound scenes.
`C_localHip_JNT` is the optional pelvis guide: both its position and orientation
drive the new pelvis frame. It is not part of the spine guide chain.
The eye aim preserves the authored roll in head-local space. Jaw collision
continues to use its anatomical hinge after the animator frame is changed.
Paw fetlock and pastern aims take their roll reference from the foot control.
Lower IK bone twist cannot flip the paw when the fetlock is lifted. Regression:
`scripts/tools/tests/test_paw_fetlock_roll.py`.
Quadruped `leg_module_self.LegModule` adds guide-centred `CorrectivePush_JNT`
bones at each internal leg guide. Their half-angle frames follow solved leg
matrices in IK and FK. Bend changes relative to the build rest pose drive a
clamped push; master-space measurement removes common global scale. Leg settings
expose `Push_Enable`, `<Joint>_Push` (signed distance) and `<Joint>_PushAngle`
(degrees to reach full push). Rest has zero displacement. The new influences
have no automatic mesh weights; paint their local skin region to preserve the
desired silhouette. They are exported as side branches in the native `_ENV`
hierarchy. No expression, callback or per-frame Python is used.
Leg skin groups publish `autorigSkeletonBranches` for the shared skeleton
builder: the main anatomical chain is ordered explicitly and each paw digit
branches independently from `legPastern_ENV`. Paw terminal `legTip` guides remain
internal sole-aim references and no longer create skinning/export joints.
Hoof tips remain available. Regression: `scripts/tools/tests/test_quadruped_leg_push.py`.
The explicit `merge_rigid_tip_weights` migration helper adds a retired tip's
weights to its pastern with native undo, preserving other weights and locks.
It requires equivalent bind-relative operators and is never run automatically
during a normal build. Chihuahua live and native-reopen evidence is in
`docs/validation/chihuahua_leg_push_20261016/summary.json`.
Guide curve exports now save their world transform together with local CVs;
both guide import paths restore it. Old guide files without it remain valid.
Native source regressions: `scripts/tools/tests/test_authored_guide_frames.py`.
Chihuahua full-build and reopen evidence is under
`docs/validation/chihuahua_guide_orientation_20261016/`.
Chihuahua curve preset `chihuahua_v005.curves` adapts the saved shapes to the
authored control frames and names both spine tangents. The updated native rig
is `assets/chihuahua/scenes/chihuahua_oriented_v002.mb`. Saved template shapes
are tagged with hidden `autorigTemplateShape`; the eyelid builder applies its
default eye-direct CV offset only to a fallback shape, preventing cumulative
offsets after export/rebuild. Shape placement, visibility, unchanged joint and
control matrices, full rebuild and native reopen evidence is under
`docs/validation/chihuahua_shapes_20261016/`.
PawFoot and the alternate quadruped digit module place their settings above
the complete digit set. `utils/controller_display.py` creates a native paw
follow offset and a `Controllers_Visibility` channel, OFF by default, on each
settings control. It hides the digit FK root groups without hiding settings
or changing joint evaluation. Regression: `test_digit_controller_display.py`.
PV indicator lines in the biped/quadruped limb builders and both eye aim lines
use Reference display (type 2), so they remain visible without being selectable.
The shared module NURBS organizer recognizes their two world-driven CVs and
keeps them under animator controls, outside hidden `modules_GRP`. Existing
scenes can use Rigging > Utilities > Restore PV / Eye Lines to reparent only
misplaced display lines. Reference/locked nodes are reported as skipped. The
operation preserves CV connections, rig output and authored visibility, is
undoable and supports namespaces. Regression: `tools/tests/test_module_nurbs.py`.
Eyebrow builds keep manual InTan/OutTan controls and `browCurve`; they no longer
create the `autoTangent` channel or its automatic tangent utility network.
Eyelids skin separate pose curves before the blink blend. Upper and lower lids
converge to one animated contact curve when both `Upper_Blink` and `Lower_Blink`
are 1, including translated/rotated primary controls. `Blink_Height` selects
the contact height. Attachment parameters converge and fitted rest offsets
fade out during closure; zero blink retains the original fitted open shape.
Detail eyelid control XYZ rotations apply after procedural aim/projection.
Primary Up/Down Z uses its original moving main-control pivot. A smooth spatial
falloff retains full central roll, about 7% on the CVs next to the corners and
zero on the shared endpoints. The opposite lid does not inherit this roll.
Calibrated aim tangents transport the skin frame and converge during blink.
Corner roll weights use standalone `multiply` nodes. Point transforms use
`multiplyPointByMatrix`; the legacy `multDoubleLinear` and `pointMatrixMult`
type names create unknown nodes in the installed Maya 2026 build.
Corner schema v4 omits zero roll terms and stores disabled inherited primary Z
on scalar compose inputs. Literal zero elements of `multiply.input[]` can be
omitted by native serialization and change the product after reopening. The
existing explicit eyelid contact upgrade repairs saved v3 graphs idempotently,
with native backup owned by the caller. Regression:
`scripts/tools/tests/test_eyelid_persistence.py`.
Current evidence: `docs/validation/eyelid_control_falloff_20261016/README.md`.
The production builder keeps the analytic projection backend. Portable aim
and De Boor CPU experiments, quality gates and scoped rejection/noise results:
`maya_tools/docs/eyelid_setup_evaluation_20261016.md`. Aim has no demonstrated
Parallel CPU gain; the De Boor prototypes are not production replacements.
For an existing standard rig, explicitly run `tools.eyelid_contact.upgrade()`
after a native backup. It keeps skin weights/bind matrices and joint/control
identities, validates the legacy route, supports namespaces, skips upgraded
sides and rolls back errors in one undo chunk. It does not upgrade references
or custom driven attachments. New builds use the corrected graph directly.
Native regression: `scripts/tools/tests/test_eyelid_blink.py`; optional
`AUTORIG_EYELID_BASELINE` supplies the previous module for migration/undo checks.
Large-angle coverage: `scripts/tools/tests/test_eyelid_corner_roll.py`.
Each module's `make` call uses `utils/module_nurbs.py` to keep its construction
NURBS curves and surfaces under its `Module_GRP`. Controller drawing keeps its
animation hierarchy. A space transform follows the original parent matrix when
needed, preserving animated evaluation and connected transform channels.
Leg impl flags on CREATE RIG: `reference` | `self`; optional `leg_solver="nodes"`.

`tools/dress_keepout_chains.py` creates `C_dressSettings_CTL` with translation,
rotation, scale and visibility locked and hidden from the Channel Box. Its
custom collision settings remain editable; the parent group follows the hip.
`showChains` and `showColliders` are created last and remain visible in the
Channel Box with keyable disabled.

The opt-in calibrated skirt upgrade in `tools/skirt_contact.py` adds panel/hem
controls, bounded lift/length correction and sparse final surface contact while
retaining existing skin data. Build, rest recalibration, presets and explicit
contact checks use the existing Framework. Architecture, native acceptance and
rollback: `maya_tools/docs/skirt_contact_rig.md`.

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

## 3. Menu vs tools

UI chrome and item order: `maya_tools/criterios-ui.md`.
Where files appear: `modulos/vision/mapa_datos.md`.

Do not add a web frontend. Do not invent a second autorig entry point
outside the menu / shelf / `userSetup.py`.

Docs guide; live scripts are the source of truth.

### Controller shape mirror and replacement

AutoRig Tools > Controllers and Tool Framework > Rigging > Controllers expose
Mirror Controllers and Replace Controller Shapes. Mirror copies all editable
`L_*_CTL` curves onto their `R_*_CTL` peers across world X=0. Replacement uses
the first selected controller as the source and every following selection as
a target, copying local curve geometry with L/R/C colors 6/13/17. Namespaces,
multiple shapes, curve form/knots/weights and line width are supported.
Both actions preserve controller transforms, animation and hierarchy, keep
non-curve shapes, preserve selection and use a single Maya undo chunk. Targets
with references, instancing, locked nodes, curve history or geometry consumers
are skipped with warnings. Maya Undo must be enabled before either action.
Display attributes that are locked or connected cause a rollback.

Implementation: `scripts/utils/controller_shapes.py`, with public compatibility
entry points in `scripts/utils/curve_tool.py`. Adapted from puiastre_tools
`mirror_shapes` and `replace_shape_colored`; provenance is in
`THIRD_PARTY_NOTICES.md`. Regression: `scripts/tools/tests/test_controller_shapes.py`.

### Shared native editor theme

`maya_tools/scripts/utils/ui_utils.py` keeps Maya's native palette/fonts/input
controls and applies shared headers, icons and semantic button accents.
`utils/ui_theme.py` declares explicit profiles for the current standalone and
embedded editors, plus repository-owned native cmds windows. Main actions are
blue; save/apply is green, preview is amber, destructive actions are muted red.
Secondary controls keep native styling. Existing artwork is tinted in memory
for light/dark Maya; no third-party artwork or installation is replaced.

`apply_maya_style` is idempotent and also handles nested profiles and dynamically
created controls. Use `action(button, role, icon_name)` for explicit controls and
`preserve_style` for functional swatches/LIVE state or vendor subtree boundaries.
Action refresh holds one valid Qt style wrapper and skips retired proxies during
stylesheet replacement. Deleted widgets are excluded from the traversal. Character
Manager detaches and deletes obsolete version pages when switching assets, keeping
only the four current category tabs in its styled hierarchy.
NG, brSmoothWeights and Ramp keep their original editors. The user explicitly
prefers Skinning Manager's previous appearance: `ui_theme.NATIVE_ONLY` excludes
that workspace and all embedded editors from new headers, icons and button
accents. Standalone editors still use the shared theme. The shared style does not
change callbacks, enabled/checked state, shortcuts, selection or scene data.

Existing Reload UI also reloads the theme and restyles open tools in place.
Lazy skinning panels, loop skinning, corrective curve, generated picker chrome,
native New Asset/Proximity Wrap/Adonis windows and dynamic asset tabs share the
same hierarchy. Curve Library uses native checked states for its source tabs
and preserves the chosen controller color when restyled.

Regression: `scripts/tools/tests/test_ui_theme.py` constructs 13 real editors,
checks primary controls and native fields, exercises dynamic asset tabs and
loop skinning, verifies rendered button fills/disabled behavior, protects
vendor controls/swatches and covers the Skinning Manager exception plus
portable picker fallback. It also checks retired QProxyStyle handling and repeated
asset switches without accumulating version pages. Existing functional Qt
regressions still apply.

### Dockable Tool Framework

Open AutoRig Tools > Tool Framework or the first AutoRig shelf button.
`scripts/ui/tool_framework_UI.py` provides a native right-docked searchable
catalogue with persistent favorites and recent tools. It restores through
Maya `workspaceControl` and launches existing editors on demand.
`scripts/framework/registry.py` contains the 42 explicit tool entries and
lazy Python adapters; it imports without Maya or Qt. Original red SVG/PNG
icons live in `maya_tools/icons/red` and are shared with menu and shelf.
The menu and catalogue share the same ordered categories and subsections:
Rigging > Guides / Build / Controllers / Utilities, and Deformers > Skinning /
Blendshapes / Correctives / Wrinkles / Wrap / Bake. Section filters and search
use the same metadata. The incomplete legacy BUILD LEG entry is disabled in
both surfaces; scene replacement actions ask to save before dispatch.
The context panel pins root, mesh and skinCluster UUIDs and the active asset.
Skinning, framework-launched Pose Blendshapes and Test Rig follow it; Picker
receives the selected root UUID. Viewport selection does not replace the
pinned character. Skin/corrective export paths prefer this explicit asset
over the old build cache. Use selection, mesh/skin choosers and Clear are
explicit actions. Finish live sculpting before switching context.

Read-only preflight checks declared requirements before menu/framework
dispatch. Tools, Workflow and Activity tabs expose the catalogue, guided
review steps and local operation history. The journal distinguishes opening
an editor from completing an action and records returned artifact paths,
duration, warnings, cancellations and errors; legacy None results remain
unconfirmed. Internal actions performed later inside an editor retain their
own status/reporting. JSON export is available from Activity.

All tools / Rigging / Deformers / Review profiles remember search, category,
expanded sections, selected tool and framework/open Skinning/QA tabs. Save
layout persists the view; profile switches and hiding also save it. Character
context is session-owned and does not change on profile switches. Workflow
marks are isolated by root UUID (or explicit asset before a root exists).
Opening a step marks it in progress; reviewed/skipped are explicit and do not
certify model/rig/package quality. Next navigates without running a tool.

Modules: `scripts/framework/context.py`, `execution.py`, `state.py`,
`adapters.py` and `scripts/ui/framework_panels.py`. Regression:
`scripts/tools/tests/test_tool_framework.py` in mayapy, plus
`scripts/tools/tests/test_tool_framework_live.py` in interactive Maya.
The latter checks scene/weight/selection preservation and owned callback
cleanup. Further editor embedding and versioned recipes are detailed in
`maya_tools/framework_plan.md`.

### Model Checker

Entry: AutoRig Tools > MODELING > Model Checker. The existing dialog in
`maya_tools/scripts/tools/model_checker.py` uses `ui_utils.apply_maya_style`
and PySide6 with a PySide2 fallback. Read-only checks and report data live in
`maya_tools/scripts/tools/model_checker_core.py`.

Run all executes all 23 automatic geometry, scene and model-design checks.
Load mesh/group roots with From selection to pin a scope; selecting findings
does not change it. Scene-wide shader, texture and namespace checks explicitly
skip a loaded selection. Full DAG paths disambiguate duplicate names;
intermediate shapes are excluded. Position/ground tolerances use scene units,
ground contact follows Maya's up axis, and symmetry tests reflected positions
on meshes crossing world X=0. Pole candidates and the checklist's configurable
NVIDIA/AMD small-mesh thresholds are advisory, not deformation/GPU certification.
Lamina and zero-area checks supplement the supplied Modeling QC Checklist.

The native results tree supports search, status filters, selected-check runs,
cancellation between checks and full component selection. Errors, skipped and
unrun checks remain explicit and never produce an overall pass. Visual review
has 24 checks with Pending/Pass/Fail/N/A and notes; N/A needs a reason. Vertex
comparison loads two explicit sets for count and bidirectional contact-position
checks, leaving loop connectivity/order to visual inspection.

Report copies all findings and exports JSON with scope, settings, diagnostics
and visual notes. Load review restores manual states only for the same scene
and scope; automatic results always require a fresh scan. Scene/node/connection
changes and watched mesh/transform dirtiness invalidate results. Scene changes
reset review and loaded vertex sets. Closing removes all owned callbacks.

Repair selected finding is one Maya Undo step and re-runs the full scan.
References, locked/driven transforms and live deformers are protected.
Topology merging, non-manifold cleanup, namespace removal and zeroing vertex
offsets require manual review rather than an automatic batch repair.
Regression: `maya_tools/scripts/tools/tests/test_model_checker.py`, run with
mayapy in a disposable standalone scene, including the real Qt editor.

### Dockable Skinning Manager

Entry: AutoRig Tools > DEFORMERS > Skinning > Skinning Manager, or the AutoRig shelf's
Skinning button. `maya_tools/scripts/ui/skinning_manager_UI.py` owns one
`AutoRigSkinningWorkspaceControl`. It initially docks to the right of the
Outliner, supports Maya's tab/dock dragging and Float / dock, and restores
through a persistent Python uiScript when Maya restores a saved workspace.
The shell inherits the same native Qt style as Character Manager.

Skinning contains NG, Smooth, Transfer, Ramp and Utilities tabs. Each native
editor loads on first use. A missing dependency produces a retry page without
breaking the other tabs. `skinning_tool_adapters.py` builds ngSkinTools2's own
Qt interface and holds its UI session reference. Its layers, influences,
paint controls, menus and native actions remain in the panel.

NG has a SkinCluster selector above its native menus. It lists the loaded
mesh's stacked skinClusters and routes the chosen node through NG's native
selection handling, including its independent layers and influences. The
explicit choice is kept when returning to vertex selection on that mesh;
selected vertices remain in Maya's selection alongside the deformer target.
Switching while painting restarts the same NG brush on the new target.
The manager's influence summary follows that active skinCluster. An unskinned
mesh disables the selector. No installed NG files or shared API functions
are patched. The regression checks independent layer data, isolated native
Flood writes, vertex selection and switching with the brush active.

NG also contains a `Loop Rigger (Preview)` tab. This prototype takes one
connected seed edge loop/chain and assigns a joint to each seed vertex.
`maya_tools/scripts/tools/facial_loop_skinning.py` follows the opposite edge
at each quad vertex until the complete transverse loop closes or has no
unambiguous continuation. It has no distance/row limit or automatic falloff.
All joints of a feature are painted in the same weight layer. Complete
traces remain in metadata and previews. At intersections the closest anchor
along the candidate loops owns the vertex; this is hard ownership, with no
falloff. Shared upper/lower corner anchors take priority and split the loop
equally. Mask values initially cover all assigned vertices.

Lip mode pairs Rotate and Non Rotate anchors by their shared seed vertex.
It creates exactly three layers: Lips, with Rotate above Non Rotate. Each
child contains all joints of that type with an identical weight distribution;
the parent mask localizes both. The 50/50 split applies to upper00/lower00
at the commissures inside each child, not to Rotate versus Non Rotate.
Loading another seed into the same named region updates these layers,
preserving existing masks. Eye and brow features use one layer each.
Optional X mirroring copies L weights to R using explicit L_/R_ joint names.
Existing joints must map uniquely within
the displayed anchor tolerance, or the UI can create review joints at the
exact seed positions. The original NG data and vendor installation are shared.

The embedded controls in `facial_loop_skinning_UI.py` load the selected seed,
preview full curves, load/create joints and create the NG group. The prototype
rejects disconnected or branching seeds and stale topology. A failed layer
operation rolls back its Maya undo chunk. Saved NG hierarchies can renumber
layer IDs; review metadata therefore resolves unique layer names on reopen.

The native Layers right-click menu now provides `LIPS RIGGER`, `EYELID RIGGER`
and `EYEBROW RIGGER`, including on NG's initialization page before layers exist.
`maya_tools/scripts/tools/facial_loop_riggers.py` resolves existing influences
from the active skinCluster and the selected connected edge loop/chain. A
feature contour generates complete transverse columns; a transverse loop can
instead update its joint's literal selection. L selections mirror to R. Lips
reuses exactly its parent and two children, with identical Rotate/Non Rotate
weights and shared upper00/lower00 commissures. Eyelids and Eyebrows each use
one shared weight layer; contour-based brow00 extends up to the midEyebrow
loop without including it. New facial masks start black; existing painted
masks survive updates. The actions preserve edge selection, reject foreign
meshes or missing joint pairs before writes, and update saved layer hierarchies.
Anchor detection uses skin input geometry and bind positions, with current
joint positions as a fallback. Smoothed eyebrow joints project to the selected
vertices within local edge spacing. The resolved vertex IDs persist in metadata
so later control poses cannot remap an existing section to a different vertex.
No joints or vendor installation files are created or modified by these actions.
The SkinCluster selector preserves edge and face components as well as vertices.
Regression: `maya_tools/scripts/tools/tests/test_facial_loop_riggers.py` uses
the real Nini rig to check the three actions, repeats, paired weights, complete
commissures, black masks, mirroring, neutral geometry and scene reopen.

Nini pilot: `maya_tools/assets/Nini/review/loop_rigger/Nini_LoopRigger_review_v003.ma`
and its JSON report, built by `scripts/build_nini_loop_review.py` in isolated
mayapy. It uses the original `Nini_v003.ma` model and the vertex-aligned curves
in `Nini_v010.guides`, with seven regions, ten total NG layers and 30 lip pairs.
The lips use the three-layer hierarchy above, with L copied to R. Each
corner00 also owns the complete 110-vertex loop through the cheek pole:
the Nini continuation is edge 220 -> 701, mirrored across the back midline.
The user's annotated cheek adds 172 surface vertices on L and their R mirrors,
split upper00/lower00 50/50 in both children. Explicit coverage overrides are
stored with the seed plan and replayed by the builder; no extra layers are
created. The update preserves weights outside the requested extension.
Each
eyebrow00 also covers the two inward columns up to the neighbor of the
midEyebrow loop; that central loop remains excluded from eyebrow00.
It is a facial skinning review, not a replacement for Nini's production rig
or saved SKC. It starts neutral at frame 1 with Lips soloed; frames 12
and 24 test translation and Rotate. Other region frames are listed in the
scene's `Nini_LOOP_REVIEW_INFO.reviewData`. Loop Rigger's review section can
solo a region/layer or enable all layers. Frame 90 tests the upper00 corner
at half weight. A static colored head and hidden
full-loop curve group help inspect ownership before painting the masks.

Regression: `maya_tools/scripts/tools/tests/test_facial_loop_skinning.py` checks
long complete columns, reversed/disconnected seeds, the exact hierarchy,
saved masks and normalized weights, all 30 lip pairs, commissure 50/50,
L/R symmetry, brow extensions, unchanged neutral model, translation in
each child and both together, and no rotation in the Non Rotate influence.
The corner check includes the complete closed loop, annotated cheek surface
and actual frame-90 movement of the newly assigned vertices.
Its `run_ui()` exercises preview/create plus appending a second seed without
adding layers or losing a painted mask.

Real-rig review: `maya_tools/assets/Nini/review/loop_rigger/Nini_LoopRigger_REAL_v001.ma`.
`scripts/build_nini_real_loop_review.py` takes a full built Nini scene and a
snapshot of the review layers. It maps the lip, eyelid and brow weights to the
existing production `_ENV` influences in `C_body_SKC`, keeps the imported
`Nini_v021.skc` skin as the base layer, and creates no review joints.
The saved rig has 576 joints and 246 body-skin influences. Its nine keyed
poses use real corner, primary lip, roll, jaw, main-mouth and head controls.
Frames 12/24 test the corners, 60/72 the roll, and 84 the jaw. The embedded
review hint reads the scene's pose labels rather than assuming prototype frames.

`test_nini_real_loop_rig.py` verifies exact transferred layer weights, all 30
matching lip pairs, 50/50 cheek weights, movement of all 172 added L cheek
vertices, roll isolation in Non Rotate, no doubled composite movement,
unchanged deformation outside the layer masks, and exact return to neutral.
The initial neutral transfer differs from the imported base by at most 0.00304
scene units; this review allows 0.005. The nine-pose validation used complete-loop
masks, where Rotate roll also moved distant forehead/neck vertices. At the user's
request, the saved real-rig review now has all nine facial masks black (0),
including Lips, Rotate and Non Rotate. Influence weights and the production base
mask are preserved. Paint the region and child masks to enable their coverage.

brSmoothWeights and brTransferWeights use the installed MEL property builders.
The adapter scopes their procedure, control and cache names in memory, gives
the builders a private parent, and preserves the original C++ brush commands.
Maya's Tool Settings can therefore remain open alongside the embedded controls.
Paint Smooth / Transfer activates the original brush; settings are disabled
while another context is active. Embedded brush activation disables the native
viewport help banner and shows mouse/modifier help in the panel instead.
Leaving a Smooth/Transfer page or hiding the manager returns its owned brush
to the selection tool, preventing painting and stale help on unrelated clicks.
Closing the manager releases its active brush
and removes its native hosts and script jobs. No vendor files are modified.

Ramp embeds the original rampWeights and weightsServer editor windows with
their node/deformer lists, ramp controls and menus. Its native type switch
stays inside the manager. The panel owns new editors and restores pre-existing
editors to their original parent on close. Install the vendor Maya modules
separately; their code and binaries are not redistributed in this repository.
Validated here with Maya 2026, ngSkinTools 2.4.0, brSmoothWeights 1.2.1,
rampWeights 4.1.1 and weightsServer 4.0.1.

From selection follows one mesh or its components; selecting a rig controller
keeps the loaded mesh. Utilities include bind, copy, mirror, normalize, prune,
remove unused influences, existing SKC import/export and transfer/wrap/bake
entry points. Auxiliary pipeline tools retain their existing dialogs.

Corrective Blendshapes embeds `pose_blendshapes_UI.py` with stacked lists,
an expandable optional pose-driver section and pinned LIVE / Save / Cancel
controls. The existing capture/sculpt/mirror/transfer/combination backend and
SKC metadata stay shared with the standalone editor. A live sculpt session
prevents switching its mesh; closing the panel leaves the recoverable scene
session intact for the next editor.

Interactive regression: `maya_tools/scripts/tools/tests/test_skinning_manager_ui.py`.
It uses temporary geometry in its own namespace and restores scene selection,
context, undo state and the modified flag after removing its test nodes.
Standalone corrective UI regression: `test_pose_blendshapes_ui.py` with mayapy.

### Jaw lip projection surface

`scripts/biped/autorig/jaw_module_nurbs.py` builds one shared projection target,
`C_jaw_NURB`. Narrow is always wired into the control projection inputs and remains
regulable through positive local corner X and `autoNarrow` (default 1). At rest,
activation and offset are zero, preserving the authored initial pose. The redundant
`C_jawStatic_NURB` and four second-pass closest-point nodes are no longer built.
Upper/lower ribbon surfaces still serve their separate downstream skin/pin roles.
This takes effect on the next rebuild; existing saved scenes are not rewritten.

Regression: `scripts/tools/tests/test_jaw_single_surface.py`, 49 poses covering
narrow, jaw opening, corner translation/rotation and sticky lips. Comparison to
the former two-surface module has maximum world-matrix component error 2.39e-7;
native binary reopen error is zero. These comparison numbers describe the
projection-surface cleanup before the subsequent rounded-U profile adjustment.

Raised corners now use a distributed quadratic U with bilateral center follow.
The native positional correction leaves each primary lip independent and has
smooth activation and retracing. See Distributed U and Edward corrective
restoration below for the current shape, test criteria and corrective audit.
The former quartic profile and its receipts are historical.

### Jaw Auto Wide

Rebuilding the jaw adds these keyable attributes on each of
`L_lipCorner_CTL` and `R_lipCorner_CTL`:

- `autoWide` / Auto Wide: 0 disables compensation, 1 enables it (default 1).

Each corner has its own intensity. Depth is fixed internally at 1 times the
neutral mouth half-width; `autoWideDepth` is no longer exposed on the controls.
Wide adds forward translation only. There is no Auto Wide Roll attribute or
automatic curl; existing manual Roll remains available on the primary lips.

The module reads negative rest-relative local corner X independently of
`autoNarrow`, plus signed secondary-controller translations calibrated to the
neutral lateral axes. It sums compression separately for each lip and side, then applies a
smooth, bounded activation. Outward secondary motion can relieve compression.
Jaw opening, head following and main-mouth movement alone do not activate it.
The central secondary's lateral translation is excluded: it is already at the
midline and cannot move inward toward itself.

Each station receives a forward-only positional offset in the jaw's deformation
space. Direction comes from the authored lip arch and lateral axis; main-mouth
and head following transform it downstream. For center weight `c`, the field is
`c*(1-c)*side + c*c*shared`, with a smooth harmonic mean of the independently
scaled L/R forward amounts as `shared`.
Equal bilateral compression gives maximum output at the center. A unilateral
input fades to zero at the center and leaves the other half unchanged. Secondary
compression on one lip does not drive the other lip. Shared corner inputs drive
both, and Sticky Lips retains its intentional coupling during closure.

Display frames are corrected before their existing neighbor aiming. Output
frames receive the same field after projection and before sticky/roll; ribbon
drivers do not receive an additional offset. No controller world matrices feed
the compression driver, no evaluation cycle is introduced, and no extra NURBS,
deformer, per-frame Python or skin-weight edit is needed. The calibration uses
rest control axes, as the existing Narrow driver does. Arbitrary secondary
translations are not collision-limited; this is volume compensation rather than
a guarantee against mesh intersections in extreme animator poses.

Native regressions: `test_jaw_auto_wide.py`, `test_jaw_auto_wide_edward.py`,
`test_jaw_single_surface.py`, `test_jaw_lips.py` and `test_lip_u_response.py`
under `maya_tools/scripts/tools/tests`. The Edward integration test owns its
temporary build cache, checks actual high/low head and body geometry, and saves
and reopens a full native scene. Validation receipts and logs are in
`maya_tools/docs/validation/jaw_auto_wide_20261015`.

Historical validation before the signed default-on inputs below: all five
regressions pass, including DG/serial/parallel,
activation and saturation continuity, mirrored secondary controls, Sticky Lips,
Roll, the rounded U and native reopen. The standard full `autoNarrow=1` pose
produces 0.07343 units of extra central joint depth. The tested 0 to 25 percent
inward half-width sweep has ordered output joints and minimum adjacent spacing
0.04735 units. Edward's nine geometry poses (jaw 0/20/30, Narrow 0/0.5/1) have
zero new triangle reversals against matching Auto Wide-off poses, unchanged
neutral/body geometry and zero geometry error after saving/reopening the rig.

Before the native graph simplification below, an isolated comparison against
commit `70302b5` gave zero matrix error in eight
poses when both corner Auto Wide attributes are disabled. The fixture grows
from 3223 to 3503 nodes. Three warmed 30-pose DG samples give median CPU
pose/query costs of 19.40 ms before and 17.37 ms with Auto Wide active
(20.22 ms disabled). The samples vary and do not establish a speed improvement
or regression. They include Python queries of 50 joints and exclude mesh/viewport
rendering; they are not animation FPS or a controlled comparison of complete
character build times.
Raw samples are in the validation folder's `performance.json`.

### Signed jaw defaults and wrinkle defaults

On both corners, `autoNarrow` and `autoWide` default to 1 and remain independent
intensity controls. The builder captures neutral local X and lateral response
once. Rest-relative X+ activates Narrow's inward offset and projection pull;
X- activates forward Wide. Smoothstep gates have zero slope at neutral and at
saturation. At X=0 both corrections are zero for every intensity, so no static
offset or changed rest surface is needed. Jaw/head following and local Y/Z alone
cannot activate these corner gates. Secondary compression remains a separate,
lip-local Wide input using the authored neutral axes.

`maya_tools/scripts/tools/tests/test_jaw_directional_defaults.py` checks defaults, rest invariance, signed
activation, boundary derivatives and forward/reverse sweeps. Existing regressions
cover per-side independence, gains, Sticky, Roll, DG/Serial/Parallel and binary
reopen. Corners project their effective inward offset once; an additional
center-directed pull on the same corner was redundant and pinched the low head
mesh under combined opening/Narrow. Only central inputs keep that pull. The
original U limits pass with Narrow at its new default 1; its corrective graph
and thresholds are unchanged.
The graph benchmark pose bank now supplies X+ for Narrow and X- for Wide.
All-pose comparisons require matching driver semantics; the comparison to
`2a3fad8` in this validation checks only poses that should remain unchanged.

Brows and lips share wrinkle reset defaults on new and reused controls:
`wrinkleValue` = 1 (range 0..1), `wrinkleDepth` = 0 (minimum 0).
Reusing a control updates both reset defaults without discarding current/saved
intensity or depth. These attributes are added by wrinkle setup import, when a
control has an authored wrinkle field. Edward's new
`maya_tools/assets/Edward/skin_clusters/Edward_v069.skc` and
`maya_tools/assets/Edward/wrinkles/Edward_v003.wrinkles.json` change only the two saved corner
Wrinkle Values from 0 to 1. All weights, sculpts, masks, rest fields and depths,
including the saved corner depths, are preserved. Earlier versions remain intact.
The later shared-checkout versions `maya_tools/assets/Edward/skin_clusters/Edward_v070.skc`
and `maya_tools/assets/Edward/wrinkles/Edward_v004.wrinkles.json` were present
before final integration tests. They retain all 26 Wrinkle Values at 1 and their
additional wrinkle-authoring changes are included in the project snapshot.
The SKC/preset regressions also verify controller defaults and native round trips.

Validation receipts: `maya_tools/docs/validation/jaw_directional_defaults_20261015`.
The independent comparison to `2a3fad8` has zero matrix error across 13 fixture
poses (152 matrices each) and zero vertex error across 12 complete Edward poses
on the high/low heads and body. These check rest, jaw opening, primary offsets,
Sticky and following; activated corner poses intentionally use the new behavior.
The fixture has 2863 nodes versus 2871 before this change. The U reference with
Narrow=1 has maximum center height fraction 0.07215 and near/outer slope ratio
0.12701, below the unchanged 0.08 and 0.25 limits. These are geometry checks,
not viewport FPS measurements.
All eight scoped regressions pass. Edward's 18 signed Narrow/Wide poses at jaw
0/20/30 have no new triangle reversals, unchanged neutral/body geometry and
zero vertex error after native scene reopen.
Concurrent regression workers now own separate Maya preference directories to
avoid startup writes racing during parallel batch tests. Rebuild to apply these
defaults and drivers; existing artist scenes are not rewritten.

### Distributed U and Edward corrective restoration

The former quartic U with a 4-percent center carry was rejected in visual review:
its corners rose too independently of the middle. The current U uses a quadratic
arc across each live mouth half. The common center rise is 30 percent of the
smooth harmonic mean of the integrated positive corner rises. It stays active
when the jaw opens. For side rise R, shared center C and normalized lateral
distance q, the activated field is `C + (R-C)*q*q`. The existing unactivated
corner motion is preserved through the smooth onset. The center fades naturally
to zero if either corner is not raised, preserving unilateral isolation.
Upper/lower primaries, fine controls, manual Roll, animator corner endpoints and
neutral rest remain independent. Wide still translates forward without Auto Wide
Roll. There is no new plugin, surface, deformer, runtime Python or skin-weight edit.

The U regression now measures the requested distribution: the middle must follow
20-50 percent of the actual corner rise and the outer quarter must carry less
than 60 percent of the center-to-corner rise. Edward's guide fixture measures
23.36-25.51 percent center follow and 22.95-23.32 percent outer-quarter share at
jaw angles 0/10/20/30. Monotone motion, smooth transition slopes, identical
retracing, a rounded middle and primary/unilateral independence are still tested.
The previous 0.08 height and 0.25 slope ratios described the rejected flat base;
they are not artistic acceptance criteria for this revision.

The corrective audit found a separate build error. `Edward_v070.skc` stores all
nine high-head targets, but their geometry path names `EdwardWrinklesGraphShape`.
That plugin node does not exist during skin/corrective import, so the old build
skipped the entire high-head blendshape and its nine pose records. The saved
sculpts and drivers were present in the file, not lost.

`skin_manager_api.py` now recovers a one-base corrective from its unique captured
mesh only when saved polygon connectivity matches exactly. Missing, ambiguous
or changed-topology bindings are skipped. Export writes the captured mesh rather
than a plugin consumer or an empty plugin DAG path. Separate wrap-driver branches
keep their branch ownership. `pose_blendshapes.geometry_index` also resolves a
saved target through explicit mesh ownership when the native output path is a
wrinkle graph, keeping that target addressable by the editor.

Native Edward validation checks all nine high-head and one low-head targets,
their names, captured poses, neutral/quarter/half/full weights, and nonzero
individual mesh contributions. The eight lip SDKs and the jaw orientation driver
are restored without modifying any saved sculpt, preset or skin snapshot.
The full build regression now compares every saved pose record against the
latest SKC so a missing corrective cannot pass silently. Twenty native skin
import/export cases cover missing plugin consumers, empty DAG paths, SDKs,
topology rejection and the separate wrap branch. The standalone test runner
passes script arguments correctly and honors unittest's normal SystemExit(0).

Receipts and native before/after renders:
`maya_tools/docs/validation/edward_distributed_u_20261015`.
The U comparison covers 52 poses with correctives restored in both variants;
nine ordinary/neutral/Wide poses and the body match exactly. U geometry changes
are intentional. DG, Serial and Parallel head geometry matches, and saving and
reopening the posed character gives zero vertex error. Contact diagnostics use
the native posed triangulation; fixed neutral diagonals on deformed quads are
not a reliable fold test. Existing mouth intersections are reported explicitly.
These are deformation checks, not interactive FPS measurements.

Contact review remains open for the extreme U at jaw=20 degrees on `cabeza_low`:
strict mouth crossing pairs increase from 130 to 144, without collapsed
triangles. The other seven sampled mesh/pose comparisons reduce crossing counts.
Existing crossings are numerous in the authored mouth; the new U is not certified
collision-free. Review/re-sculpt the low-head jaw/lip combination after approving
the new base profile, rather than silently changing the saved sculpts or weights.

The earlier center-follow receipts remain historical; they did not check that
every saved corrective was actually imported. Rebuild Edward to apply the U and
restored correctives. The artist's open scene is not rewritten.

### Native jaw graph simplification

The jaw uses the existing Maya nodes; there is no new plugin or per-frame Python.
Rebuild the rig to apply the simplified graph. Controls, skin joints, skin weights,
the shared projection NURBS and the corner Auto Wide attributes retain their
existing behavior and names.

- Corner orientation axes and rotation/pivot bases are evaluated once per corner.
  Neighbor aiming shares one position extraction per displayed station.
- `translationFromMatrix` replaces full TRS decomposition where only position is
  consumed. The primary/up-vector guards and continuous singularity fallback stay.
- Corner drag, center compensation, rounded U and Auto Wide feed one positional
  offset matrix per station. Scalar sums retain double precision. Display offsets
  remain separate from ribbon bases, including at zero weights, avoiding feedback
  and a second application of corrections to the ribbon.
- Equal Sticky Lips falloffs share the same driver. Roll's base sum is evaluated
  once per lip. Non Rotate joints extract position from the solved Sticky matrix;
  Roll still acts downstream on the Rotate joint's local channel.

Validation uses Maya 2026. `scripts/benchmark_jaw_graph.py` compares a prior Git
revision in a disposable fixture without replacing the checkout or artist scene.
Its 278 poses cover jaw opening, primary translation/rotation/scale, secondary
controls, corner rotation orders, Narrow, Auto Wide, rounded U, partial/full
sticky closure, Roll and deterministic combinations. The five jaw/lip regressions
also rebuild Edward's real geometry and save/reopen the full scene.
Receipts are in `maya_tools/docs/validation/jaw_native_graph_20261015`.

Against `a6f81f2`, the fixture has 2871 nodes instead of 3503 (-18.04%) and
5339 connections instead of 5860 (-8.89%). Across 278 poses and 152 matrices per
pose, the maximum component error is 3.95e-13. All five existing regressions
pass, including full Edward geometry, zero new triangle reversals and zero
native reopen error. No additional Maya plugins are loaded by the new graph.

Six warmed samples per version in paired ABBA order give mixed-control CPU
pose/query medians of 17.69 ms before and 14.21 ms after (-19.69%) for the
isolated fixture. Jaw-only medians are 14.56/13.75 ms, corner-only 14.16/14.23 ms,
and secondary-only 10.56/10.22 ms. These query all joint/control-group matrices;
they are not viewport FPS or a uniform speed improvement for every control.

Four complete Edward builds with the same imported skin/wrinkle settings give
zero vertex difference in six comparison poses. CPU geometry-query medians
before/after are 92.07/79.27 ms for jaw motion, 78.96/74.56 ms for corners,
66.07/75.74 ms for secondaries and 80.17/79.97 ms for mixed motion. The secondary
result is slower in this cross-build sample. Follow-up ABBA trials inside a
single scene favor the selected shared Non Rotate path (66.20 vs 70.45 ms for
secondaries) and translation-only extraction (63.91 vs 72.15 ms). This exposes
substantial whole-character timing variability; no general secondary-control,
full-rig playback or viewport speedup is claimed. Raw samples and the separate
geometry checks remain in the validation folder.

Reproduce the fixture comparison in a disposable worker with:
`mayapy scripts/run_maya_test.py scripts/benchmark_jaw_graph.py --baseline-ref a6f81f2 --output .git/jaw_graph_comparison`.
The output directory must be new. The tool reads the baseline through Git and
never replaces the working source or an artist scene.

The second orientation pass connects rigid `uvPin` matrices directly into
two-axis aiming, keeping the primary/up-vector guards and continuous fallback.
Generic matrix callers retain the translation-only input. Equal corner rotation
interpolations share one node per side/weight, rest-compensated corner frames
share one node per side, and zero-weight corner blends are omitted. Edward's
fixture drops from 2931 to 2860 nodes; 266 distinct comparison poses retain all
152 joint/control matrices within 6.89e-8 per component.

`tools/jaw_graph_optimizer.py:optimize()` applies that layout to existing owned
graphs as one undoable transaction, preserving controllers, joints and skins.
It preserves all target component weights and their incoming drivers when
reconnecting `blendMatrix.targetMatrix`; Maya can delete the entire target
element on disconnect. Referenced nodes and artist-extended position paths are
retained. Running the upgrade again makes no further graph edits.

`scripts/tools/tests/test_jaw_orientation.py` validates the upgrade, Undo,
singularity guards, evaluation modes and native reopen. The existing lip,
Auto Wide, directional-default and single-surface tests also cover the new
layout. Directional gate continuity is checked without mouth-size scaling now
that Wide depth is fixed at 1.

For animated head geometry, run a disposable worker with
`mayapy scripts/run_maya_test.py scripts/benchmark_jaw_orientation.py --scene <snapshot.mb> --output <new-directory>`.
It compares original/upgraded geometry in DG and Parallel, then samples Parallel
in ABBA order with one warm pass and three measured passes. It includes
`currentTime` and CPU geometry queries, excludes viewport/GPU timing, and keeps
all temporary keys and edits inside the worker.

Current-scene evidence is in `docs/validation/jaw_orientation_20261015`.
The short Parallel CPU sample uses eight keyed endpoint poses, ABBA blocks,
one warm pass and three measured passes per block (12 frames per scenario and
version). Median time falls by 8.0% for jaw, 6.9% for corners, 2.9% for fine
controls and 6.1% for mixed motion. These include full high/low-head and body
geometry queries in a headless CPU worker, not viewport FPS. Maximum mesh
deviation is 1.5259e-5 cm, one float32 ULP at the head's world height; rotation
matrix components differ by at most 3.45e-8. The checked mesh tolerance is
2e-5 cm and rotation tolerance is 1e-5.

### Biped spine controls and foot blending

`biped/autorig/spine_module.py` uses the `.build` `spine_controllers`
count independently of the guide and skin-joint counts. Controls are spaced
uniformly between the body and chest control rest matrices. Five controls
sit at 0, 0.25, 0.5, 0.75 and 1; Edward's current build requests five.
For five or more controls, the first and last interior controls are tangents.
Three or four controls use ordinary interior controls and an appropriate
spline degree. The five-control names remain compatible with saved curves.
These changes take effect when rebuilding the rig.

Both biped leg solvers use IK/FK blend matrices for ankle and ball skin
outputs. The custom solver also blends its terminal toe: the FK endpoint
keeps its guide offset from the ball FK control. Its ball and toe skin joints
must read those blend outputs, not the raw IK matrices. The standard solver
has ankle and ball skin outputs; its terminal guide is not a separate skin
joint. Reverse-foot pivot controls remain part of the IK hierarchy.

The custom solver translates the raw ball and toe IK results by the difference
between the solved ankle and the requested reverse-foot ankle. Unreachable
controls with Stretch=0 and softened IK therefore keep the complete foot attached
without lengthening the ankle-to-ball segment. Both outputs share the same world
offset; roll, toe pivots and FK blending remain independent. Native regression:
`scripts/tools/tests/test_biped_foot_reach.py` (bilateral reach, scale, stretch,
soft IK, roll, DG/Serial/Parallel and scene reopen).

Regression: `scripts/tools/tests/test_biped_spine_and_foot.py` under
`maya_tools/`, run with mayapy. It checks Edward's real guide/build data,
saved curve creation, configurable counts, every curve driver, both sides
and solvers, IK/FK/intermediate weights, global scale and absence of cycles.
Chest stretch/squash remains covered by `test_spine_chest_stretch.py`.

### Joint corrective targets

Entry: AutoRig Tools > DEFORMERS > Correctives > Joint Corrective Targets.
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

Entry: AutoRig Tools > DEFORMERS > Blendshapes > Pose Blendshapes.
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

### Build startup and diagnostics

CREATE RIG uses one guarded DG/refresh/undo construction session through skin,
correctives and wrinkles, restoring Maya state in finally. Nested geometry
organization must not resume the viewport mid-build. Required matrixNodes,
quatNodes and lookdevKit dependencies load explicitly for every rig family.
User input is excluded while updating build progress; recursive builds are rejected.
Failures remain failures in the progress dialog and timing receipt.

The ordinary build does not run the optional history/role health audit.
`AutoRig().build(validate=True)` requests it explicitly. Test Rig's existing
Build comparison and validation profiles remain the quality-review entry points.
Automatic and explicit CPU audits never call native deformerEvaluator per-node
GPU introspection; those queries caused interactive crashes on dirty build graphs.
Use separate native Profiler captures to inspect actual GPU work.

Model loading opens just the selected model, without an empty-scene reset first.
ASCII models can use a derived local binary copy in `maya_tools/cache/models`.
Source content, Maya API and binary hashes are checked before use. A changed source
regenerates the copy; corrupt copies are rejected. Failed conversion retains the
source scene. Source models and their version selection are unchanged. First-time
conversion and first-time renderer/plugin loading are separate costs in timings.
The cache is local and ignored by Git; it is rebuilt once on another computer.

Each build writes `assets/<character>/validation/<stamp>.buildtiming.json`, with
phase durations, model open/cache preparation, Bifrost load and graph compilation.
These are build wall times, not playback FPS. Skin and wrinkle stages share the
same imported snapshot, avoiding a second full SKC parse; changed files invalidate it.
`scripts/benchmark_rig_builds.py` runs every asset with model/guides/build inputs in
an isolated process, with private build caches. `--assets` selects a subset and
`--validate` includes the optional health audit. Build completion is a smoke check,
not approval of artistic deformation or completeness of legacy asset data.
Regression: `scripts/tools/tests/test_build_pipeline.py`.
Measured results and known legacy input limitations:
`docs/build_performance_results.md`.

### Portable wrinkle regions

Edward's current import preset is `maya_tools/assets/Edward/wrinkles/Edward_v004.wrinkles.json`.
It retains inward/up brows (Forehead), down brows on the upper nose (Nose),
and smile (Cheeks); Eyes and Chin fields and their local masks are removed.
The 19 retained local controls keep the approved maps, settings and rest data,
including the lip-corner Wrinkle Value 1 defaults from v003. The matching
`maya_tools/assets/Edward/skin_clusters/Edward_v070.skc` changes only the v069
wrinkle snapshot, so CREATE RIG imports this configuration after skin/correctives.
Replace an existing setup with prefix `EdwardWrinkles` when applying the preset.
Native preset restoration has zero geometry difference across neutral and all
four expressions; evidence: `maya_tools/assets/Edward/validation/Edward_v070_four_wrinkles.json`.

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
Edward's portable preset is `maya_tools/assets/Edward/wrinkles/Edward_v001.wrinkles.json`.
It retains 26 local controls, including lip-corner depth 7.4. Five expression
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
conditions switch rendered high/low meshes and wrinkle envelopes. Owned wrinkle
outputs also support explicit primary/detail routing at workflow boundaries.
Temporal A/B/C/D benchmarks require interactive Maya, changing time curves and
visible output. Geometry reads and native Profiler captures are separate from
clean timing. Control interaction uses only changed channels and forced refresh.
These wall times include submission and are not isolated GPU execution times.
Backends: `maya_tools/scripts/tools/facial_contact_validation.py`,
`maya_tools/scripts/tools/skinning_volume.py`,
`maya_tools/scripts/tools/rig_performance.py`.
Runtime, quality evidence and limitations:
`maya_tools/docs/rig_performance_results.md`.

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
that file after deformers/wrinkles. The optional health audit discovers known
controls and records role coverage and unbound conventionally named controls. Frozen rig
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
bundle and portable single-file installer under `assets/thaiz/picker`.
CREATE RIG does not generate, embed or open the picker. Open it manually from
the menu, shelf or Tool Framework; opening generates a bundle if it is missing.
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
