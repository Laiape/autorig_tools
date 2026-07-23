# Flujo de pesos, herramientas del repo y QA

## Orden del build (dónde entra el skin)

`create_rig.py::AutoRig.build`:

1. `basic_structure()` → grupos base.
2. `make_rig()` → todos los módulos (los `corrective_setup()` de brazo/pierna corren
   DENTRO del make, así que los joints correctivos ya existen). Al final,
   `skeleton_hierarchy()` genera el esqueleto `_ENV`.
3. `label_joints()`, `hide_connections()`, `inherit_transforms()`.
4. **`import_weights()`** → `skin_manager_api.SkinManager().import_skins()`.
5. **`localize_correctives()`** → arregla la doble transformación de los skinClusters
   de correctivas apilados (conecta `bindPreMatrix`). Corre en pose neutra, justo
   después de importar pesos — no lo muevas de ahí.
6. `import_corrective_blendshapes()` + cleanup + picker.

**No hay bind por defecto**: si no existe `.skc`, `import_skins` da error y las mallas
quedan SIN piel. El auto-transfer del build (`_auto_transfer_from_source`) está
comentado. Primer skinning de un personaje = bind manual en escena o transferencia
desde otro personaje, y export inmediato.

## skin_manager_api (el que usa el build) — formato `.skc`

- Un ÚNICO archivo por personaje con TODAS las mallas:
  `assets/<char>/skin_clusters/<char>_v###.skc`. Versionado automático: al exportar
  crea la versión siguiente; al importar coge la más alta. Para volver a una versión
  anterior: `import_skins(in_path="…/<char>_v007.skc")` con ruta explícita (o borra en
  disco las versiones posteriores antes de rebuildar — son tu historial, muévelas, no
  las machaques).
- Por malla guarda la LISTA de skinClusters en orden de stack (soporta body +
  correctivas apilados), sus atributos (`skinningMethod`, `normalizeWeights`,
  `maxInfluences`…), influencias, pesos sparse (> 1e-5) y blend weights de dual
  quaternion.
- Import: valida topología (nº de vértices), crea el skinCluster con `multi=True`
  (apilable) o añade influencias que falten si ya existe, y REORDENA los deformers
  para respetar el stack. Los skinClusters ya presentes en escena no se pisan.
- Export: la selección o toda la escena; solo mallas (ignora NURBS/curvas).
- `copy_skin_cluster` (estático): copia skin de una malla a otra con auto-mirror YZ —
  útil para mirror de personaje completo o props duplicados.

Rutina de trabajo: pinta → `export_skins()` → sigue. El `.skc` es tu undo de sesión y
lo que el build reproduce. Exporta ANTES de cualquier operación arriesgada (transfer,
prune agresivo, mirror).

## Correctivas: skinCluster apilado

El skin de correctivas se añade ENCIMA del body en un skinCluster propio con
`corrective` en el nombre (p. ej. `C_corrective_SKC`), pesos pico 0.2-0.5 robados del
body por normalización, parche pequeño. El build lo localiza
(`localize_corrective_skin`) y el `.skc` lo persiste con su orden. Detalle en la skill
`corrective-joints` (referencia repo-y-qa).

## Alternativas y transferencia

- **skin_manager_ng** (`tools/skin_manager_ng.py`): variante con capas de ngSkinTools2,
  archivo `assets/<char>/skin_clusters/<char>.json`. NO la llama el build — es
  herramienta de trabajo (UI). Si pintas con ng, exporta igualmente el `.skc` clásico
  para que el build lo importe.
- **auto_skin_transfer** (`tools/auto_skin_transfer.py`): transferencia independiente
  de topología por proyección UV relativa al esqueleto — sirve para pasar pesos entre
  mallas distintas o ENTRE personajes (puede leer el source directamente de un `.skc`,
  sin abrir su escena), hace el bind del target y proyecta (KNN + IDW + refinado). Es
  el atajo para el primer bind de un personaje nuevo si ya tienes otro bien skinneado:
  transfiere → repasa zonas del catálogo → exporta `.skc`.

## Checklist de QA antes de cerrar una versión

1. **ROM completa por zona** (poses del catálogo): codo/rodilla 0→140°, brazo 170°,
   pronación completa, sentadilla, twist de torso, puño, roll de pie, giro de cabeza.
   Mira SILUETAS, no wireframes.
2. **Masterwalk**: lleva el rig lejos del origen y escálalo — nada debe arrastrarse ni
   temblar (si algo flota: prune de pesos residuales; si es el skin de correctivas:
   falta la localización).
3. **Mirror numérico**: pesos L/R simétricos, línea central limpia.
4. **Prune** < 0.001 y revisa `maxInfluences` según destino (4 juego / 8 film).
5. **Normalización** activa en todos los skinClusters.
6. **Export `.skc`** y, si el rig va a cache/engine, comprueba que el esqueleto `_ENV`
   se mueve idéntico al rig (el skin va sobre joints de `skel_GRP`; el `_ENV` los
   duplica — cualquier joint nuevo debe aparecer en `skeletonHierarchy_GRP`).
7. **Rebuild de prueba**: lanza el build del personaje y verifica que importa la
   versión nueva sin errores de topología (si cambiaste la malla, el conteo de
   vértices debe coincidir).
8. Solo cuando la base pasa todo esto: siguiente capa (correctivas) si aún falta
   volumen en poses extremas.
