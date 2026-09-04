---
paths:
  - "maya_tools/scripts/**"
---

# Deformacion y skin

Este fichero es la unica politica del stack de deformacion. El conocimiento
(que shape buscar, como pintar, catalogo de correctivas) vive en las skills:
`.claude/skills/como_funciona.md`.

## Stack (orden fijo, de dentro hacia fuera)
1. blendShape correctivo (`frontOfChain`), pre-skin.
2. skinCluster del body (`.skc`, `create_rig.import_weights`).
3. skinCluster de correctivas, aparte, con `corrective` en el nombre
   (`C_corrective_SKC`), localizado con `correctives.localize_corrective_skin`
   (bindPreMatrix). El build lo hace en `localize_correctives`, en pose neutra,
   justo tras importar pesos: no moverlo de ahi.
4. Capas de suavizado al final (`deltaMush`, hoy comentado en `apply_delta_mush`).

## Reglas
- Las joints `*Corrective_JNT` / `*Ring##_JNT` NUNCA van en el skin del body.
  Se pintan en el skin apilado localizado (pico 0.2-0.5, parche pequeno).
- Rest = identidad: en bind pose ninguna correctiva ni deformer mueve un
  vertice. Envelope o Enable a 0 = el paso anterior del stack, exacto.
- Todo skin apilado pasa por `localize_corrective_skin`. Una influencia anadida
  tras el build sin localizar = doble transformacion (la zona se hunde).
- El `.skc` (`skin_manager_api`) es el unico formato que importa el build:
  stack completo por malla, sparse, DQ blendWeights. `skin_manager_ng` es
  herramienta de pintado; tras pintar con ng se exporta `.skc` igualmente.
- Deformers nativos en uso: skinCluster, blendShape, deltaMush (comentado),
  uvPin. wire, cluster, lattice, wrap y proximityWrap NO se usan: no montar
  setups sobre ellos sin documentarlo y anadir el tipo a `KEEP_TYPES` de
  `hide_all_utility_nodes`.
- Export: solo viajan joints `_ENV` y morphs. Lo que un deformer aporte y no se
  hornee no existe para el engine.
- `auto_skin_transfer` esta roto: no usarlo ni recomendarlo. Transfer por
  defecto: `copySkinWeights -uvSpace -label` (boton Proxy Skinning,
  `maya_tools/scripts/tools/proxy_skinning.py`).
- El build corre en fast session (cycleCheck off): los ciclos se validan en QA.

## QA minima antes de cerrar una version de skin
ROM completa de la zona, masterwalk a 0.1x/10x y a 1000 unidades, mirror
numerico L/R, prune < 0.001, `cycleCheck -e on`, `.skc` exportado y cada joint
nueva colgando de su `_ENV` en `skeletonHierarchy_GRP`.
