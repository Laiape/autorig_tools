# Thaiz picker

Drag `Thaiz_Picker_Installer.py` into a Maya 2024+ viewport. The receiver does not
need AutoRig. Installation opens the native body/face picker and saves a
`thaizPicker` button on the AutoRig shelf. Load Thaiz's compatible rig separately;
the installer contains no model or rig.

With a Thaiz rig already loaded, installation also embeds its picker and the
automatic scriptNode/scriptJob setup in that scene. **Save the scene once.**
It then opens automatically when the rig is loaded, including after restarting
Maya, without running the installer again or needing AutoRig. Maya may ask for
permission to execute the rig's scene scripts. Newly built AutoRig rigs embed this
automatically. Reinstallation reuses the node and avoids duplicate callbacks.

The picker uses Thaiz's exported guides for proportions and schematic backgrounds.
The offline `.curves` source provides 285 targets: 127 body and 158 face. Live
generation instead uses controls actually built under the Thaiz root. The guide
prerequisites are shared with the rig modules; absent modules produce no buttons.

Edit `picker_profile.json` to change canvas dimensions or individual button sizes
and positions, then regenerate:

```powershell
python -m maya_tools.scripts.tools.character_picker_builder thaiz
```

See `maya_tools/scripts/tools/CHARACTER_PICKER.md` for the shared pipeline.
`generated/build_report.json` records source data, guide ownership and final
dimensions. Offline target planning is separate from validation in real Maya.
