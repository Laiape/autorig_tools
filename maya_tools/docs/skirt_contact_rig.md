# Skirt contact and lift rig

Parent: `maya_tools/how_it_works.md`.
Scope: a calibrated closed skirt, native Maya 2026 and MayaMuscle.

## Behavior and ownership

`tools/skirt_contact.py` upgrades an existing calibrated
`tools/dress_keepout_chains.py` module. The Nini reference is
`assets/Nini/scenes/Nini_dress_chains_v005.ma`. The later artist version v006
is retained separately and is not a neutral calibration input.

`SkirtContactModule` adapts the existing AutoRig build in place. It reuses
the original skin chains and the populated ENV skeleton instead of rebuilding
the character. Mechanics remain under the existing dress module and its
`Controllers_GRP` belongs to the character's control hierarchy.

The upgrade retains the existing skeleton, garment topology, UVs, materials,
skin weights, DQ masks and bind matrices. It adds five translation controls:
Front, Back, Left, Right and Hem. The controls follow an independent waist
space and never follow their own deformation output.

Evaluation order:

1. Calibrated native KeepOut pressure from the existing leg capsules.
2. Bounded angular/vertical propagation and panel/hem offsets.
3. Horizontal span limiting and upward length-budget correction, from the
   anchored waist down each chain.
4. Final station KeepOut correction. Contact takes priority; measure final
   segment lengths rather than assuming that projection preserves length.
5. Tangent frames, matrix blend with the retained legacy branch, existing
   parent-space joint matrices and existing skinClusters.
6. Sparse waist-surface projection for the tunic and embroidery.

`tools/skirt_surface_contact.py` reads an explicit upstream intermediate skin
output. Native edge-endpoint nodes obtain evaluated vertex positions; closest
body points and normals produce outward-only deltas on a separate output mesh
shape. This closes gaps between sparse joints without editing skin weights.
The source shape never reads the final surface. Its UVs, topology, shading
assignments and render/display properties pass to the new output.

Message bindings resolve saved handles after namespace changes and control
renaming. A versioned JSON preset stores layout, settings and manual offsets.
The native scene carries the runtime graph; importing a skin file alone does
not recreate the contact graph.

## Controls

- `solverBlend`: 0 selects the retained legacy result; 1 selects the upgrade.
- `autoLift`, `maxLift`, `lengthStiffness`: upward length correction and its cap.
- `bendStiffness`: pressure coherence and tangent-frame following.
- `spreadAround`, `spreadDown`: propagation to adjacent stations.
- `contactPadding`: additional pressure while contact is active.
- `surfaceContact`, `surfaceMargin`: sparse final waist contact.
- Existing collision enable/blend, margin and capsule radii remain available.
- `calibrationValid`: a native indicator of edits to calibrated collision
  parameters. Recalibration is an explicit authoring operation at rest.

Partial blends and manual offsets are artistic controls, not a guarantee of
collision-free output. Run the explicit contact check on the intended poses.

## Authoring API

```python
from maya_tools.scripts.tools import skirt_contact

# Select the calibrated module or pass it explicitly. The legs must be neutral.
data = skirt_contact.upgrade("NiniDress_Module_GRP")
skirt_contact.reset_controls(data["module"])
skirt_contact.export_preset("C:/output/skirt_v001.json", data["module"])
skirt_contact.import_preset("C:/output/skirt_v001.json", data["module"])

# After collider edits, restore the recorded leg pose and zero manual offsets.
skirt_contact.recalibrate(data["module"])

# Explicit, potentially expensive QA; never runs during normal rig evaluation.
report = skirt_contact.check_contact(data["module"])
```

For another character pass `collision_mesh` explicitly if its body does not use
the default namespaced `c_body_GEO` name. The original calibrated module must
already describe that garment, skeleton and rest layout. A preset import only
updates a matching layout; it does not silently refit another topology.

The current Nini scenes, previews, presets and measured limitations are indexed
in `assets/Nini/review/skirt_contact/README.md`. The full correction adds
substantial evaluation cost; that delivery is functional deformation evidence,
not a real-time performance acceptance.

The existing Framework/menu exposes Upgrade Skirt Contact, Calibrate Skirt Rest,
Import/Export Skirt Preset, Reset Skirt Controls and Check Skirt Contact.
No additional window or per-frame Python callback is installed.

Construction suspends refresh and uses lazy DG evaluation. A successful upgrade
adopts the project's conservative Parallel CPU profile with GPU/cache override
off and a data-only marker on the character root. Failure undoes owned changes
and restores evaluator/refresh/selection state. Profiling is never part of
CREATE RIG or the upgrade action.

## Native validation and delivery

Run `scripts/validate_skirt_contact.py` through `scripts/run_maya_test.py` in a
disposable mayapy process. It retains failures and writes versioned JSON reports
under `assets/Nini/experiments/skirt_contact/`. A delivery scene is written under
`assets/Nini/scenes/` only after that run's acceptance checks pass.

The gate compares neutral appearance, topology/UV/materials, actual skin/bind/DQ
data, body preservation, sampled tunic/embroidery contacts, final chain lengths,
DG/Serial/Parallel output, reverse pose access, manual controls, legacy bypass,
presets, recalibration, lossless SKC round-trip, native reopen, two rebuilds and
namespaced/renamed controls. Separate delivery checks cover global transforms,
runtime portability, timings and the demonstration animation.

The delivered Nini pose cohort uses its recorded global transform and scale 1.
Global transformation tests are reported separately. The archived source body
already fails exact uniform-scale covariance in a held leg pose; the skirt
upgrade does not repair the character's global rig. Positive uniform matrices
are a structural precondition, not an acceptance certificate for arbitrary
global edits. Do not scale the top `Nini` asset transform as an animation control.
Use `C_masterwalk_CTL` and its `globalScale`, then validate the new pose cohort.

Equivalent-data comparisons use maximum error <= 1e-4 scene units. Contact
checks fail for sampled penetration deeper than 0.01 cm. The length gate is
maximum final segment stretch <= 5 percent. A 0.10 cm surface gap is an offset
target, not a guaranteed minimum gap between all sampled triangle interiors.
Do not increase tolerances after a failed candidate.

## Boundaries and rollback

This is a stateless procedural contact rig. It does not solve physical cloth,
general self collision, cloth length across all mesh edges, floor or chair
contacts. The sparse final projection assumes useful outward closest-point
normals in the convex waist region. Concavities, larger poses, custom meshes,
open skirts and unsupported scales require their own acceptance tests.
Finite vertex/edge-midpoint/triangle-center sampling does not prove absence of
all triangle intersections. Open pants only support unsigned proximity in the
existing audit; do not label that measurement penetration-free.

KeepOut and all added utilities are native nodes, but native nodes are not an
automatic performance or GPU guarantee. Measure build, control edits and
uncached playback separately; a batch-demand timing is not viewport FPS.
CPU is the acceptance reference. GPU/cache remain unapproved without dedicated
geometry, invalidation and stability coverage.

The source scene and earlier candidates remain untouched. `solverBlend=0`
restores the retained baseline deformation branch, including disabling the
final surface offsets. Undo reverts a fresh upgrade; reopening the original
version is the complete rollback after saving. Keep intermediate source shapes
and their graph connections; do not delete history or freeze a skinned mesh.
