# Original eyelid pivot with soft corner influence

Parent: `maya_tools/how_it_works.md`.

Artistic request: restore the previous main-control rotation feel and let
only a small amount of rotation reach the ends. This intentionally supersedes
the eye-centered rotation in `../eyelid_shared_corners_20261016/`.

Each primary lid rolls around its original moving local-joint pivot. Before
blink, the posed border uses squared smoothstep falloff from each endpoint
to the center. Seven-CV rotation weights are approximately
`[0, 0.0672, 0.5487, 1, 0.5487, 0.0672, 0]`. Shared endpoints remain stationary;
the other lid receives no primary Z roll. Calibrated tangent transport,
manual detail XYZ rotations, existing bind data and shared blink remain.
The installer upgrades version 2 to version 3 in an undoable operation.

Native regressions pass for L/R, 7/11 guide samples, independently rotated
Up/Down, translated main pivots, DG/Serial/Parallel, rotated/nonuniform eye
frames, neutral bind orientation, blink position/orientation and save/reopen.
The falloff checks require stationary endpoints, less than 10% displacement
next to each endpoint versus full rigid rotation, an unchanged opposite lid,
and the original central/pivot response. The unchanged-pivot test and the
full blink suite also pass. GUI captures in `visual/` inspect the actual
Edward mesh at +/-60 degrees and full blink. Camera and artist pose are
restored after capture. This is an artistic adjustment, not a performance claim.

Native backups/corrected copy, outside the runtime checkout:
`C:/proyectos/auto-rig/recovery/eyelids_before_control_falloff_20261016_v001.mb`,
`C:/proyectos/auto-rig/recovery/Edward_eyelids_soft_ends_20261016_v001.mb`.
