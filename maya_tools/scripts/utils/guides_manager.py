from importlib import reload
import maya.cmds as cmds
import maya.api.OpenMaya as om
import json
import math
import os
import pathlib

from maya_tools.scripts.utils import data_manager
from maya_tools.scripts.utils import rig_manager

# Recarga de módulos
reload(data_manager)
reload(rig_manager)


# ─────────────────────────────────────────────────────────────────────────────
# Cache del archivo .guides
# Cada get_guides() releía el JSON de disco (+ listado de directorio para
# resolver la versión). En un build completo eso son decenas de relecturas del
# mismo archivo (en disco de red, segundos perdidos). Se cachea la resolución
# de ruta y el JSON parseado por personaje; se invalida al empezar un build o
# al re-exportar las guías.
# ─────────────────────────────────────────────────────────────────────────────
# Sobrevive a reload(): importlib.reload re-ejecuta el módulo sobre su mismo
# __dict__ sin limpiarlo, así que el guard conserva el cache entre los
# reload(guides_manager) que hace cada submódulo de autorig al importarse.
if "_GUIDES_CACHE" not in globals():
    _GUIDES_CACHE = {}  # character_name -> (template_file, parsed_data)


def clear_guides_cache():
    """Vacía el cache del .guides. Llamar al empezar un build o tras re-exportar."""
    _GUIDES_CACHE.clear()


def _load_guides_file(character_name):
    """
    Devuelve (template_file, guides_data) para un personaje, cacheado.
    template_file/guides_data son None si no existe el archivo.
    """
    cached = _GUIDES_CACHE.get(character_name)
    if cached is not None:
        return cached

    template_path = rig_manager.asset_path(character_name, "guides")
    template_file = rig_manager.get_latest_version(template_path)

    if not template_file or not os.path.exists(template_file):
        _GUIDES_CACHE[character_name] = (None, None)
        return None, None

    with open(template_file, "r") as input_file:
        guides_data = json.load(input_file)

    _GUIDES_CACHE[character_name] = (template_file, guides_data)
    return template_file, guides_data

def get_guides_info(path=None):
    """
    Get the guides transform and take the information from the joints and locators.
    """
    # --- 1. Inicialización de variables para evitar UnboundLocalError ---
    guides_node = "C_guides_GRP"
    
    joint_guides = []
    locator_guides = []
    curves_in_scene = []
    nurbs_surfaces = []
    nurbs_data = []
    shapes_data = []
    joint_matrices = []
    joint_parents = []
    locator_positions = []
    
    # --- 2. Validación de escena y rutas ---
    CHARACTER_NAME = rig_manager.get_character_name_from_scene(avoid=guides_node)
    if not CHARACTER_NAME:
        om.MGlobal.displayError("No se pudo determinar el nombre del personaje.")
        return None

    try:
        guides_transform = cmds.ls(guides_node, type="transform")[0]
    except IndexError:
        om.MGlobal.displayError(f"No se encontró el nodo principal de guías: {guides_node}")
        return None

    # --- 3. Recolección de datos de Maya (con guardas para evitar None) ---
    joint_guides = cmds.listRelatives(guides_transform, allDescendents=True, type="joint") or []
    locator_guides = cmds.listRelatives(guides_transform, allDescendents=True, type="locator") or []
    curves_in_scene = cmds.ls("*_CRV", type="transform", long=True) or []
    nurbs_surfaces = cmds.ls("*_NURB", type="transform", long=True) or []

    # --- 4. Procesamiento de NURBS Surfaces ---
    if nurbs_surfaces:
        for nurbs_surface in nurbs_surfaces:
            clean_name = nurbs_surface.split("|")[-1]+"Shape"
            surface_shapes = cmds.listRelatives(nurbs_surface, shapes=True, type="nurbsSurface")
            
            if surface_shapes:
                shape_path = surface_shapes[0]
                sel_list = om.MSelectionList()
                sel_list.add(shape_path)
                shape_obj = sel_list.getDependNode(0)
                fn_nurbs = om.MFnNurbsSurface(shape_obj)

                # Extracción de data técnica
                cvs = []
                is_rational = False
                for u in range(fn_nurbs.numCVsInU):
                    row = []
                    for v in range(fn_nurbs.numCVsInV):
                        pt = fn_nurbs.cvPosition(u, v)
                        if abs(pt.w - 1.0) > 1e-6:
                            is_rational = True
                            row.append((pt.x, pt.y, pt.z, pt.w))
                        else:
                            row.append((pt.x, pt.y, pt.z))
                    cvs.append(row)

                nurbs_data.append({
                    "name": clean_name,
                    "surface": {
                        "degreeInU": int(fn_nurbs.degreeInU),
                        "degreeInV": int(fn_nurbs.degreeInV),
                        "formInU": str(fn_nurbs.formInU),
                        "formInV": str(fn_nurbs.formInV),
                        "knotsInU": list(fn_nurbs.knotsInU()),
                        "knotsInV": list(fn_nurbs.knotsInV()),
                        "cvs": cvs,
                        "isRational": is_rational
                    }
                })

    # --- 5. Procesamiento de CURVAS ---
    if curves_in_scene:
        for crv in curves_in_scene:
            c_shapes = cmds.listRelatives(crv, shapes=True, type="nurbsCurve")
            if not c_shapes: continue
            
            for shp in c_shapes:
                sel = om.MSelectionList()
                sel.add(shp)
                curve_fn = om.MFnNurbsCurve(sel.getDependNode(0))
                
                cvs = [ (pt.x, pt.y, pt.z) for pt in [curve_fn.cvPosition(i) for i in range(curve_fn.numCVs)] ]
                
                shapes_data.append({
                    "name": shp.split("|")[-1],
                    "curve": {
                        "cvs": cvs,
                        "degree": curve_fn.degree,
                        "knots": list(curve_fn.knots()),
                        "form": str(curve_fn.form)
                    }
                })

    # --- 6. Procesamiento de JOINTS ---
    if joint_guides:
        for jnt in joint_guides:
            joint_matrices.append(cmds.xform(jnt, q=True, ws=True, m=True))
            parent = cmds.listRelatives(jnt, parent=True)
            joint_parents.append(parent[0] if parent else None)
    else:
        om.MGlobal.displayWarning("No se encontraron joints bajo el grupo de guías.")

    # --- 7. Procesamiento de LOCATORS ---
    if locator_guides:
        for loc in locator_guides:
            parent_transform = cmds.listRelatives(loc, parent=True)[0]
            locator_positions.append(cmds.xform(parent_transform, q=True, ws=True, m=True))

    # --- 8. Construcción del Diccionario Final ---
    guides_data = {CHARACTER_NAME: {}}

    for i, guide in enumerate(joint_guides):
            children = cmds.listRelatives(guide, allDescendents=True)
            key = guide[0] if isinstance(guide, list) else guide
            guides_data[CHARACTER_NAME][key] = {
                "joint_matrix": joint_matrices[i],
                "parent": joint_parents[i],
                "isLocator": False,
                "isJoint": True,
                "isCurve": False,
                "isSurface": False,
                "children": list(reversed(children if children else [])),
        }

    for i, loc in enumerate(locator_guides):
        guides_data[CHARACTER_NAME][loc] = {
            "locator_position": locator_positions[i],
            "isLocator": True,
            "isJoint": False,
            "isCurve": False,
            "isSurface": False
        }

    for s_data in shapes_data:
        guides_data[CHARACTER_NAME][s_data["name"]] = {
            "curve_data": s_data["curve"],
            "isCurve": True,
            "isLocator": False,
            "isJoint": False,
            "isSurface": False
        }

    for n_data in nurbs_data:
        guides_data[CHARACTER_NAME][n_data["name"]] = {
            "surface_data": n_data["surface"],
            "isSurface": True,
            "isCurve": False,
            "isLocator": False,
            "isJoint": False
        }
    # --- 9. Guardado del JSON ---
    assets_path = rig_manager.asset_path(CHARACTER_NAME, "guides")
    
    # Creamos la carpeta si no existe
    if not os.path.exists(assets_path):
        os.makedirs(assets_path)

    if path:
        TEMPLATE_FILE = os.path.normpath(path)
    else: 
        TEMPLATE_FILE = os.path.join(assets_path, f"{CHARACTER_NAME}_v001.guides")

    with open(TEMPLATE_FILE, "w") as output_file:
        json.dump(guides_data, output_file, indent=4)

    clear_guides_cache()  # el archivo en disco cambió: invalida el cache

    om.MGlobal.displayInfo(f"Guías guardadas con éxito en: {TEMPLATE_FILE}")

    rig_manager.get_rig_data(character_name=CHARACTER_NAME, guides_transform=guides_node)
    return TEMPLATE_FILE

def load_guides_info(filePath=None):

    """ Load guides information from a JSON file and create the guides in the scene."""
    
    guides_node = "C_guides_GRP"
    rig_manager.create_new_scene()
    character_name = rig_manager.get_character_name_from_build()

    if not filePath:
    
        TEMPLATE_PATH = rig_manager.asset_path("", "") # Get base assets path

        final_path = cmds.fileDialog2(fileMode=1, caption="Select a file", dir=TEMPLATE_PATH, fileFilter="*.guides")[0]
        print("Selected file path:", final_path)
        if not final_path:
            om.MGlobal.displayError("No file selected.")
            return None

        character_name = None
        parts = pathlib.Path(final_path).parts
        try:
            assets_idx = next(i for i, p in enumerate(parts) if p.lower() == "assets")
            character_name = parts[assets_idx + 1]
        except (StopIteration, IndexError):
            om.MGlobal.displayWarning("Could not determine character name from path (no 'assets' folder found).")
            character_name = None
            return None
        
    else:

        final_path = os.path.normpath(filePath)

    if "v0" in final_path:
        name = os.path.basename(final_path).split(".")[0].split("_v0")[0]
    else:
        name = os.path.basename(final_path).split(".")[0]

    with open(final_path, "r") as input_file:
        guides_data = json.load(input_file)
    
    if not cmds.objExists("C_guides_GRP"):
        guides_node = cmds.createNode("transform", name="C_guides_GRP", ss=True)
        rig_manager.create_rig_settings(guides_node, load=False) 

        rig_data = rig_manager.build_rig_from_data(character_name)

        if rig_data:
            print(f"--- Aplicando ajustes desde el build de {character_name} ---")
            for attr, value in rig_data.items():
                attr_path = f"C_guides_GRP.{attr}"
                if cmds.objExists(attr_path):
                    try:
                        cmds.setAttr(attr_path, value)
                    except Exception as e:
                        print(f"No se pudo setear {attr}: {e}")

        for guide, data in reversed(list(guides_data[name].items())):
                
                if "isLocator" in data and data["isLocator"]:
                        locator = cmds.spaceLocator(name=guide.replace("LOCShape", "LOC"))[0]
                        cmds.xform(locator, ws=True, m=data["locator_position"])
                        cmds.parent(locator, guides_node)

                elif "isJoint" in data and data["isJoint"]:

                    cmds.select(clear=True)
                    imported_joint = cmds.joint(name=guide, r=5)
                    cmds.xform(imported_joint, ws=True, m=data["joint_matrix"])
                    cmds.makeIdentity(imported_joint, apply=True, r=True)
                    
                    # Make joint blue if L side, red if R side
                    if guide.startswith("L_"):
                        cmds.setAttr(f"{imported_joint}.overrideEnabled", 1)
                        cmds.setAttr(f"{imported_joint}.overrideColor", 6)  # Blue
                    elif guide.startswith("R_"):
                        cmds.setAttr(f"{imported_joint}.overrideEnabled", 1)
                        cmds.setAttr(f"{imported_joint}.overrideColor", 13)  # Red
                    elif guide.startswith("C_"):
                        cmds.setAttr(f"{imported_joint}.overrideEnabled", 1)
                        cmds.setAttr(f"{imported_joint}.overrideColor", 17)  # Yellow

                    if data["parent"] == "C_root_JNT":
                        cmds.parent(imported_joint, guides_node)
                    else:
                        cmds.parent(imported_joint, data["parent"])
                
                elif "isCurve" in data and data["isCurve"]:

                    curve_name = guide
                    dag_modifier = om.MDagModifier()
                    transform_obj = dag_modifier.createNode("transform")
                    dag_modifier.doIt()
                    transform_fn = om.MFnDagNode(transform_obj)
                    transform_fn.setName(curve_name.split("Shape")[0])
                    dag_modifier.doIt()
                    cmds.parent(transform_fn.name(), guides_node)

                    
                    curve_info = data["curve_data"]
                    cvs = curve_info["cvs"]
                    degree = curve_info["degree"]
                    knots = curve_info["knots"]
                    form = curve_info["form"]

                    form_flags = {
                        "open": om.MFnNurbsCurve.kOpen,
                        "closed": om.MFnNurbsCurve.kClosed,
                        "periodic": om.MFnNurbsCurve.kPeriodic
                    }
                    form_flag = form_flags.get(form, om.MFnNurbsCurve.kOpen)

                    points = om.MPointArray()
                    for pt in cvs:
                        points.append(om.MPoint(pt[0], pt[1], pt[2]))

                    curve_fn = om.MFnNurbsCurve()
                    shape_obj = curve_fn.create(
                        points,
                        knots,
                        degree,
                        form_flag,
                        False,    
                        True,     
                        transform_obj
                    )

                    shape_fn = om.MFnDagNode(shape_obj)
                    shape_fn.setName(curve_name)

                elif "isSurface" in data and data["isSurface"]:

                    surface_name = guide
                    dag_modifier = om.MDagModifier()
                    transform_obj = dag_modifier.createNode("transform")
                    dag_modifier.doIt()
                    transform_fn = om.MFnDagNode(transform_obj)
                    transform_fn.setName(surface_name.split("Shape")[0])
                    dag_modifier.doIt()
                    cmds.parent(transform_fn.name(), guides_node)

                    surface_info = data["surface_data"]
                    degree_u = surface_info["degreeInU"]
                    degree_v = surface_info["degreeInV"]
                    form_u = surface_info["formInU"]
                    form_v = surface_info["formInV"]
                    knots_u = surface_info["knotsInU"]
                    knots_v = surface_info["knotsInV"]
                    cvs = surface_info["cvs"]
                    is_rational = surface_info["isRational"]

                    form_flags = {
                        "open": om.MFnNurbsSurface.kOpen,
                        "closed": om.MFnNurbsSurface.kClosed,
                        "periodic": om.MFnNurbsSurface.kPeriodic
                    }
                    form_u_flag = form_flags.get(form_u, om.MFnNurbsSurface.kOpen)
                    form_v_flag = form_flags.get(form_v, om.MFnNurbsSurface.kOpen)

                    points = om.MPointArray()
                    for row in cvs:
                        for pt in row:
                            num = +1
                            if len(pt) == 4:
                                points.append(om.MPoint(pt[0], pt[1], pt[2], pt[3]))
                            else:
                                points.append(om.MPoint(pt[0], pt[1], pt[2], 1.0))

                    surface_fn = om.MFnNurbsSurface()
                    shape_obj = surface_fn.create(
                        points,
                        knots_u,
                        knots_v,
                        degree_u,
                        degree_v,
                        form_u_flag,
                        form_v_flag,
                        bool(is_rational),        
                        transform_obj
                    )

                    shape_fn = om.MFnDagNode(shape_obj)
                    shape_fn.setName(surface_name)

        if character_name:
            rig_manager.import_meshes_for_guides(character_name=character_name)

        else:
            rig_manager.import_meshes()

    else:

        om.MGlobal.displayError("Guides group 'C_guides_GRP' already exists. Please delete it before loading new guides.")

def delete_guides():

    """ Deletes the guides group and all its children."""

    guides_group = "C_guides_GRP"

    if cmds.objExists(guides_group):
        cmds.delete(guides_group)
        om.MGlobal.displayInfo(f"Deleted guides group: {guides_group}")
    else:
        om.MGlobal.displayError(f"Guides group '{guides_group}' does not exist.")

def get_guides(guide_export, parent=None):

    """
    Get the guides from the scene based on the provided guide export data.
    
    Args:
        guide_export (dict): The guide export data containing joint matrices and locator positions.
        allDescendants (bool): Whether to include all descendants in the search.

    Returns:
        list: A list of guides found in the scene.
    """

    CHARACTER_NAME = rig_manager.get_character_name_from_build()
    TEMPLATE_FILE, guides_data = _load_guides_file(CHARACTER_NAME)

    if not TEMPLATE_FILE:

        om.MGlobal.displayError("Guides path does not exist. Please create the guides first.")

        return

    else:

        path = pathlib.Path(TEMPLATE_FILE)
        parts = path.parts # Get the parts of the path
        name = parts[parts.index('assets') + 1] # Get the character name after 'assets'

        try:
            if guides_data[name][guide_export]["isJoint"] == True:
                chain = []

                joint_exported = cmds.joint(name=guide_export, r=5)
                cmds.xform(joint_exported, ws=True, m=guides_data[name][guide_export]["joint_matrix"])
                cmds.makeIdentity(joint_exported, apply=True, r=True)
                chain.append(joint_exported)

                if "children" in guides_data[name][guide_export]:
                    for child in guides_data[name][guide_export]["children"]:
                        child_joint = cmds.joint(name=child, r=5)
                        cmds.xform(child_joint, ws=True, m=guides_data[name][child]["joint_matrix"])
                        cmds.makeIdentity(child_joint, apply=True, r=True)
                        chain.append(child_joint)

                if parent:
                    cmds.parent(chain[0], parent)

                return chain
            
            elif guides_data[name][guide_export]["isLocator"] == True:
                locator = cmds.spaceLocator(name=guide_export.replace("LOCShape", "LOC"))[0]
                cmds.xform(locator, ws=True, m=guides_data[name][guide_export]["locator_position"])
                return locator
            
            elif guides_data[name][guide_export]["isCurve"] == True:

                curve_name = guide_export
                dag_modifier = om.MDagModifier()
                transform_obj = dag_modifier.createNode("transform")
                dag_modifier.doIt()
                transform_fn = om.MFnDagNode(transform_obj)
                transform_fn.setName(curve_name.split("Shape")[0])
                dag_modifier.doIt()

                # Retrieve curve data from the loaded guides_data
                curve_info = guides_data[name][curve_name]["curve_data"]
                cvs = curve_info["cvs"]
                degree = curve_info["degree"]
                knots = curve_info["knots"]
                form = curve_info["form"]

                form_flags = {
                    "open": om.MFnNurbsCurve.kOpen,
                    "closed": om.MFnNurbsCurve.kClosed,
                    "periodic": om.MFnNurbsCurve.kPeriodic
                }
                form_flag = form_flags.get(form, om.MFnNurbsCurve.kOpen)

                points = om.MPointArray()
                for pt in cvs:
                    points.append(om.MPoint(pt[0], pt[1], pt[2]))

                curve_fn = om.MFnNurbsCurve()
                shape_obj = curve_fn.create(
                    points,
                    knots,
                    degree,
                    form_flag,
                    False,    
                    True,     
                    transform_obj
                )

                shape_fn = om.MFnDagNode(shape_obj)
                shape_fn.setName(curve_name)

                if parent:
                    cmds.parent(transform_fn.name(), parent)
            
                return shape_fn.name()
            
            elif guides_data[name][guide_export]["isSurface"] == True:

                surface_name = guide_export
                dag_modifier = om.MDagModifier()
                transform_obj = dag_modifier.createNode("transform")
                dag_modifier.doIt()
                transform_fn = om.MFnDagNode(transform_obj)
                transform_fn.setName(surface_name.split("Shape")[0])
                dag_modifier.doIt()


                surface_info = guides_data[name][guide_export]["surface_data"]
                degree_u = surface_info["degreeInU"]
                degree_v = surface_info["degreeInV"]
                form_u = surface_info["formInU"]
                form_v = surface_info["formInV"]
                knots_u = surface_info["knotsInU"]
                knots_v = surface_info["knotsInV"]
                cvs = surface_info["cvs"]
                is_rational = surface_info["isRational"]

                form_flags = {
                    "open": om.MFnNurbsSurface.kOpen,
                    "closed": om.MFnNurbsSurface.kClosed,
                    "periodic": om.MFnNurbsSurface.kPeriodic
                }
                form_u_flag = form_flags.get(form_u, om.MFnNurbsSurface.kOpen)
                form_v_flag = form_flags.get(form_v, om.MFnNurbsSurface.kOpen)

                points = om.MPointArray()
                for row in cvs:
                    for pt in row:
                        num = +1
                        if len(pt) == 4:
                            points.append(om.MPoint(pt[0], pt[1], pt[2], pt[3]))
                        else:
                            points.append(om.MPoint(pt[0], pt[1], pt[2], 1.0))

                surface_fn = om.MFnNurbsSurface()
                shape_obj = surface_fn.create(
                    points,
                    knots_u,
                    knots_v,
                    degree_u,
                    degree_v,
                    form_u_flag,
                    form_v_flag,
                    bool(is_rational),        
                    transform_obj
                )

                shape_fn = om.MFnDagNode(shape_obj)
                shape_fn.setName(surface_name)

            return transform_fn.name()
    
        except KeyError:
            om.MGlobal.displayError(f"Guide '{guide_export}' not found in the guide export data.")
            return None
        

def create_new_guides():
    """
    1. Crea la estructura de carpetas para el nuevo personaje.
    2. Localiza las guías maestras en la ruta assets/-/new/guides.
    3. Carga la información de esas guías en la escena actual.
    """

    complete_path = os.path.realpath(__file__)
    relative_path = complete_path.split(os.sep + "scripts")[0]
    
    template_path = os.path.join(relative_path, "assets", "-", "new", "guides")
    try:
        template_file = rig_manager.get_latest_version(template_path)
        
        if template_file and os.path.exists(template_file):
            om.MGlobal.displayInfo(f"Cargando guías de plantilla desde: {template_file}")
        
            load_guides_info(filePath=template_file)
            
        else:
            om.MGlobal.displayError(f"No se encontró ningún archivo .guides en: {template_path}")
            
    except Exception as e:
        om.MGlobal.displayError(f"Error al intentar automatizar las guías: {str(e)}")

    # Finalmente, crea el nuevo asset
    rig_manager.create_new_asset()

def read_guides_info(character_name, guide_name=None):
    """
    Lee la información de guías. 
    
    MODO 1: Si guide_name es None -> Devuelve TODO el diccionario de guías (para cache).
    MODO 2: Si hay guide_name -> Devuelve True/False si existe.

    Args:
        character_name (str): Nombre del personaje.
        guide_name (str, optional): Nombre de la guía específica. Defaults to None.

    Returns:
        dict: Si guide_name es None, devuelve todo el diccionario de datos.
        bool: Si guide_name tiene valor, devuelve True/False.
        None: Si hay error.
    """
    try:
        guides_file, guides_info = _load_guides_file(character_name)
    except Exception as e:
        om.MGlobal.displayError(f"[LOG ERROR] Error leyendo JSON: {str(e)}")
        return None

    if not guides_file:
        om.MGlobal.displayError(f"[LOG ERROR] No se encontró archivo de guías para: {character_name}")
        return None

    character_data = guides_info.get(character_name)

    if character_data is None:
        om.MGlobal.displayError(f"[LOG ERROR] El personaje '{character_name}' no está en el JSON.")
        return None

    if guide_name is None:
        return character_data



def mirror_specific_guide(guide, is_joint):
    """
    Mirroriza un guide del lado L al lado R.
    Para joints usa mirrorJoint; para el resto copia/crea el nodo en R con posición mirroreada.
    """
    r_guide = guide.replace("L_", "R_", 1)

    if is_joint:
        # Maya maneja joints de forma nativa con mirrorJoint
        if cmds.objExists(r_guide):
            cmds.delete(r_guide)

        cmds.mirrorJoint(
            guide,
            mirrorYZ=True,          # mirror en el plano YZ (eje X)
            mirrorBehavior=True,    # invierte orientación del joint
            searchReplace=("L_", "R_")
        )

    else:
        # Para nurbsCurves, locators, etc: obtener transform y mirrorear en X
        obj_type = cmds.objectType(guide)

        # Obtener posición/rotación/escala en world space
        ws_pos   = cmds.xform(guide, q=True, worldSpace=True, translation=True)
        ws_rot   = cmds.xform(guide, q=True, worldSpace=True, rotation=True)
        ws_scale = cmds.xform(guide, q=True, relative=True,   scale=True)

        # Mirror en X (negar X de posición y rotaciones Y/Z)
        mirrored_pos = [-ws_pos[0], ws_pos[1], ws_pos[2]]
        mirrored_rot = [ws_rot[0], -ws_rot[1], -ws_rot[2]]

        if cmds.objExists(r_guide):
            # Si ya existe, solo actualizar transforms
            cmds.xform(r_guide, worldSpace=True, translation=mirrored_pos)
            cmds.xform(r_guide, worldSpace=True, rotation=mirrored_rot)
            cmds.xform(r_guide, relative=True, scale=ws_scale)
        else:
            # Duplicar el nodo L y renombrarlo a R
            duplicated = cmds.duplicate(guide, name=r_guide, returnRootsOnly=True)[0]

            # Aplicar transforms mirroreados
            cmds.xform(duplicated, worldSpace=True, translation=mirrored_pos)
            cmds.xform(duplicated, worldSpace=True, rotation=mirrored_rot)
            cmds.xform(duplicated, relative=True, scale=ws_scale)

            # Reparentar al mismo contenedor si no es hijo directo ya
            container = "C_guides_GRP"
            parent = cmds.listRelatives(duplicated, parent=True, fullPath=False)
            if not parent or parent[0] != container:
                cmds.parent(duplicated, container)


def mirror_guides():
    container = "C_guides_GRP"

    if not cmds.objExists(container):
        om.MGlobal.displayError(f"No existe el grupo: {container}")
        return

    # Hijos directos del contenedor
    children = cmds.listRelatives(container, children=True, fullPath=False) or []

    # Si hay selección, filtrar solo los hijos seleccionados del contenedor
    selected = set(cmds.ls(sl=True, long=False))
    if selected:
        guides_to_process = [g for g in children if g in selected and g.startswith("L_")]
    else:
        guides_to_process = [g for g in children if g.startswith("L_")]

    if not guides_to_process:
        om.MGlobal.displayWarning("No se encontraron guides con prefijo 'L_' para mirrorear.")
        return

    count = 0
    for guide in guides_to_process:
        obj_type = cmds.objectType(guide)
        is_joint = (obj_type == "joint")
        mirror_specific_guide(guide, is_joint)
        count += 1

    om.MGlobal.displayInfo(f"Mirror finalizado: {count} guide(s) procesados de L → R.")


def _axis_index_sign(axis):
    """Devuelve el índice del eje cardinal dominante y su signo (+1/-1)."""
    idx = max(range(3), key=lambda i: abs(axis[i]))
    return idx, (1.0 if axis[idx] >= 0 else -1.0)


def _aim_matrix(pos, aim_pos, up_pos, primary_axis, secondary_axis):
    """
    Matriz mundo equivalente a un aimMatrix con secondaryMode=Aim: el eje
    primario apunta a aim_pos, el secundario hacia up_pos (ortogonalizado)
    y la traslación queda en pos. Calculada en Python, sin crear nodos.
    """
    aim = om.MVector(aim_pos) - om.MVector(pos)
    if aim.length() < 1e-6:
        aim = om.MVector(1.0, 0.0, 0.0)
    aim.normalize()

    up = om.MVector(up_pos) - om.MVector(pos)
    up -= aim * (up * aim)  # proyección ortogonal al eje primario
    if up.length() < 1e-6:
        world_up = om.MVector(0.0, 1.0, 0.0)
        if abs(aim * world_up) > 0.999:
            world_up = om.MVector(0.0, 0.0, 1.0)
        up = world_up - aim * (world_up * aim)
    up.normalize()

    primary_idx, primary_sign = _axis_index_sign(primary_axis)
    secondary_idx, secondary_sign = _axis_index_sign(secondary_axis)
    third_idx = 3 - primary_idx - secondary_idx
    # signo de Levi-Civita para que la base resultante sea una rotación pura
    parity = 1.0 if (primary_idx, secondary_idx) in ((0, 1), (1, 2), (2, 0)) else -1.0
    third = (aim ^ up) * (primary_sign * secondary_sign * parity)

    rows = [None] * 3
    rows[primary_idx] = aim * primary_sign
    rows[secondary_idx] = up * secondary_sign
    rows[third_idx] = third
    return om.MMatrix([
        rows[0].x, rows[0].y, rows[0].z, 0.0,
        rows[1].x, rows[1].y, rows[1].z, 0.0,
        rows[2].x, rows[2].y, rows[2].z, 0.0,
        pos.x, pos.y, pos.z, 1.0,
    ])


def _with_translation(matrix, pos):
    """Copia una matriz sustituyendo su traslación."""
    values = list(matrix)
    values[12:15] = [pos.x, pos.y, pos.z]
    return om.MMatrix(values)


def _scale_rotation(matrix, weight):
    """Rotación de la matriz escalada por weight (slerp desde identidad)."""
    quat = om.MTransformationMatrix(matrix).rotation(asQuaternion=True)
    w = max(-1.0, min(1.0, quat.w))
    sin_half = math.sqrt(max(0.0, 1.0 - w * w))
    if sin_half < 1e-9:
        return om.MMatrix.kIdentity
    axis = om.MVector(quat.x, quat.y, quat.z) / sin_half
    half = math.acos(w) * weight
    s = math.sin(half)
    return om.MQuaternion(axis.x * s, axis.y * s, axis.z * s, math.cos(half)).asMatrix()


def orient_guides(guides, primaryInputAxis=(1, 0, 0), secondaryInputAxis=(0, 1, 0), ribbon=False):

    """
    Orienta las guías. Cada guía se orienta hacia la siguiente (la última hereda
    la orientación de la anterior). Las matrices se calculan en Python y se
    hornean como valores estáticos en un único nodo network, en vez de dejar
    transforms + aimMatrix/blendMatrix vivos en el rig: las guías no se mueven
    después del build, así que el resultado es el mismo sin coste de evaluación.

    Returns:
        guides_matrices (list): atributos de matriz orientada por guía (conectables).
        point_matrices (list): atributos de matriz de posición (rotación identidad)
            por guía; sustituyen al worldMatrix de los antiguos trn_guides.
    """
    positions = [om.MVector(cmds.xform(g, q=True, ws=True, t=True)) for g in guides]
    count = len(positions)

    side, base_name = guides[0].split("_")[0:2]
    net = cmds.createNode("network", name=f"{side}_{base_name}Guides_NET", ss=True)
    cmds.addAttr(net, longName="orientMatrix", dataType="matrix", multi=True)
    cmds.addAttr(net, longName="pointMatrix", dataType="matrix", multi=True)

    sec_axis = tuple(secondaryInputAxis)
    matrices = []

    for i, guide in enumerate(guides):

        # A partir del ankle (incluido) el eje secundario se invierte
        if "ankle" in guide.split("_")[1]:
            sec_axis = tuple(-v for v in sec_axis)

        pos = positions[i]

        if i == 0:
            up_pos = positions[2] if count > 2 else om.MVector(0.0, 0.0, 0.0)
            matrix = _aim_matrix(pos, positions[1], up_pos, primaryInputAxis, sec_axis)

        elif i == count - 1:
            if ribbon:
                matrix = _with_translation(om.MMatrix.kIdentity, pos)
            else:
                # rotación de la guía anterior con la posición propia
                matrix = _with_translation(matrices[-1], pos)

        else:
            if ribbon:
                weight = 1.0 - (i / (count - 1))
                matrix = _with_translation(_scale_rotation(matrices[0], weight), pos)
            else:
                matrix = _aim_matrix(pos, positions[i + 1], positions[i - 1], primaryInputAxis, sec_axis)

        cmds.setAttr(f"{net}.orientMatrix[{i}]", list(matrix), type="matrix")
        cmds.setAttr(f"{net}.pointMatrix[{i}]", list(_with_translation(om.MMatrix.kIdentity, pos)), type="matrix")
        matrices.append(matrix)

    guides_matrices = [f"{net}.orientMatrix[{i}]" for i in range(count)]
    point_matrices = [f"{net}.pointMatrix[{i}]" for i in range(count)]

    return guides_matrices, point_matrices