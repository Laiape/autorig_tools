# Compilar / instalar el plugin `colliders` (Maya 2024 y 2026)

El repo trae binarios para **2022, 2023, 2025**. Para **2024** y **2026** hay que
**compilar** (los `.mll` NO son compatibles entre versiones de Maya). Una vez compilado,
el `.mll` va a `plugins/<version>/colliders.mll` y `load_plugin()` lo carga solo.

## Requisitos (Windows)
1. **Visual Studio 2022** (workload *Desktop development with C++*, x64). Maya
   2024/2025/2026 usan MSVC v143.  ← lo único que falta en esta máquina.
2. **CMake** (3.10+) en el PATH (o el que trae VS 2022).
3. **Maya Devkit**: NO hay que descargarlo. **Maya 2024 y 2026 ya lo traen** dentro
   de su install (`C:\Program Files\Autodesk\Maya<ver>\include` y `\lib`). `build.bat`
   lo auto-detecta.

## Forma rápida (script incluido)
```bat
cd C:\GIT\autorig_tools\scripts\tools\colliders
build.bat 2024
build.bat 2026
```
(auto-detecta el devkit del install de Maya). Deja el binario en
`plugins\2024\colliders.mll` y `plugins\2026\colliders.mll`.

## Forma manual (CMake)
```bat
cd C:\GIT\autorig_tools\scripts\tools\colliders
cmake -S . -B build\2026 -G "Visual Studio 17 2022" -A x64 -DMAYA_DEVKIT_DIR="C:\ruta\al\Maya2026_DEVKIT"
cmake --build build\2026 --config Release
copy build\2026\Release\colliders.mll plugins\2026\colliders.mll
```
(igual para 2024 cambiando `2026` por `2024` y su devkit).

## Cargar en Maya
No hace falta instalarlo en `MAYA_PLUG_IN_PATH`: el módulo lo carga por ruta absoluta.
```python
from tools.colliders import load_plugin
load_plugin()   # carga plugins/<tuVersion>/colliders.mll
```
Si prefieres que aparezca en Plug-in Manager, copia el `.mll` a una carpeta de
`MAYA_PLUG_IN_PATH` (p.ej. `Documents\maya\2026\plug-ins\`) y cárgalo desde ahí.

## Nota
`load_plugin()` intenta un **fallback** a la versión más cercana si no hay build para la
tuya, pero un `.mll` de 2025 normalmente **no** carga en 2026 (API distinta). Compila para
tener el de 2024/2026 propio.
