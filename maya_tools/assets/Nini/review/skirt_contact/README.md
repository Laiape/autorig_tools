# Nini skirt contact delivery

Runtime: the active `autorig_tools` checkout, Maya 2026, native MayaMuscle.
Implementation: `maya_tools/docs/skirt_contact_rig.md`.

## Open and inspect

- Neutral editable rig: `../../scenes/Nini_skirt_contact_v006.ma`.
- Separate animated demonstration: `../../scenes/Nini_skirt_contact_demo_v006.ma`.
- Retained source: `../../scenes/Nini_dress_chains_v005.ma`.
- Settings: `C_dressSettings_CTL`. Five new panel/hem translation controls.
- Timeline: frames 1-289, film/24 FPS, about 12 seconds. Frame 49 lifts the
  left leg; 97 lifts the right leg; 145 crosses; 193 spreads; 241 holds;
  253 demonstrates a Front panel correction; 289 returns to neutral.
- `test_rig_v006.json` is a semantic custom profile for the existing Test Rig
  workflow. All six cases resolve without missing or skipped channels.
- `delivery_preset_v006.json` stores the matching layout/settings/offsets.

The two PNGs use disposable diagnostic materials and faceted source shading.
The saved Maya scenes retain the original materials. These are deformation
previews, not final reel lighting or final beauty renders.

## Acceptance evidence

`validation_v003.json` covers 29 neutral/leg-pose transition samples on the
tunic and embroidery. Vertex, edge-midpoint and triangle-center samples have
no penetration beyond the unchanged 0.01 cm tolerance and no ambiguous inside
classifications. Final joint segments stay within the 5 percent stretch gate;
the observed maximum ratio is approximately 1.0000002. Neutral vertex error
is 0.000000954 cm.

The same gate checks exact original skin weights, bind matrices and DQ data,
topology, UVs, materials, normals, body preservation, evaluator equivalence,
reverse access, manual reset, solver bypass, presets, rest recalibration,
lossless two-skin SKC round-trip, native reopen, two independent rebuilds and
namespaced/renamed controls.

`final_delivery_v006.json` checks the final class adapter and Controllers_GRP
convention against that accepted deformation: zero vertex difference across
eight full poses, with the existing 258-joint ENV hierarchy preserved.
`native_portability_v006.json` independently cold-opens the final scene with
no project Python imports or unknown nodes. DG and Parallel geometry match
the saved references exactly in four poses.

`demo_validation_v006.json` adds 15 samples of the actual saved animation,
including interpolated poses and the manual Front correction. All pass the
same contact and final joint-length gates. Finite surface samples do not prove
absence of every possible triangle intersection.

## Global transformation limits

This delivery is accepted at the recorded Nini global transform and scale 1.
Uniform scaling to 0.5 already changes the archived source body relative to an
exact scaled held pose by 1.985204 cm. The upgraded garment inherits that
limitation. A combined 35-degree Y rotation/translation also misses the strict
0.0001 cm covariance tolerance at one tunic region (0.000579 cm); the separate
12/-8 degree X/Z rotation passes. These are explicit failed coverage cases,
not accepted global-transform variants. Failed finalization attempts v004 and
v005 are retained here as evidence.

Do not transform the top `Nini` container as an animation control. Use the
existing `C_masterwalk_CTL` and its `globalScale`, and validate any new global
setup. Nonuniform or mirrored scale is unsupported. Floor, chair and cloth
self collision are outside this procedural skirt module.

## Rollback and performance

`solverBlend=0` restores the retained original contact/deformation branch,
including disabling the sparse surface projection. Reopen the unchanged source
for a complete graph rollback after saving. Do not delete intermediate mesh
history or freeze the garment transforms.

Native nodes do not establish playback speed. Batch-demand timing evidence is
recorded separately from geometry QA; it does not measure interactive VP2 FPS.
GPU and Cached Playback remain unapproved for this scene. Keep the conservative
Parallel CPU profile with cache and GPU override off for the accepted setup.

`batch_timings_v006.json` contains a bounded reference/candidate/reference
comparison with three passes in each state, identical bilateral time curves,
17 frames, a full warm-up and eight discarded frames per timed pass. Geometry
collection and rendering are outside the timing loop. Parallel temporal demand
has median/p95/max 85.93/103.62/117.19 ms for the candidate versus
4.96/7.00/7.61 ms for the original. The two reference medians drift by 14.42
percent; the approximately 17-fold cost increase is well outside that noise.

DG temporal demand is much slower (candidate median 1638.14 ms). Paired control
edits followed by explicit `dgeval` are also expensive: 1666.27 ms median in
the Parallel-configured batch process. This direct demand test does not run
the interactive manipulator or viewport scheduler, so it must not be presented
as measured UI interaction latency. Actual viewport playback/manipulation
remains unmeasured. The full correction is not accepted as a real-time
performance improvement or as meeting the project's 24 FPS playback budget.

The longer original timing trial was stopped after about five minutes without
a completed candidate cohort. `batch_timings_v006_incomplete_full.json` retains
that attempt; the shorter completed comparison is a separate protocol. Do not
combine their raw samples. The next performance experiment should isolate and
reduce the repeated closest-body queries, then repeat the geometry/contact
gate before accepting a replacement. Disabling surface contact is an artistic
bypass that can reintroduce waist penetration, not an equivalent optimization.
