# cache (estado del ultimo build)

Parent: `maya_tools/como_funciona.md`. Donde vive cada dato: `maya_tools/mapa_datos.md`.

`biped.cache` (y `quadruped.cache`, sin uso) son JSON que
`data_manager.DataExportBiped` escribe durante el build (`append_data`) y que
los modulos leen (`get_data`). Se regeneran con `new_build()` al empezar cada
build y estan fuera de git (`.gitignore`). Esta carpeta existe en el repo solo
por este fichero; `data_manager` la crea si falta. No es configuracion: lo que
cambia por personaje va en `maya_tools/assets/<p>/build/`.
