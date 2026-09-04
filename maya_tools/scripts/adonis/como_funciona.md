# AdonisFX (copyWeightsAdonis)

Parent: `maya_tools/como_funciona.md`.
Skill: `.claude/skills/custom-deformers/SKILL.md` (referencia `catalogo-profesional.md` seccion AdonisFX).
Regla: `.claude/rules/deformacion-y-skin.md`.
Fichero: `maya_tools/scripts/adonis/copyWeightsAdonis.py` (2698 lineas).

## 1. Que es y para que existe

Tooling propio para los deformadores comerciales de AdonisFX (Inbibo):
transferir, copiar/pegar, espejar y re-mallar los mapas de pesos y escalares
de `AdnSkin`, `AdnFat`, `AdnSkinMerge`, `AdnMuscle`, `AdnRelax`, `AdnPush` y
`AdnMush`. AdonisFX no forma parte del build: es simulacion sobre el rig ya
construido y no viaja al export.

## 2. Como esta montado

- UI de cuatro pestanas (`show()`, o arrastrar el `.py` al viewport:
  `onMayaDroppedPythonFile`): Transfer (malla origen -> destino, copia mapas y
  conexiones entrantes), Copy/Paste (buffer en memoria, con mirror X),
  Mirror L -> R (`scan_mirror_candidates`, `mirror_l_to_r`), Replace Mesh
  (`replace_mesh_in_setup`: pasa skinCluster y todos los Adn a una malla
  nueva con snapshot del grafo auxiliar).
- API publica: `copy_weights(src, dst, maps, mirror_connections)`,
  `copy_scalar_attrs`, `copy_connections`, `apply_and_copy`,
  `copy_from_selection`, `copy_from_selection_multi`, `copy_to_buffer`,
  `paste_from_buffer(maps, mirror_x)`, `clear_buffer`.
- `_DEFORMER_MAPS` define los mapas por tipo (AdnSkin 13, AdnFat 6,
  AdnMuscle 11; Relax/Push/Mush sin mapas, solo escalares). Ruta de atributo
  `node.<listAttr>[0].<elemAttr>[i]`. Misma topologia: copia indice a indice;
  distinta: closest point + baricentricas.
- Entrada: menu SIMULATION > AdonisFX Copy Weights. Tambien desde el Asset
  Manager (Tools > AdonisFx abre la UI de AdonisFX, no esta tool).

## 3. Datos que lee y escribe

Solo en escena y en el buffer en memoria. No hay fichero versionado de pesos
de AdonisFX en `assets/` (decision pendiente si se quiere persistir).

## 4. Estado hoy

Funcional como herramienta de artista. El repo no tiene test ni escena de
ejemplo con AdonisFX. Los tipos nuevos de Adn* hay que anadirlos a
`_DEFORMER_MAPS` y a `KEEP_TYPES` de `create_rig.hide_all_utility_nodes` si
deben verse en el channel box tras el cleanup.

## 5. Como probarlo

Con el plugin de AdonisFX cargado: dos mallas con `AdnSkin`, pintar en una,
Transfer a la otra y comparar mapas; Copy en L, Paste con mirror X en R.

## 6. Do not

- No meter AdonisFX en el build ni en el export: se queda en Maya.
- No documentar setups de AdonisFX como si el repo los construyera; el repo
  solo mueve pesos.
