# Tools (herramientas de artista y tests)

Parent: `como_funciona.md` (raiz).
Reglas: `.claude/rules/deformacion-y-skin.md`, `.claude/rules/datos-y-versionado.md`.
Menu que las abre: `maya_tools/scripts/ui/como_funciona.md`.
Skills: `.claude/skills/como_funciona.md` (skinning, proxy, correctivas, deformers, ropa).

## 1. Que es y para que existe

Herramientas que se usan sobre un rig ya construido o sobre el modelo: skin
(`.skc`), correctivas, transferencias, QC del modelo, ROM, utilidades de
animacion, plugins Python y el listener MCP. Tambien viven aqui los tests
headless (`tests/`) y el analisis de metraje (`analysis/`).

## 2. Como esta montado

| Fichero | Que hace | Entrada | Dependencias | Ficheros | Estado |
|---|---|---|---|---|---|
| `skin_manager_api.py` (599) | `SkinManager`: exporta e importa el stack completo de skinClusters por malla a `.skc` (sparse, DQ blendWeights, attrs `skinningMethod`, `normalizeWeights`, `maintainMaxInfluences`, `maxInfluences`, `weightDistribution`); `import_skins` valida topologia, crea con `multi=True`, anade influencias que falten y reordena el stack; `copy_skin_cluster` con mirror YZ | menu SKINNING > Skin Cluster Manager > Export / Import; Asset Manager pestana skin_clusters; `create_rig.import_weights` | OpenMaya | `assets/<p>/skin_clusters/<p>_vNNN.skc` (numero mas alto) | ACTIVO, el unico formato de pesos que importa el build |
| `skin_manager_ng.py` (302) | variante con capas de ngSkinTools2 (daisy chains, `force_skin_cluster_from_data`) | sin item de menu | `ngSkinTools2` (avisa si falta) | `assets/<p>/skin_clusters/<p>.json` | herramienta de pintado; el build no la llama |
| `proxy_skinning.py` (284) | `proxy_skin(proxy, high, root_joint, max_influences=4, ...)`: bind por Geodesic Voxel (bindMethod 3), `copySkinWeights` por label o UV del proxy a la alta, prune y normalizado; `skin_report` | menu SKINNING > Skin Cluster Manager > Proxy Skinning (selecciona proxy y alta) | nativo | - | ACTIVO; es el transfer por defecto |
| `corrective_blendshape_manager.py` (805) | `CorrectiveBlendshapeManager`: `export`, `import_from`, `mirror_in_scene`, `mirror_targets`; targets `frontOfChain` con driven keys; `_push_before_skin` reordena si hace falta | menu CORRECTIVES > Corrective Blendshapes > Export / Import; `create_rig.import_corrective_blendshapes` | OpenMaya | `assets/<p>/corrective_blendshapes/<p>_vNNN.json` | ACTIVO |
| `auto_skin_transfer.py` (1307) | transfer independiente de topologia por UV relativas al esqueleto: `UVMatchingModule`, `SkinSamplingModule`, `JointMappingModule`, `WeightProjectionModule`, `RefinementModule`, `JointZoneAnalyzer`, `AutoSkinTransferSystem.transfer` | menu SKINNING > Auto Skin Transfer (Clothes) -> `skin_transfer_UI` | numpy | lee `.skc` y `.skinmap` | DADO POR ROTO por el usuario (las skills y la regla lo dicen; el codigo no tiene aviso). `create_rig._auto_transfer_from_source`, que lo usaba, esta comentado |
| `mesh_data_exporter.py` (350) | `SourceSkinExporter.export_all / export_mesh`: escribe `.skc` + `.skinmap` (mapa UV de pesos) del personaje `source` para transfers | funcion `auto_rig_UI.export_source_skin_data` (sin item de menu) | numpy | `assets/source/skin_clusters/*.skc`, `*.skinmap` | solo lo usa el transfer comentado |
| `cloth_skin_transfer.py` (410) | cuerpo -> prenda sin UVs: closest point en triangulo + baricentricas + inpainting de los vertices sin correspondencia (`transfer(body, cloth, ...)`) | sin item de menu (API) | nucleo sin numpy ni Maya; `transfer` usa OpenMaya | - | con test propio (`tests/test_cloth_skin_transfer.py`, python3 puro) |
| `efficient_cloth_skin.py` (300) | prenda con `proximityWrap` al cuerpo y horneado a skinCluster lineal con `bakeDeformer` (`build_efficient_cloth_skin`) | sin item de menu (API) | nativo | - | prototipo de la skill de ropa |
| `skirt_collider.py` (440) | colision falda-piernas 100% nodos: campana NURBS por pierna + anillo de reposo + closestPointOnSurface (`build_from_rig`) | sin item de menu (API) | nativo | - | sustituye al plugin C++ y al `native_collider` borrados (historia en `.claude/skills/custom-deformers/references/repo-deformers.md`) |
| `auto_collision.py` (76) | `auto_collision_rig(collider_list, target_obj, axis, direction)`: empuje por distancia de un joint (offset group) | sin item de menu (API) | nativo, nodos legacy (`plusMinusAverage`) | - | funciona; migrar a nodos 2024+ al tocarlo |
| `model_checker.py` (1322) | QC del modelo ("Minimo Model Checker", estandares de modelado): ngons, tris, non-manifold, history, frozen transforms, pivots, nombres duplicados, shapes multiples, mesh bajo mesh, verts solapados, tweaks, grupos vacios, shaders y texturas sin uso, nodos pegados, namespaces; topo: contacto con el suelo, simetria, polos, nodos ilegales; checks manuales; `fix_*` por check | menu MODELING > Model Checker | PySide | - | ACTIVO |
| `pose_tester.py` (474) | ROM estandar: `animate_pose(zone, pose_index, sides, spacing)`, `animate_full_body`, `clear_test`; cada zona aislada, un eje cada vez, vuelve a neutral entre extremos | menu ANIMATION > Test Rig -> `pose_tester_UI` | - | - | ACTIVO (biped) |
| `rig_tools.py` (657) | utilidades tipo ml_tools: `ArcTracer`, `WorldBake` a locators y vuelta, color por gradiente, parent/unparent shape, `reset_channels`, `switch_rotation_order` con bake; `RigToolsUI` | `auto_rig_UI.show_rig_tools` existe pero NO esta en el menu | PySide | - | funciona; sin entrada |
| `curve_library.py` (754) | grid de shapes de control: guardar, listar y aplicar (`save_shape_to_library`, `apply_library_to_selected`) | `auto_rig_UI.show_curve_library` existe pero NO esta en el menu | PySide | `tools/curve_shapes/*.json` (la carpeta no existe en el repo; se crea al guardar) | funciona; sin entrada |
| `ik_fk_match.py` (195) | `MPxCommand` `ikFkMatch` (flags `fkJoints`, `ikControllers`, `ikJoints`, `fkCtls`, `type`), undoable; se autocarga como plugin | sin item de menu | OpenMaya | - | sin llamadas desde el repo (NO VERIFICADO desde el picker) |
| `proxy_locator.py` (484) | plugin Python: `ProxyLocatorNode` (`MPxLocatorNode`) + `MPxDrawOverride` que pinta sobre cada control el parche de malla mas cercano; `assign_all_proxy_locators`, `create_proxy_locator` | carga en `userSetup.init_proxy_locator`; Asset Manager > Quick Tools > Assign / Remove Proxy Locators | OpenMaya, OpenMayaRender | - | ACTIVO. El docstring aun cita `C:/GIT/...` (el arranque real busca por `sys.path`) |
| `restore_node_visibility.py` (41) | `restore_all()`: devuelve `isHistoricallyInteresting` a lo que escondio `hide_all_utility_nodes` | sin item de menu | - | - | utilidad de depuracion |
| `mcp_listener.py` (84) | listener TCP en `localhost:9877` para el MCP de Maya: una linea JSON por comando (`execute_python`, `execute_mel`, `scene_info`, `list_nodes`), ejecuta en el hilo principal | `userSetup.init_mcp_listener` | - | - | ACTIVO |
| `export_engine.py` (2) | vacio | - | - | - | placeholder |

Formato `.skc` (por malla): lista de skinClusters en orden de stack, cada uno
con `attributes`, influencias, `sparse_weights` `{influencia: {indices, pesos}}`
y `sparse_blend`. Detalle en `.claude/skills/skinning-deformation/references/flujo-pesos-y-qa.md`.

## 3. Tests y analisis

| Fichero | Como se lanza | Que comprueba |
|---|---|---|
| `tests/test_build_horse_leg_self.py` (602) | `mayapy maya_tools/scripts/tools/tests/test_build_horse_leg_self.py` | build headless de las 4 patas de `leg_module_self` con las guias del caballo: reposo, espejo, `Bend_Bias`, solver `nodes`, `sc_rp_sc`, `sc_rp_sc_carpus`, drift IK/FK, sling de escapula |
| `tests/test_wing_module.py` (108) | `mayapy maya_tools/scripts/tools/tests/test_wing_module.py` | tres cadenas sinteticas, `WingModule.make`, joints clavados a la surface en reposo y en pose, falloff del control de membrana. Parchea `DataExportBiped.__init__` a un cache temporal y `curve_tool.build_curves_from_template` |
| `tests/test_cloth_skin_transfer.py` (177) | `python3 maya_tools/scripts/tools/tests/test_cloth_skin_transfer.py` (sin Maya) | closest point en triangulo, el transfer no cruza pesos entre piernas, inpainting del bajo de la falda |
| `analysis/gallop_kinematics.py` (150) | script con CSV de landmarks 2D (Kinovea, DLTdv) | angulos interiores codo / carpo / menudillo de un caballo real en las mismas unidades que mide el test del rig |

Los tests con Maya usan `maya.standalone` y un cache falso: no tocan
`maya_tools/cache` ni los assets.

## 4. Estado hoy

- Cadena de skin recomendada y activa: bind manual o `proxy_skinning` ->
  pintar -> `SkinManager.export_skins` -> el build importa. Lo demas
  (`auto_skin_transfer`, `mesh_data_exporter`, `skin_manager_ng`) son
  alternativas no cableadas al build.
- Cinco funciones de `auto_rig_UI` no tienen item de menu: `show_curve_library`,
  `show_rig_tools`, `copy_skin_cluster`, `export_source_skin_data`,
  `mirror_corrective_blendshapes` / `mirror_corrective_blendshape_targets`.
- `export_engine.py` esta vacio. `ik_fk_match` no lo llama nada del repo.

## 5. Como probarlo

- Skin: exportar con el menu, borrar el skin, importar; la malla debe deformar
  igual y el stack conservar el orden. Rebuild del personaje: `import_weights`
  tiene que coger la version nueva sin error de topologia.
- Tests: los tres comandos de la tabla; salida `OK`/`MAL` por linea.

## 6. Do not

- No exportar pesos con otro formato que `.skc` para el build.
- No recomendar ni cablear `auto_skin_transfer` hasta que se arregle y tenga test.
- No anadir una tool sin fila en esta tabla y, si tiene UI, sin item en el
  menu (`maya_tools/scripts/ui/como_funciona.md`).
- No escribir un test que use `maya_tools/cache` real: parchear
  `DataExportBiped` como hace `test_wing_module.py`.
