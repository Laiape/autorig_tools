import maya.cmds as cmds
import maya.api.OpenMaya as om
import maya.api.OpenMayaAnim as oma
import os
import json

# --- DEPENDENCIAS ---
try:
    from utils import data_manager
    HAS_RIG_UTILS = True
except ImportError:
    HAS_RIG_UTILS = False

class SkinManager(object):
    def __init__(self):
        self.geo_root = "geo_GRP" or "geo"
        self.local_group = "LOCAL" 
        self.folder_path, self.asset_name = self.get_path_and_name()
        self.json_path = os.path.join(self.folder_path, f"{self.asset_name}.json")

    def get_path_and_name(self):
        """Calcula la ruta del JSON basándose en la estructura del proyecto."""
        # Intento obtener la ruta del script, si falla (Script Editor), uso el directorio actual de Maya
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
            # Usamos el último objeto que no sea una cámara (normalmente el grupo del asset)
            char_name = scene_assemblies[-1]
            print(f"  [INFO] Nombre detectado (excluyendo cámaras): '{char_name}'")
        
        # Intentar sobreescribir con Data Manager si existe
        if HAS_RIG_UTILS:
            try:
                dm_name = data_manager.DataExportBiped().get_data("basic_structure", "character_name")
                if dm_name:
                    char_name = dm_name
                    print(f"  [INFO] Nombre obtenido desde Data Manager: '{char_name}'")
            except Exception as e:
                print(f"  [WARN] Fallo al consultar Data Manager: {e}")

        # Validar que root_github no sea None antes del join
        if not root_github:
            root_github = "C:/GIT/autorig_tools"  # Valor por defecto si no se puede determinar

        path = os.path.join(root_github, "autorig_tools", "assets", char_name, "skin_clusters")
        return os.path.normpath(path), char_name

    def find_mesh_in_scene(self, name):
        """Busca la malla por nombre exacto o nombre corto."""
        if cmds.objExists(name): return name
        matches = cmds.ls(f"*{name}", type="transform")
        for m in matches:
            if m.endswith(f"|{name}") or m.endswith(f":{name}"): return m
        return matches[0] if matches else None

    def ensure_local_group(self):
        if not cmds.objExists(self.local_group):
            return cmds.group(em=True, name=self.local_group)
        return self.local_group

    def get_dag_path(self, node_name):
        sel = om.MSelectionList()
        try:
            sel.add(node_name)
            return sel.getDagPath(0)
        except:
            return None
    # ----------------------------------------------------------------
    # --- IMPORT SKINS ---
    # ----------------------------------------------------------------
    def import_skins(self):
        """
        Importa los skins utilizando OpenMaya y conecta la Daisy Chain al final.
        """
        if not os.path.exists(self.json_path):
            om.MGlobal.displayError(f"Archivo JSON no encontrado: {self.json_path}")
            return

        print(f"\n# --- IMPORTANDO SKIN CLUSTERS: {self.asset_name} ---")

        with open(self.json_path, 'r') as f:
            data = json.load(f)

        # Separamos las llaves para procesar primero las base y luego las locales
        all_keys = list(data.keys())
        base_keys = [k for k in all_keys if "_local" not in k]
        local_keys = sorted([k for k in all_keys if "_local" in k])
        sorted_keys = base_keys + local_keys

        for mesh_name in sorted_keys:
            skin_data = data.get(mesh_name)
            
            # 1. Buscar o crear el target (incluyendo lógica de duplicados locales)
            target = self.find_mesh_in_scene(mesh_name)
            
            if not target and "_local" in mesh_name:
                source_base_name = mesh_name.split("_local")[0]
                base_mesh = self.find_mesh_in_scene(source_base_name)
                if base_mesh:
                    local_parent = self.ensure_local_group()
                    target = cmds.duplicate(base_mesh, name=mesh_name)[0]
                    try: cmds.parent(target, local_parent)
                    except: pass
                    cmds.delete(target, ch=True)
                    print(f"  [CREATED LOCAL] {target}")

            if not target:
                continue

            # 2. Obtener MDagPath y Shape para OpenMaya
            mesh_path = self.get_dag_path(target)
            mesh_path.extendToShape()
            mf_mesh = om.MFnMesh(mesh_path)
            num_verts = mf_mesh.numVertices
            
            # 3. Gestión de SkinCluster e Influencias
            json_influences = skin_data["influences"]
            history = cmds.listHistory(target, pruneDagObjects=True) or []
            sc_nodes = cmds.ls(history, type="skinCluster")
            
            mf_skin = None
            if sc_nodes:
                sc_name = sc_nodes[0]
                sel_s = om.MSelectionList()
                sel_s.add(sc_name)
                mf_skin = oma.MFnSkinCluster(sel_s.getDependNode(0))
                # Add missing influences
                scene_infs = [p.partialPathName() for p in mf_skin.influenceObjects()]
                missing = [inf for inf in json_influences if inf not in scene_infs and cmds.objExists(inf)]
                if missing:
                    cmds.skinCluster(sc_name, e=True, ai=missing, wt=0.0)
            else:
                valid_joints = [j for j in json_influences if cmds.objExists(j)]
                if not valid_joints: continue
                sc_name = cmds.skinCluster(valid_joints, target, tsb=True, n=f"{target}_SC")[0]
                sel_s = om.MSelectionList()
                sel_s.add(sc_name)
                mf_skin = oma.MFnSkinCluster(sel_s.getDependNode(0))

            # 4. Aplicar Pesos
            scene_inf_paths = mf_skin.influenceObjects()
            scene_inf_map = {p.partialPathName(): i for i, p in enumerate(scene_inf_paths)}
            num_scene_infs = len(scene_inf_paths)

            full_weight_list = [0.0] * (num_verts * num_scene_infs)
            
            # Soporte para formato "weights" plano o "sparse_weights"
            if "weights" in skin_data:
                # Si el conteo de influencias coincide, usamos directo, si no, mapeamos
                json_weights = skin_data["weights"]
                num_json_infs = len(json_influences)
                for v_idx in range(num_verts):
                    for j_idx, j_name in enumerate(json_influences):
                        if j_name in scene_inf_map:
                            val = json_weights[(v_idx * num_json_infs) + j_idx]
                            full_weight_list[(v_idx * num_scene_infs) + scene_inf_map[j_name]] = val
            
            # Aplicar vía OpenMaya
            m_influence_indices = om.MIntArray(range(num_scene_infs))
            final_weights = om.MDoubleArray(full_weight_list)
            single_comp = om.MFnSingleIndexedComponent()
            vertex_comp = single_comp.create(om.MFn.kMeshVertComponent)
            single_comp.setCompleteData(num_verts)

            prev_norm = cmds.getAttr(f"{sc_name}.normalizeWeights")
            cmds.setAttr(f"{sc_name}.normalizeWeights", 0)
            try:
                mf_skin.setWeights(mesh_path, vertex_comp, m_influence_indices, final_weights, False)
            finally:
                cmds.setAttr(f"{sc_name}.normalizeWeights", prev_norm)

        # --- AQUÍ SE AÑADE EL DAISY CHAIN ---
        print("# --- CONECTANDO JERARQUÍAS DAISY CHAIN ---")
        self.process_daisy_chains(local_keys)
        
        print("# --- IMPORTACIÓN Y CONEXIÓN COMPLETADA ---")

    def force_skin_cluster_from_data(self, mesh, data_dict):
        influences_names = data_dict.get('influences', [])
        joints = []
        for j_name in influences_names:
            clean_j_name = j_name.split("|")[-1].split(":")[-1]
            found = cmds.ls(f"*{clean_j_name}", type="joint")
            
            exact = [j for j in found if j.endswith(f"|{clean_j_name}") or j.endswith(f":{clean_j_name}")]
            
            if exact: joints.append(exact[0])
            elif found: joints.append(found[0])
        
        if not joints: 
            return False
        
        history = cmds.listHistory(mesh, pruneDagObjects=True) or []
        existing = cmds.ls(history, type="skinCluster")
        
        if not existing:
            try:
                cmds.skinCluster(joints, mesh, tsb=True, name=f"{mesh}_SC")
                return True
            except Exception as e:
                print(f"Error creando SC en {mesh}: {e}")
                return False
        else:
            sc = existing[0]
            current_infs = cmds.skinCluster(sc, q=True, inf=True) or []
            new_j = [j for j in joints if j not in current_infs]
            if new_j: 
                cmds.skinCluster(sc, e=True, ai=new_j, lw=True, wt=0)
        return True

    # ----------------------------------------------------------------
    # --- EXPORT SKINS (NATIVE) ---
    # ----------------------------------------------------------------
    def export_skins(self):
        if not os.path.exists(self.folder_path):
            os.makedirs(self.folder_path)

        print(f"\n# --- INICIANDO EXPORTACIÓN NATIVA: {self.asset_name} ---")

        target_meshes = []
        geo_groups = [t for t in cmds.ls(type="transform") if t.lower().endswith("geo_grp")]
        
        for grp in geo_groups:
            relatives = cmds.listRelatives(grp, ad=True, type="mesh", f=True) or []
            for m in relatives:
                p = cmds.listRelatives(m, p=True, f=True)[0]
                if p not in target_meshes: target_meshes.append(p)

        master_data = {}

        for mesh in target_meshes:
            history = cmds.listHistory(mesh, pruneDagObjects=True) or []
            sc_list = cmds.ls(history, type="skinCluster")
            if not sc_list: continue
            
            sc_name = sc_list[0]
            clean_name = mesh.split("|")[-1].split(":")[-1]

            try:
                sel = om.MSelectionList()
                sel.add(sc_name)
                sc_node = sel.getDependNode(0)
                fn_sc = oma.MFnSkinCluster(sc_node)

                mesh_path = fn_sc.getPathAtIndex(0)
                fn_mesh = om.MFnMesh(mesh_path)
                num_verts = fn_mesh.numVertices
                
                fn_comp = om.MFnSingleIndexedComponent()
                vtx_comp = fn_comp.create(om.MFn.kMeshVertComponent)
                fn_comp.setCompleteData(num_verts)

                infl_paths = fn_sc.influenceObjects()
                infl_names = [p.partialPathName() for p in infl_paths]

                weights_marray, num_infs_util = fn_sc.getWeights(mesh_path, vtx_comp)
                
                weights_list = [round(w, 5) for w in list(weights_marray)]

                master_data[clean_name] = {
                    "influences": infl_names,
                    "weights": weights_list,
                    "vertex_count": num_verts
                }
                print(f"  [EXPORTED] {clean_name}")

            except Exception as e:
                cmds.warning(f"Error exportando {clean_name}: {e}")

        if master_data:
            with open(self.json_path, 'w') as f:
                json.dump(master_data, f)
            print(f"# --- EXPORTACIÓN COMPLETADA: {self.json_path} ---")

    def process_daisy_chains(self, local_keys):
        hierarchy_map = {}
        for l_key in local_keys:
            base_name = l_key.split("_localq")[0]
            if base_name not in hierarchy_map: hierarchy_map[base_name] = []
            hierarchy_map[base_name].append(l_key)

        for base_name, locals_list in hierarchy_map.items():
            main_mesh = self.find_mesh_in_scene(base_name)
            if main_mesh:
                self.connect_daisy_chain_nodes(main_mesh, locals_list)

    def connect_daisy_chain_nodes(self, main_mesh, local_keys):
        shapes = cmds.listRelatives(main_mesh, s=True, f=True)
        if not shapes: return
        final_shape = shapes[0]

        # Obtener el SkinCluster del Main
        hist = cmds.listHistory(main_mesh, pruneDagObjects=True)
        main_sc = cmds.ls(hist, type="skinCluster")
        if not main_sc: return
        main_sc_node = main_sc[0]

        # 1. Primero agregamos los Locales a la cadena
        chain = []
        for local_name in local_keys:
            l_mesh = self.find_mesh_in_scene(local_name)
            if l_mesh:
                l_hist = cmds.listHistory(l_mesh, pruneDagObjects=True)
                l_sc = cmds.ls(l_hist, type="skinCluster")
                if l_sc: chain.append(l_sc[0])

        # 2. Y el Main va AL FINAL
        chain.append(main_sc_node)
        # ---------------------------------------------

        # Si solo tenemos el Main (sin locales válidos), aseguramos que esté conectado al shape y salimos
        if len(chain) < 2: 
            # Opcional: asegurar conexión Main -> Shape si se rompió antes
            last_output = f"{chain[-1]}.outputGeometry[0]"
            if not cmds.isConnected(last_output, f"{final_shape}.inMesh"):
                cmds.connectAttr(last_output, f"{final_shape}.inMesh", force=True)
            return

        # Conectar en serie: Local 1 -> Local 2 -> ... -> Main
        print(f"  [CHAIN ORDER] {' -> '.join(chain)}") # Debug visual
        
        for i in range(len(chain) - 1):
            src = f"{chain[i]}.outputGeometry[0]"
            dst = f"{chain[i+1]}.input[0].inputGeometry"
            
            # Verificación de seguridad para no reconectar lo mismo
            if not cmds.isConnected(src, dst):
                try:
                    cmds.connectAttr(src, dst, force=True)
                except Exception as e:
                    print(f"  [ERROR LINK] {src} -> {dst}: {e}")
        
        # Conectar el ÚLTIMO elemento (que ahora es el Main) al Shape visible
        last_output = f"{chain[-1]}.outputGeometry[0]"
        if not cmds.isConnected(last_output, f"{final_shape}.inMesh"):
            cmds.connectAttr(last_output, f"{final_shape}.inMesh", force=True)
            print(f"  [FINAL LINK] {chain[-1]} -> {final_shape}")