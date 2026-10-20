# Chihuahua anatomical knee rest correction

Parent: `maya_tools/how_it_works.md`.
Evidence: `docs/validation/chihuahua_forward_knees_20261020/summary.json`.

This supersedes the v003 model and guide-only ankle correction. The user's
annotated front view showed the knee volume still pointing outward. Coplanar
guide positions and controller matrices did not establish anatomical alignment.

## Delivery

- `models/chihuahua_v004.mb`: corrected static hind-leg rest model.
- `guides/chihuahua_v014.guides`: sagittal hind-leg frames and paw digit guides
  fitted to the corrected rest. Foreleg and facial guides are retained.
- `skin_clusters/chihuahua_v014.skc`: lossless finite body weights, native
  deformation data and rigid rear-nail attachment.
- `scenes/chihuahua_forward_knees_v001.mb`: rebuilt native rig, neutral and
  ready to test using the rear foot IK controls.
- `scenes/chihuahua_planar_guides_work_v003.mb`: model and editable guides.

All prior versions remain available. No runtime module or solver code changes.

## Anatomical correction and source data repair

The original skinned rig remains the posing source. A temporary, static
rest-preparation pass rotates the upper, middle and lower hind-leg skin input
matrices around their longitudinal axes. Mirrored turns of approximately
53.2704 degrees bring the tracked outward knee landmarks into forward-facing
planes while preserving the prepared feet. These temporary skin input overrides
are baked into the static model; they are not present in the delivered rig.
The normal shared AutoRig builder creates its controls and populated native
`_ENV` hierarchy from the new guides and model.

Source SKC v013 had four nonfinite weights: `C_neck00_ENV` and `C_head_ENV` on
body vertices 11682 and 20147. They made both vertices nonfinite, including in
the original neutral rig. Replace only those four invalid entries with zero;
every originally finite body weight, tiny positive weight, DQ mask and skin
method is retained exactly. Earlier error maxima silently failed to reject
nonfinite values and are not valid geometry-quality approval.

The v003 static model had baked those invalid coordinates. Build the new model
from the uncorrupted v002 mesh base, retaining topology, UVs, face material
assignments and the previously prepared nail positions/normals. An explicit
finite-value check is required after native save/reopen. Editing invalid base
points through Maya tweaks alone is insufficient because NaN differences can
remain NaN.

Rear nails were previously unskinned. A rigid native `C_nails_SKC` now follows
the two rear fetlock influences. Front nails retain their static behavior
through the native freeze root. This does not author foreleg body skinning.
The body is bound to the new intentional rest and exported through the existing
lossless SkinManager. Native rebuilds reproduce the rest and repaired weights.

## Validation scope

- All ten primary meshes have finite points and face-vertex normals. Topology,
  UV data and face material assignments match v002. The 17,150 front body
  vertices with source Z >= 10 cm are unchanged. Other primary meshes remain
  unchanged except the intentionally reposed body and rear nails.
- The final SKC contains no nonfinite numeric values anywhere. Body finite
  weights and DQ data survive lossless export and a normal rebuild exactly.
- Native rig/model reopening and further normal builds match the corrected
  neutral body within 7.5e-9 cm. The export skeleton is populated.
- Nine bounded poses cover left/right IK lifts of 2 and 4 cm, both feet lifted
  4 cm, and left/right FK knee flexion at 25 and 50 degrees. Actual ankle lift
  and nonzero body motion are checked. Tracked knee lateral drift is zero.
- DG, Serial and Parallel body outputs agree in each pose. Reverse transitions
  return exactly to neutral. Rear nails match their rigid paw operators within
  1e-6 cm and front nails retain their previous static positions.
- All tested body points are finite. Rear-region triangle area ratios are
  recorded, rather than treating unchanged topology as proof of good skinning.
  Native front/side renders of neutral, 2 cm and 4 cm lift were inspected.

The 4 cm lift is a tightly compressed pose. These checks demonstrate corrected
bend direction in the stated samples, not approval of arbitrary extremes,
global/nonuniform scale, or a new corrective sculpt. Original groom data remains
unloaded and has not been adapted to the new model.
