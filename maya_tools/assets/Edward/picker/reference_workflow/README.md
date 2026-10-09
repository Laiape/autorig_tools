# Edward reference picker

This folder contains the three stages of the requested workflow:

1. `01_reference_without_character.png`: the supplied two-panel reference,
   with the character removed using the built-in image generation tool.
   It is a generated reconstruction; tiny shapes are not pixel-identical.
2. `controls/body/` and `controls/face/`: 310 independent, transparent SVG
   and PNG controller assets, named after Edward's actual exported targets.
   These are editable vector redraws in the reference palette, not crops.
   `02_body_controls` and `02_face_controls` are transparent layout overlays.
   `02_controls_catalog` shows all assets; `controls_manifest.json` records
   target name, panel, position, shape, dimensions, color and layer.
3. `03_edward_picker.png` and `.svg`: the assembled body and face design.
   Separate body and face versions are also supplied. The body uses the front
   A-pose from `edward_reference_sheet.png`; the face uses the later supplied
   `edward_face_front_hd.png`, restored to 1380 x 1140 pixels with the built-in
   image generation tool. The 224 x 185 original is preserved. Fine HD details
   are reconstructed. Native viewports isolate the selected regions; a gray
   vector backing fills the body frame's margins. Controls are aligned to
   each source. The facial background renders at 1500 x 2000 for zooming.

`Edward_reference_picker.json` is a separate DWPicker document. The original
`Edward_picker.json` is preserved. All 310 exported targets are covered:
127 body and 183 face. Right is red, left blue, IK cyan/pink, center yellow,
secondary green. Facial secondary controls use light blue (`#82b9ed`) on L
and pink (`#ed96b0`) on R, including fine eyelid points. Central secondaries
remain green. Fine eyelid points are hidden by default in `Fine eyelids`;
enable that visibility layer in DWPicker to use the individual points.
Scissor buttons target the five digit roots on each hand. Secondary points
select the additional exported finger joints.

## Load in Maya

The native Maya 2024+ picker requires no third-party picker. Drag
`install_edward_picker.py` into Maya or use the integrated `Edward Picker`
menu/shelf button. Full instructions: `README_MAYA.md`.

### Optional DWPicker version

DWPicker must already be installed. Open the JSON with DWPicker's file-open
command on this checkout, or run this in Maya's Python Script Editor:

```python
import runpy
tool = runpy.run_path(
    "C:/proyectos/auto-rig/maya_tools/assets/Edward/picker/"
    "reference_workflow/load_in_maya.py",
    run_name="edward_picker_loader",
)
tool["load"](namespace="")
```

If the scene uses a namespace, supply it, e.g. `namespace="Edward"`.
The loader resolves local background paths, reports missing scene targets,
embeds the document in the scene and opens DWPicker. Other named pickers are
preserved. Direct JSON opening uses absolute image paths for this checkout;
use the loader after moving the asset folder to another location.

## Rebuild

From the repository root:

```text
python maya_tools/scripts/tools/build_edward_reference_picker.py
node maya_tools/scripts/tools/render_edward_reference_picker.cjs
```

The Node renderer requires `sharp` through `NODE_PATH` or a local installation.
It rasterizes native SVG layouts and does not repaint the source photograph.
The builder rejects unknown targets and checks full exported control coverage.

## Verification and sources

Controller PNGs were checked for transparency. All targets match
`maya_tools/assets/Edward/curves/Edward_v001.curves`. Layout PNGs were visually
inspected. The DWPicker schema and loader entry point were checked against
the upstream DreamWall-Animation/dwpicker source. Runtime interaction in Maya
has not been tested in this task; the live rig can differ from the export.

- User-supplied screenshot: `reference_original.png`.
- Current body source: `edward_reference_sheet.png` (user-supplied).
- Original face source: `edward_face_front.png` (user-supplied `edward.png`).
- Current HD face: `edward_face_front_hd.png` (built-in AI restoration).
- Previous Edward photograph: `maya_tools/assets/Edward/Edward.png`.
- Additional supplied reference: https://www.artstation.com/artwork/EzezLv
  (its image content was inaccessible through the available web requests).
- Generation prompts and outcome: `image_generation_prompts.json`.
  Character removal succeeded. The frontal repose request was rejected by
  the generation safety filter. The current design uses the later supplied
  reference sheet and restored frontal face image. Native Qt interaction
  tests passed with a simulated Maya API; see `README_MAYA.md` for the limits.
