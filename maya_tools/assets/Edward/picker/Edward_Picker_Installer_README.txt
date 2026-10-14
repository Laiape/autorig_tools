EDWARD PICKER - SINGLE FILE INSTALLER

Send Edward_Picker_Installer.py to the recipient. No other files required.

1. Open Maya.
2. Drag Edward_Picker_Installer.py into the Maya viewport.
3. The picker opens and the AutoRig shelf gets an EdwardPicker button.
4. Open a scene containing the matching Edward rig.
5. For a reference, select a rig control and click Use Selection.

The script embeds its code, controller data and body/face images.
It does not require the author's AutoRig repository or DWPicker.
It does not include the character rig, model, animation or scene.
Reinstalling replaces the picker button instead of duplicating it.
After installation, reopen from AutoRig > EdwardPicker.

Run inside Maya's graphical interface, not by double-clicking in Windows.
Alternative in Maya's Python Script Editor:

import runpy
runpy.run_path(r"C:\path\Edward_Picker_Installer.py", run_name="__main__")

Validated on Maya 2026.2 with PySide6 / Qt 6.5.3.
Maya 2024 / PySide2 is designed to be supported but remains untested.
