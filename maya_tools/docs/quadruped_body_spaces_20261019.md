# Quadruped spine, neck and body spaces

Parent: `maya_tools/how_it_works.md`.
Evidence: `docs/validation/quadruped_body_spaces_20261019/summary.json`.

## Delivered behavior

- Spine00 has body/localHip/masterWalk source choices. TranslateValue and
  RotateValue default to 1, and body is the default source.
- Intermediate spine controls follow spine00. The tip follows the middle and
  endpoint tangents follow their endpoint. Every secondary primary/tangent has
  its own Follow Local/Global enum. Global follows masterwalk, independently of
  the root, while Local retains the normal hierarchy. Neck controls have the
  same per-control choice and neck00 has localChest/body/masterWalk spaces.
- BodyPivot uses the actual back-leg PV curve drawing. Its world matrix drives
  body_GRP with inheritance disabled. Native rotate/scale pivots and rotation
  pivot translation compensate the offset, so repositioning the pivot at neutral
  does not move body. Body rotations use the selected point. Pivot Visibility
  on body controls the drawing.
- LocalChest translates/scales the upper spine input points. Its local rotation
  remains local to chest; it does not bend the spine curve. Its parent position
  follows the solved tip, with local translation removed once to avoid doubling.
  Cross-sectional chest scale fades from the middle to full effect at the tip.
- Body and neck00 expose Volume Preservation, default 1. The native graph uses
  the solved ribbon's upstream segment distances and inverse-square-root length
  compensation. GlobalScale is removed from that measurement. Transverse scaling
  is applied in solver axes before the authored skin-joint axes are calibrated.
  Setting the attribute to 0 disables automatic compensation.
- Head Space is Local/Global. Local follows the last neck control. Global pins
  position and orientation in world space. The head control drives both the
  actual head skin joint and the neck endpoint, so the neck adapts to a pinned
  head. Character-global secondary controls and a world-pinned head are distinct
  animator choices. New builds default to Local; the delivered review scene is
  set to Global.

The normal builder, module groups, native ENV hierarchy, lazy DG construction
and successful-build Parallel CPU/cache-OFF policy remain in use. There is no
expression, per-frame Python, callback or benchmark in the new runtime graph.

## Existing scene and persistence

The starting scene was the artist's modified CHAR_chihuahua_v001.ma. A complete
ASCII export preserved its unsaved work before adapting the existing graph.
The migration reuses production module methods, keeps existing skin nodes,
influences, weights, DQ weights, bindPreMatrix values and the artist's static
translation/rotation channels. It calibrates at neutral and restores those
channels afterward. Driven/animated channels are rejected before editing.
This bounded authored-frame migration is not an automatic scene upgrade.

Saved files:

- `assets/chihuahua/scenes/chihuahua_body_spaces_v001.ma`.
- `assets/chihuahua/scenes/chihuahua_before_body_spaces_20261019_v001.ma`.

Maya had changed to an edited Nini scene by delivery time. That scene was not
replaced; the updated Chihuahua is provided separately. The outer checkout's
runtime files were not modified.

## Native acceptance

Maya 2026 passed six new behavior regressions, three spine-tangent regressions,
four authored-frame regressions and twelve ordered-guide fixture cases. The
ordered-guide cases exercise two reproducible module builds and native reopen.
Two complete Chihuahua builds through AutoRig.build passed the new space enums,
per-control Global independence, root hierarchy, world-pinned head, globalScale
0.5/2, native ENV skeleton, DG/Serial/Parallel agreement and native binary reopen.

The artist-scene migration preserved all 11 skins, including polygon and NURBS
bindings. Native weight arrays, DQ weights, influences, bindPreMatrix and skinning
methods matched exactly after migration and reopen. Ten visible mesh outputs
had a maximum neutral coordinate difference of 4.76837158203125e-7 scene units.
Joint-matrix difference was 5.959726956383804e-8. Face-vertex normal difference
was zero; topology, UV assignments, materials and smooth edges matched exactly.
The actual body pose changed skin output by 4.679718017578125 units while the
head joint stayed fixed. DG/Serial/Parallel and native ASCII reopen differences
were zero in the tested poses. The delivered pivot CVs match the actual PV shape.

Standalone logs retain pre-existing optional-guide/XGen preview warnings. The
artist snapshot contains nodeGraphEditorInfo data not recognized in standalone;
it is preserved by keeping the delivery in ASCII rather than deleting UI data
to force conversion to binary. Full-builder binary scenes are separate tests.

No playback speedup, GPU/cache acceptance, arbitrary leg-axis permutation or
general nonuniform character-scale equivalence is claimed by these checks.

## Leg guide planes and axes

Guide positions and pole-vector placement determine the solve's bend plane.
Tilting a leg's entire plane relative to the world is valid. Rotating a guide's
local axes is a separate operation: with authored_guide_orientation enabled,
static adapters separate authored animator/skin axes from the solver's required
frames. This does not make arbitrary axis changes deformation-equivalent.
Ankle orientation, paw roll, FK channels and bind-relative deformation still
need anatomical intent and validation. Change guides before binding and review
the rebuilt bind/skin data when revising an already weighted skeleton.

The current quadruped node solver also preserves a non-planar authored rest
residual on output frames. Preserving that rest shape does not certify that
every non-planar moving pose has the same result as a different 3D solver.

Primary reference: [Autodesk rotate-plane IK solver](https://help.autodesk.com/cloudhelp/2022/ENU/Maya-CharacterAnimation/files/GUID-9942FFB5-65C2-46E2-B5A3-297667A9FB5D.htm).
