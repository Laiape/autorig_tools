# NURBS painting extension for ngSkinTools 2

Parent: `maya_tools/how_it_works.md`.
Status: approved and implemented; current use and validation are in `ng_nurbs_bridge.md`.
Date: 2026-10-16. Tested installation: Maya 2026, API 20260303, NG 2.4.0.

## Decision

Use an independent Python package, `ng_nurbs_bridge`, with two hosts: the
existing AutoRig NG editor and the standalone NG workspace control. NG owns
layer composition on a hidden polygon data proxy; the original NURBS keeps its
existing skinCluster and deformation graph. Use native DG weight connections
where the validated index mapping allows them. A separate surface-aware brush
is required to hit the evaluated NURBS rather than its control cage.

This is scenario B. No NG C++ source was found in the workspace or the installed
distribution examined. This does not establish whether source is available
elsewhere. The attachment in this conversation is a UI screenshot.

The hypothesis is that NG can remain the layer engine without a fork of its
compiled plugin. This improves the authoring workflow, not rig playback speed.
No timing, FPS, RAM or package-size improvement is claimed.

## Phase 1 evidence

The running artist session resolves both `skinning_tool_adapters.py` and
`skinning_manager_UI.py` to `C:/proyectos/auto-rig/autorig_tools/`. The installed
`self_module.mod` points there. The outer checkout is a distinct older copy.
The live session was unsaved and modified; only read-only provenance was queried.
All geometry and layer probes ran in a separate mayapy process.

NG Python is installed under:
`C:/ProgramData/Autodesk/ApplicationPlugins/ngskintools2/Contents/scripts/ngSkinTools2/`.
The running binary is `Contents/plug-ins/2026/ngSkinTools2.mll`.

`pluginInfo` reports compiled commands `ngst2Layers`, `ngst2PaintSettingsCmd`,
`ngst2Hotkey`, `ngst2BrushHandlerCmd`, `ngst2Tools`, and
`ngst2PaintContextToolCommand`. Compiled nodes are `ngst2MeshDisplay` and
`ngst2SkinLayerData`. The Python wrapper also invokes `cmds.ngst2PaintContext`.
There is no inspected implementation of those commands, nodes or raycaster in C++.
The repository's collision plugin is unrelated to the NG engine.

### Actual target restrictions

- `api/target_info.py:get_related_skin_cluster()` delegates to
  `plugin.ngst2Layers(..., q=True, layerDataAttachTarget=True)`.
- `api/plugin.py:ngst2Layers()` delegates to the compiled Maya command.
- `api/events.py:Events.__init__()` contains nested `check_target_changed()`.
  It resolves the final selected object through that target query.
- `ui/targetui.py:build_no_layers_ui()` displays the mesh-only instruction.
  This text is not the underlying geometry implementation.
- `operations/layers.py:build_action_initialize_layers()` enables initialization
  when a skinCluster resolves; `initializeLayers()` calls `api.init_layers()`.
- `api/layers.py:init_layers()`, `Layers.add()`, `Layer.get_weights()` and
  `Layer.set_weights()` all delegate layer storage/editing to the binary.
- `api/paint.py:PaintTool.start()` enters the compiled context;
  `PaintTool.flood()` dispatches NG tools. `DisplaySettings` configures the
  compiled display; it does not implement a Python NURBS draw override.
- `ui/paintContextCallbacks.py:definePaintContextCallbacks()` defines MEL
  property callbacks, not brush stroke or intersection callbacks.
- `pluginCallbacks.py` exposes target/settings/tool lifecycle callbacks.
  No public per-dab or end-stroke notification was found in the inspected API.

The disposable probes establish an important partial-acceptance failure:
NURBS transform target resolution returns None, but its shape and skinCluster
resolve. `init_layers(skin)` creates a data node, and `Layers.add()` creates a
layer. That layer has zero influence weights. `Layer.set_weights()` fails;
NG warns that the mesh has zero vertices. Therefore initialization success alone
does not prove NURBS support, and selecting the shape instead of the transform
does not fix the engine.

AutoRig has additional polygon-only assumptions:

- `ui/skinning_manager_UI.py:mesh_transform()` validates polygon meshes;
  `SkinningManager.load_selection()` calls it and captures framework context.
- `ui/skinning_tool_adapters.py:NGPanel.mesh_for()` recognizes meshes only.
  `clusters_for()`, `select_cluster()` and `refresh()` route native NG targets.
- `framework/context.py:transform()`, `is_mesh()`, `meshes()` and
  `ContextService.capture_selection()` are shared polygon context paths.
  They should not be generalized indiscriminately: other hosted tools and
  correctives rely on that contract.

### Bounded capability probe results

On an open 5 x 7 CV surface, `MItSurfaceCV.index()` matched `u * 7 + v`.
The iterator's traversal order was U-first; traversal position is not the
flattened CV index. A proxy with 35 vertices and matching influence order
accepted NG layers.

Connecting `proxySkin.weightList` to `surfaceSkin.weightList` succeeded in that
fixture. A native NG layer edit propagated with maximum weight delta 0.0 from
the proxy. Undo, redo and native scene reopen each had maximum weight delta 0.0.
For one moved-joint Classic Linear pose, CV positions agreed with a direct
weight-write reference with maximum error 0.0 scene units. This validates the
small fixture, not arbitrary skins or interactive brush strokes.

The periodic-V fixture had 66 raw CVs and 48 deformed membership entries.
The periodic-U/V fixture had 99 raw CVs and 48 deformed membership entries.
Their weightList indices were sparse. The bulk API query returned 96 doubles
for two influences in these probes. Do not infer a dense raw-CV layout from
that result; build and validate the membership/component map explicitly.

The attempted kClosed fixture did not retain kClosed after the tested setup;
its actual reported forms were open/open. It is not closed-surface evidence.
Closed topology, periodic transfer, sparse influences, DQ, painting and VP2
visualization remain acceptance work. One early probe process crashed because
an API iterator survived scene replacement; the final probe destroys iterators
before replacing geometry. The artist process was not involved.

Evidence and reproducible probes:
`docs/validation/ng_nurbs_bridge_20261016/`.

## Phase 2 architecture

### Components and ownership

Keep a raw CV map `(u, v) <-> flattened index <-> proxy vertex`, using actual
surface dimensions and verified indices. Store deformer membership separately.
Record degrees, forms, knots, influence UUIDs/logical indices and topology
signature. Identify nodes through message connections and UUIDs, not names.

The data proxy has one point per raw CV. Periodic dependent CVs are aliases of
independent CVs for authoring, not additional independent skin weights. Retain
the raw map, exclude dependent rows from writes, and derive the canonical graph
from the surface's actual periodicity and membership. Validate that Maya mesh
creation and NG preserve the requested raw vertex indices, including unused
dependent points; otherwise reject that construction before attaching.

Build open-grid quads from explicit indices, not `nurbsToPoly`: tessellation
does not supply the required CV correspondence. Store the undeformed cage for
NG's geometry-dependent layer operations. Do not feed the deformed NURBS output
into the proxy skin input: the return weight connection would create feedback.
The hidden data proxy need not reproduce the visible NURBS deformation.

NG's layers and masks remain on the proxy. Its composed weights drive the
original skin, whose bindPreMatrix, input geometry, influence connections,
normalization, DQ settings and deformer order remain owned by the original rig.
Snapshot weights and DQ blend weights before attaching. Detect locked,
referenced or already-driven destination weights and incompatible stacks before
any change; do not force-disconnect existing authoring networks.

Use the tested parent-array connection only when CV row and influence logical
indices match. Use explicitly mapped row/leaf connections for sparse or
different logical indices after those paths pass tests. API weight-array
columns use physical influence order; weight plugs and NG paint targets use
logical indices. Matching names/order alone is insufficient.

No Python polling, per-frame callback or assumed NG stroke callback is needed
for the weight bridge. Python creates the authoring graph; native connections
propagate edits. Adding/removing influences or changing topology must invalidate
the session and require an explicit remap before editing resumes.

### Smooth and seams

The bridge owns a four-neighbor U/V graph for its NURBS brush operations.
Open boundaries do not wrap. Periodic axes wrap across independent CVs and
their dependent aliases are excluded from independent edits. kClosed requires
its own tested seam policy; do not silently merge independently weighted,
coincident endpoint CVs. Preserve the original relationship and expose any
intentional seam-weight constraint explicitly.

Implement NURBS Smooth, Flood and Sharpen against this graph and write the
selected NG layer through its actual API. Preserve masks, layer transparency,
locked influences and normalization rules. The closed binary's smoothing
kernel cannot be replaced by a Python neighbor list. Native NG smoothing and
Effects must not be presented as equivalent for unsupported seam cases.

### Painting and visualization

A hidden proxy cannot be assumed to accept the native mesh brush, and its CV
cage is not the evaluated surface. A visible native-proxy cage mode can be a
diagnostic tool, but it does not satisfy surface painting by itself.

The recommended surface mode uses an extension-owned Python API 2.0
`MPxContext` and `MPxContextCommand`. Both were confirmed in Maya 2026.
`M3dView.viewToWorld` supplies the mouse ray; `MFnNurbsSurface.intersect`
returns a surface hit and U/V parameters. Resolve the nearest valid forward
hit in the correct object/world space and test trim behavior explicitly.
Map the hit to the canonical CV neighborhood using knots, basis support and a
declared falloff. CVs need not lie on the surface; do not use distance to the
control cage as the only surface-brush metric. Handle periodic distance at seams.

NG stores each layer update through `Layer.set_weights()`. Own the complete
stroke transaction so Undo restores all touched influences and masks together;
API setters are not automatically Maya-undoable. A small extension command can
own pre/post snapshots and rollback. The exact stroke undo mechanism must be
validated with NG's own undo commands, including aborted strokes.

Use `MUIDrawManager` in VP2 context drawing for the cursor and CV feedback.
Any sampled surface heatmap is a display interpolation of CV weights, with
explicit sampling tolerance, not another set of skin weights. A draw override
may be needed for persistent feedback while the tool is active. Validate depth,
trimmed holes, perspective/orthographic cameras, mirrored transforms and scale.
Remove tool-only callbacks/overlays on tool exit; do not install rig evaluation
callbacks. Interactive responsiveness is unmeasured.

### AutoRig host and standalone host

The new AutoRig tab is `NURBS Skin`, immediately after `Loop Rigger (Preview)`
inside `NGPanel.editor_tabs`. It owns its NURBS selection and skin choice rather
than putting a proxy into the framework's shared polygon mesh field. Reuse NG's
layer/influence widgets through the inspected UI/API entry points with scoped
actions, while the extension owns NURBS Paint/Flood/Smooth/Sharpen controls.
Audit the global NG session carefully: it is shared by open NG windows.

Suspend polygon-only facial actions while a bridge target is active. Stop both
the native and extension brush when switching editors, hiding/closing the host,
changing skin or replacing the scene. Do not let `NGPanel.refresh()` reroute a
NURBS brush to a previously selected polygon skin. Other polygon tools retain
their existing framework contract.

The independent host attaches to NG's own workspace control, identified by
`ui/mainwindow.py:DOCK_NAME`. The actual entry points are `build_ui(parent)`,
`open()` and `resume_in_workspace_control()`. Use an idempotent, reversible
in-memory host adapter and the extension's own widgets. Do not modify vendor
files. Future NG window creation/restoration must attach exactly once; current
windows need a validated attach/rebuild path that releases active tools.
Do not globally replace `PaintTool.start()` for ordinary mesh painting.

The drag-and-drop installer defines `onMayaDroppedPythonFile(*args)`. It embeds
the extension's own package, installs it under user Maya scripts/modules and
registers the standalone NG attachment for later sessions. It checks NG and
PySide capabilities before loading. The installer contains no `maya_tools`
imports, AutoRig paths, NG binaries or copied vendor source. Its dependencies
are Maya, its bundled Python/Qt and a compatible installed NG version.
Reinstall/update/uninstall must own only this extension's files and callbacks.

### Persistence and delivery

Persist layer data, identity map and schema in ordinary scene nodes/attributes;
do not embed executable scriptNodes. Native links must survive scene reopen
without the UI. Reopening the editor reconstructs UI state from owned metadata.
Proxy NG nodes still require the existing NG plugin for editable layers.

Provide two explicit reversible exit operations: cancel/restore original
weights, and bake composed weights to the original skin then detach owned
links/nodes. Preserve native NURBS deformation and final weights when the
extension is absent after bake. Never delete the source skin or unrelated data.
Keep skin-only export separate from authoring layer export.

## Exact implementation locations

Existing runtime files to extend, after design validation:

- `maya_tools/scripts/ui/skinning_tool_adapters.py`: `NGPanel.__init__()` adds
  the adjacent tab; `change_editor_tab()`, `deactivate()`, `refresh()` and
  `refresh_rigger_actions()` coordinate tools and routing. Extend `select_cluster()`
  only where necessary to preserve the explicit polygon/bridge distinction.
- `maya_tools/scripts/ui/skinning_manager_UI.py`: lifecycle integration in
  `SkinningManager.release_brushes()`, `scene_changed()` and `hideEvent()` if the
  child adapter cannot handle all cleanup. Keep `mesh_transform()` and other
  polygon-only tools scoped; do not turn every hosted editor into a NURBS editor.
- `maya_tools/how_it_works.md` and `maya_tools/criterios-ui.md`: supported scope,
  tab placement and standalone delivery instructions.

New standalone files, imported without any AutoRig dependency:

- `maya_tools/scripts/ng_nurbs_bridge/__init__.py`: public attach/open entry.
- `maya_tools/scripts/ng_nurbs_bridge/topology.py`: CV/membership/influence maps
  and canonical adjacency. Proposed API; not existing NG functions.
- `maya_tools/scripts/ng_nurbs_bridge/core.py`: preflight, proxy ownership,
  snapshot, links, validation, bake and restore. Proposed API.
- `maya_tools/scripts/ng_nurbs_bridge/brush_plugin.py`: context/command
  registration, stroke undo and VP2 feedback. Proposed API.
- `maya_tools/scripts/ng_nurbs_bridge/ui.py`: shared NURBS panel and actions.
- `maya_tools/scripts/ng_nurbs_bridge/ng_host.py`: standalone NG attachment,
  version checks and restoration/cleanup hooks.
- `scripts/build_ng_nurbs_bridge_installer.py`: generate the single-file bundle.
- `dist/install_ng_nurbs_bridge.py`: generated portable drag-and-drop artifact.
- `maya_tools/scripts/tools/tests/test_ng_nurbs_bridge.py`: Maya fixtures for
  weights, deformation, ownership and persistence.
- `maya_tools/scripts/tools/tests/test_ng_nurbs_bridge_ui.py`: NG host, tools,
  restoration and portable-install integration checks.

No inspected vendor Python file or NG binary needs to be edited. Runtime and
installer implementation followed user approval of this audit and design.
The final UI targets the bridge through NG's layer API without changing the
vendor UI's global selection session. Each editable CV/influence pair uses a mapped native
connection, including sparse influence indices. Authoring topology comes from
the skin input so deformed closed seams can open without invalidating their map.

## Implementation order and acceptance

1. Build mapped proxy/restore on a non-square open surface. Reject any initial
   weight delta above 1e-8 and compare evaluated CVs at <= 1e-4 scene units.
   Validate mapped logical influence holes before adding broad live attachment.
2. Cover actual kClosed, periodic U, V and U/V, degree 1/3, rational data,
   sparse membership, namespaces, transforms and pre-existing DQ blend weights.
   Do not infer closed behavior from a failed kClosed fixture.
3. Add surface intersection, brush footprint, masks, smoothing and transactional
   strokes. Check forward/reverse/held-out poses, locked weights and layer
   opacity/enable/reorder changes against direct native-weight references.
4. Add the adjacent AutoRig tab and standalone NG adapter. Verify no duplicate
   tabs/jobs, no global mesh-brush regression, correct selection and tool release.
5. Build and test the single-file installer with AutoRig absent from sys.path.
   Test reinstall, Maya restart, workspace restoration, native reopen, cancel,
   bake/detach and clean uninstall. Treat other Maya/NG versions as unverified
   until tested. Test trimmed/stacked/referenced cases or reject them explicitly.

Measure pointer-to-feedback latency and authoring graph cost separately from
normal rig playback. A hidden proxy or fewer Python calls is not timing evidence.
Run all probes explicitly, outside CREATE RIG and normal scene startup.

## Autodesk references

- [MFnSkinCluster](https://help.autodesk.com/cloudhelp/2024/ENU/MAYA-API-REF/cpp_ref/class_m_fn_skin_cluster.html): physical influence order and periodic dependent CV caveat.
- [MItSurfaceCV](https://help.autodesk.com/cloudhelp/2017/ENU/Maya-SDK/cpp_ref/class_m_it_surface_c_v.html): flattened surface CV index.
- [MFnNurbsSurface Python API](https://help.autodesk.com/cloudhelp/2026/ENU/MAYA-API-REF/py_ref/class_open_maya_1_1_m_fn_nurbs_surface.html): actual surface intersection and evaluation methods.
