import maya.cmds as cmds
import os
import re
import json

# Intentamos importar la API de ngSkinTools2
try:
    from ngSkinTools2.api import transfer, plugin
    NG_AVAILABLE = True
except ImportError:
    NG_AVAILABLE = False

class SkinManager(object):
    """
    Clase para gestionar la exportación e importación de SkinClusters.
    Features:
    - Auto-detecta paths.
    - Exporta recursivamente buscando 'geo_grp'.
    - Crea joints faltantes en 'missing_skel_GRP' para evitar pérdida de datos.
    - Reordena inputs para prioridad de deformación.
    """

    def __init__(self):
        self.asset_name, self.project_path = self.get_scene_data()
        self.skin_folder = self.find_skin_folder_path()

        # Si falla la búsqueda inteligente, fallback a ruta relativa
        if not self.skin_folder:
            print(f"Warning: Usando ruta relativa al archivo actual.")
            scene_dir = os.path.dirname(cmds.file(q=True, sn=True))
            self.skin_folder = os.path.join(scene_dir, "skin_clusters")

    def get_scene_data(self):
        """ Analiza la ruta de la escena para extraer nombre del asset. """
        scene_path = cmds.file(q=True, sn=True)
        if not scene_path:
            cmds.error("Guarda la escena antes de ejecutar SkinManager.")
        
        scene_dir = os.path.dirname(scene_path)
        match = re.search(r"assets-(.+?)-guides", scene_path)
        if match:
            asset_name = match.group(1)
            project_path = scene_path.split(f"assets-{asset_name}-guides")[0]
            return asset_name, project_path

        folder_name = os.path.basename(scene_dir)
        project_path = os.path.dirname(scene_dir)
        return folder_name, project_path

    def find_skin_folder_path(self):
        if self.project_path and self.asset_name:
            return os.path.join(self.project_path, f"assets-{self.asset_name}-guides", "skin_clusters")
        return None

    def verify_plugin(self):
        if not NG_AVAILABLE:
            cmds.warning("ngSkinTools2 module not found.")
            return False
        if not cmds.pluginInfo("ngSkinTools2", query=True, loaded=True):
            try:
                cmds.loadPlugin("ngSkinTools2")
            except:
                return False
        return True

    # ----------------------------------------------------------------
    # 1. EXPORTACIÓN AUTOMÁTICA DESDE GEO_GRP
    # ----------------------------------------------------------------
    def export_skins(self):
        if not self.verify_plugin(): return

        if not os.path.exists(self.skin_folder):
            os.makedirs(self.skin_folder)
        
        print(f"\n--- EXPORTANDO SKINS DESDE 'geo_grp' ---")

        # 1. Buscar el grupo de geometría
        # Usamos wildcard por si se llama "char_geo_grp", "geo_grp", etc.
        geo_groups = cmds.ls("*geo_GRP", type="transform")
        
        if not geo_groups:
            cmds.warning("No se encontró ningún grupo terminado en 'geo_GRP' en la escena.")
            return

        # Tomamos el primero encontrado (asumiendo estructura limpia) o loopeamos si hay varios
        target_meshes = []
        
        for grp in geo_groups:
            # listRelatives con allDescendents (ad=True) busca en toda la jerarquía interna
            children = cmds.listRelatives(grp, allDescendents=True, type="mesh", fullPath=True) or []
            for shape in children:
                # Obtenemos el transform del shape
                trans = cmds.listRelatives(shape, parent=True, fullPath=True)[0]
                if trans not in target_meshes:
                    target_meshes.append(trans)

        if not target_meshes:
            cmds.warning(f"El grupo {geo_groups} está vacío o no tiene mallas.")
            return

        count = 0
        for mesh in target_meshes:
            # Verificar si tiene SkinCluster
            shapes = cmds.listRelatives(mesh, shapes=True)
            if not shapes: continue
            
            history = cmds.listHistory(shapes[0])
            skin_cluster = cmds.ls(history, type="skinCluster")
            
            if skin_cluster:
                # Nombre limpio para el archivo
                clean_name = mesh.split("|")[-1].split(":")[-1]
                file_path = os.path.join(self.skin_folder, f"{clean_name}.json")

                config = transfer.TransferConfig()
                config.mesh = mesh
                try:
                    transfer.export_json(file_path, config)
                    print(f" > Exportado: {clean_name}")
                    count += 1
                except Exception as e:
                    print(f"Error exportando {clean_name}: {e}")
            
        print(f"--- Exportación finalizada. Total: {count} archivos. ---")

    # ----------------------------------------------------------------
    # 2. IMPORTACIÓN CON GESTIÓN DE MISSING JOINTS
    # ----------------------------------------------------------------
    def import_skins(self):
        if not self.verify_plugin(): return

        if not os.path.exists(self.skin_folder):
            cmds.warning(f"Carpeta no existe: {self.skin_folder}")
            return

        json_files = [f for f in os.listdir(self.skin_folder) if f.endswith(".json")]
        if not json_files:
            cmds.warning("No hay JSONs para importar.")
            return

        print(f"\n--- IMPORTANDO SKINS (Asset: {self.asset_name}) ---")

        for json_file in json_files:
            file_path = os.path.join(self.skin_folder, json_file)
            mesh_name = os.path.splitext(json_file)[0]

            # Buscar mesh en la escena
            target_mesh = self._find_mesh_in_scene(mesh_name)

            if target_mesh:
                try:
                    # PASO CRÍTICO: Crear joints faltantes antes de importar
                    self._create_missing_joints(file_path)

                    # Importar
                    config = transfer.TransferConfig()
                    config.mesh = target_mesh
                    config.vertex_transfer_mode = transfer.VertexTransferMode.vertexId
                    transfer.import_json(file_path, config)
                    
                    # Reordenar inputs (especialmente Body)
                    self.reorder_deformation_stack(target_mesh)
                    
                    print(f" > Importado: {target_mesh}")
                except Exception as e:
                    print(f" ERROR en {target_mesh}: {e}")
            else:
                print(f" SKIPPING: Geometría '{mesh_name}' no encontrada.")

    def _find_mesh_in_scene(self, mesh_name):
        if cmds.objExists(mesh_name): return mesh_name
        # Búsqueda laxa
        candidates = cmds.ls(f"*{mesh_name}", type="transform")
        if candidates: return candidates[0]
        return None

    def _create_missing_joints(self, json_path):
        """
        Lee el JSON antes de importar. Si encuentra una influencia (joint)
        que no existe en la escena, la crea en 'missing_skel_GRP'.
        """
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)
        except Exception as e:
            print(f"Error leyendo JSON {json_path}: {e}")
            return

        # Estructura del JSON de ngSkinTools2: data['influences'] es una lista de dicts
        if 'influences' not in data: return

        missing_grp = "missing_skel_GRP"

        for influence in data['influences']:
            # Dependiendo de la versión, puede ser 'path' o 'name'. NgSkinTools2 suele usar path.
            jnt_path = influence.get('path', influence.get('name', ''))
            
            if not jnt_path: continue

            # Extraemos el nombre corto (leaf node) por si la jerarquía ha cambiado
            jnt_name = jnt_path.split("|")[-1]

            # Verificamos si existe
            if not cmds.objExists(jnt_name):
                # NO EXISTE: Crearlo
                if not cmds.objExists(missing_grp):
                    cmds.createNode("transform", name=missing_grp)
                    print(f"   [!] Creado grupo contenedor: {missing_grp}")

                # Crear joint en el origen (0,0,0)
                cmds.select(clear=True) # Importante para no emparentarlo a la selección actual
                new_jnt = cmds.createNode("joint", name=jnt_name)
                
                # Emparentar al grupo de missing
                cmds.parent(new_jnt, missing_grp)
                
                print(f"   [!] Missing Joint Creado: {jnt_name} -> {missing_grp}")

    def reorder_deformation_stack(self, mesh):
        shapes = cmds.listRelatives(mesh, shapes=True)
        if not shapes: return
        history = cmds.listHistory(shapes[0], pruneDagObjects=True)
        skin_clusters = cmds.ls(history, type="skinCluster")
        
        if skin_clusters and "body" in mesh.lower():
            try:
                cmds.reorderDeformers(skin_clusters[0], front=True)
            except:
                pass