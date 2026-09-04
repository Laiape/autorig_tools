# Datos y versionado

Este fichero es la unica politica de assets y versiones. El formato interno
de cada fichero se documenta en su area (Fase 2) o en la skill que lo usa.

## Layout: `maya_tools/assets/<personaje>/`
| Carpeta | Fichero | Escribe | Lee en el build |
|---|---|---|---|
| `build/` | `<p>_v001.build` (JSON) | rig settings de `C_guides_GRP` -> `rig_manager.get_rig_data` | `rig_manager.build_rig_from_data` |
| `guides/` | `<p>_vNNN.guides` | Export Guides / Asset Manager | `guides_manager` (cacheado por personaje) |
| `curves/` | `<p>_vNNN.curves` | Export All Controllers / Asset Manager | `curve_tool.build_curves_from_template` |
| `skin_clusters/` | `<p>_vNNN.skc` | `SkinManager.export_skins` | `create_rig.import_weights` |
| `corrective_blendshapes/` | `<p>_vNNN.json` | CBS manager export | `create_rig.import_corrective_blendshapes` |
| `picker/` | `<p>_picker.json` | `picker.generate_and_load` | picker |
| `models/` | `<p>_vNNN.ma` | Asset Manager | `rig_manager.open_model_scene` |

## Reglas
- Versionado `_vNNN` (tres digitos). Exportar crea la version siguiente; una
  version existente no se pisa (el Overwrite del Asset Manager es la unica
  excepcion, y consciente).
- OJO: `.skc` y `corrective_blendshapes` se resuelven por NUMERO mas alto;
  `.guides`, `.curves` y `.build` por FECHA de modificacion
  (`rig_manager.get_latest_version`). Tocar o copiar un fichero viejo cambia su
  mtime y el build lo cogera. No editar versiones antiguas.
- `.build` es siempre `_v001` y se sobreescribe al guardar los rig settings.
  Claves: `Rig_Type`, `solver_mode`, `solver_front_leg`, `solver_back_leg`,
  `reciprocal_coupling`, `foot_type`, `*_skinning_jnts`, `*_controllers`,
  `mGear_integration`, `character_extras` (`set_attrs` y `add_attrs`: listas de
  dicts `node`/`name`/`value`; `node` admite `"modulo/clave"` del data manager).
- Valores tuneados a mano en escena (amounts de correctivas...) se vuelcan a
  `character_extras`; si no, el siguiente build los pierde.
- Nada de `.bak`, copias sueltas ni `.mayaSwatches/` en assets. El historial es git.
- Modelos `.ma` grandes van por LFS (`.gitattributes`).
- `maya_tools/cache/*.cache` es el estado del ultimo build (`data_manager`):
  se regenera en cada build; no se edita a mano ni es configuracion.
- Sin bind por defecto: sin `.skc`, el build deja las mallas sin piel. Primer
  skin = manual o transferido, y export inmediato.
- Rutas con `os.path` o `pathlib`; nunca separadores de Windows a mano
  (`data_manager` aun tiene un `split("\\scripts")` pendiente).
