# Character picker pipeline

The rig and picker share `utils/module_guides.py`. A module contributes buttons
only when its complete guide prerequisite exists. An empty guide export is an
error; no picker is generated. A removed digit root also excludes its old exported
controls. Unknown control naming is reported in `build_report.json`, never guessed.

The native picker uses the **actual controls under the character root**. CREATE
RIG does not generate, embed or open a picker. Open it through Animation > Character Picker
or the CharacterPicker button on the AutoRig shelf. Select a control first when
several characters are present. Namespace and Use Selection choose the instance.
Opening generates the picker bundle if it is missing; existing bundles are reused.
Ambiguous targets are excluded from selection. Maya 2024+ is required; Qt uses
PySide6 when available, otherwise PySide2. Version compatibility requires actual
testing on each Maya version.

## Optional embedded picker for explicit installation

Explicit `character_picker.generate(load=True)` or the portable installer embeds
one `scriptNode` per character root after successful guide-driven generation.
CREATE RIG never installs this node. Existing scenes with a previously embedded
picker retain their saved scene-load behavior. The node contains the runtime,
config, shapes and backgrounds, linked
to its rig root by a message connection. On GUI scene load it recreates a
`SelectionChanged` scriptJob and opens the picker. Selecting another embedded rig
switches to its picker and namespace; targets are restricted to that exact root.
Local nodes use UUID identity; referenced nodes use their unique full names,
because multiple references to one source file retain the same source UUIDs.
The receiver needs neither AutoRig nor a separate installation. No build logic or
model is embedded in the picker payload.

ScriptJobs are session objects. The scriptNode is the saved part that restores
them after Maya restarts. Reinstalling reuses the node; scene changes
and root deletion clean up jobs and the window. Closing the picker intentionally
is respected until another rig/scene is selected or it is opened manually.
Maya's scene-script security approval remains in force; no trust preferences are
changed by the picker.

For an existing rig, drag the portable installer into Maya once **with the rig
loaded**, then save the scene. Installation embeds the same auto-open node on each
matching rig root. Installing in an empty scene only creates the usual shelf entry.

## Reproducible generation outside Maya

From the repository root:

```powershell
python -m maya_tools.scripts.tools.character_picker_builder thaiz
python -m unittest maya_tools.scripts.tools.tests.test_character_picker_builder -v
```

Offline generation reads the highest numeric versions of `.guides`, `.build` and
`.curves`. It plans targets from the curve export; this does **not** prove that a
scene contains the rig. Maya generation uses the same guide dictionary as the rig
and only live character controls. The report lists skipped controls and reasons.

## Character dimensions

Each asset stores `picker/picker_profile.json`. Body and face default to 750 by
1000 pixels. The guide bounds, padded by 16%, determine an aspect-preserving XY
frame per panel. The face frame uses only facial module anchors. Backgrounds are
drawn from the actual guide joints and curves in that same coordinate frame.
They are schematic guide backgrounds, not photographs of the model.

Primary buttons measure 10% of their module's projected guide span, clamped to
12–32 pixels. Secondary buttons use 1.2% of panel width, clamped to 7–14 pixels;
fine eyelids use 0.8%, minimum 5 pixels. Named master/settings buttons use panel
fractions. Dense buttons are displaced deterministically to prevent overlap.
The report records world anchors, guide ownership, dimensions and final pixel
bounds. The config records module measurements and both world frames.

Override a panel's `size` or `world_bounds` (`xmin, ymin, xmax, ymax`), or a named
control's `position` (pixel center) and `size` (pixel width/height), in the profile:

```json
{
  "schema_version": 1,
  "panels": {"body": {"size": [750, 1000]}, "face": {"size": [750, 1000]}},
  "controls": {"C_head_CTL": {"size": [70, 25]}}
}
```

Regenerate the picker explicitly after modifying a profile or guides, using
`character_picker.generate(character, load=False)` for bundle generation only.
Controls use standard module naming;
new naming requires an explicit ownership/anchor mapping in the shared builder.

## Share without AutoRig

Generation emits `picker/<character>_Picker_Installer.py`, containing only picker
data, backgrounds, runtime and installer. Send that single file. Drag it into a
Maya 2024+ viewport: it installs into the user's Maya scripts folder, opens the
picker and saves one `<character>Picker` button on AutoRig. Reinstallation replaces
that character's button. The receiver needs a compatible rig in their scene.
The model, rig, skin data, AutoRig repository and DWPicker are not included.

Generated bundle files live under `picker/generated`. Keep the profile as the
editable source; regenerate runtime copies and the single-file installer through
the builder rather than editing generated files. Pure planner and simulated API
tests are separate from real GUI/scene validation.
