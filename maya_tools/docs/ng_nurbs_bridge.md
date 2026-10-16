# NURBS Skin for ngSkinTools 2

Parent: `maya_tools/how_it_works.md`.
Implementation: `maya_tools/scripts/ng_nurbs_bridge/`.
Portable installer: `dist/install_ng_nurbs_bridge.py`.
Validated environment: Windows, Maya 2026.3.3, API 20260303, ngSkinTools 2.4.0.
The package uses Maya's Python API 2.0, bundled Qt and the installed NG API.
It has no AutoRig imports, external Python packages or compiled extension.
Other Maya/NG versions have not been validated.

## Use inside AutoRig

Open Skinning Manager > Skinning > NG. The new **NURBS Skin** tab is immediately
after **Loop Rigger (Preview)**. Reopen the Skinning Manager after updating an
already-running editor. Existing polygon editors retain their original targets.
The NURBS tab has its own pinned surface and layer selection; it does not put a
helper mesh into the Tool Framework's shared polygon context.

1. Select an untrimmed NURBS surface with one skinCluster, then click
   **Use selection** in NURBS Skin. Surface CV selections also work.
2. Click **Initialize NURBS Skin Layers**. Existing weights become Base weights.
3. Select a layer and an influence. Choose Replace, Add, Scale, Smooth or Sharpen;
   set radius in scene units, intensity and value, then click **Paint NURBS**.
4. Paint with LMB, hold Shift for Smooth, or Ctrl to invert. Esc cancels the
   current stroke. A completed stroke is one Maya Undo operation. Flood applies
   the current mode to all editable CVs of the loaded surface.
5. Select **Layer mask**, or **DQ blend** for a blended DQ skin, to paint those
   channels. Influence checkboxes in the Lock column affect the selected layer.
   Maya influence locks are also respected. Editing a full weight vector
   redistributes available unlocked weights while preserving normalization;
   alternatives come from the CV or its neighbors. If no unlocked local
   alternative has weight, paint another influence first.
6. Add/remove/reorder layers, edit names and opacity, or toggle layer enable.
   **Export layers** writes NG's JSON data for the CV proxy. The native Maya
   scene is the complete authoring document, including the bridge identity map.

The brush intersects the evaluated NURBS itself, with the correct world/object
transform. Its footprint uses Greville coordinates and the local world-space
surface tangent metric; it is not an exact geodesic-radius solver on strongly
curved or folded surfaces. VP2 feedback samples the selected layer's CV channel
on a 24 x 24 surface grid. It is a display interpolation, not extra skin weights.
The preview updates on brush edits and tool entry; leave/re-enter Paint after
external pose edits. Exiting/hiding the editor releases the tool and feedback.

## Install on another computer

Copy **only** `dist/install_ng_nurbs_bridge.py` to the other computer and drag it
into a Maya viewport. NG must already be installed and compatible with that Maya
version. The installer opens NG and adds **NURBS Skin** beside **Layers / Paint**.
It does not install Loop Rigger or any other AutoRig tool.

The installer embeds only this package. It writes its own module under
`<Maya user directory>/ngNurbsBridge/`, with a module descriptor at
`<Maya user directory>/modules/ng_nurbs_bridge.mod`. It does not modify NG's
installation or an existing userSetup.py. Its own module userSetup attaches the
tab on subsequent Maya sessions, without opening NG automatically or eagerly
loading its binary. Repeating installation/attachment does not duplicate tabs.
When the same package was already imported from another location, restart Maya
to use the installed copy.

With Maya's Secure Plugin Loading enabled, the first brush/Flood use can show
the native **Untrusted Plugin Loading** dialog for `brush_plugin.py` in this
extension's directory. Review that path and choose Allow to use the brush.
The installer does not disable Maya security or change trusted-location lists.
See [Autodesk Secure Plugin Loading](https://help.autodesk.com/cloudhelp/2025/ENU/Maya-Customizing/files/GUID-11BEE3D6-C2D5-4FFE-B0DA-989CEDE00C9B.htm).

To disable automatic attachment, execute the installer's `uninstall()` function
in Maya. It removes the extension's own module descriptor/bootstrap and restores
the native NG host. Runtime files are retained so existing Undo commands and
scene recovery can still use their Python code.

Rebuild the single-file installer after runtime changes:
`python scripts/build_ng_nurbs_bridge_installer.py`.
The builder validates ASCII, syntax, embedded-file hashes and absence of AutoRig
imports. It packages no NG source, binaries, license or vendor resources.

## Scene ownership and delivery

The extension creates an owned hidden polygon CV grid, its skinCluster, NG layer
data and a network node containing the versioned identity/snapshot map. Proxy
vertices retain raw `u * numCVsInV + v` indices. Periodic dependent CVs are aliases,
and only actual source deformer membership receives weight connections. Source
and proxy influence logical indices are explicitly mapped by UUID.

Per-weight native DG connections carry composed weights to the original NURBS
skin. Blended DQ skins also receive mapped blendWeights connections. No Python
poller, frame scriptJob, expression or executable scene scriptNode performs
deformation. The Python plugin registers only an authoring context and an Undo
command; scenes require NG's existing data node, not an extension-defined node.
The original skin, geometry input, bind matrices and deformer order stay in place.

Native save/reopen preserves the authoring graph. **Restore original** disconnects
the bridge, restores captured weights/DQ data and removes only owned helper nodes.
**Bake + detach** keeps the composed weights on the original skin and removes the
helpers/layers. Both operations support Undo/Redo. Bake before a skin-only handoff
that must not require NG. No operation saves or replaces the artist's scene.

Open, kClosed and periodic U/V grids are handled separately. Closed endpoints
remain independently weighted; there is no automatic endpoint merge. The closed
seam's authored form comes from the skin input, so a seam that opens during
deformation does not falsely invalidate the CV map. Periodic dependent CVs are
never independent paint targets.

This version rejects trimmed surfaces, stacked skinClusters, referenced targets,
pre-driven/locked destination weights and invalid/non-normalized initial weights.
Topology, influence identity and skin-method changes invalidate painting/detach;
undo the incompatible edit before continuing. No history cleanup, skin replacement
or forced disconnection is used to bypass those checks.

## Validation

`scripts/tools/tests/test_ng_nurbs_bridge.py` exercises native Maya weights,
geometry, real kClosed data, periodic U/V, logical influence holes, DQ, locks,
degree 1/3, rational CV weights, namespaces, tiny positive weights, mapped undo,
bake/restore, native reopen, ownership and DG/Serial/Parallel evaluation.
`scripts/tools/tests/test_ng_nurbs_bridge_ui.py` exercises the two actual hosts,
real viewport mouse strokes, VP2 feedback, tool release and reversible attachment.
Installer checks also run with AutoRig removed from sys.path and sys.modules.
Reports and images: `docs/validation/ng_nurbs_bridge_20261016/`.
Weight initialization tolerance is 1e-8; tested geometric equivalence uses a
maximum error of 1e-4 scene units. These are quality gates, not speed claims.
