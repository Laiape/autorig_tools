import maya.cmds as cmds
import maya.api.OpenMaya as om
import os
import json
import sys
from importlib import reload

# --- DEPENDENCIAS ---
try:
    from biped.utils import data_manager
    HAS_RIG_UTILS = True
except ImportError:
    HAS_RIG_UTILS = False

try:
    from ngSkinTools2 import api as ngst_api
    from ngSkinTools2.api import InfluenceMappingConfig, VertexTransferMode
    NG_AVAILABLE = True
except ImportError:
    NG_AVAILABLE = False
    cmds.warning("ngSkinTools2 API no encontrada.")

class SkinManager(object):
    def __init__(self):
        self.geo_root = "geo_GRP"
        self.local_group = "LOCAL" # Nombre del transform/grupo para los locales
        self.folder_path, self.asset_name = self.get_path_and_name()
        self.json_path = os.path.join(self.folder_path, f"{self.asset_name}.json")

    def get_path_and_name(self):
        """Calcula la ruta del JSON basándose en la estructura del proyecto."""
        script_path = os.path.realpath(__file__)
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

    def import_skins(self):
        """Función principal de importación de pesos."""
        if not NG_AVAILABLE:
            cmds.error("ngSkinTools2 no está instalado.")
            return
        
        if not os.path.exists(self.json_path):
            cmds.warning(f"Archivo JSON no encontrado: {self.json_path}")
            return

        print(f"\n# --- INICIANDO IMPORTACIÓN: {self.asset_name} ---")

        with open(self.json_path, 'r') as f:
            master_data = json.load(f)

        all_keys = list(master_data.keys())
        base_keys = [k for k in all_keys if "_local" not in k]
        local_keys = sorted([k for k in all_keys if "_local" in k])
        sorted_keys = base_keys + local_keys

        config = InfluenceMappingConfig.transfer_defaults()
        config.use_name_matching = True

        for mesh_name in sorted_keys:
            mesh_data = master_data.get(mesh_name)
            if not mesh_data: continue

            target = self.find_mesh_in_scene(mesh_name)

            # NUEVA LÓGICA: Crear locales dentro del transform "LOCAL"
            if not target and "_local" in mesh_name:
                source_base_name = mesh_name.split("_local")[0]
                base_mesh = self.find_mesh_in_scene(source_base_name)
                
                if base_mesh:
                    local_parent = self.ensure_local_group()
                    # Duplicamos la malla base
                    target = cmds.duplicate(base_mesh, name=mesh_name)[0]
                    # Limpiamos historial y emparentamos al grupo LOCAL
                    cmds.delete(target, ch=True)
                    target = cmds.parent(target, local_parent)[0]
                    print(f"  [CREATED LOCAL] {target} emparentado a {local_parent}")

            if target:
                if self.force_skin_cluster_from_data(target, mesh_data):
                    try:
                        # Usamos 'data=' para pasar el dict directamente y evitar errores internos
                        ngst_api.import_json(
                            target, 
                            data=mesh_data, 
                            vertex_transfer_mode=VertexTransferMode.vertexId,
                            influences_mapping_config=config
                        )
                        print(f"  [OK] Pesos aplicados: {target}")
                    except Exception as e:
                        print(f"  [NG ERROR] {target}: {e}")

        self.process_daisy_chains(local_keys)

    def force_skin_cluster_from_data(self, mesh, data_dict):
        """Asegura skinCluster e influencias necesarias."""
        influences = data_dict.get('influences', [])
        if not influences:
            influences = data_dict.get('ngSkinToolsData', {}).get('influences', [])

        joints = []
        for inf in influences:
            path = inf.get('path', inf.get('name', ''))
            j_name = path.split("|")[-1].split(":")[-1]
            found = cmds.ls(f"*{j_name}", type="joint")
            if found: joints.append(found[0])
        
        if not joints: return False
        
        history = cmds.listHistory(mesh, pruneDagObjects=True) or []
        existing = cmds.ls(history, type="skinCluster")
        
        if not existing:
            try:
                cmds.skinCluster(joints, mesh, tsb=True, name=f"{mesh}_SC")
            except: return False
        else:
            sc = existing[0]
            current = cmds.skinCluster(sc, q=True, inf=True) or []
            new_j = [j for j in joints if j not in current]
            if new_j: cmds.skinCluster(sc, e=True, ai=new_j, lw=True, wt=0)
        return True

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

    def force_skin_cluster_from_data(self, mesh, data_dict):
        # Extraer joints del JSON
        joints = []
        for inf in data_dict.get('influences', []):
            # Obtener nombre limpio del joint
            path = inf.get('path', inf.get('name', '')) # ngSkinTools v2 usa 'path', v1 usaba 'name'
            j_name = path.split("|")[-1].split(":")[-1]
            
            found = cmds.ls(f"*{j_name}", type="joint")
            if found: joints.append(found[0])
            
        if not joints: 
            print(f"  [WARNING] No joints encontrados para {mesh}")
            return False
        
        # Crear o actualizar SkinCluster
        history = cmds.listHistory(mesh, pruneDagObjects=True) or []
        existing = cmds.ls(history, type="skinCluster")
        
        if not existing:
            try:
                cmds.skinCluster(joints, mesh, tsb=True, name=f"{mesh}_SC")
            except Exception as e:
                print(f"Error creando SC en {mesh}: {e}")
                return False
        else:
            # Si ya existe, nos aseguramos de que tenga los joints necesarios
            sc = existing[0]
            current = cmds.skinCluster(sc, q=True, inf=True) or []
            new_j = [j for j in joints if j not in current]
            if new_j: 
                cmds.skinCluster(sc, e=True, ai=new_j, lw=True, wt=0)
                
        return True