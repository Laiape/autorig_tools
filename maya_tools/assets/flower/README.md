# Flower asset

Open `scenes/flower_rig_v003.mb` in Maya 2026. It is the neutral rig scene.
`flower_v01.ma` is the untouched Maya 2024 source. `models/flower_v001.ma` is
the prepared geometry/material asset used by Character Manager and CREATE RIG.

The asset keeps its authored centimeter scale and position. Five meshes contain
3,351 vertices: the stem, central disk, two leaves and two rows of 15 petals.
Petals remain disconnected shells within their original two meshes. Preparation
renames and groups geometry while keeping topology, UVs and materials; unused
source lighting/HDRI and editor dependencies are excluded from the model export.
The manifold/lamina checks passed for all five meshes.

## Controls

- `C_masterwalk_CTL`: move, rotate and uniformly scale the complete flower.
- `C_stem00_CTL` through `C_stem06_CTL`: seven FK stem anchors for bending/fall.
- `C_flowerHead_CTL`: head orientation/offset, global petal curl/spread/twist
  and the petal/leaf detail visibility switches.
- `C_leaf0100_CTL` and `C_leaf0200_CTL`: leaf roots with independent curl.
- `C_petalA0100_CTL` through `C_petalA1500_CTL`: cyan first-row petal roots.
- `C_petalB0100_CTL` through `C_petalB1500_CTL`: pink second-row petal roots.

Each petal and leaf has three FK controls. Enable `showPetalDetails` or
`showLeafDetails` on the head for the hidden middle/tip controls. The rig has
104 module controls plus the three shared character/master/settings controls.
Selection sets: `flower_controls_SET`, `flower_petals_SET`, `flower_skinJoints_SET`.
Polygon counts refer to the original cage.
`C_settings_CTL` has an F drawing and keeps the shared visibility/display channels.

## Scene structure

The main transform is `flower`. Its `rig_GRP` contains `modules_GRP`, `skel_GRP`
and `skeletonHierarchy_GRP`; `controls_GRP`, `geo_GRP` and `deformers_GRP` are
siblings of `rig_GRP`. All 34 module instances follow the existing ArmModule
class/group pattern and own separate mechanics, skinning and controller groups.
The export hierarchy contains 105 `_ENV` joints with leaf branches on the stem
and independent petal branches on the head. `showSkeletonHierarchy` displays it.

## Animate a release

Animate the fall with master rotation/translation and stem FK overlap. Use the
head for a small secondary lag. At the release frame, select one or more cyan/
pink petal root controls and choose AutoRig Tools > ANIMATION > Release Selected
Flower Petals. This matches their current world pose and keys Head -> World.
Continue the petal's translation/rotation, with curl/twist for secondary motion.
Attach Selected Flower Petals matches them back to Head space if needed.

The menu uses the same actions as Tool Framework. Changing `space` directly
does not run the pose match. Released petals still receive the head's global
curl/spread/twist values; use the petal's own channels for individual variation.

## Rebuild and evidence

Select flower in Character Manager and use normal CREATE RIG. `Rig_Type = 2`
loads `maya_tools/scripts/flower/autorig/`. The asset recipe is in
`rig_data/flower.json`; guides, controller shapes and lossless skin data use
the existing `.guides`, `.curves` and `.skc` formats. Import the guide file into
the prepared model to edit its placement and export through the existing tools.

`validation/asset_setup_20261016.json` records the source hash and model checks.
`validation/structure_equivalence_20261016.json` compares the revised rig with
the previous rig over four poses, including curl and global scale/rotation.
Weights are exact; evaluated vertices/normals have zero maximum difference.
`validation/structure_rig_validation_20261016.json` records two full rebuilds,
source appearance, per-shell posing, modes, native reopen, module group parents
and matching skinning/ENV world matrices. The previous `flower_rig_v001.mb`
and original curve preset remain available.
See `maya_tools/scripts/flower/how_it_works.md` for implementation and limits.

## Rabbit petal smoothing

`skin_clusters/flower_v002.skc` is the current lossless skin export. The two
petal meshes were smoothed with the installed brave rabbit `brSmoothWeights`
tool: surface mode, cross-shell smoothing disabled, strength 0.5, four samples
and three Flood passes. Petal vertices can blend their three chain joints;
each shell retains only its own influences. The other three skins are unchanged.

`scenes/flower_rabbit_review_v001.mb` preserves the artist's frame 1001 and
`petalCurl = 195` review pose. The before-edit recovery scene is retained.
`validation/rabbit_smoothing_20261016.json` records scope, settings, normalized
weights and exact export verification. `rabbit_rebuild_validation_20261016.json`
records two rebuilds and native reopen with the new weights.
