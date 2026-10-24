# Edward pants weight editing settings

Parent: `../how_it_works.md`. Date: 2026-10-24.

The artist reported losing or unexpectedly redistributing pants weights when
editing one influence. The live `C_pants_SKC` had normalization disabled and
`maintainMaxInfluences=True`, with `maxInfluences=5`. Its authored weights use
up to ten positive influences per vertex; 1,434 vertices exceed five.

Interactive normalization now keeps the total weight consistent during edits,
and disabling the editing influence limit preserves the authored distribution.
No weight cleanup, pruning, smoothing, rebinding or skinning-method change is
included. The scene settings were changed in one undo chunk after a native
backup, with zero change to all weights and world positions.

`assets/Edward/skin_clusters/Edward_v078.skc` persists these settings for the
next rebuild. It derives from the artist's newer v077 export, preserving that
revision's weights and other work, including the v075 eyelash attachment fix.
Only the pants normalization/limit attributes and matching metadata change.
Versions v076 and v077 remain untouched.

## Validation

- A native weight-edit fixture uses an actual pants row with ten influences.
  Reducing its largest influence with the original settings leaves a total of
  0.9240180428948527. With the repaired settings the total is 1, retaining all
  ten original significant influences. This skinPercent fixture does not
  reproduce the brush's influence pruning; it verifies normalization behavior.
- The production importer reconstructs the pants from v078 geometry, influences
  and weights. Imported weights match exactly. Native ASCII reopen differs by
  at most 1.3552527156068805e-20, with every nonzero weight and sign retained.
  Both settings persist. The native ASCII tolerance is 1e-15.
- A deep JSON comparison confirms that every weight and all unrelated records
  are unchanged relative to v077. No complete CREATE RIG run is claimed.

Evidence: `validation/edward_pants_paint_20261024/summary.json`.

Maya's Interactive mode redistributes weight among unlocked influences. For
an exact transfer between two joints, leave only those two influences unlocked
or use an explicit weight-transfer operation. These settings do not choose a
destination joint automatically.

References:
[Maya skinCluster node](https://help.autodesk.com/cloudhelp/2024/ENU/Maya-Tech-Docs/Nodes/skinCluster.html),
[normalization modes](https://help.autodesk.com/cloudhelp/2026/ENU/Maya-Basics/files/GUID-F632811C-DE7C-4464-B025-9B6379FAA750.htm).
