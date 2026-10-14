# Edward Picker for Maya 2024 and later

## Install

For a single-file handoff, send `Edward_Picker_Installer.py` from the parent
picker folder. Drag that file into Maya's viewport. It embeds the runtime,
controller data and images, installs the shelf button and opens the picker.
No extracted bundle or AutoRig repository is required. Run it inside Maya,
not by double-clicking it in Windows. It does not contain the Edward rig;
the recipient still needs a scene with the matching rig to select controls.

The ZIP installation below remains available:

1. Extract `Edward_Maya_Picker_2024_plus.zip` to a folder.
2. Open Maya 2024 or later.
3. Drag `install_edward_picker.py` from the extracted folder into the Maya
   viewport. Keep the other extracted files beside it during installation.
4. The picker opens and an `EdwardPicker` button is added to the `AutoRig`
   shelf. Reopen it with that button after restarting Maya.
5. Load the Edward rig. If it is referenced, select one of its controls and
   click `Use Selection`, or enter its namespace, then `Refresh`.

The installer copies the runtime payload to the shared Maya user scripts
folder, so the extracted source folder is not needed for subsequent launches.
Run the installer in each Maya version where you want the shelf button.
No DWPicker, pip installation, or external runtime is required in Maya.

Inside this repository, `AutoRig Tools > ANIMATION > Edward Picker` and the
`EdwardPicker` shelf button open the same native picker.

## Use

- Click: select a controller. Shift-click: add. Ctrl-click: toggle.
- `Select Body`, `Select Face`, `Select All`: select groups of rig controls.
- `Secondary`: show/hide secondary controls. `Fine Eyelids`: show the fine
  eyelid points, hidden by default.
- Mouse wheel: zoom. Middle mouse: pan. `Fit`: fit both panels.
- White outlines track Maya's selection in either direction.
- `Namespace`, `Use Selection`, `Refresh`: resolve controls for the loaded rig.
  Missing or ambiguous targets are not selected.

All 310 targets come from Edward's curve export (127 body, 183 face).
Facial secondaries remain light blue on L and pink on R.

## Facial image

`edward_face_front_hd.png` is 1380 x 1140 pixels. The original
`edward_face_front.png` is 224 x 185. The HD version was restored with the
built-in image generation tool, preserving the pose and facial landmarks;
fine hair, skin and material details are AI reconstructions. The original is
preserved. The prompt is in `image_generation_prompts.json`.
The facial background renders at 1500 x 2000 pixels for clearer zooming.

## Compatibility and verification

The picker uses Maya's bundled PySide2/shiboken2 or PySide6/shiboken6, with
enum handling for Qt5/Qt6. It does not require the repository's autorig
Python modules when installed from the standalone package.

Five interaction tests passed under real PySide6 with a simulated Maya API:
controller clicks, Shift/Ctrl selection, highlighting, group selection,
layer visibility, missing namespaces, callback cleanup and installer
relaunch after closing the window. `04_maya_picker_preview.png` is an
offline Qt preview, not a screenshot from Maya.

Live validation on 2026-10-09 passed in Maya 2026.2 with PySide6/Qt 6.5.3,
using `edward_source.mb` and a temporary scene with two references of that
rig (`EdwardA`, `EdwardB`). All 310 targets resolved in each rig: 127 body
and 183 face, with no missing or ambiguous targets. Click/Shift/Ctrl,
selection synchronization, group selectors, layers, zoom, pan, Fit,
namespace isolation, close/reopen and shelf launch after a Maya restart
were checked against the real Maya API and GUI. Ambiguous targets were
also checked with a temporary duplicate DAG node and were not selected.
The installer now saves to the local preferences shelf directory instead
of treating the studio shelf search path as one directory, and replaces
existing EdwardPicker buttons when reinstalled.

The five simulated-API Qt tests were run separately from the live Maya
session. Maya 2024, PySide2 and other Maya versions remain untested.
These results apply to this Edward rig; the exported target list can differ
from another scene. The status bar reports how many targets actually resolve.

Primary compatibility references:

- Maya 2024 PySide2: https://help.autodesk.com/cloudhelp/2024/CHS/Maya-SDK/files/Maya-Python-API/Maya_SDK_Maya_Python_API_Working_with_PySide_in_Maya_html.html
- Autodesk Qt5/Qt6 migration: https://help.autodesk.com/cloudhelp/2026/ENU/Maya-DEVHELP/files/Whats-New-Whats-Changed/2025-Whats-New-in-API/Qt6Migration.html

## Remove

Remove the `EdwardPicker` shelf button and the shared Maya user scripts
files `edward_picker_launcher.py` and `edward_picker_payload/`. These are the
only files installed by the standalone installer.
