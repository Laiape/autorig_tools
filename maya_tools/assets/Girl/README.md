# Girl

## Selected finger-band clusters (2026-10-21)

`scenes/Girl_finger_clusters_v001.mb` preserves the artist's current scene and
adds four editable left-hand clusters for index, middle, ring and pinky.
The selected continuous 128-face band is divided at the three interdigital
concavities into disjoint vertex regions; all 256 selected vertices are covered.
Handle pivots use each region's bounding-box center. Model positions are unchanged.
Source membership is recorded in `reference/finger_loop_clusters_20261021.json`
and the four `L_*Loop_SOURCE_SET` component sets in the native scene.

## Edward controller drawings (2026-10-21)

`curves/Girl_v002.curves` reuses Edward v002 controller drawings, fitted in
object space to Girl v007 guide proportions. Body, limbs, feet, neck, head,
mouth, brows, eyelids, eyes, ears and each finger use separate measured spans.
Long finger-root boxes also fit the complete target finger length; finger
drawings have a width bound relative to that span to avoid oversized controls.
Girl keeps its own settings drawing. Fourteen additional eyelid/finger controls
reuse equivalent Edward drawings. The 332 templates cover all 310 controls
created by Girl's current module configuration; unused donor templates remain
available for compatible module configurations.

`fit_edward_curves.py` regenerates the template and its per-control fitting
receipt. The normal template loader selects this version automatically.
`scenes/Girl_edward_curves_v002.mb` is an editable controller review built with
the shared native model/module builder and a populated export skeleton. It has
no imported skin weights and is not a deformation-approved rig. Earlier model,
guide and curve versions remain available. Existing socket guide-name warnings
from the module builder are outside this controller-drawing adaptation.
This revision ends the spine at its last spine guide and places localChest at
the independent chest guide; v001 retains the earlier endpoint placement.
Its native reopened anchors and controller-template checks are recorded in
`validation/spine_endpoint_reopen_v002.json`.

Native reopen, complete template coverage, exact drawing topology, controller
matrix preservation and unchanged model points after shape application are
checked in `validation/edward_curve_reopen_v002.json`. The fitting receipt is
`validation/edward_curves_v002.json`.

## Current model and guides (2026-10-21)

New builds start with `C_settings_CTL.resolution` set to High Res. High Res is
also the attribute's reset value. Reconfiguring an existing selector retains
its currently chosen resolution.

The current model is `models/Girl_v002.mb`, prepared from the new download
`YDRAY-Girl_rigging.ma`. Open `scenes/Girl_guides_high_v008.mb` for editable
guides, or load `guides/Girl_v011.guides` through Character Manager. Earlier
models, guide exports and native review scenes remain available.

The latest facial edit uses the artist's 108 selected Body_high edges: a
64-edge lip ring and a 44-edge left eyelid ring. The right eyelid follows its
real connected counterpart vertices; the maximum distance from a perfect
reflection is 0.002619 cm. Each CV is an actual High Res vertex, with 33 CVs
per lip arc and 23 per eyelid arc. Paired arcs share both endpoints and start
at the maximum world-X vertex of their complete ring. Each ring is split into
equal edge counts, including the independently reordered right eyelid. V011
corrects v010's right-eye maximum X at CV[1]. The selected and mirrored
source edges are inspectable under `Girl_selectedFacialGuideSources_20261021_SET`.
Joints, other curves, model vertices and existing native attachments are
preserved. Native reopen and export correspondence are checked in
`validation/facial_cv_order_20261021_v002.json`. Exact ordered source IDs are in
`guide_sources/selected_facial_edges_20261021_v002.json`.

This model preserves the new source's 25 primary mesh outputs and topology,
including its revised High Res body, hair blocking, gums and watch placement.
`Body_high8` is named `Body_high` for compatibility. Low/High/shared groups retain
their explicit LOD roles. The 14 PNG texture paths point to this asset's existing
texture tree. XGen/scalps remain outside the prepared model, matching the earlier
Girl delivery. The downloaded source, including its grooming, is unchanged.

The new guide scene retains all 118 joints and the current live guide matrices.
Upper/lower lip and eyelid curves use the newly selected connected source
routes; socket rings and evaluated eyebrow curves retain their earlier routes.
The artist's current loaded-guide scene had no cluster or surface-constraint
nodes before this edit. The earlier v006 native scene remains the archive of
the nine clusters and 26 brow/foot attachments; the static `.guides` format
does not reconstruct those dependencies. Paired facial arcs begin at the shared
vertex with maximum world X across both arcs.

The shoulders retain their approved positions and orientations. Elbow TX is
the closest projection of the new loop's bounding-box center onto shoulder X;
elbow RY and wrist TX place the wrist as close as its XZ plane permits. This
leaves elbow residuals of 0.563/0.561 cm and wrist residuals of 1.150/1.150 cm
on L/R. These are explicit constrained approximations, not exact loop centers.
Both sides have inspectable `Girl_*_modelRefreshLoop_SET` component sets.
All 24 finger guides per hand, including their independent root branches, follow
the revised hand's rigid correspondence; maximum surface residual is 0.00138 cm.
The outfit and polygon hair review layers can be enabled to inspect those meshes.

Native model/guide reopening, source geometry/topology, finite points/normals,
guide matrices, facial connectivity/order, shoulder preservation, and actual
brow/foot attachment motion have been checked. Evidence and review images are
indexed in `../../docs/model_refresh_20261021.md`. This is a model/guide update;
the initial model's full Model Checker results below do not certify the new
source, and no new rig build, skinning or animation acceptance is claimed.

## Earlier preparation and guide history

Registered Character Manager asset, prepared from
`D:/RIGS/Girl/Girl_rigging.ma` on 2026-10-20. The source scene is preserved.
`thumbnail.png` is the supplied reference image; its full copy is in `reference/`.

Open `models/Girl_v001.ma` for modeling or `scenes/CHAR_Girl_v001.ma` for the
prepared character structure and `C_settings_CTL.resolution` selector.
This is a model preparation delivery. The first editable guide fit is in
`scenes/Girl_guides_high_v001.ma` and `guides/Girl_v001.guides`, with High Res
active. Its native biped hierarchy has 118 joints, 12 locators, ten facial
curves and two hidden construction surfaces, fitted from the existing project
schema to Girl. This is an initial proposal awaiting artist feedback; animation
modules, an export skeleton and skinning have not been built.

The guide review scene uses neutral viewport shading. Two review display layers,
`Girl_guideOutfit_LYR` and `Girl_guideHair_LYR`, hide the outfit and polygon hair
to expose the anatomy; turn them on to inspect those meshes again. The source
model and earlier character scene are unchanged. The unsaved artist model was
preserved in `scenes/Girl_before_guides_live_v001.ma` before guide placement.
Front/side captures and native guide round-trip checks are in `validation/`.

The previous loop review is `scenes/Girl_guides_high_v002.ma` with
`guides/Girl_v002.guides`. It preserves the artist's nine component-tag clusters,
adjusts 22 joint anchors from the selected anatomical loops/patches, and replaces
all ten facial curves by connected High Res mesh-edge polylines. Lips have 33 CVs
per arc, eyelids 23 per arc and socket rings 45 including the repeated closure.
Each upper/lower lip or eyelid pair shares CV[0] at its maximum world-X corner
and also shares its other endpoint. No model points were changed.
`Girl_guideLoopSelections_SET` contains the inspectable source selections.
Cluster5 is two open breast-front chains and remains an anatomical reference;
it was not silently substituted for the thoracic pivot. Other unconfirmed guide
positions remain editable for further artist feedback.

The full Edward reference audit, cluster mappings and exact curve connectivity
checks are saved in `validation/edward_guide_placement_audit.json`,
`validation/artist_cluster_loop_mapping_v002.json` and
`validation/topology_guide_fit_v002.json`. The learned workflow is recorded in
`.cursor/rules/rig-guide-placement.mdc` at the repository root.
`validation/topology_guide_fit_v002_reopen.json` verifies the saved native scene:
all curve segments are actual mesh edges, curve-to-vertex and model position
errors are zero, all nine cluster selections are preserved, and High Res is active.

The previous channel review is `scenes/Girl_guides_high_v003.ma` with
`guides/Girl_v003.guides`. It applies the artist's channel conventions:

- Arm roots allow T/R; elbows use TX/RY; wrists use TX with zero rotation.
- Leg roots allow T/R; knees use TX/RZ; ankles use TX with zero rotation.
- These limb chains retain all their previous world anatomical anchors.
  jointOrient and rotateAxis are zero, so no extra bend axes are hidden there.
- Spine and neck retain their endpoints and use uniform TY-only spacing in
  their root-oriented local frame. Child rotations are zero.
- Each ear starts on a lobe vertex, ends on the superior helix and has an exact
  midpoint, with uniform TY-only spacing along its root-oriented local frame.
- Eight foot pivot locators follow `suela_low` in X/Z and stay at Y=0.
- Each eyebrow follows nine consecutive vertices of the actual `cejas_low`
  longitudinal edge chain, projected onto `Body_high`. The CVs use native body
  surface attachments, with CV[0] nearest the world centerline. Source eyebrow
  edge sets and body attachment UVs are recorded separately; the curve is not
  forced to switch body edge rows to approximate the brow arch.

The native scene retains 26 `pointOnPolyConstraint` nodes under
`Girl_guideAttachments_GRP` for the foot and brow attachments. The existing
`.guides` format exports their evaluated matrices/CVs as static guide data.
Native reopen checks, actual attachment-follow trials and viewport captures
are in `validation/channel_feedback_v003*.json` and the v003 PNGs. All 25 model
meshes are unchanged; nine artist clusters and paired lip/eyelid endpoints are
preserved. Other guide frames are unchanged within floating-point precision.

The previous torso review is `scenes/Girl_guides_high_v004.ma` with
`guides/Girl_v004.guides`. The live artist correction is authoritative: all five
left leg joints and their local channels are preserved exactly, and the entire
branch, including ball/tip, is behavior-mirrored to R. L hip is RX=90/RZ=-90,
with its authored RY retained; R hip is RX=-90/RZ=90 with mirrored RY.
Shoulder X retains upper-arm aim. L shoulder RX=0 and mirrored R RX=180 make
signed local Y vertical in the side projection; elbow channels and independent
finger frames are preserved.

Spine retains its artist root frame and uses uniform local TY=2.63292700644
between its eight guides. Its endpoint reaches Y=122.31533813477, the marked
front edge through `Top_high.vtx[15]`. The actual 20-edge chain is stored in
`Girl_spineEndReferenceEdges_SET`. Chest is the centered world midpoint between
that endpoint and the bilateral clavicle center. This matches the indicated
height while keeping the spine pivot inside the torso.

The unsaved artist state is preserved locally in
`C:/GIT/maya_scripts/girl_asset_20261020/Girl_artist_leg_correction_before_v004.ma`.
Native reopen checks and captures are in `validation/artist_feedback_v004*.json`
and the v004 PNGs: exact left preservation, mirrored right matrices, single-axis
limb channels, shoulder side-view alignment, spine/chest placement, unchanged
25 model meshes and unchanged other joint/locator frames. The nine clusters,
26 brow/foot attachment nodes and paired lip/eyelid endpoints are retained.

The previous review is `scenes/Girl_guides_high_v005.ma` with
`guides/Girl_v005.guides`. It retains the latest artist shoulder correction.
The artist explicitly chose to preserve both shoulder positions/orientations,
retain TX/RY at the elbows and use the closest reachable loop-center positions.
Elbow TX is the closest point on shoulder X; wrist TX/elbow RY give the closest
point in the shoulder XZ plane. L elbow residual is 0.0076758 cm, R is numerical
zero, and both wrists retain an accepted 1.87035069 cm residual. These are
constrained approximations, not exact wrist-loop centers. Shoulder matrices and
channels, independent finger frames and all other unaffected joints are intact.

Both feet now use positive X from ankle to ball and from ball to tip, with
positive world Y projected perpendicular to each aim as the up reference.
Ankle and ball centers are unchanged; each tip exactly matches its tip locator
at ground height. Ball/tip translations use local TX only; tip rotations and
all foot jointOrient/rotateAxis values are zero. This orientation request
supersedes the earlier ankle zero-rotation convention, while hip/knee frames
are preserved. The right foot also uses positive X/Y for these aim frames.

The pre-edit native snapshot is retained locally as
`C:/GIT/maya_scripts/girl_asset_20261020/Girl_artist_arm_correction_before_v005.ma`.
`validation/artist_foot_arm_v005*.json` verifies a native reopen, the constrained
arm closest-point conditions, exact foot aims/locator placement, unchanged 25
model meshes, unchanged guide curves/locators, nine clusters and 26 native
brow/foot attachments. The v005 PNGs show the arm and foot axes for review.

- Low Res uses Body_low, Top_low and Pantalon_low.
- High Res uses Body_high, Top_high and pantalon_high.
- Model_shared contains the 19 eye, mouth, hair-blocking and accessory meshes
  displayed in either resolution. The source high group only supplied three
  meshes; no high-resolution accessories are claimed.
- Both derived scenes exclude XGen, dedicated scalp meshes, missing groom-only
  IFF paint-map nodes and the XGen refresh expression. Polygon hair is retained.
- All 14 surviving file-texture plugs resolve to the asset's `textures/` tree.
  Base color is sRGB; normal, roughness, metallic and SSS mask inputs are Raw.
  The SSS mask retains its distinct `SubsurfaceScattering_Mask/` path.

The shared basic-structure builder reads explicit `autorigLodRole` metadata and
recreates the Resolution selector. Its geometry organization preserves nested
LOD groups instead of flattening their meshes into FINAL. Untagged models do
not gain a Resolution attribute.

Model Checker ran all 23 automatic checks on the final reopened model:
zero automatic blockers, zero execution errors, three advisory categories.
The six gum n-gons were split, degenerate hair-blocking geometry was cleaned,
mesh offsets were baked without changing evaluated positions/normals/UVs or
material membership, watch transforms were frozen, pivots were reset and
pasted node names were replaced. The source grooming data is still available
in the original scene.

The report is INCOMPLETE because all 24 guided visual-review rows remain
Pending. Triangles, 16 overlapping gum vertices, six nearby hair-blocking
vertices, asymmetry, pole candidates and small-mesh guidance remain explicit
review findings. Nearby anatomical or UV seams were not blindly welded.

Validation receipts:

- `validation/source_model_checker.json`: original findings.
- `validation/model_checker_after.json` and `.txt`: final full checker results.
- `validation/changes.json`: repairs, texture remapping and exact mesh-bake checks.
- `validation/file_path_editor.json`: Maya File Path Editor resolution statuses.
- `validation/structure_validation.json`: two independent structure builds,
  effective visible-mesh membership in both resolutions, zero position change
  and native save/reopen verification.
- `validation/acceptance.json`: delivery checks and remaining scope.

Native regression coverage: four LOD/group-preservation tests and all 15 tests
in the existing build-pipeline suite passed. Low/High review renders were also
inspected; they carry Arnold's unlicensed-preview watermark, and their temporary
lighting was not saved in either delivery scene. File identities are recorded
in `validation/manifest.json`. Preparation scripts and raw Maya logs are retained in
`C:/GIT/maya_scripts/girl_asset_20261020/`.
