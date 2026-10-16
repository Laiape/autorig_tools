# Edward custom limb solver comparison

Parent: `maya_tools/how_it_works.md`. Date: 2026-10-16.

## Decision

The direct custom-module rebuild is not deformation-equivalent to the current
Edward delivery. Keep the current Maya solver modules for this release.
Performance below describes the current implementations, including missing
custom-module features; it is not an accepted equivalent optimization.

## Frozen inputs and procedure

Both complete rigs use the same frozen current checkout, model v003, guides
v013, curves v002, build v001, lossless skin v073 and wrinkles v004. Only
`solver_mode` changed in the disposable working recipe. Product settings
and the artist scene were preserved. The artist had no keyed controls.

Both builds contain 318 controls and 81 skins with no reported cycles.
Maya/custom node counts are 11785/12016; joints 852/824; ikHandles 10/2.
Custom retains the two spine handles and adds two toe skin joints.

## Animation and deformation

Thirty bilateral cases, forward/reverse, compare 59 matching polygon outputs
(3540 mesh comparisons), topology, positions, face-vertex normals and common
limb skin-joint matrices. All requested channels resolved in both variants.
The fixed same-topology limit is 1e-4 cm. The candidate fails it.

- Maximum mesh difference: 40.4480 cm on boot polySurface891 in FK neutral.
- IK neutral: 11.3290 cm maximum on brazaletes1; body maximum 1.4414 cm.
- Left FK bend: wrist position differs by 9.7090 cm and orientation by 10 deg.
- Left IK bend: body maximum differs by 3.1273 cm.
- Forward/reverse maximum within each variant: Maya 2.8801e-5 cm, custom zero.

Custom modules omit 24 existing keyable attributes: bilateral AutoClavicle,
StartAngle and Factor; six biceps/triceps controls per arm; and three front
thigh controls per leg. AutoClavicle and muscle pushes are enabled in the
reference. Custom adds Soft_Start and pvOrientation controls. Equal control
names therefore do not preserve the old animation/volume contract.

Four corrective influences used by the delivery SKC do not exist in the
custom build: bilateral bicepsCorrective_ENV and tricepsCorrective_ENV.
They carry nonzero weights in the body and brazaletes1 skin records.
This directly prevents lossless reuse of those two skins. See
`missing_skin_influences.json` for the stored nonzero vertex counts.

The test reuses the delivery SKC. Bind-frame and foot orientation differences
are part of the direct-switch result; this is not a fresh custom skin bind.

## Interactive performance

Parallel CPU, cache/GPU deformation OFF. Same camera and viewport. Four ABBA
blocks, three measured 48-frame passes per cohort/block; first eight frames
discarded from every measured pass. Values below are medians of six pass
medians per variant. Each cohort includes limb and common facial motion.
The 879x686 viewport cohort uses A1/B1/B2/A3. All four original A2 reports
are excluded and preserved: the viewport had changed to 1319x907. The A3
reference repeats all four cases with the window size locked.
Wrinkles ON has verified nonzero displacement (about 0.1752 cm).

- FK, wrinkles OFF: Maya 22.427 ms/frame; custom 20.830 ms/frame; frame-time reduction 7.12%. Verdict: custom_faster. Reference drift 0.690 ms.
- FK, wrinkles ON: Maya 103.518 ms/frame; custom 94.446 ms/frame; frame-time reduction 8.76%. Verdict: inconclusive. Reference drift 24.441 ms.
- IK, wrinkles OFF: Maya 28.718 ms/frame; custom 25.378 ms/frame; frame-time reduction 11.63%. Verdict: inconclusive. Reference drift 9.212 ms.
- IK, wrinkles ON: Maya 123.149 ms/frame; custom 107.975 ms/frame; frame-time reduction 12.32%. Verdict: inconclusive. Reference drift 32.520 ms.

These are viewport wall times, not isolated GPU times or a guaranteed
production playback rate. No solver-only FPS gain is established. Initial
reports store per-pass statistics; later reports include raw full passes.

One build per variant took 37.904/35.597 seconds. This single pair does not
establish a reproducible build-time improvement. No native data reduction
or node-count result substitutes for performance or quality acceptance.

## Possible future implementation

A compatible optimization would replace only the IK calculation inside the
existing module contract, retaining AutoClavicle, muscle correctives, bendy
frames, bind matrices, foot outputs and animation channels. Match both sides
through FK/IK blends, soft/reach/pin/roll, spaces and scale, then repeat
geometry, persistence and timing checks before proposing a delivery switch.

## Evidence

Raw files and both native scenes are in the outer experiment workspace:
`maya_tools/assets/Edward/experiments/custom_solvers_20261016_v001/`.
See `summary.json`, `quality_summary.json`, `quality_rows.json`,
`joint_rows.json`, `*_build.json`, `timing_*.json` and the frozen manifest.
Opt-in scripts are `scripts/edward_solver_trial_*.py`,
`scripts/edward_solver_compare.py`, `scripts/run_edward_solver_timings.py`
and `scripts/finish_edward_solver_trial.py` in the outer workspace.

The last A3 dispatch exceeded the client 150-second wait. Its complete successful
receipt and timing report were recovered without rerunning or fabricating
samples; see `dispatch_timeout_recovered.json`.
