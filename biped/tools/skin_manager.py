import maya.cmds as cmds
import os
import json
from ngSkinTools2 import api as ngst_api

from biped.utils import data_manager
from importlib import reload
reload(data_manager)

# Check API
try:
    from ngSkinTools2.api import InfluenceMappingConfig, VertexTransferMode
    NG_AVAILABLE = True
except ImportError:
    NG_AVAILABLE = False
    cmds.warning("ngSkinTools2 API not found.")

class SkinManager(object):
    def __init__(self):
        self.skin_folder = self.get_github_production_path()

    def get_github_production_path(self):

        script_path = os.path.realpath(__file__) 
        root_github = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(script_path))))
        character_name = data_manager.DataExportBiped().get_data("basic_structure", "character_name")
        path = os.path.join(root_github, "assets", character_name, "skin_clusters")
        return os.path.normpath(path)

    def import_skins(self):
        """
        Imports skins and then builds the connection chain.
        """
        if not NG_AVAILABLE or not os.path.exists(self.skin_folder):
            print(f"# ERROR: Check path: {self.skin_folder}")
            return

        print(f"\n# --- STARTING IMPORT ---")

        # 1. Configuration (Vertex ID based on your previous request)
        config = InfluenceMappingConfig.transfer_defaults()
        config.use_distance_matching = False 
        config.use_name_matching = True      

        # 2. Sort files (Body first, then Locals)
        all_files = [f for f in os.listdir(self.skin_folder) if f.endswith(".json")]
        base_files = sorted([f for f in all_files if "_local_" not in f])
        local_files = sorted([f for f in all_files if "_local_" in f])
        sorted_files = base_files + local_files

        main_body_mesh = None

        # 3. Import Loop
        for f in sorted_files:
            file_path = os.path.join(self.skin_folder, f)
            export_name = f.replace(".json", "")
            
            # Identify the main body mesh name (the one without _local_)
            if "_local_" not in export_name:
                main_body_mesh = self.find_mesh_in_scene(export_name)

            # Find or Create Target
            target = self.find_mesh_in_scene(export_name)
            if not target and "_local_" in export_name:
                body_name = export_name.split("_local_")[0]
                body_mesh = self.find_mesh_in_scene(body_name)
                
                if body_mesh:
                    target = cmds.duplicate(body_mesh, name=export_name)[0]
                    cmds.delete(target, ch=True)
                else:
                    continue

            # Apply Skin & Import
            if target:
                if self.force_skin_cluster(target, file_path):
                    try:
                        ngst_api.import_json(
                            target, 
                            file=file_path, 
                            vertex_transfer_mode=VertexTransferMode.vertexId,
                            influences_mapping_config=config
                        )
                        self.delete_default_layer(target)
                        print(f"[IMPORT OK] {target}")
                    except Exception as e:
                        print(f"[ERROR] {target}: {e}")

        # 4. BUILD THE STAIRCASE / DAISY CHAIN
        if main_body_mesh:
            print(f"\n# --- BUILDING SKIN CHAIN FOR: {main_body_mesh} ---")
            self.connect_daisy_chain(main_body_mesh, local_files)
        else:
            cmds.warning("Could not identify Main Body Mesh to build the chain.")

    def connect_daisy_chain(self, main_mesh, local_files):
        """
        Crea la conexión en cadena corrigiendo el error de niveles de atributos:
        Output -> Input[0].Geometry
        """
        shapes = cmds.listRelatives(main_mesh, shapes=True, fullPath=True) or []
        if not shapes: return
        final_shape = shapes[0]
        
        main_history = cmds.listHistory(main_mesh, pruneDagObjects=True)
        main_sc = cmds.ls(main_history, type="skinCluster")
        
        if not main_sc:
            cmds.warning(f"No se encontró SkinCluster en {main_mesh}")
            return

        body_sc = main_sc[0]
        
        # 1. Identificar todos los SkinClusters locales
        ordered_sc_chain = [body_sc]
        for f in local_files:
            local_name = f.replace(".json", "")
            l_mesh = self.find_mesh_in_scene(local_name)
            if l_mesh:
                l_history = cmds.listHistory(l_mesh, pruneDagObjects=True)
                l_sc = cmds.ls(l_history, type="skinCluster")
                if l_sc:
                    ordered_sc_chain.append(l_sc[0])

        print(f"# Iniciando cadena para {len(ordered_sc_chain)} nodos.")

        # 2. Conexiones entre Deformadores (La "Escalera")
        # En lugar de .originalGeometry, usamos .input[0].inputGeometry
        for i in range(len(ordered_sc_chain) - 1):
            source_node = ordered_sc_chain[i]
            target_node = ordered_sc_chain[i+1]
            
            source_attr = f"{source_node}.outputGeometry[0]"
            # Esta es la ruta correcta para evitar el error de niveles
            target_attr = f"{target_node}.input[0].inputGeometry"
            
            try:
                cmds.connectAttr(source_attr, target_attr, force=True)
                print(f"  [OK] {source_node} -> {target_node}")
            except Exception as e:
                print(f"  [ERROR] No se pudo conectar {source_node}: {e}")

        # 3. Conexión final a la malla
        last_sc = ordered_sc_chain[-1]
        try:
            cmds.connectAttr(f"{last_sc}.outputGeometry[0]", f"{final_shape}.inMesh", force=True)
            print(f"# --- CADENA FINALIZADA EN {final_shape} ---")
        except Exception as e:
            print(f"  [ERROR FINAL] {e}")

    def find_mesh_in_scene(self, name):
        if cmds.objExists(name): return name
        search = cmds.ls(f"*{name}", type="transform")
        return search[0] if search else None

    def delete_default_layer(self, mesh):
        try:
            layers = ngst_api.list_layers(mesh)
            for layer in layers:
                if layer.name == "Default":
                    ngst_api.delete_layer(mesh, layer.id)
        except:
            pass

    def force_skin_cluster(self, mesh, json_path):
        try:
            with open(json_path, 'r') as f_read:
                data = json.load(f_read)
        except:
            return False

        if not data: return False

        influences_data = data.get('influences', [])
        inf_names = [i.get('path', i.get('name')).split("|")[-1].split(":")[-1] for i in influences_data]
        
        joints_in_scene = []
        for jnt in inf_names:
            found = cmds.ls(f"*{jnt}", type="joint")
            if found:
                joints_in_scene.append(found[0])

        if not joints_in_scene: return False

        history = cmds.listHistory(mesh, pruneDagObjects=True) or []
        existing_sc = cmds.ls(history, type="skinCluster")

        if not existing_sc:
            cmds.skinCluster(joints_in_scene, mesh, tsb=True, name=f"{mesh}_SC")
        else:
            sc_node = existing_sc[0]
            current_inf = cmds.skinCluster(sc_node, q=True, inf=True) or []
            to_add = [j for j in joints_in_scene if j not in current_inf]
            if to_add:
                cmds.skinCluster(sc_node, edit=True, ai=to_add, lw=True, wt=0)
        
        return True
    
    def get_github_production_path(self):
        
        # Ensure this matches your local folder structure for testing
        character_name = data_manager.DataExportBiped().get_data("basic_structure", "character_name")
        script_path = os.path.realpath(__file__) 
        root_github = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(script_path))))
        path = os.path.join(root_github, "assets", character_name, "skin_clusters")
        return os.path.normpath(path)