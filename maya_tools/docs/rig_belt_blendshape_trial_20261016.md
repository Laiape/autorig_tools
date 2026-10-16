# Edward belt deformation bake trial

Parent: `maya_tools/how_it_works.md`. Date: 2026-10-16.
Verdict: review copies delivered; no production replacement is accepted.

## Source and scope

The current modified `CHAR_Edward_v001.ma` was frozen through native Maya ASCII
export, preserving the artist filename, modified flag, selection and frame.
All experiments ran in an owned mayapy process using the active nested runtime.
The artist session was not replaced. Two additional Maya GUI windows were
requested explicitly for manual deformation validation.

The affected meshes are `cinturon3` (5,589 vertices) and `cinturones2` (4,885).
Their original PRX drivers differ: the first uses the body corrective/padding
branch and the second the regular body output. These source routes remain intact.

## Candidates and construction

One native blendShape can handle both geometries through separate base geometry
indices (0 and 1), despite their different topology. Each of its 76 pose weights
has matching target data for both bases. One belt is not a target for the other.
The fallback creates one blendShape per belt, with identical targets and SDKs.
Targets are internal baked deltas, not live PRX outputs. Candidate histories
contain no PRX. The blendshape-only copies use native global-motion matrices.

Additional copies test a fitted LBS skin plus pre-skin blendshape residuals.
Residual targets invert each vertex's blended LBS transform at the captured pose.
These hybrid trials reuse the earlier diagnostic fitted weights, explicitly
identified in `manifest.json`; they do not certify the earlier skin conversion.

At the user's follow-up, skin-only copies were fitted again on the current
snapshot and capture bank. They use 9/18 candidate joints, at most eight nonzero
weights per vertex and normalized rows (maximum sum error 4.44e-16). The fit uses
only the 101 capture poses; all 74 held-out poses remain excluded from fitting.

## Geometry results

Tolerance was fixed at 0.0001 cm before validation. The workload covers 101
capture poses, 74 held-out intermediate/combined poses, global translation,
rotation, authored globalScale, and two additional root-scale probes. There are
180 cases, evaluated forward/reverse on both belts: 2,880 blendshape/hybrid
comparisons and another 720 skin-only comparisons. Normals are face-vertex
normals. Topology, UV coordinates/assignments, materials/assignments and edge
smoothness match the originals for every copy.

Both blendshape layouts match stored capture poses within tolerance. Their
positions are identical to each other in every tested case. Splitting the node
does not repair interpolation or missing pose coverage.

Maximum held-out body-pose position errors, in belt order cinturon3/cinturones2:

- Blendshape only: 0.128333 / 0.537984 cm (1.283334 / 5.379844 mm).
- Skin plus residual blendshape: 0.065218 / 0.053643 cm (0.652184 / 0.536428 mm).
- Newly fitted skin only: 0.256998 / 0.240853 cm (2.569982 / 2.408530 mm).

The new skin-only fit also has capture-pose maxima of 0.403296 / 0.432407 cm.
Normal, global motion and scale checks reveal additional failures. Authored
globalScale 1.15 fails; root-scale probes are recorded separately from animator
controls. No arbitrary-pose, IK, contact or global-scale equivalence is claimed.
The original PRX remains the accepted production route.

The combined four-candidate review was saved and reopened natively: selector,
multi-base indices, 76 target weights and drivers persist. Eight representative
cases were rechecked forward/reverse (128 comparisons): capture poses still
pass and the held-out failures persist. The two focused artist review scenes
are additionally reopened in separate Maya GUI instances. Failed quality gates
mean no SKC integration, normal CREATE RIG change or two-build approval follows.

## Timing

Standalone Maya 2026 DG CPU measures setting three control channels and forcing
only the two belt outMesh outputs. Eight warmups per pass are discarded. Three
passes per candidate are interleaved with six original PRX passes. Vertex reads
and profiling are outside timing. This is not viewport playback or full-rig FPS.

The final cohort includes all five candidates. Median / p95 milliseconds:

- Original PRX: 12.301 / 18.408, 360 samples.
- Shared blendshape only: 1.273 / 2.377, 180 samples.
- Separate blendshapes only: 1.343 / 2.268, 180 samples.
- Skin only: 5.165 / 8.727, 180 samples.
- Skin plus shared residual: 5.746 / 9.805, 180 samples.
- Skin plus separate residual: 5.974 / 9.572, 180 samples.

Shared/separate pass ranges overlap, so the small difference does not establish
a stable winner. All faster alternatives fail the deformation gate. Earlier
four-candidate timings remain in a separate file; do not merge those cohorts.

## Artist review files

The outer workspace folder is
`maya_tools/assets/Edward/experiments/belt_blendshape_20261016_v001/`.

- `Edward_belts_BLENDSHAPE_COMPARE_v001.ma`: original PRX, shared blendShape,
  and separate blendShapes. Starts on shared blendShape with limbs in FK.
- `Edward_belts_SKIN_COMPARE_v001.ma`: original PRX and newly fitted skins.
  Starts on SkinClusters. The regular rig remains available for posing.

Select `Edward_BeltBlendshape_Review` and change `beltVariant` in the Channel Box.
Original_PRX is available in both scenes. These are comparison packages that
retain the original deformation for A/B review; file size and visible-scene
playback do not represent an optimized delivery rig. Keep the test scenes
separate from the production source while the artist judges their appearance.

## Evidence and next steps

The folder stores the frozen native source, all-candidate scenes, focused scenes,
`manifest.json`, capture/weight arrays, quality rows/summaries, timing samples,
native reopen records, GUI launch/ready records and original snapshot metadata.
Compact identities/hashes live in `docs/validation/belt_blendshape_20261016/`.

Opt-in scripts are in the outer `scripts/edward_belt_*.py` files. Mutating trial
scripts check the recorded owned process ID. GUI launches use separate preference
folders and unique command ports. They do not load over the current artist scene.

A denser target bank or joint-space pose interpolation with combined-pose
residuals could be a further bounded experiment; neither guarantees equivalence.
Test new held-out poses after refinement. Shot-specific dense bakes need an
explicit limited animation scope. Keep expensive fitting outside CREATE RIG.
Connecting a live PRX output as a target retains its runtime work.

Native multi-geometry/target command reference:
https://help.autodesk.com/cloudhelp/2025/ENU/Maya-Tech-Docs/CommandsPython/blendShape.html
