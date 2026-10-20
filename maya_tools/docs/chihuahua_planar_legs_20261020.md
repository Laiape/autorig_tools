# Chihuahua hind-leg model preparation

Parent: `maya_tools/how_it_works.md`.
Evidence: `docs/validation/chihuahua_planar_legs_20261020/summary.json`.

The user requested a planar model for refitting guides, with the knees facing
forward, hocks backward and ankles untwisted. Only the hind legs are changed.

`models/chihuahua_v003.mb` bakes the posed body and matching rear nails into a
new static model. It retains topology, UV data, material connections and the
unloaded original groom reference. The original v002 model remains available.
The normal model loader selects this new version.

`scenes/chihuahua_planar_legs_v001.mb` retains the editable native rig and its
FK preparation pose. It was built with the shared AutoRig builder from model
v002, guides v012, skin v013 and the existing character build settings. The
body uses its existing skin; the unskinned rear nail vertices follow the same
rigid paw operators. No new body weights are authored.

`scenes/chihuahua_planar_guides_work_v001.mb` contains the static model and
the original v012 guides, ready for artist repositioning. Only their display
radius is reduced. The model is reference-displayed so guides remain selectable.
The saved guide and skin presets are not replaced. This is a model preparation
delivery, not approval of a new rig built with the old guides and new model.

Hip, knee, hock and ankle lie in one vertical sagittal plane per side. FK
rotations preserve segment lengths and the existing side-profile bend signs.
Foot orientation uses the central toe direction and transverse toe span,
rather than assuming the authored controller axes describe the actual sole.
The forefoot retains its longitudinal pitch while yaw and lateral bank are zero.
The old pastern guide offset remains provisional for the artist's refit.

## Native checks

- Both main hind-leg chains have transverse spans below 3e-14 cm. Segment
  length errors are below 1.4e-15 cm. Knee bend is forward and hock bend backward.
- Central foot yaw and lateral bank are below 1e-12 degrees on both sides.
- Exact hashes of body skin weights, DQ blend weights, bind matrices,
  influence identities and skin method agree before posing and after native
  save/reopen of the editable rig.
- All 17,150 body vertices with original Z >= 10 cm remain exactly unchanged.
  Every other primary mesh except the body and rear nails is unchanged.
- Static-model topology, UV data and material connections remain unchanged.
  Native reopening matches posed body points within 7.5e-9 cm and all other
  outputs exactly. The rig reopens with zero point error.
- Nail locked normals rotate with their paw; body normals follow the new
  surface. Rear and side native hardware renders were visually inspected.
- The working guide scene was natively reopened and its body rechecked.

The original optional groom is retained unloaded and has not been reposed.
Its hind-leg fit needs a separate groom update if that original groom is used
with the changed model. No runtime code, solver, saved guides or SKC is changed.

## Left ankle guide correction

The follow-up guide delivery is `guides/chihuahua_v013.guides` and
`scenes/chihuahua_planar_guides_work_v002.mb`. It corrects the left fetlock,
pastern and internal sole-tip guide that were deliberately still at their
old positions in the v001 working scene. Other guide entries, including the
digit guides and the right side, remain unchanged.

Fetlock and pastern are placed between opposite front/back mesh surfaces at
their respective heights. Both share the hock's transverse plane, X =
3.321261788 cm. Their transverse offsets from the surface midpoints are only
0.016335 cm and 0.021362 cm; the common plane avoids introducing a lateral
bend between them. Fetlock local X aims at pastern, pastern local X aims at
the centered sole-tip helper, and their local Z axes point along world -X.
This removes lateral roll and yaw from the guide frames.

Only these three world matrices change in the preset. Other guide world
matrices and the model geometry are preserved. The v002 guide scene reopens
with the corrected matrices and zero model point error. Evidence is in
`docs/validation/chihuahua_ankle_guides_20261020/`. The artist's previously
unsaved rig test was saved separately before changing scenes, under the
outer workspace's `tmp/chihuahua_ankle_guides_20261020/`.

A normal shared AutoRig build succeeds using v013. Both generated FK control
matrices match their authored guides within 3.2e-15 and remain exact after
native save/reopen; the native export skeleton is populated. This checks
guide-to-control placement, not a skin rebind or deformation acceptance.
The artist session is left in the corrected guide scene for further fitting.
