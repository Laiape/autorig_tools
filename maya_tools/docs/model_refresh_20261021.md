# Girl and Chihuahua model refresh

Parent: `maya_tools/how_it_works.md`.
Date: 2026-10-21. Native checks: Maya 2026, active checkout
`C:/proyectos/auto-rig/autorig_tools`.

## Delivery

- Girl: `assets/Girl/models/Girl_v002.mb`, `guides/Girl_v006.guides` and
  `scenes/Girl_guides_high_v006.mb`.
- Chihuahua: `assets/chihuahua/models/chihuahua_v005.mb`,
  `guides/chihuahua_v015.guides` and `scenes/chihuahua_guides_model_v005.mb`.
- Chihuahua's revised source groom: `assets/chihuahua/groom/Chihuahua_groom_v002.mb`,
  retained as an unloaded, message-owned native reference in its new model and
  guide scene. The existing SHOW GROOM action explicitly loads it.

Paths after each asset's first path are relative to that asset folder.
All earlier versions remain available. Character Manager resolves the new model
and guide exports as the latest versions. No runtime module or solver changes.

The inputs are the two new files in Downloads: `YDRAY-Girl_rigging.ma` and
`YDRAY-Chihuahua_RIgging.ma`. Both original files remain unchanged. Exact hashes,
primary mesh comparisons, placement sources and native checks are recorded in
`model_refresh_20261021/Girl.json` and `model_refresh_20261021/chihuahua.json`.
Orthographic geometry reviews are in each asset's
`review/model_refresh_20261021.png`; they are x-ray guide projections from the
native-reopened data, not a rendered grooming or deformation approval.

## Source model handling

The new primary meshes replace the earlier prepared outputs, including genuine
source topology changes. Their evaluated world positions and polygon topology
are retained, rather than baking the previous Chihuahua rig pose into the new
artist model. Compatibility names are `Body_high8` -> `Body_high`,
`body_high7` -> `body_geo`, and `tonhue` -> `tongue`.

Girl retains its Low/High/shared organization and existing portable PNG texture
tree; its primary model excludes scalp/XGen data as before. Chihuahua retains
the new full groom separately so ordinary model/guide opening does not load
its four descriptions. Existing external Chihuahua texture paths are retained;
this update does not certify external texture availability. Unsupported Maya
node-editor UI records and the unrelated XGen preview expression are excluded
from the lightweight primary model/guide scenes. The original sources remain
the recovery copies for all source-only data.

## Guide fitting

Girl retains the approved shoulder frames. New elbow/wrist bounding-box centers
come from the exact previously recorded anatomical High Res loops. TX/RY at
the elbows and TX-only wrists remain enforced; the closest reachable positions
leave explicit residuals: elbows L 0.562640 cm / R 0.560523 cm, wrists
L 1.149687 cm / R 1.150213 cm. The shoulder frames are not changed to hide those
residuals. The independent finger branches follow the new high-resolution hand
correspondence, with surface residual below 0.00138 cm. Native artist clusters,
source sets, leg/foot frames and the 26 brow/foot attachments remain present.

Chihuahua's elbows, carpi, stifles, hocks, fetlocks and all digit guide centers
use explicit closed local mesh loops, with the bounding-box center recorded
separately from a vertex centroid. Source vertex IDs and left edge IDs are
retained in the receipt and `chihuahua_*_modelRefreshLoop_SET` sets. Right-side
source vertices are matched through the symmetric topology. The authored torso
attachment roots remain intact; they are not replaced by a distal limb ring.
Changed limb segments retain the previous roll while adapting their aim.
Settings/foot pivots and the unresolved foot tips/pasterns use bounded paw
correspondence transforms, preserving their authored heights. Those latter
transports are editable approximations, not exact per-guide anatomical loop
fits. The older broad paw correspondence trial's residuals remain in the receipt
for that limited scope; all digit centers use explicit loops instead.

Both characters retain their facial source routes. Each lip/eyelid CV uses its
corresponding actual mesh vertex, each consecutive pair is a mesh edge, paired
arcs share endpoints and counts, and CV[0] is the shared world +X corner. Girl's
socket rings also retain their exact source edges. Brow body-UV attachments
and foot mesh attachments are native scene data; the existing `.guides` export
stores evaluated matrices/CVs, not those live dependency nodes or channel locks.

## Validation and scope

The new native models and guide scenes reopen successfully. All 25 Girl and
ten Chihuahua primary meshes match their new source positions within 1e-4 cm,
with identical polygon topology and finite points/face-vertex normals. Exported
guide matrices match their native scenes; joint counts, facial edge connectivity,
paired endpoint order, and latest-version selection are checked. Girl retains
nine clusters and 26 surface constraints, and a real 0.1 cm model movement tests
both brow and shoe attachment following before restoring the model.

The update is editable model/guide preparation. The earlier Chihuahua model
v004/skin v014/forward-knee rig remains a separate historical delivery; its pose
tests do not approve a rig built from the new source and guides. No skin snapshot,
corrective, full rig build, animation benchmark or broad Model Checker approval
is produced by this update. The residuals and anatomical proposals above remain
available for artist review.
