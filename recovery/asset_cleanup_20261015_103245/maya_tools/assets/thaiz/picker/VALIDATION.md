# Validación real de Thaiz — 2026-10-09

El proceso compartido está conectado a CREATE RIG, al menú Character Picker y al
shelf AutoRig. Las condiciones de guías son las mismas que usa cada módulo del rig.
El perfil de Thaiz define dos lienzos de 750 × 1000 px. El encuadre se calcula con
sus guías, conservando proporciones; las medidas por módulo y botón quedan en
`generated/picker_config.json` y `generated/build_report.json`.

Se construyó un rig real en una copia aislada del repositorio, con caché propia.
La escena de trabajo abierta en Edward tenía cambios sin guardar y se preservó.
No se incluyó ningún modelo ni rig en el instalador. No se hizo commit ni push.

| Entorno realmente probado | Escena | Resultado |
| --- | --- | --- |
| Maya 2026.2, API 20260200, PySide6, Qt 6.5.3, GUI | `C:/GIT/tmp/thaiz_picker_validation/thaiz_real_rig.ma` | Rig construido y picker: 285/285 controles |
| Maya 2026.2, dos referencias | `C:/GIT/tmp/thaiz_picker_validation/thaiz_two_references.ma` | ThaizA y ThaizB: 285/285 cada uno; clic selecciona la instancia correcta |
| Maya 2026.2 tras cierre y nuevo proceso, sin módulos ni rutas de AutoRig | `C:/GIT/tmp/thaiz_picker_validation/thaiz_picker_validation_scene.ma` | Instalador portable: 285/285, selección correcta y un único botón |
| Maya 2024.2, API 20240200, PySide2, Qt 5.15.2, GUI, sin módulos ni rutas de AutoRig | `C:/GIT/tmp/thaiz_picker_validation/thaiz_real_rig.ma` | Instalador portable: 285/285, selección correcta y un único botón |

La copia utilizada tras el reinicio conserva los controles del rig real y omite
sus script nodes, para probar el picker independientemente de los scripts de
animación del rig. Esta validación no certifica la deformación ni el match IK/FK.

| Comprobación | Resultado / alcance |
| --- | --- |
| Generación al terminar CREATE RIG | Pasa en Maya 2026.2, incluida la repetición después de corregir los fallos |
| Instalación, apertura y shelf | Pasa en 2024.2 y 2026.2; reinstalar mantiene un `thaizPicker` |
| Fondos y colores | Fondos SVG esquemáticos construidos con las guías; L azul y R rosa en secundarios faciales. Capturas reales adjuntas. No se generaron fotografías ni una imagen facial HD |
| Destinos | 127 corporales + 158 faciales = 285. Ausentes: ninguno. Ambiguos en el rig: ninguno |
| Ambigüedad deliberada | Un duplicado del nombre de un control bajo otra rama se detecta y se excluye; al eliminarlo vuelven los 285 destinos |
| Clic, Shift, Ctrl | Pasa mediante eventos QtTest en el picker real de Maya 2026.2, verificando `cmds.ls(selection=True, long=True)`. En 2024.2 se verificó selección simple a través del runtime |
| Selección externa y sincronización visual | Pasa en Maya 2026.2 |
| Select Body, Select Face, Select All | Pasa en Maya 2026.2 con selección real: 127, 158 y 285 |
| Secondary, Fine Eyelids | Activación y ocultación pasan en Maya 2026.2 |
| Zoom, desplazamiento, Fit | Eventos de rueda y botón central pasan; Fit restaura la escala en Maya 2026.2 |
| Namespace vacío y dos personajes referenciados | Pasa en Maya 2026.2; 285 destinos por instancia |
| Cierre y reapertura | Callbacks antiguos eliminados; reapertura pasa en 2026.2. Reinstalación y limpieza de callbacks pasan también en 2024.2 |
| Reinicio real | Pasa en 2026.2. No se repitió el reinicio ni la batería completa de namespaces/interacciones en 2024.2 |

Pruebas separadas: ocho tests puros del planificador pasan en otro proceso Python.
Verifican ausencia de guías, pares incompletos, dedos retirados, alternativas de
cejas, tamaños, versiones numéricas y botones sin solapamientos. Los cinco tests
de Edward con API Maya simulada pasan en un proceso mayapy independiente; no se
contabilizan como pruebas de Thaiz en Maya real.

Fallos corregidos: `reload(pathlib)` invalidaba clases Path importadas previamente;
la reapertura podía intentar cerrar un objeto Qt ya eliminado. Se eliminaron esa
recarga y el acceso inseguro. La generación y reapertura afectadas se repitieron.
Los errores completos conservados están en `validation/errors.txt`.

Los JSON de `validation/` contienen los resultados y los 285 caminos DAG resueltos.
`thaiz_standalone_2024.png`, `thaiz_standalone_2026.png`, `thaiz_picker_final.png`
y `thaiz_namespaces.png` son capturas del picker real, no renders simulados.
Solo quedan declaradas las versiones y comprobaciones efectivamente probadas.

## Apertura automática integrada en el rig — 2026-10-09

El rig incorpora un scriptNode GUI que guarda el código y los datos del picker.
Al cargarlo restaura los scriptJobs de sesión y abre el picker. No guarda modelos
en el instalador ni depende del repositorio AutoRig del destinatario. El rig debe
guardarse después de ejecutar el instalador una vez, o después de CREATE RIG.

Pruebas reales de esta incorporación: **Maya 2026.2, API 20260200, PySide6,
Qt 6.5.3**. Escena aislada:
`C:/GIT/tmp/thaiz_picker_validation/thaiz_with_embedded_picker.ma`.
La escena del usuario con cambios sin guardar se conservó en su proceso original.

| Comprobación | Resultado |
| --- | --- |
| CREATE RIG integra el picker | Pasa; 285 controles y un scriptNode en el rig construido |
| Instalador actualizado ejecutado dos veces | Pasa; un scriptNode, una instancia y 285 controles |
| Reinicio real de Maya con perfil independiente | Pasa; apertura desde el scriptNode de la escena, sin ejecutar instalador ni cargar AutoRig; 285/285 destinos |
| Dependencias del repositorio en el proceso independiente | Ningún módulo ni ruta de AutoRig |
| Cambio de escena y reapertura del bootstrap | Pasa; ventana nueva, callbacks anteriores eliminados y 285 destinos |
| Nueva escena vacía | Pasa tras volver al ciclo de interfaz; cero callbacks del picker y gestor vacío |
| Dos referencias del mismo archivo | Pasa; dos instancias, 285 destinos por personaje y selección externa cambia al picker de la referencia correcta |

Para aislar la limpieza y el cambio entre referencias, esas pruebas cargaron
escenas con `executeScriptNodes=False` y ejecutaron explícitamente el bootstrap.
La prueba de reinicio sí dejó que Maya ejecutara el scriptNode de la escena.
Se comprobó la limpieza después de devolver el control a la interfaz: scriptJob
ejecuta sus callbacks durante el ciclo de eventos, no dentro del comando file.
Los identificadores numéricos de jobs pueden reutilizarse; se compararon los
callbacks y la identidad de la ventana, además de comprobar el gestor vacío.

Fallo corregido: las referencias del mismo rig comparten UUID de origen. El
gestor utiliza nombres completos únicos para nodos referenciados y UUID para
nodos locales; la prueba con ThaizA y ThaizB se repitió y pasó. Al cambiar de
personaje se cierra también la ventana anterior y se liberan sus callbacks.

Maya mostró advertencias de seguridad para las importaciones del script de escena.
Se permitió cada dependencia conocida para la prueba, sin añadirla a listas de
confianza ni desactivar preferencias de seguridad. El destinatario debe permitir
los scripts del rig para obtener la apertura automática. Esta incorporación
automática no se ha validado en Maya 2024; las pruebas anteriores del picker en
2024.2 siguen teniendo únicamente el alcance indicado arriba.

Evidencias: `validation/scene_job_install_latest.json`,
`validation/job_build_result.json`, `validation/scene_job_lifecycle_verified.json`,
`validation/scene_job_references.json`, `validation/embedded_restart_2026.json`
y la captura real `validation/embedded_restart_2026.png`.
