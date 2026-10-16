# Large-angle eyelid rotation correction

Parent: `maya_tools/how_it_works.md`.

Superseded at the artist's request by the original main-control pivot with
reduced corner influence. Current implementation and evidence:
`../eyelid_control_falloff_20261016/README.md`. This folder retains the previous
orbital experiment and its scoped validation, not current acceptance.

The previous rigid primary-control pivot separated shared corners: Edward's
lower Z=-25.241064, Y=-0.210380 pose had a 1.19927 cm maximum corner gap.
Joining endpoint positions alone removed that gap but still folded the mesh
at 60 degrees. Numerical contact alone was insufficient acceptance evidence.

The corrected construction rotates in the authored eye frame. The endpoint
and adjacent CV on both borders share the mean upper/lower roll; interior
CVs transition to the corresponding primary roll. Calibrated tangent axes
transport the existing aim frames without changing the neutral bind.
Both tangent reference axes converge during full blink. Detail rotations
remain downstream and can deliberately change individual joint orientation.

Production changes are in `tools/eyelid_rotation.py`, `eyelid_corners.py`,
`eyelid_contact.py`, and `biped/autorig/eyelid_module.py`, under
`maya_tools/scripts/`. No skin weights, bind matrices, joint names or
animator channels are edited by the installer. The explicit legacy upgrade
is undoable and idempotent; new builds install the same graph. No profiling
is added to CREATE RIG. The earlier CPU comparison predates this correction.

## Validation scope

- Synthetic L/R builds, 7/11 guide samples, independent Up/Down Z=-90..90,
  translation, blink 0/0.5/1, DG/Serial/Parallel, native save/reopen.
- Neutral aim orientation agrees with the original frame within 1e-5.
  Full blink agrees in joint position and orientation within 1e-4.
- Additional rotated and nonuniformly scaled authored eye frames are tested.
- The pre-fix Edward snapshot passes 252 pose/evaluation cases, with no
  border segment self-intersections, unchanged joint identities, idempotent
  upgrade and native MB reopen. Neutral maximum matrix error is 3.33e-8;
  reopen maximum matrix error is zero.
- GUI captures in `final/` inspect the actual mesh at +/-60 and +/-90 degrees
  and closed blink at 60 degrees. The large folded rim is removed at 60.
  The -90 extreme still exposes contact/shading imperfections around the
  lower orbital edge; it is not certified as production-quality deformation
  at arbitrary angles. Numerical on-sphere attachment is not a final mesh
  intersection guarantee.

Earlier rejected corner-displacement and frame trials remain in the sibling
image folders for comparison. Only `final/` represents the delivered graph.
Native regressions: `test_eyelid_blink.py`, `test_eyelid_primary_roll.py`,
`test_eyelid_corner_roll.py` in `maya_tools/scripts/tools/tests/`.

Artist recovery files, outside this checkout:
`C:/proyectos/auto-rig/recovery/eyelids_large_roll_before_20261016_v001.mb`,
`C:/proyectos/auto-rig/recovery/eyelids_before_orbit_final_20261016_v001.mb`,
`C:/proyectos/auto-rig/recovery/Edward_eyelids_rotation_fixed_20261016_v001.mb`.
