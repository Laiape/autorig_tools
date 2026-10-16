# Flower rig family

Parent: `maya_tools/how_it_works.md`.

The shared `utils/create_rig.AutoRig.build` dispatches `Rig_Type = 2` through
`utils/rig_manager.py` to `flower/autorig/flower_module.py`. The existing
Character Manager, guides, controller templates, skin import/export, build
progress and scene evaluation contract apply.

## Inputs and ownership

- `assets/<asset>/models/`: prepared model with unique geometry names.
- `build/*.build`: normal guide settings, including `Rig_Type: 2`.
- `guides/*.guides`: standard world matrices for stem, head, leaves and petals.
- `rig_data/flower.json`: schema 1 shell membership and module/guide mapping.
- `curves/*.curves`: existing editable controller shape templates.
- `skin_clusters/*.skc`: standard lossless skin snapshots.

The shell map is separate from the guide settings so exporting settings from
the existing editor retains the module recipe. An optional inline `flower`
block in `.build` is also supported. Each leaf/petal entry names its mesh,
ordered guides, vertex membership and expected vertex count. Topology changes
require authoring a new shell map and compatible skin data.

The module classes follow `biped/autorig/arm_module.py`: `__init__` reads the
shared build data and `make` calls explicit guide, control, setup and export
stages. `StemModule` owns the FK stem. `HeadModule` owns the head attachment.
Each `LeafModule` instance owns one leaf; each `PetalModule` instance owns one
petal. The supplied asset has 34 module instances.

Each instance creates `*Module_GRP` below `rig_GRP/modules_GRP`,
`*Skinning_GRP` below `rig_GRP/skel_GRP`, and `*Controllers_GRP` below the
master control. Module groups own attachment references or native space
constraints. Controls drive skin joints through their world matrix and the
actual joint parent's inverse matrix. Skinning groups remain independent.

The normal rig builder calls `rig_manager.skeleton_hierarchy(module_chains=...)`
after module creation. Its explicit chain attachments use the existing
`parented_chain` helper and create 105 `_ENV` joints under
`rig_GRP/skeletonHierarchy_GRP`: freeze -> stem -> head, leaves branching from
their stem anchors, and 30 petal chains branching from the head.

Control inputs flow to matrices/joints and then to skinClusters. Global/local
curl, spread and twist use native utility nodes on separate AUTO offsets.
Static shell fitting and initial weight interpolation run only at authoring
or build time. A first build without SKC binds complete shell coverage with
at most two adjacent influences. Later builds restore the asset's saved SKC.

## Animation

Root petal controls expose `space`, `curl`, `spread` and `twist`. Head exposes
`petalCurl`, `petalSpread`, `petalTwist`, `showPetalDetails`, `showLeafDetails`.
The raised root-control drawing sits over its petal; its pivot stays at the
attachment. Detail shapes default hidden while their FK chains evaluate.
`C_settings_CTL` uses an F curve from the shared `curve_tool.text_curve` helper.
The supplied `flower_v002.curves` preserves that drawing across builds.

Select petal roots and use the existing ANIMATION catalogue/menu actions:

- Release Selected Flower Petals: match to World and key the current frame.
- Attach Selected Flower Petals: match back to Head and key the switch.

`petal_module.set_space(controls=None, space='World', key=True)` implements the
same action. It preserves world TRS, inserts previous-frame keys and uses a
stepped space curve. Directly editing `space` changes the reference without
matching. Released petals can be translated/rotated and curled by the animator.
World release keeps a petal independent of subsequent master/stem movement;
global petal shape channels continue to affect its curvature by design.

## Quality and rollback

This family adds an editable flower rig. The quality contract preserves the
model's neutral vertices, topology, UVs, normals, hard edges and materials.
The initial recipe uses seven stem anchors, three joints per petal/leaf and
one head joint. FK deformation is an authored animation behavior.

`tools/tests/test_flower_module.py` validates the supplied flower in a
disposable native Maya session. It checks independent shell movement,
nonzero posing, both petal rows, scaled/rotated space switches, keyed release,
DG/Serial/Parallel agreement, native animation reopen, guide matrices,
lossless SKC, controller drawings, module parenting and every `_ENV` world
matrix across two full rebuilds.
Tolerance is 1e-4 cm for geometry and 1e-5 for evaluated normals.

Source and delivered scene identities and measured results are in
`assets/flower/validation/structure_rig_validation_20261016.json`.
`structure_equivalence_20261016.json` separately compares four poses against
the previous rig: zero vertex/normal error and exact weights. The original
`flower_v01.ma` and previous rigs are preserved. Reopening `scenes/flower_rig_v003.mb` restores
the delivered neutral rig after a trial. Scene construction stays lazy DG;
successful builds adopt Parallel CPU with cache/GPU override disabled.
The validation is separate from ordinary CREATE RIG. No playback speed claim
is inferred from node counts or build receipts.

The artist-requested Rabbit weight revision is `skin_clusters/flower_v002.skc`.
It smooths the two petal meshes in surface mode without cross-shell mixing,
using their three existing joints per petal. Initial automatic binding still
uses two adjacent joints; saved authored skin data is restored as exported.
See `assets/flower/validation/rabbit_smoothing_20261016.json` and
`rabbit_rebuild_validation_20261016.json` for export and persistence checks.
