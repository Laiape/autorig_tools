# Eyelid Z rotation and CPU setup evaluation

Parent: `maya_tools/how_it_works.md`.
Raw evidence and decisions: `validation/eyelid_variants_20261016/decision.json`.

## Delivered animation behavior

`tools/eyelid_rotation.py` removes partial primary Z skin inheritance and
uses the original moving main-control pivot. `eyelid_corners.py` now applies
smooth spatial falloff: full rotation centrally, approximately 7% next to
the corners, and zero at the shared endpoints. Each lid rotates independently.
Calibrated aim tangents make
the skin frame follow the border and converge during blink. XY, translation,
secondary edits and detail XYZ rotation remain available. Blink blending is
downstream; projection preserves the contact curve's local Y and tilt.

This is in the shared builder, the explicit legacy contact upgrade, and the
open Edward artist scene. Native snapshots are in the outer workspace:
`recovery/eyelids_before_roll_20261016_v001.mb` and
`recovery/Edward_eyelids_roll_20261016_v001.mb`. The artist file name, pose,
camera and authored skin bindings were retained. The saved corrected copy
reopened and passed curve/joint contact checks. Visual open, lower-roll and
closed-roll captures are in the evidence folder. The subsequent large-angle
correction and its current snapshot are documented in
`validation/eyelid_shared_corners_20261016/README.md`.
The artist subsequently requested the original pivot with less corner motion;
this supersedes the orbital behavior. Current evidence and saved copy:
`validation/eyelid_control_falloff_20261016/README.md`.

The timing experiments below predate that corner/tangent correction. They
compare the recorded experiment graphs only; they are not timings for the
current production graph. No speedup is claimed for this geometry fix.

## What the existing projection actually does

The eye NURBS is an authoring/reference object. Runtime attachment does not
query closestPointOnSurface. It uses native scalar math to retain local Y
and normalize XZ onto the corresponding spherical latitude. An aim-only
orientation on an unprojected curve would still allow the eyelid to travel
through the globe; it is not an equivalent replacement.

The tested aim alternative computes longitude with aimMatrix in normalized
eye space, preserves/clamps latitude and restores the authored eye frame.
It supports positive XYZ ellipsoid radii and arbitrary affine rest frames,
rather than hard-coded world Y, world Z or Edward names. Six L/R builds and
native reopens tested spheres, ellipsoids, rotation/translation/nonuniform
frame scale, extreme latitude, blink contact and DG/Serial/Parallel output.
Maximum normalized surface equation error was 2.84e-14. In Edward's tested
poses its maximum joint matrix difference from the corrected spherical
projection was 1.21e-7, below the 1e-4 equivalence gate.

## Measured CPU costs

The isolated cohort contains one eye, two lids and 14 output joints. The
Edward cohort contains 84 output joints, 21 guide samples per lid, and also
demands `cabeza_low_Shape.outMesh` and `cabeza_high_Shape.outMesh`, including
their upstream deformation. Both comparisons include the delivered Z fix.
They are different cohorts and must not be compared as absolute rig costs.

Each timed block had a complete warmup, eight discarded frame advances and
three measured passes. References bracketed each candidate. Isolated blocks
contain 120 retained samples; Edward blocks contain 48. The timer contains
currentTime plus native output data demand, without vertex extraction,
Profiler recording or viewport refresh. These are CPU demand timings, not
interactive FPS, GPU execution or complete-character viewport performance.

For each candidate, the comparison reference is the mean of the two adjacent
reference-block medians. The descriptive noise band is the larger of 5% of
that reference or the difference between its before/after reference medians.
It is not a statistical confidence interval. Raw pass medians, p95, maxima,
environment, channels, source hashes and failures are retained.

In Edward Parallel CPU, aim measured 352.74 ms against a 360.73 ms bracketed
reference: an apparent 2.21% reduction. Adjacent references drifted 8.08%, so
this is inconclusive. Edward DG likewise had 26.15% reference drift and does
not establish a gain. In the isolated Parallel cohort, aim measured 1.764 ms
against 1.698 ms, also inside its noise band. No stable Parallel CPU speedup
is demonstrated. This workload does not change scene evaluation defaults.

## De Boor experiments and rejection

The fast static prototype compiles spline/skin moments at the rest/contact
parameters and interpolates their basis weights during the blink. This is
an approximation to evaluating a cubic at a changing parameter. It failed
the 1e-4 deformation gate; its timings are not savings for an equivalent rig.

A second prototype compiles the exact moving-parameter cubic coefficient
functions into native animCurveUU nodes, followed by direct linear-skin
point/vector moments. It avoids demanding the curve, curve skin,
blendShape and motionPath branch. It matched DG/Serial positions within
1.81e-6 before native save. However, isolated DG measured 4.503 ms against
2.466 ms for its bracketed reference: 82.6% more time. The combined exact
De Boor/aim candidate measured 4.256 ms against 2.382 ms: 78.7% more time.
These diagnostics do not support a cheaper native implementation.

The exact prototype also failed Parallel evaluation and native save/reopen.
The separate native reopen probe has no graph cycles but records a maximum
matrix error of 3.204, far above tolerance. It is rejected globally even
where a faster timing appears. API coefficient construction, new native
point-math behavior and serialization would need further investigation;
the cause is not certified by this bounded experiment. This is a result for
these prototypes, not a claim that every De Boor or compiled design is slow.

## Decision and limits

Keep the corrected projection setup as the production builder. Retain the
portable aim implementation as an explicit experiment; its smaller active
arithmetic branch is not evidence of faster control interaction. Do not
apply either De Boor experiment to an artist rig. No failed variant was
installed in the artist scene. No GPU/cache profile, final-mesh normal/UV
equivalence, full SKC pipeline, RAM reduction or all-character speedup is
certified here. No performance audit runs during normal CREATE RIG.

Relevant code: `tools/eyelid_candidates.py`, `tools/eyelid_deboor_exact.py`,
`scripts/eyelid_setup_trial.py`, `scripts/summarize_eyelid_trials.py`.
Tests: `test_eyelid_primary_roll.py`, `test_eyelid_blink.py`,
`test_eyelid_aim_surface.py` in `maya_tools/scripts/tools/tests/`.
The evidence decision record identifies completed, failed and excluded runs;
incomplete/overlapping runs are not used to claim a speedup.
