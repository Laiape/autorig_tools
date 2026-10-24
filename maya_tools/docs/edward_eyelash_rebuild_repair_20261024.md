# Edward eyelash rebuild data repair

Parent: `../how_it_works.md`. Date: 2026-10-24.

`assets/Edward/skin_clusters/Edward_v075.skc` carries the verified eyelash
attachment repair into the next Edward rebuild. The production
`AutoRig.import_weights()` calls `SkinManager.import_skins()` without an
explicit path; its numeric latest-version selector now chooses v075.

The previous v074 assigns every vertex of `C_eyelashes_global_SKC` to
`C_freeze_ENV`. The local eyelid skin works, but the lashes remain at their
rest location when the head or masterwalk moves. The new revision assigns
the same 288 unit weights to `C_head_ENV`. Its optimized influence list and
matching serialized skin metadata use the head influence as well.

All other records are identical to v074, including the v074 mouth-mask repair,
local eyelash weights, blend weights, garments, correctives and wrinkles.
Earlier SKC versions remain unchanged. There is no character-specific runtime
repair and no automatic edit of other characters. The existing builder already
contains the geometry display enum correction; publish-only editor metadata
cleanup does not require a rebuild hook.

## Verification

Maya 2026, using the production skin importer and the corrected v006 publish
as the deformation reference:

- The normal latest-version selector resolves `Edward_v075.skc`.
- A scoped fixture takes both eyelash skin records and their metadata directly
  from v075. Both existing skins are deleted and reconstructed twice with
  `optimize_new_bindings=True`, as used by the normal builder.
- The resulting global influence is `C_head_ENV`; the evaluated order remains
  local then global. Eleven neutral, head, masterwalk, left/right blink and
  combined head/scale/blink poses match the corrected publish exactly.
- Native ASCII save/reopen also matches all eleven poses exactly.
- A deep comparison verifies that only the global eyelash skin record and its
  corresponding serialized metadata change relative to v074.

Compact evidence: `validation/edward_eyelash_rebuild_20261024/summary.json`.
The diagnostic scripts and native snapshots remain in the local
`C:/GIT/maya_scripts/edward_publish_repair_20261024/eye_layer_audit` workspace.

This verifies skin reconstruction and persistence, not a complete CREATE RIG
run. The exact elongated-eye symptom from Elena's screenshot remains
unconfirmed; this revision fixes the independently reproduced eyelash defect.
