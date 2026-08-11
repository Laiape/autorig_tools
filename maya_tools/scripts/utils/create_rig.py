import time
import maya.cmds as cmds
import maya.api.OpenMaya as om
from importlib import reload

# Utils
from maya_tools.scripts.tools import proxy_locator
from maya_tools.scripts.utils import guides_manager
from maya_tools.scripts.utils import basic_structure
from maya_tools.scripts.utils import data_manager
from maya_tools.scripts.utils import rig_manager
from maya_tools.scripts.utils import matrix_manager
from maya_tools.scripts.tools import skin_manager_api
from maya_tools.scripts.tools import mesh_data_exporter
from maya_tools.scripts.tools import auto_skin_transfer
from maya_tools.scripts.tools import corrective_blendshape_manager
from maya_tools.scripts.utils import picker as picker_generator


reload(guides_manager)
reload(basic_structure)
reload(data_manager)
reload(rig_manager)
reload(matrix_manager)
reload(skin_manager_api)
reload(mesh_data_exporter)
reload(auto_skin_transfer)
reload(proxy_locator)
reload(corrective_blendshape_manager)
reload(picker_generator)



class AutoRig(object):

    """
    AutoRig class to create a custom rig for a character in Maya.
    """

    def build(self, leg_impl="self"):

        """
        Initialize the AutoRig class, setting up the basic structure and connecting UI elements.
        leg_impl: "self" | "reference" — implementación de pata de cuadrúpedo.
        """
        from maya_tools.scripts.ui import rig_progress
        reload(rig_progress)

        start = time.time()
        char_name = rig_manager.get_character_name_from_build() or "Asset"

        # Read mGear setting early so the icon shows from the start
        mgear = False
        try:
            settings = rig_manager.build_rig_from_data(char_name)
            if settings:
                mgear = bool(settings.get("mGear_integration", 0))
        except Exception:
            pass

        progress = rig_progress.RigProgressDialog(char_name, mgear=mgear)
        progress.show()

        session = self._begin_fast_session()

        try:
            progress._set_pct("Creating basic structure…", 2)
            data_manager.DataExportBiped().new_build()
            self.basic_structure()

            def on_module_step(label, current, total):
                pct = 5 + int(current / max(total, 1) * 75)
                progress._set_pct(label, pct)

            progress._set_pct("Building rig modules…", 5)
            self.make_rig(on_step=on_module_step, leg_impl=leg_impl)

            progress._set_pct("Labeling joints…", 82)
            self.label_joints()

            progress._set_pct("Hiding utility nodes…", 85)
            self.hide_connections()

            progress._set_pct("Setting inherit transforms…", 88)
            self.inherit_transforms()
            self._end_fast_session(session)
            session = None

            progress._set_pct("Importing skin weights…", 91)
            self.import_weights()

            progress._set_pct("Localizing corrective skin…", 95)
            self.localize_correctives()

            # progress._set_pct("Applying delta mush…", 95)
            # self.apply_delta_mush()

            progress._set_pct("Importing corrective blendshapes…", 96)
            self.import_corrective_blendshapes()

            progress._set_pct("Cleaning up node graph…", 98)
            self.hide_all_utility_nodes()

            progress._set_pct("Generating picker…", 99)
            try:
                picker_generator.generate_and_load()
            except Exception as e:
                om.MGlobal.displayWarning(f"[Picker] Could not generate picker: {e}")

        finally:
            self._end_fast_session(session)
            elapsed = time.time() - start
            progress.finish(elapsed)
        # self.proxy_locator()

    def _begin_fast_session(self):

        """
        Pone Maya en modo "build rápido": en Parallel/Serial cada connectAttr
        reconstruye el grafo de evaluación y el viewport se redibuja sin parar.
        Devuelve el estado previo para restaurarlo en _end_fast_session.
        """
        state = {}
        try:
            state["eval_mode"] = cmds.evaluationManager(q=True, mode=True)[0]
            cmds.evaluationManager(mode="off")  # DG lazy: no reconstruye el grafo por nodo
        except Exception:
            state["eval_mode"] = None
        try:
            state["cycle_check"] = cmds.cycleCheck(q=True, evaluation=True)
            cmds.cycleCheck(e=True, evaluation=False)  # sin chequeo de ciclos en cada conexión
        except Exception:
            state["cycle_check"] = None
        try:
            state["undo"] = cmds.undoInfo(q=True, state=True)
            cmds.undoInfo(stateWithoutFlush=False)  # sin cola de undo (memoria + velocidad)
        except Exception:
            state["undo"] = None
        try:
            cmds.scriptEditorInfo(e=True, suppressInfo=True, suppressWarnings=True, suppressResults=True)
            state["script_editor"] = True
        except Exception:
            state["script_editor"] = None
        try:
            cmds.refresh(suspend=True)  # congela el viewport durante el build
            state["refresh"] = True
        except Exception:
            state["refresh"] = None
        return state

    def _end_fast_session(self, state):

        """Restaura el estado guardado por _begin_fast_session (siempre, en finally)."""
        if not state:
            return
        if state.get("refresh"):
            try:
                cmds.refresh(suspend=False)
            except Exception:
                pass
        if state.get("script_editor"):
            try:
                cmds.scriptEditorInfo(e=True, suppressInfo=False, suppressWarnings=False, suppressResults=False)
            except Exception:
                pass
        if state.get("undo") is not None:
            try:
                cmds.undoInfo(stateWithoutFlush=state["undo"])
            except Exception:
                pass
        if state.get("cycle_check") is not None:
            try:
                cmds.cycleCheck(e=True, evaluation=state["cycle_check"])
            except Exception:
                pass
        if state.get("eval_mode"):
            try:
                cmds.evaluationManager(mode=state["eval_mode"])
            except Exception:
                pass
        try:
            cmds.refresh(force=True)  # un único redibujado al final
        except Exception:
            pass

    def basic_structure(self):

        """
        Create the basic structure for the rig, including character, rig, controls, meshes, and deformers groups.
        """

        basic_structure.create_basic_structure()

    def make_rig(self, on_step=None, leg_impl="self"):

        """
        Create the rig for the character, including joints, skinning, and control curves.
        """

        char_name = rig_manager.get_character_name_from_build()
        rig_manager.build_rig(char_name, on_step=on_step, leg_impl=leg_impl)

        cmds.inViewMessage(
        amg=f'Completed <hl>{char_name.upper()} RIG</hl> build.',
        pos='midCenter',
        fade=True,
        alpha=0.8)
    

    def label_joints(self):

        """
        Label all the joints in the rig with appropriate names.
        """
        
        # El lado sale del PREFIJO, no de buscar la letra dentro del nombre: con
        # `"C" in jnt` cualquier joint con una C en el cuerpo (Carpus, Chest...) se
        # etiquetaba como central, y al ser tres `if` sin `elif` ganaba el último
        # que coincidiera. Los joints sin prefijo se saltan: `split("_")[1]` reventaba
        # con cualquier nombre sin guion bajo.
        side_ids = {"L": 1, "R": 2, "C": 0}

        for jnt in cmds.ls(type="joint"):
            parts = jnt.split("|")[-1].split("_")
            if len(parts) < 2:
                continue
            side = side_ids.get(parts[0])
            if side is None:
                continue
            cmds.setAttr(f"{jnt}.side", side)
            cmds.setAttr(f"{jnt}.type", 18)
            cmds.setAttr(f"{jnt}.otherType", parts[1], type="string")


    def delete_unused_nodes(self):

        """
        Delete unused nodes in the scene to clean up the workspace.
        """

        all_nodes = cmds.ls(ap=True)

        unused_nodes = []

        for node in all_nodes:
            connections = cmds.listConnections(node, source=True, destination=True)
            if not connections:
                unused_nodes.append(node)
        
        if unused_nodes:

            cmds.delete(unused_nodes)
            
    
    def hide_connections(self):

        """
        Hides utility/math nodes from the Node Editor by setting
        isHistoricallyInteresting=0. Only targets computational nodes —
        joints, transforms, shapes and deformers are left untouched.
        """

        UTILITY_TYPES = {
            "multMatrix", "decomposeMatrix", "composeMatrix", "blendMatrix",
            "wtAddMatrix", "pickMatrix", "fourByFourMatrix", "rowFromMatrix",
            "condition", "reverse", "clamp", "remapValue", "blendTwoAttr",
            "addDoubleLinear", "multDoubleLinear", "multiplyDivide",
            "plusMinusAverage", "blendColors", "pairBlend",
            "floatMath", "floatConstant", "floatLogic", "floatCorrect",
            "pointMatrixMult", "vectorProduct", "angleBetween",
            "distanceBetween", "curveInfo", "motionPath",
            "parentMatrix", "animBlendNodeBase",
        }

        registered = set(cmds.allNodeTypes() or [])
        for node_type in UTILITY_TYPES:
            if node_type not in registered:
                continue
            for node in cmds.ls(type=node_type) or []:
                try:
                    cmds.setAttr(f"{node}.isHistoricallyInteresting", 0)
                except Exception:
                    pass

    def hide_all_utility_nodes(self):
        """
        Set isHistoricallyInteresting=0 on every non-essential DG node so they
        don't appear in the Channel Box history or Node Editor clutter.
        Essential nodes — transforms, joints, shapes, deformers, constraints,
        ik, animation curves, sets, layers — are untouched.
        Nothing is deleted.
        """
        KEEP_TYPES = frozenset({
            # DAG / hierarchy
            "transform", "joint",
            "mesh", "nurbsCurve", "nurbsSurface", "subdiv",
            "locator", "camera", "imagePlane",
            "directionalLight", "pointLight", "spotLight", "areaLight", "volumeLight",
            "lattice", "baseLattice", "clusterHandle",
            # Deformers
            "skinCluster", "tweak", "groupParts", "groupId",
            "blendShape", "cluster", "wire", "jiggle",
            "deltaMush", "tension", "proximityWrap", "shrinkWrap",
            "nonLinear", "softMod",
            # Rigging
            "ikHandle", "ikEffector",
            "follicle", "hairSystem", "nRigid", "nCloth",
            # Constraints
            "parentConstraint", "pointConstraint", "orientConstraint",
            "aimConstraint", "scaleConstraint", "geometryConstraint",
            "normalConstraint", "tangentConstraint", "poleVectorConstraint",
            # Sets / layers / scene management
            "objectSet", "displayLayer", "renderLayer",
            "shadingEngine", "partition", "character",
            "layerManager", "displayLayerManager", "renderLayerManager",
            "lightLinker", "renderPartition",
            "defaultShaderList", "defaultRenderingList", "defaultRenderGlobals",
            "defaultTextureList", "renderSetup",
            # Animation
            "animCurveTL", "animCurveTA", "animCurveTT", "animCurveTU",
            "animCurveUL", "animCurveUA", "animCurveUT", "animCurveUU",
            # Scene internals
            "time", "hyperGraphInfo", "hyperView",
            "selectionListOperator", "unknown", "unknownDag",
        })

        for node in cmds.ls(dependencyNodes=True, long=False) or []:
            try:
                if cmds.nodeType(node) in KEEP_TYPES:
                    continue
                if not cmds.attributeQuery("isHistoricallyInteresting", node=node, exists=True):
                    continue
                cmds.setAttr(f"{node}.isHistoricallyInteresting", 0)
            except Exception:
                pass

    def inherit_transforms(self):

        """
        Set the inherit transforms for the rig controls to ensure proper movement and rotation.
        """

        curves = cmds.ls("*CRV")

        for crv in curves:
           if "Shape" in crv:
               continue
           else:
               try:
                   cmds.setAttr(crv + ".inheritsTransform", 0)
               except Exception as e:
                   om.MGlobal.displayError(f"Error setting inherit transforms for {crv}: {e}")


    def import_corrective_blendshapes(self):
        """Import pre-deformation corrective blendShapes after the rig is built."""
        reload(corrective_blendshape_manager)
        corrective_blendshape_manager.CorrectiveBlendshapeManager().import_from()

    def import_weights(self):
        """
        Import skin weights for the rig after creation.

        Priority
        --------
        1. Direct .skc import for THIS character (existing behaviour).
        2. Auto skin transfer from the 'source' character if .skinmap files
           are found and this character has no direct weights yet.
        """
        skinner = skin_manager_api.SkinManager()
        skinner.import_skins()

        # self._auto_transfer_from_source()

    def apply_delta_mush(self):
        """
        Capa de deltaMush DESPUÉS de los skinClusters en toda malla skineada (patrón
        del rig de kessi): settings default de Maya (smoothingIterations=10,
        smoothingStep=0.5, pinBorderVertices=1, sin overrides) y el `.scale` conectado
        al masterwalk para que no se rompa al escalar el rig. Deja el rig más fino.
        """
        mw = data_manager.DataExportBiped().get_data("basic_structure", "masterwalk_ctl")
        dcm = None
        for skc in cmds.ls(type="skinCluster") or []:
            for mesh_shape in cmds.deformer(skc, q=True, geometry=True) or []:
                if cmds.nodeType(mesh_shape) != "mesh":
                    continue  # solo geo de render; las curvas/NURBS son mecánica del rig
                mesh = (cmds.listRelatives(mesh_shape, parent=True, fullPath=True) or [mesh_shape])[0]
                short = mesh.split("|")[-1]
                if not any(w in short.lower() for w in ("body", "skin")):
                    continue  # solo el body/skin (como capa principal de kessi; freya usa "skin")
                if cmds.objExists(f"{short}_DMH"):
                    continue  # una capa por malla (aunque tenga 2 skc apilados)
                try:
                    dm = cmds.deltaMush(mesh, name=f"{short}_DMH",
                                        smoothingIterations=10, smoothingStep=0.5,
                                        pinBorderVertices=True)[0]
                except Exception as e:
                    om.MGlobal.displayWarning(f"[DeltaMush] '{short}': {e}")
                    continue
                # scale del rig -> mush (como kessi: decomposeMatrix del main -> .scale)
                if mw and cmds.objExists(mw) and cmds.attributeQuery("scale", node=dm, exists=True):
                    if dcm is None:
                        dcm = cmds.createNode("decomposeMatrix", name="C_deltaMushScale_DCM", ss=True)
                        cmds.connectAttr(f"{mw}.worldMatrix[0]", f"{dcm}.inputMatrix")
                    cmds.connectAttr(f"{dcm}.outputScale", f"{dm}.scale")
                om.MGlobal.displayInfo(f"[DeltaMush] '{short}' -> {dm}")

    def localize_correctives(self):
        """
        Hace LOCALES los skinClusters de correctivas para que NO se rompan al mover el
        rig global (masterwalk). Soluciona la doble transformación de apilar dos
        skinClusters (body + correctivas): conecta el bindPreMatrix de cada influencia
        a la worldInverseMatrix de su hueso padre, así su contribución es identidad en
        reposo y solo aplica el delta local del push.

        Se ejecuta en pose neutra (justo tras importar pesos) y detecta automáticamente
        cualquier skinCluster cuyo nombre contenga 'corrective' (p.ej. C_corrective_SKC).
        """
        from maya_tools.scripts.utils import correctives
        reload(correctives)
        skins = [s for s in (cmds.ls(type="skinCluster") or []) if "corrective" in s.lower()]
        if not skins:
            return
        for s in skins:
            try:
                done = correctives.localize_corrective_skin(s)
                om.MGlobal.displayInfo(f"[Correctives] Skin '{s}' localizado ({len(done)} influencias).")
            except Exception as e:
                om.MGlobal.displayWarning(f"[Correctives] No se pudo localizar '{s}': {e}")

    
    def proxy_locator(self):
        """Assign proxy locators to the rig controls based on the character's geometry."""
        proxy_locator.assign_all_proxy_locators(mesh_transform=None, ctl_suffix="_CTL", radius=10.0)

    def _auto_transfer_from_source(self, source_char="source"):
        """
        Checks whether pre-computed .skinmap files exist for the source
        character and, if so, transfers skinning to every mesh in the scene
        that does not yet have a skinCluster.

        The source character never needs to be loaded — all data comes from
        the .skinmap files produced by SourceSkinExporter.export_all().
        """
        skinmaps = mesh_data_exporter.SourceSkinExporter.find_skinmaps_for_char(source_char)
        if not skinmaps:
            om.MGlobal.displayInfo(
                f"AutoRig: no .skinmap files found for '{source_char}' — skipping auto transfer."
            )
            return

        # Collect meshes in scene that still have no skin
        unskinned = self._get_unskinned_meshes()
        if not unskinned:
            om.MGlobal.displayInfo("AutoRig: all meshes already have skin weights.")
            return

        char_name  = data_manager.DataExportBiped().get_data("basic_structure", "character_name") or ""
        skc_path   = mesh_data_exporter.SourceSkinExporter.find_skc_for_char(source_char)
        sys        = auto_skin_transfer.AutoSkinTransferSystem()

        om.MGlobal.displayInfo(
            f"AutoRig: transferring skin from '{source_char}' to "
            f"{len(unskinned)} mesh(es) via .skinmap…"
        )

        transferred = 0
        for target_mesh in unskinned:
            # Match target mesh to a source .skinmap by normalised name
            skinmap_path = self._match_skinmap(target_mesh, skinmaps, char_name)
            if not skinmap_path:
                om.MGlobal.displayWarning(
                    f"  AutoRig: no .skinmap match for '{target_mesh}', skipping."
                )
                continue

            om.MGlobal.displayInfo(f"  Transferring → '{target_mesh}'")
            try:
                result = sys.transfer(
                    source_mesh     = target_mesh,   # UV projection runs on target only
                    target_mesh     = target_mesh,   # same mesh; weights come from map
                    skin_map_path   = skinmap_path,  # pre-computed source UV weight map
                    source_skc_path = skc_path,      # for influence list if needed
                    uv_method       = "skeleton",
                    joint_strategy  = "auto",
                    smooth_iter     = 3,
                    max_infs        = 4,
                    boost_critical  = True,
                    cleanup_uvs     = True,
                )
                if result:
                    transferred += 1
            except Exception as e:
                om.MGlobal.displayWarning(f"  AutoRig: transfer failed for '{target_mesh}': {e}")

        if transferred:
            cmds.inViewMessage(
                amg=f"Auto Skin Transfer: <hl>{transferred}</hl> mesh(es) weighted from source.",
                pos="midCenter", fade=True, alpha=0.9
            )

    def _get_unskinned_meshes(self):
        """Returns transform names of meshes in the scene with no skinCluster."""
        unskinned = []
        for shape in cmds.ls(type="mesh"):
            if cmds.getAttr(f"{shape}.intermediateObject"):
                continue
            hist = cmds.listHistory(shape, pruneDagObjects=True, interestLevel=1) or []
            if not any(cmds.nodeType(n) == "skinCluster" for n in hist):
                parent = cmds.listRelatives(shape, parent=True, fullPath=True)
                if parent:
                    unskinned.append(parent[0])
        return unskinned

    @staticmethod
    def _match_skinmap(target_mesh, skinmaps, char_name):
        """
        Finds the best .skinmap for target_mesh.

        Strategy
        --------
        1. Exact short name match.
        2. Strip character prefix/suffix and match remainder.
        3. Single-skinmap fallback (if source has only one mesh).
        """
        short = target_mesh.split("|")[-1].split(":")[-1]

        # 1. exact
        if short in skinmaps:
            return skinmaps[short]

        # 2. strip char name prefix / suffix from target, then match
        normalised = short
        for token in (char_name, "_GEO", "_geo", "_Mesh", "_mesh", "_Body", "_body"):
            normalised = normalised.replace(token, "")
        normalised = normalised.strip("_")

        for src_name, path in skinmaps.items():
            src_norm = src_name
            for token in ("source", "_GEO", "_geo", "_Mesh", "_mesh", "_Body", "_body"):
                src_norm = src_norm.replace(token, "")
            src_norm = src_norm.strip("_")
            if normalised and src_norm and (
                normalised.lower() == src_norm.lower() or
                normalised.lower() in src_norm.lower() or
                src_norm.lower() in normalised.lower()
            ):
                return path

        # 3. single skinmap fallback
        if len(skinmaps) == 1:
            return next(iter(skinmaps.values()))

        return None
    


    
    


