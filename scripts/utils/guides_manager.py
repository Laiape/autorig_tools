from importlib import reload
import maya.cmds as cmds
import maya.api.OpenMaya as om
import json
import os
import pathlib

from utils import data_manager
from utils import rig_manager

# Recarga de módulos
reload(data_manager)
reload(rig_manager)

def get_guides_info():
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
            clean_name = nurbs_surface.split("|")[-1]
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
        children = cmds.listRelatives(guide, children=True) or []
        guides_data[CHARACTER_NAME][guide] = {
            "joint_matrix": joint_matrices[i],
            "parent": joint_parents[i],
            "isJoint": True,
            "children": children
        }

    for i, loc in enumerate(locator_guides):
        guides_data[CHARACTER_NAME][loc] = {
            "locator_position": locator_positions[i],
            "isLocator": True
        }

    for s_data in shapes_data:
        guides_data[CHARACTER_NAME][s_data["name"]] = {
            "curve_data": s_data["curve"],
            "isCurve": True
        }

    for n_data in nurbs_data:
        guides_data[CHARACTER_NAME][n_data["name"]] = {
            "surface_data": n_data["surface"],
            "isSurface": True
        }

    # --- 9. Guardado de archivo ---
    assets_path = rig_manager.asset_path(CHARACTER_NAME, "guides")
    
    # Creamos la carpeta si no existe
    if not os.path.exists(assets_path):
        os.makedirs(assets_path)

    TEMPLATE_FILE = os.path.join(assets_path, f"{CHARACTER_NAME}_v001.guides")

    with open(TEMPLATE_FILE, "w") as output_file:
        json.dump(guides_data, output_file, indent=4)
    
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

        # get the folder name immediately after the "assets" folder in the selected path
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
    
    if not cmds.ls("C_guides_GRP"):

        guides_node = cmds.createNode("transform", name="C_guides_GRP", ss=True)
        rig_manager.create_rig_settings(guides_node)

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
    TEMPLATE_PATH = rig_manager.asset_path(CHARACTER_NAME, "guides")
    TEMPLATE_FILE = rig_manager.get_latest_version(TEMPLATE_PATH)

    
    path = pathlib.Path(TEMPLATE_FILE)
    parts = path.parts # Get the parts of the path
    name = parts[parts.index('assets') + 1] # Get the character name after 'assets'

    if not os.path.exists(TEMPLATE_FILE):

        om.MGlobal.displayError("Guides path does not exist. Please create the guides first.")

        return 
    
    else:

        with open(TEMPLATE_FILE, "r") as input_file:
            guides_data = json.load(input_file)
              
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
                    if len(chain[0]) > 1:
                        cmds.parent(chain[0], parent)
                    else:
                        cmds.parent(chain, parent)

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
                num_spans_u = int(surface_info["numCVsInU"])
                num_spans_v = int(surface_info["numCVsInV"])

                form_flags = {
                    "open": om.MFnNurbsSurface.kOpen,
                    "closed": om.MFnNurbsSurface.kClosed,
                    "periodic": om.MFnNurbsSurface.kPeriodic
                }
                form_u_flag = form_flags.get(form_u, om.MFnNurbsSurface.kOpen)
                form_v_flag = form_flags.get(form_v, om.MFnNurbsSurface.kOpen)


                cvs = surface_info["cvs"]
                points = om.MPointArray()
                for u in range(num_spans_u):
                    for v in range(num_spans_v):
                        pt = cvs[u][v]
                        points.append(pt)

                surface_fn = om.MFnNurbsSurface()
                shape_obj = surface_fn.create(
                    points,
                    om.MDoubleArray(knots_u),
                    om.MDoubleArray(knots_v),
                    degree_u,
                    degree_v,
                    form_u_flag,
                    form_v_flag,
                    bool(is_rational),        
                    transform_obj
                )

                shape_fn = om.MFnDagNode(shape_obj)
                shape_fn.setName(surface_name)
            
                parent_obj = om.MSelectionList().add(parent).getDagPath(0).node()
                dag_modifier.reparentNode(transform_obj, parent_obj)
                dag_modifier.doIt()

            
                
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
        complete_path = os.path.realpath(__file__)
        relative_path = complete_path.split(os.sep + "scripts")[0]
        base_path = os.path.join(relative_path, "assets")
        character_path = os.path.join(base_path, character_name)
        guides_folder = os.path.join(character_path, "guides")
        
        guides_file = rig_manager.get_latest_version(guides_folder)
        
    except Exception as e:
        om.MGlobal.displayError(f"[LOG ERROR] Error rutas: {str(e)}")
        return None

    if not guides_file or not os.path.exists(guides_file):
        om.MGlobal.displayError(f"[LOG ERROR] No se encontró archivo de guías en: {guides_folder}")
        return None

    try:
        with open(guides_file, 'r') as file:
            guides_info = json.load(file)
    except Exception as e:
        om.MGlobal.displayError(f"[LOG ERROR] Error leyendo JSON: {str(e)}")
        return None

    character_data = guides_info.get(character_name)
    
    if character_data is None:
        om.MGlobal.displayError(f"[LOG ERROR] El personaje '{character_name}' no está en el JSON.")
        return None

    
    if guide_name is None:
        return character_data


