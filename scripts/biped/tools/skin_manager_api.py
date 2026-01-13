import maya.cmds as cmds
import maya.api.OpenMaya as om
import maya.api.OpenMayaAnim as oma
import os
import json
import sys

# --- DEPENDENCIAS ---
try:
    from biped.utils import data_manager
    HAS_RIG_UTILS = True
except ImportError:
    HAS_RIG_UTILS = False

# Eliminada la comprobación de NG, ya no se usa.

class SkinManager(object):
    def __init__(self):
        self.geo_root = "geo_GRP"
        self.local_group = "LOCAL" 
        self.folder_path, self.asset_name = self.get_path_and_name()
        self.json_path = os.path.join(self.folder_path, f"{self.asset_name}.json")

    def get_path_and_name(self):
        """Calcula la ruta del JSON basándose en la estructura del proyecto."""
        script_path = os.path.realpath(__file__)
        # Ajusta este depth según tu estructura real
        root_github = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(script_path))))
        
        char_name = "asset"
        if HAS_RIG_UTILS:
            try: 
                char_name = data_manager.DataExportBiped().get_data("basic_structure", "character_name")
            except: 
                pass
        
        path = os.path.join(root_github, "assets", char_name, "skin_clusters")
        return os.path.normpath(path), char_name

    def find_mesh_in_scene(self, name):
        """Busca la malla por nombre exacto o nombre corto."""
        if cmds.objExists(name): return name
        matches = cmds.ls(f"*{name}", type="transform")
        for m in matches:
            if m.endswith(f"|{name}") or m.endswith(f":{name}"): return m
        return matches[0] if matches else None

    def ensure_local_group(self):
        """Asegura que exista el grupo 'LOCAL' en la escena."""
        if not cmds.objExists(self.local_group):
            return cmds.group(em=True, name=self.local_group)
        return self.local_group

    # ----------------------------------------------------------------
    # --- IMPORT SKINS (NATIVE) ---
    # ----------------------------------------------------------------
    def import_skins(self):
        """Función principal de importación de pesos (Nativa Maya API)."""
        if not os.path.exists(self.json_path):
            cmds.warning(f"Archivo JSON no encontrado: {self.json_path}")
            return

        print(f"\n# --- INICIANDO IMPORTACIÓN NATIVA: {self.asset_name} ---")

        with open(self.json_path, 'r') as f:
            master_data = json.load(f)

        all_keys = list(master_data.keys())
        base_keys = [k for k in all_keys if "_local" not in k]
        local_keys = sorted([k for k in all_keys if "_local" in k])
        sorted_keys = base_keys + local_keys

        for mesh_name in sorted_keys:
            mesh_data = master_data.get(mesh_name)
            if not mesh_data: continue

            target = self.find_mesh_in_scene(mesh_name)

            # LÓGICA LOCALES (Intacta)
            if not target and "_local" in mesh_name:
                source_base_name = mesh_name.split("_local")[0]
                base_mesh = self.find_mesh_in_scene(source_base_name)
                
                if base_mesh:
                    local_parent = self.ensure_local_group()
                    target = cmds.duplicate(base_mesh, name=mesh_name)[0]
                    try:
                        cmds.parent(target, local_parent)
                    except:
                        pass # Ya podría estar emparentado al duplicar
                    
                    # Es importante borrar el historial para quitar skin clusters previos duplicados
                    cmds.delete(target, ch=True) 
                    print(f"  [CREATED LOCAL] {target} emparentado a {local_parent}")

            if target:
                # 1. Asegurar Joints y SkinCluster
                if self.force_skin_cluster_from_data(target, mesh_data):
                    # 2. Aplicar pesos con OpenMaya
                    try:
                        self.apply_weights_native(target, mesh_data)
                        print(f"  [OK] Pesos aplicados: {target}")
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
                        print(f"  [ERROR] Falló aplicar pesos en {target}: {e}")

        self.process_daisy_chains(local_keys)

    def force_skin_cluster_from_data(self, mesh, data_dict):
        """Asegura skinCluster e influencias necesarias (Adaptado a formato nativo)."""
        # En el nuevo formato, las influencias están bajo la key "influences"
        influences_names = data_dict.get('influences', [])

        joints = []
        for j_name in influences_names:
            # Buscamos el joint en la escena (quitamos namespaces si vienen en el json)
            clean_j_name = j_name.split("|")[-1].split(":")[-1]
            found = cmds.ls(f"*{clean_j_name}", type="joint")
            
            # Priorizamos coincidencia exacta si existe
            exact = [j for j in found if j.endswith(f"|{clean_j_name}") or j.endswith(f":{clean_j_name}")]
            
            if exact:
                joints.append(exact[0])
            elif found:
                joints.append(found[0])
        
        if not joints: 
            print(f"  [WARNING] No se encontraron joints en escena para {mesh}")
            return False
        
        history = cmds.listHistory(mesh, pruneDagObjects=True) or []
        existing = cmds.ls(history, type="skinCluster")
        
        if not existing:
            try:
                # Creamos el SkinCluster con los joints encontrados
                cmds.skinCluster(joints, mesh, tsb=True, name=f"{mesh}_SC")
            except Exception as e:
                print(f"Error creando SC en {mesh}: {e}")
                return False
        else:
            sc = existing[0]
            current_infs = cmds.skinCluster(sc, q=True, inf=True) or []
            
            # Añadir joints faltantes
            # Es vital para que los índices coincidan o se puedan mapear
            new_j = [j for j in joints if j not in current_infs]
            if new_j: 
                cmds.skinCluster(sc, e=True, ai=new_j, lw=True, wt=0)
                
        return True

    def apply_weights_native(self, mesh_name, data_dict):
        """Aplica los pesos usando OpenMaya MFnSkinCluster."""
        
        # 1. Obtener el nodo SkinCluster
        history = cmds.listHistory(mesh_name, pruneDagObjects=True)
        sc_name = cmds.ls(history, type="skinCluster")[0]

        # 2. Preparar objetos OpenMaya
        sel = om.MSelectionList()
        sel.add(sc_name)
        sc_node = sel.getDependNode(0)
        fn_sc = oma.MFnSkinCluster(sc_node)

        # Obtener influencias actuales en el SkinCluster (orden físico)
        infl_paths = fn_sc.influenceObjects()
        scene_influences = [p.partialPathName().split("|")[-1].split(":")[-1] for p in infl_paths]
        num_influences_scene = len(scene_influences)

        # 3. Datos del JSON
        json_influences = [n.split("|")[-1].split(":")[-1] for n in data_dict.get('influences', [])]
        json_weights = data_dict.get('weights', []) # Lista plana [v0_j0, v0_j1, ..., v1_j0...]
        num_influences_json = len(json_influences)
        num_verts = int(len(json_weights) / num_influences_json)

        # 4. Mapa de reordenamiento (JSON Index -> Scene Index)
        # Si el orden de joints en escena es diferente al del JSON, necesitamos remapear los pesos
        remap_indices = []
        for i, j_name in enumerate(json_influences):
            try:
                idx = scene_influences.index(j_name)
                remap_indices.append(idx)
            except ValueError:
                # El joint del JSON no está en el SkinCluster (no debería pasar si corrimos force_skin_cluster)
                remap_indices.append(-1)

        # 5. Construir el array de pesos final
        # MFnSkinCluster.setWeights espera una lista plana que corresponda a TODAS las influencias del SC actual
        final_weights = om.MDoubleArray()
        final_weights.setLength(num_verts * num_influences_scene) # Inicializar en 0.0

        # Rellenar el array
        # Iteramos vértice por vértice
        for v_idx in range(num_verts):
            # Offset en la lista plana del JSON para este vértice
            json_offset = v_idx * num_influences_json
            # Offset en la lista plana final para este vértice
            scene_offset = v_idx * num_influences_scene

            for j_idx in range(num_influences_json):
                weight_val = json_weights[json_offset + j_idx]
                
                if weight_val > 0.0001: # Solo procesamos pesos significativos
                    scene_inf_idx = remap_indices[j_idx]
                    
                    if scene_inf_idx != -1:
                        # Colocamos el peso en la posición correcta del array final
                        final_weights[scene_offset + scene_inf_idx] = weight_val

        # 6. Setear pesos
        # Necesitamos los componentes (todos los vértices)
        mesh_path = fn_sc.getPathAtIndex(0) # Asumimos que la mesh está en el index 0
        vtx_comp = om.MFnSingleIndexedComponent().create(om.MFn.kMeshVerts)
        om.MFnSingleIndexedComponent(vtx_comp).setCompleteData(num_verts)
        
        # Índices de influencia (todos los joints del skinCluster actual)
        inf_indices = om.MIntArray(range(num_influences_scene))

        fn_sc.setWeights(mesh_path, vtx_comp, inf_indices, final_weights)

    # ----------------------------------------------------------------
    # --- EXPORT SKINS (NATIVE) ---
    # ----------------------------------------------------------------
    def export_skins(self):
        """
        Exporta Skins usando OpenMaya a un único JSON limpio.
        Estructura: { "mesh": { "influences": [], "weights": [] } }
        """
        if not os.path.exists(self.folder_path):
            os.makedirs(self.folder_path)

        print(f"\n# --- INICIANDO EXPORTACIÓN NATIVA: {self.asset_name} ---")

        # 1. Recolectar mallas
        target_meshes = []
        geo_groups = [t for t in cmds.ls(type="transform") if t.lower().endswith("geo_grp")]
        if not geo_groups:
            cmds.warning("No se encontró 'geo_GRP'.")
        
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
                # --- EXTRAER DATOS CON OPENMAYA ---
                sel = om.MSelectionList()
                sel.add(sc_name)
                sc_node = sel.getDependNode(0)
                fn_sc = oma.MFnSkinCluster(sc_node)

                # Nombres de Influencias
                infl_paths = fn_sc.influenceObjects()
                infl_names = [p.partialPathName() for p in infl_paths]

                # Pesos (Devuelve MDoubleArray plano: v0_i0, v0_i1... v1_i0...)
                # indexForOutputConnection(0) suele ser la mesh conectada
                weights_marray, num_infs_util = fn_sc.getWeights(fn_sc.getPathAtIndex(0), -1)
                
                # Convertir a lista de Python estándar para JSON
                weights_list = list(weights_marray)
                
                # Optimización simple: redondear float para ahorrar espacio
                weights_list = [round(w, 5) for w in weights_list]

                mesh_data = {
                    "influences": infl_names,
                    "weights": weights_list,
                    "vertex_count": int(len(weights_list) / len(infl_names))
                }

                master_data[clean_name] = mesh_data
                print(f"  [EXPORTED] {clean_name}")

            except Exception as e:
                cmds.warning(f"Error exportando {clean_name}: {e}")

        # Guardar JSON
        if master_data:
            with open(self.json_path, 'w') as f:
                json.dump(master_data, f) # sin indent para ahorrar espacio, o indent=2 para leer
            print(f"# --- EXPORTACIÓN COMPLETADA: {self.json_path} ---")
        else:
            cmds.warning("Nada que exportar.")

    # ----------------------------------------------------------------
    # --- UTILS (DAISY CHAIN) ---
    # ----------------------------------------------------------------
    def process_daisy_chains(self, local_keys):
        """Agrupa locales por malla base y conecta los nodos."""
        hierarchy_map = {}
        for l_key in local_keys:
            base_name = l_key.split("_local")[0]
            if base_name not in hierarchy_map: hierarchy_map[base_name] = []
            hierarchy_map[base_name].append(l_key)

        for base_name, locals_list in hierarchy_map.items():
            main_mesh = self.find_mesh_in_scene(base_name)
            if main_mesh:
                self.connect_daisy_chain_nodes(main_mesh, locals_list)

    def connect_daisy_chain_nodes(self, main_mesh, local_keys):
        """Conecta físicamente los outputGeometry en serie."""
        shapes = cmds.listRelatives(main_mesh, s=True, f=True)
        if not shapes: return
        final_shape = shapes[0]

        hist = cmds.listHistory(main_mesh, pruneDagObjects=True)
        main_sc = cmds.ls(hist, type="skinCluster")
        if not main_sc: return

        chain = [main_sc[0]]
        for local_name in local_keys:
            l_mesh = self.find_mesh_in_scene(local_name)
            if l_mesh:
                l_hist = cmds.listHistory(l_mesh, pruneDagObjects=True)
                l_sc = cmds.ls(l_hist, type="skinCluster")
                if l_sc: chain.append(l_sc[0])

        if len(chain) < 2: return

        print(f"# --- CONECTANDO DAISY CHAIN: {main_mesh} ---")
        
        for i in range(len(chain) - 1):
            src = f"{chain[i]}.outputGeometry[0]"
            dst = f"{chain[i+1]}.input[0].inputGeometry"
            if not cmds.isConnected(src, dst):
                cmds.connectAttr(src, dst, force=True)
        
        last_output = f"{chain[-1]}.outputGeometry[0]"
        if not cmds.isConnected(last_output, f"{final_shape}.inMesh"):
            cmds.connectAttr(last_output, f"{final_shape}.inMesh", force=True)