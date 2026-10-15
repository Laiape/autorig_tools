# Where data is represented

Parent: `modulos/vision/how_it_works.md`.
UI: `maya_tools/criterios-ui.md`.

When someone says "this information is here" (a Maya scene, a guides
file, a skin dump, an Unreal note), **do not invent a new window**.
Read this map, pick the row that matches the meaning, and put it there.

---

## How to resolve a source

1. Name what the data *means*.
2. Find that meaning in the table below.
3. Represent it on that Maya menu item or Unreal path, for the rigger.
4. If it fits two rows, keep the split (Maya rig vs Unreal notes).
5. After wiring a new file type, add it to the Sources column in the same task.

---

## Audience

| Who | Sees |
|---|---|
| Maya rigger | AutoRig Tools menu, AutoRig shelf, current scene |
| Unreal rigger | `ue_tools/docs/` notes. No editor UI in this repo yet |

---

## Map

| If the data is... | Show it on | Who uses it | Sources |
|---|---|---|---|
| Active character UUIDs, work profiles and guided review marks | Tool Framework > Character context / Workflow | Maya rigger | `maya_tools/scripts/framework/context.py`; `state.py`; session-owned UUIDs and versioned Maya optionVars |
| Framework/menu action outcomes and returned artifact paths | Tool Framework > Activity | Maya rigger | `maya_tools/scripts/framework/execution.py`; Maya app directory `autorig/framework/operations.jsonl`; explicit JSON export |
| Character Maya scene (`.ma` / `.mb`) | Character Manager | Maya rigger | Character Manager `ALLOWED_ENDINGS`; `maya_tools/scripts/utils/character_manager.py` |
| Guide locators / fit data (`.guides`) | Rigging > Guides (create/import/export/mirror); Rigging > Build > Test Rig by Guide | Maya rigger | `maya_tools/scripts/utils/guides_manager.py` |
| Controller curve shapes (`.curves`) | Rigging > Controllers (export/mirror/library) | Maya rigger | `maya_tools/scripts/utils/curve_tool.py` |
| Skin cluster dump (`.skc`) | Deformers > Skinning (export/import) | Maya rigger | `maya_tools/scripts/tools/skin_manager_api.py` |
| Skin weights, NG layers and procedural ramp masks | Deformers > Skinning > Skinning Manager; AutoRig shelf | Maya rigger | `maya_tools/scripts/ui/skinning_manager_UI.py`; `maya_tools/scripts/ui/skinning_tool_adapters.py`; installed ngSkinTools2, brSmoothWeights, rampWeights and weightsServer native editors |
| Complete transverse facial-loop weights and paired lip influences | Skinning Manager > NG > Layers right-click > LIPS / EYELID / EYEBROW RIGGER; Loop Rigger (Preview) | Maya rigger | `maya_tools/scripts/tools/facial_loop_riggers.py`; `maya_tools/scripts/tools/facial_loop_skinning.py`; `maya_tools/scripts/ui/skinning_tool_adapters.py`; existing skin influences, black initial masks and Lips parent with Rotate / Non Rotate children; Nini pilot under `maya_tools/assets/Nini/review/loop_rigger/` |
| JSON / other sidecar listed by the manager | Character Manager | Maya rigger | `ALLOWED_ENDINGS` includes `.json` |
| Autorig build cache | Internal `maya_tools/cache/biped.cache` during build. Not a menu. | Build (`create_rig.AutoRig`) | `maya_tools/scripts/utils/data_manager.py` |
| Corrective blendshape export/import | Deformers > Blendshapes | Maya rigger | `maya_tools/scripts/tools/corrective_blendshape_manager.py` |
| Controller or orientation-driven corrective sculpt targets | Deformers > Blendshapes > Pose Blendshapes; Skinning Manager > Corrective Blendshapes | Maya rigger | `maya_tools/scripts/tools/pose_blendshapes.py`; `maya_tools/scripts/tools/orientation_correctives.py`; `maya_tools/scripts/ui/pose_blendshapes_UI.py`; native scene-stored deltas, SDK/native pose drivers and `.skc` metadata |
| Joint corrective targets and scene-stored vertex masks | Deformers > Correctives > Joint Corrective Targets | Maya rigger | `maya_tools/scripts/tools/joint_correctives.py`; `maya_tools/scripts/ui/joint_correctives_UI.py`; native Maya scene and normalized skin layer |
| Procedural wrinkle regions, masks and presets | Deformers > Wrinkles > Wrinkle Regions / Presets | Maya rigger | `maya_tools/scripts/tools/wrinkle_presets.py`; `maya_tools/scripts/ui/wrinkle_regions_UI.py`; `maya_tools/assets/<character>/wrinkles/*.wrinkles.json`; native Bifrost graph and `.skc` wrinkle snapshot |
| Cloth / auto skin transfer | Auto Skin Transfer (Clothes) window | Maya rigger | `maya_tools/scripts/ui/skin_transfer_UI.py` |
| Baked deformation copies and error validation | Deformers > Bake > Bake Deformation to Skin | Maya rigger | `maya_tools/scripts/tools/proximity_bake.py`; `maya_tools/scripts/ui/proximity_bake_UI.py`; scene-stored validation, error color set and optional new `.skc` |
| Pose test and versioned build comparison | Test Rig (pose tester) | Maya rigger | `maya_tools/scripts/ui/pose_tester_UI.py`; `maya_tools/scripts/tools/rig_validation.py`; `.rigqa.json` pose/geometry reports and `maya_tools/assets/<character>/validation/*.righealth.json` |
| Character animation control picker | Character Picker (ANIMATION menu / shelf) | Maya animator/rigger | Shared guide gates `utils/module_guides.py`; per-asset `picker/picker_profile.json`; native entry `tools/character_picker.py`; generated data/report and portable installer per character |
| Model sanity before rig | Model Checker | Maya rigger | `maya_tools/scripts/tools/model_checker.py` |
| Composite corrective poses | Pose Blendshapes | Maya rigger | `maya_tools/scripts/tools/combination_correctives.py`; native combination data in `.skc` |
| Facial contact and local skinning comparisons | Test Rig | Maya rigger | `maya_tools/scripts/tools/facial_contact_validation.py`; `maya_tools/scripts/tools/skinning_volume.py`; `.contact.json` and `.skincompare.json` |
| Viewport detail, animated state benchmarks and measured interaction | Test Rig | Maya animator/rigger | `maya_tools/scripts/tools/rig_performance.py`; `rig_benchmark.py`; explicit primary/detail routing, `.performance.json`, `.viewport.json` and separate `.mayaProfile` |
| Hybrid deformation approximations | Bake Deformation to Skin | Maya rigger | `maya_tools/scripts/tools/hybrid_bake.py`; scene `hybridBakeValidation` and per-vertex errors |
| Frozen validated rig inputs | Validated Rig Packages | Maya rigger/pipeline | `maya_tools/scripts/tools/rig_package.py`; manifest hashes, captured asset versions and publish comparison reports |
| Character semantic bindings (`.roles.json`) | Test Rig > General rig tools > Rig roles | Maya rigger | `maya_tools/scripts/tools/rig_roles.py`; native message membership; optional `maya_tools/assets/<character>/rig_data/roles.roles.json` rebuild sidecar |
| Portable validation profiles and pose libraries | Test Rig > General rig tools | Maya rigger | `maya_tools/scripts/tools/rig_profiles.py`; `maya_tools/scripts/tools/rig_pose_library.py`; `.rigprofile.json`, `.rigposes.json` and `.rigqa.json` with PNG captures and optional colored snapshot |
| Surface regions and migration preflight | Test Rig > General rig tools > Surface contact / Version migration | Maya rigger | `maya_tools/scripts/tools/rig_surface_contact.py`; `maya_tools/scripts/tools/rig_migration.py`; profile contact specs, scene diagnostics and fresh destination candidate |
| Unreal production rigging notes | `ue_tools/docs/` | Unreal rigger | `ue_tools/docs/unreal_fest_chicago_2026_rigging_produccion.md` |

Wrong: a new dump window because the map had no row. Add a row with the user, or leave TODO.
Wrong: putting Unreal notes behind a Maya menu item.
Wrong: a second Character Manager.
