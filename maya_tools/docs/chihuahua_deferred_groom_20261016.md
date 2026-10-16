# Chihuahua opening with an optional groom

Parent: `maya_tools/how_it_works.md`.
Evidence: `docs/validation/chihuahua_deferred_groom_20261016/`.
Supersedes the delivery choice in `chihuahua_model_open_20261016.md`.

## Requested behavior

The user explicitly chose fast opening and enabling the groom afterward.
The original already had `xgen.visibility = 0`: merely hiding it was not an
optimization. The first binary retained 272 MB of scene data and its initial
redraw cost. That distinction corrects the earlier chat attribution of the
entire first redraw delay to visible hair.

`assets/chihuahua/models/chihuahua_v002.mb` now contains the primary model and
an unloaded native reference to `assets/chihuahua/groom/Chihuahua_groom_v001.mb`.
The original v001 ASCII and full binary are retained. The model opens with no
XGen description nodes instantiated. Its native reference node remains connected
by a data-only message attribute on the character root. There are no new scene
scripts, expressions, frame callbacks or global preferences.

Character Manager > Models > SHOW GROOM explicitly loads and displays the groom.
It reuses the existing panel. Native File > Reference Editor can also load the
reference. Loading is optional and its cost is paid at that explicit action.
Keep both files together when moving the asset; this is not a standalone hair
cache or a baked replacement. Saving the scene with the reference loaded will
naturally restore that loaded state on its next opening.

Guide model import now uses the verified binary helper and preserves native
references and their saved load states. It imports only the latest model version,
matching CREATE RIG, rather than importing every version in the models folder.
Import does not replace the current guide scene or its filename. If no valid
binary cache exists for an ASCII input, import retains the original ASCII path;
it does not export the artist's current scene to create a cache.

## Measured acceptance

An owned interactive Maya 2026/Viewport 2.0 session opened the delivered model:

- First open including the first explicit redraw: 2.783 s.
- Three subsequent opens including redraw: 0.181, 0.149 and 0.163 s.
- Warm median: 0.163 s total, with 0.127 s opening and 0.037 s redraw medians.
- Main file: 12,388,840 bytes; optional groom: 259,592,084 bytes.

The first sample starts with Maya already running; application startup is not
included. The warm samples use warm plugins/filesystem. The earlier full-file
comparison used another session/cohort; do not turn those cross-cohort values
into a controlled percentage improvement. These are file-opening measurements,
not animation FPS, cold-machine guarantees or CREATE RIG completion times.

SHOW GROOM loaded all four native descriptions, set the group visible and drew
them successfully. A native playblast was inspected in the local trial folder.
The final interactive trial completed load/show/unload. Model and reference were
exported in a bounded prototype and a second delivery run, followed by native
save/reopen and reference reload.

All 14 loaded mesh outputs match the original native source exactly for points,
topology, face-vertex normals, UVs/assignments and material memberships. The 11
primary meshes match with the reference unloaded. World matrices and the four
groom descriptions' direct connections match on reload. The source hash is
unchanged. Maya can restore the message-owned groom under the character root;
the comparison explicitly normalizes that DAG prefix while comparing actual
world-space values. SHOW GROOM adopts the rig's FINAL parent space when present;
a native regression exercises translated/scaled parent space and repeated clicks.

The quality scope is the static source model and retained native groom graph,
not a new full-rig pose library or external texture availability certification.
The existing missing D:/E: texture paths are retained. A separate normal CREATE
RIG smoke check succeeds from v002 and reports 907 joints and 10 skins. Its batch
timing is not used to claim viewport performance.

Fifteen native pipeline regressions cover ordinary builds and cleanup, source
identity/cache invalidation, guide-scene preservation, latest-version selection,
deferred reference import and explicit groom activation/parenting. No profiling
was added to ordinary opening or construction.

## Retained failures and rollback

The first full-groom interactive import experiment was cancelled after the user
chose optional groom loading. A diagnostic owned GUI then stalled in file(new);
no timing from that trial is accepted. Some standalone reference quality runs
crashed during native teardown after their comparisons. Those logs are retained;
the final interactive open/show/unload run and native pipeline suite pass. This
does not approve arbitrary reference teardown behavior in every Maya version.

The initial delivery assertion also compared literal DAG paths and rejected the
new ownership prefix. The independent comparison confirms exact world data with
that declared hierarchy change; the tolerance was not loosened.

Rollback uses `models/chihuahua_v001.ma` or the prior full binary. All full source
data remains. Experiments, signatures, playblast and failure logs are in the
outer workspace's `tmp/chihuahua_*20261016*` folders. Explicit runners are the
outer `scripts/chihuahua_deferred_groom_trial.py`,
`chihuahua_preview_gui_check.py`, `chihuahua_verify_deferred_groom.py` and
`finalize_chihuahua_deferred_evidence.py`.

Native reference serialization/load flags follow Autodesk's
[file command](https://help.autodesk.com/cloudhelp/2026/ENU/Maya-Tech-Docs/CommandsPython/file.html).
