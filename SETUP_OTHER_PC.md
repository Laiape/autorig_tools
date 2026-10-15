# Preparar otro PC

## Descargar el repositorio completo

Instala Git y Git LFS. En PowerShell:

```powershell
git lfs install
git clone https://github.com/Laiape/autorig_tools.git
cd autorig_tools
git lfs pull
git lfs ls-files
```

Si ya tienes el repositorio, ejecuta `git pull --ff-only` y `git lfs pull` desde
su carpeta. Git LFS descarga los modelos, escenas y skins reales; sin esos
objetos el checkout puede contener solamente sus archivos de referencia.
No uses el ZIP de GitHub como sustituto del clone con LFS.

## Maya y Python

La escena de trabajo de Edward se ha guardado y comprobado en Maya 2026.
Usa Maya 2026 para continuar con ese rig. Varias herramientas también se han
probado en Maya 2024, pero esto no convierte la escena de 2026 a ese formato.

Desde la raíz del repositorio:

```powershell
python scripts/install_maya_module.py
& "C:/Program Files/Autodesk/Maya2026/bin/mayapy.exe" -m pip install --user -r requirements-maya.txt
```

Si no tienes Python del sistema, el instalador también se puede ejecutar con
`mayapy.exe`. Instala las dependencias Python con el `mayapy` de cada versión
que vayas a usar. No instales PySide ni shiboken por pip: usa los de Maya.
`requirements-maya.txt` fija las versiones de NumPy y ReportLab del equipo de
origen (1.26.4 y 5.0.1).

El instalador genera `self_module.mod` con la ruta real del clone. Conserva una
copia del módulo anterior si tiene otro contenido. Detecta Documents de Windows,
`MAYA_APP_DIR` o la carpeta de usuario de Maya si se ejecuta dentro de Maya.
Para una ubicación personalizada:

```powershell
python scripts/install_maya_module.py --modules-dir "D:/MayaUser/modules"
```

Reinicia Maya. Deben aparecer el menú **AutoRig Tools** y el shelf **AutoRig**.
Desde AssetMgr puedes abrir Character Manager y seleccionar el personaje.

## Plug-ins externos

Estos instaladores y sus licencias se obtienen por separado; no forman parte
del código del repositorio.

| Componente | Cuándo hace falta |
| --- | --- |
| Autodesk Maya 2026 | Continuar con el rig de Edward guardado en este equipo. |
| ngSkinTools 2 | Abrir y editar las capas pintadas de skinning. La versión instalada en el equipo de origen es 2.4.0. |
| Bifrost para Maya | Evaluar y editar el grafo de wrinkles de Edward. |
| MtoA / Arnold para Maya | Usar los nodos de materiales y render de Arnold de las escenas que los contengan. |
| mGear | Solo para builds con `mGear_integration` activado; el build actual de Edward lo tiene desactivado. |
| Rabbit Skinning Tools, Kangaroo Builder, AdonisFX | Accesos opcionales de Character Manager; cada herramienta necesita su propia instalación para abrirse. |

En Plug-in Manager, activa los componentes que utilices. `matrixNodes`,
`quatNodes`, `lookdevKit`, `poseInterpolator`, `ikSpringSolver` y `fbxmaya`
son componentes de Maya que las herramientas cargan al necesitarlos.
Los scripts del autorig, correctivos, deformación, exportación de skins,
wrinkles y pickers sí están incluidos en este repositorio.

## Archivos de trabajo

- Rig actual: `maya_tools/assets/Edward/scenes/Edward_working_v002.mb`.
  Para abrirlo con las texturas de este clone, guarda primero tu escena y
  ejecuta en la pestaña Python del Script Editor (ajusta la ruta):

  ```python
  import runpy
  runpy.run_path(r"C:/GIT/autorig_tools/scripts/open_edward.py", run_name="__main__")
  ```

  El script configura el proyecto y recalcula las rutas de los 22 nodos de
  textura a partir de `sourceimages` del clone. Maya puede guardar estas rutas
  como absolutas; vuelve a usar el script si cambias el repositorio de carpeta.
  Para una escena ya abierta, puedes usar `relink_scene_textures()` del mismo
  script. No requiere la unidad D del equipo original.
- `maya_tools/assets/Edward/portable_assets.json` enumera las texturas incluidas
  y diez mapas antiguos de XGen que ya faltaban en el equipo original. Esos
  mapas no se han recuperado; los rigs y las capas de skinning sí se incluyen.
- Assets para reconstrucción: `maya_tools/assets/<personaje>/models`, `guides`,
  `curves`, `build` y `skin_clusters`.
- Skins recientes de Edward: versiones 064, 065 y 068, con los skins locales de
  nariz, sockets, cheeks y cheekbones en la high y el interpolador de mandíbula
  reparado. Character Manager usa las versiones de cada categoría.
- Pickers: instaladores de Edward, Nini y thaiz en sus carpetas `picker`.
  El instalador de Edward también funciona como script independiente.

Los modelos de Edward y chihuahua que antes estaban excluidos están incluidos
con Git LFS para poder reconstruirlos en otro equipo.

El `.gitignore` excluye cachés regenerables, entornos locales, credenciales,
logs, experimentos, paquetes generados y resultados de validación. Estos archivos
se mantienen en el equipo original y no se necesitan para instalar las herramientas.
Las versiones de assets y los recursos de los pickers se conservan.

Si Maya avisa de un plug-in externo ausente al abrir una escena, instala ese
componente antes de guardar la escena de trabajo.

Para inspeccionar o corregir otras rutas externas, Maya dispone del
[File Path Editor](https://help.autodesk.com/cloudhelp/2025/ENU/Maya-Tech-Docs/Commands/filePathEditor.html).
