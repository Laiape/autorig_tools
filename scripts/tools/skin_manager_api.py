import maya.cmds as cmds
import maya.api.OpenMaya as om
import maya.api.OpenMayaAnim as oma
import os
import json

# --- DEPENDENCIAS OPCIONALES ---
try:
    from utils import data_manager
    HAS_RIG_UTILS = True
except ImportError:
    HAS_RIG_UTILS = False

class SkinManager(object):
    def __init__(self):
        # --- Configuración de Rutas (Tu lógica original) ---
        ext = ".skc"
        self.folder_path, self.asset_name = self.get_path_and_name()
        files = [f for f in os.listdir(self.folder_path) if f.endswith(ext)]
        version = 1
        if files:
            files.sort()
            try:
                last = files[-1]
                if "_v" in last:
                    ver_str = last.split("_v")[-1].split(".")[0]
                    version = int(ver_str) + 1
            except: pass
        
        # 3. Construir path final
        asset_name = os.path.basename(self.folder_path)
        self.json_path = os.path.join(self.folder_path, f"{asset_name}_{version:03d}{ext}")

        # --- Configuración de Skin (Lógica de referencia) ---
        self.k_skin_attrs = [
            "skinningMethod",
            "normalizeWeights",
            "maintainMaxInfluences",
            "maxInfluences",
            "weightDistribution"
        ]
        self.tolerance = 1e-5 

    # ----------------------------------------------------------------
    # --- PATH & NAME HELPERS (Original) ---
    # ----------------------------------------------------------------
    def get_path_and_name(self):
        """Calcula la ruta del JSON basándose en la estructura del proyecto."""
        try:
            script_path = os.path.realpath(__file__)
            root_github = script_path
            for _ in range(4):
                root_github = os.path.dirname(root_github)
        except NameError:
            root_github = cmds.workspace(q=True, rd=True) 

        char_name = "asset"
        
        all_assemblies = cmds.ls(assemblies=True)
        scene_assemblies = [
            obj for obj in all_assemblies 
            if not cmds.listRelatives(obj, type='camera')
        ]

        if scene_assemblies:
            char_name = scene_assemblies[-1]
        
        if HAS_RIG_UTILS:
            try:
                dm_name = data_manager.DataExportBiped().get_data("basic_structure", "character_name")
                if dm_name: char_name = dm_name
            except Exception: pass

        if not root_github:
            root_github = "C:/GIT/autorig_tools"

        path = os.path.join(root_github, "autorig_tools", "assets", char_name, "skin_clusters")
        return os.path.normpath(path), char_name

    # ----------------------------------------------------------------
    # --- OPENMAYA HELPERS (Referencia) ---
    # ----------------------------------------------------------------
    def _get_dag_path(self, node_name):
        sel = om.MSelectionList()
        try:
            sel.add(node_name)
            return sel.getDagPath(0)
        except:
            return None

    def _get_skin_clusters(self, dag_path):
        """
        Retorna los skinClusters en orden de deformación (Stack Order).
        Inner (primero en aplicarse) -> Outer (ultimo en aplicarse).
        """
        history = cmds.listHistory(dag_path.fullPathName(), pruneDagObjects=True, interestLevel=1) or []
        skins = [x for x in history if cmds.nodeType(x) == "skinCluster"]
        # listHistory devuelve [Outer... Inner], invertimos para tener [Inner... Outer]
        return list(reversed(skins))

    def _get_meshes_from_skin(self, skin_mobj):
        """
        Encuentra las mallas conectadas a un SkinCluster MObject de forma robusta.
        """
        try:
            fn_skin = oma.MFnSkinCluster(skin_mobj)
            geoms = fn_skin.getOutputGeometry()
            found_paths = []
            
            for i in range(len(geoms)):
                node = geoms[i]
                if node.hasFn(om.MFn.kMesh):
                    fn_dag = om.MFnDagNode(node)
                    if not fn_dag.isIntermediateObject:
                        found_paths.append(fn_dag.getPath())
            return found_paths
        except Exception as e:
            om.MGlobal.displayWarning(f"Error recuperando geometría del skin: {e}")
            return []

    # ----------------------------------------------------------------
    # --- EXPORT SKINS (Lógica Referencia: Sparse & Stack) ---
    # ----------------------------------------------------------------
    def export_skins(self, in_path=None):
        if not os.path.exists(self.folder_path):
            os.makedirs(self.folder_path)
        if in_path:
            self.json_path = os.path.normpath(in_path)
        om.MGlobal.displayInfo(f"--- Exportando Skins a: {self.json_path} ---")
        
        sel = om.MGlobal.getActiveSelectionList()
        meshes_map = {} # Key: FullPath, Value: MDagPath

        # 1. Lógica de Selección (Mesh, Transform o SkinCluster)
        if sel.length() > 0:
            it_sel = om.MItSelectionList(sel)
            while not it_sel.isDone():
                obj = it_sel.getDependNode()
                
                if obj.hasFn(om.MFn.kSkinClusterFilter):
                    paths = self._get_meshes_from_skin(obj)
                    for p in paths: meshes_map[p.fullPathName()] = p
                
                elif obj.hasFn(om.MFn.kMesh):
                    path = it_sel.getDagPath()
                    path.extendToShape()
                    fn_dag = om.MFnDagNode(path)
                    if not fn_dag.isIntermediateObject:
                        meshes_map[path.fullPathName()] = path
                
                elif obj.hasFn(om.MFn.kTransform):
                    try:
                        path = it_sel.getDagPath()
                        path.extendToShape()
                        if path.node().hasFn(om.MFn.kMesh):
                            meshes_map[path.fullPathName()] = path
                    except: pass
                
                it_sel.next()
        else:
            # Si no hay selección, iteramos TODOS los skinClusters de la escena
            om.MGlobal.displayInfo("Sin selección. Escaneando escena completa...")
            it_dep = om.MItDependencyNodes(om.MFn.kSkinClusterFilter)
            while not it_dep.isDone():
                skin_obj = it_dep.thisNode()
                paths = self._get_meshes_from_skin(skin_obj)
                for p in paths: meshes_map[p.fullPathName()] = p
                it_dep.next()

        if not meshes_map:
            om.MGlobal.displayWarning("No se encontraron mallas con skin.")
            return

        # 2. Extracción de Datos
        full_data = {}
        
        for mesh_path in meshes_map.values():
            mesh_name = mesh_path.partialPathName() # Nombre corto para el JSON
            mf_mesh = om.MFnMesh(mesh_path)
            vtx_count = mf_mesh.numVertices
            
            # Obtenemos TODOS los skins en orden para mantener el Stack
            skins = self._get_skin_clusters(mesh_path)
            if not skins: continue

            om.MGlobal.displayInfo(f"Procesando: {mesh_name} | Skins: {len(skins)}")
            
            mesh_skins_data = []
            
            for skin_name in skins:
                sel_skin = om.MSelectionList()
                sel_skin.add(skin_name)
                mf_skin = oma.MFnSkinCluster(sel_skin.getDependNode(0))

                # Atributos
                attrs = {}
                for attr in self.k_skin_attrs:
                    try: attrs[attr] = cmds.getAttr(f"{skin_name}.{attr}")
                    except: pass

                # Influencias
                influences_paths = mf_skin.influenceObjects()
                inf_names = [p.partialPathName() for p in influences_paths]

                # --- Pesos SPARSE (Optimizado) ---
                single_comp = om.MFnSingleIndexedComponent()
                vertex_comp = single_comp.create(om.MFn.kMeshVertComponent)
                single_comp.setCompleteData(vtx_count)
                
                weights_marray, _ = mf_skin.getWeights(mesh_path, vertex_comp)
                flat_weights = list(weights_marray)
                
                sparse_weights = {}
                stride = len(inf_names)
                
                for inf_idx, inf_name in enumerate(inf_names):
                    j_indices = []
                    j_weights = []
                    
                    # Recorrer vértices para esta influencia
                    for v_idx in range(vtx_count):
                        val = flat_weights[v_idx * stride + inf_idx]
                        if val > self.tolerance:
                            j_indices.append(v_idx)
                            j_weights.append(round(val, 5))
                    
                    if j_indices:
                        sparse_weights[inf_name] = {"ix": j_indices, "vw": j_weights}

                # --- Blend Weights (Dual Quaternion) ---
                sparse_blend = {}
                try:
                    blend_weights_marray = mf_skin.getBlendWeights(mesh_path, vertex_comp)
                    flat_blend = list(blend_weights_marray)
                    b_indices = []
                    b_values = []
                    for v_idx, val in enumerate(flat_blend):
                        if val > self.tolerance:
                            b_indices.append(v_idx)
                            b_values.append(round(val, 5))
                    if b_indices:
                        sparse_blend = {"ix": b_indices, "vw": b_values}
                except: pass # Si no soporta blend weights, ignorar
                
                skin_entry = {
                    "name": skin_name,
                    "vertex_count": vtx_count,
                    "attributes": attrs,
                    "influences": inf_names, 
                    "sparse_weights": sparse_weights,
                    "sparse_blend": sparse_blend
                }
                mesh_skins_data.append(skin_entry)

            full_data[mesh_name] = mesh_skins_data

        if path:
            self.json_path = os.path.normpath(path)
        else:            
            self.json_path = os.path.join(self.folder_path, f"{self.asset_name}.json")

        with open(self.json_path, 'w') as f:
            json.dump(full_data, f, separators=(',', ':')) # Separators comprime el JSON
            
        om.MGlobal.displayInfo(f"Export completado: {self.json_path}")

    # ----------------------------------------------------------------
    # --- IMPORT SKINS (Lógica Referencia: Reorder & Sparse) ---
    # ----------------------------------------------------------------
    def import_skins(self):
        if not os.path.exists(self.json_path):
            om.MGlobal.displayError(f"Archivo JSON no encontrado: {self.json_path}")
            return

        om.MGlobal.displayInfo(f"--- Importando Skins de: {self.json_path} ---")

        with open(self.json_path, 'r') as f:
            data = json.load(f)

        for mesh_name, skins_list in data.items():
            # Buscar Mesh en escena
            mesh_path = self._get_dag_path(mesh_name)
            if not mesh_path:
                # Intento de búsqueda laxa si falla el nombre exacto
                found = self.find_mesh_in_scene(mesh_name)
                if found: mesh_path = self._get_dag_path(found)
            
            if not mesh_path:
                om.MGlobal.displayWarning(f"Saltando malla no encontrada: {mesh_name}")
                continue
            
            mesh_path.extendToShape()
            mf_mesh = om.MFnMesh(mesh_path)
            processed_skins = []

            # Limpiar skins previos si se desea una importación limpia (Opcional)
            # current_hist = cmds.listHistory(mesh_path.fullPathName(), pruneDagObjects=True)
            # old_skins = [x for x in current_hist if cmds.nodeType(x) == "skinCluster"]
            # if old_skins: cmds.delete(old_skins)

            for skin_data in skins_list:
                skin_name = skin_data["name"]
                target_vtx_count = skin_data["vertex_count"]
                
                # Validación topología
                if mf_mesh.numVertices != target_vtx_count:
                    om.MGlobal.displayError(f"Topología incorrecta para {skin_name}. Mesh: {mf_mesh.numVertices} vs Data: {target_vtx_count}")
                    continue 

                json_influences = skin_data["influences"]
                
                # Crear o Editar SkinCluster
                skin_exists = cmds.objExists(skin_name) and cmds.nodeType(skin_name) == "skinCluster"
                mf_skin = None
                
                if skin_exists:
                    sel_s = om.MSelectionList()
                    sel_s.add(skin_name)
                    mf_skin = oma.MFnSkinCluster(sel_s.getDependNode(0))
                    scene_infs = [p.partialPathName() for p in mf_skin.influenceObjects()]
                    missing_infs = [inf for inf in json_influences if inf not in scene_infs and cmds.objExists(inf)]
                    if missing_infs:
                        # Bloquear pesos existentes para no destruirlos al añadir huesos
                        cmds.skinCluster(skin_name, e=True, lw=True) 
                        cmds.skinCluster(skin_name, e=True, addInfluence=missing_infs, weight=0.0)
                        cmds.skinCluster(skin_name, e=True, lw=False)
                else:
                    valid_joints = [j for j in json_influences if cmds.objExists(j)]
                    if not valid_joints: 
                        om.MGlobal.displayWarning(f"No hay joints válidos para {skin_name}")
                        continue
                    
                    # IMPORTANTE: multi=True permite stackear deformadores
                    new_skin = cmds.skinCluster(valid_joints, mesh_path.fullPathName(), n=skin_name, toSelectedBones=True, multi=True)[0]
                    sel_s = om.MSelectionList()
                    sel_s.add(new_skin)
                    mf_skin = oma.MFnSkinCluster(sel_s.getDependNode(0))

                # Restaurar Atributos
                for attr, val in skin_data.get("attributes", {}).items():
                    try: cmds.setAttr(f"{skin_name}.{attr}", val)
                    except: pass
                
                # Mapeo de Influencias
                scene_inf_paths = mf_skin.influenceObjects()
                scene_inf_names = [p.partialPathName() for p in scene_inf_paths]
                scene_inf_map = {name: i for i, name in enumerate(scene_inf_names)}

                num_verts = target_vtx_count
                num_scene_infs = len(scene_inf_names)
                full_weight_list = [0.0] * (num_verts * num_scene_infs)
                
                # --- Reconstruir Pesos SPARSE ---
                sparse_data = skin_data.get("sparse_weights", {})
                
                for j_name, data_block in sparse_data.items():
                    if j_name not in scene_inf_map: continue
                    scene_inf_idx = scene_inf_map[j_name]
                    indices = data_block["ix"]
                    values = data_block["vw"]
                    for v_idx, weight_val in zip(indices, values):
                        flat_index = (v_idx * num_scene_infs) + scene_inf_idx
                        full_weight_list[flat_index] = weight_val
                
                # Aplicar Pesos
                m_influence_indices = om.MIntArray(list(range(num_scene_infs)))
                final_weights = om.MDoubleArray(full_weight_list)
                
                single_comp = om.MFnSingleIndexedComponent()
                vertex_comp = single_comp.create(om.MFn.kMeshVertComponent)
                single_comp.setCompleteData(num_verts)
                
                prev_norm = cmds.getAttr(f"{skin_name}.normalizeWeights")
                cmds.setAttr(f"{skin_name}.normalizeWeights", 0) # Desactivar norma para setWeights exacto
                
                try:
                    mf_skin.setWeights(mesh_path, vertex_comp, m_influence_indices, final_weights, False)
                finally:
                    cmds.setAttr(f"{skin_name}.normalizeWeights", prev_norm)

                # Aplicar Blend Weights
                sparse_blend = skin_data.get("sparse_blend", {})
                if sparse_blend:
                    full_blend = [0.0] * num_verts
                    for v_idx, val in zip(sparse_blend["ix"], sparse_blend["vw"]):
                        full_blend[v_idx] = val
                    mf_skin.setBlendWeights(mesh_path, vertex_comp, om.MDoubleArray(full_blend))

                processed_skins.append(skin_name)

            # --- Reordenamiento de Deformers (Stack Order) ---
            # Asegura que el orden visual en Maya coincida con el orden del JSON
            if processed_skins:
                current_hist = cmds.listHistory(mesh_path.fullPathName(), pruneDagObjects=True, interestLevel=1)
                current_skins = [x for x in current_hist if cmds.nodeType(x) == "skinCluster"]
                # listHistory es [Outer, Inner], lo invertimos a [Inner, Outer] para comparar
                current_skins = list(reversed(current_skins))
                
                # Si hay skins en la escena que no estaban en el JSON (raro, pero posible), los ponemos primero
                unknown = [s for s in current_skins if s not in processed_skins]
                desired_order = unknown + processed_skins
                
                # ReorderDeformers espera el orden de aplicación
                for skin in reversed(desired_order):
                    try: cmds.reorderDeformers(skin, mesh_path.fullPathName(), back=True)
                    except: pass
        
        om.MGlobal.displayInfo("Importación completada con éxito.")

    def find_mesh_in_scene(self, name):
        """Helper para fallback de búsqueda."""
        if cmds.objExists(name): return name
        matches = cmds.ls(f"*{name}", type="transform")
        for m in matches:
            if m.endswith(f"|{name}") or m.endswith(f":{name}"): return m
        return matches[0] if matches else None