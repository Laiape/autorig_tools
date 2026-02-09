import maya.cmds as cmds
import maya.api.OpenMaya as om
import json
import os

# Intentamos importar tus utilidades. Si fallan, el script no se romperá inmediatamente,
# pero necesitarás que existan para que funcione la lógica de rutas automática.
try:
    from utils import rig_manager
except ImportError:
    print("Warning: 'utils.rig_manager' no encontrado. Asegúrate de pasar 'path' manual o tener el módulo accesible.")

# -----------------------------------------------------------------------------
# FUNCIONES AUXILIARES (Robustas contra nodos 'zombies' de mGear)
# -----------------------------------------------------------------------------

def get_override_info_safe(m_obj):
    """
    Intenta obtener la información de override de un MObject.
    Si el objeto es inválido o mGear lo ha desconectado internamente,
    devuelve valores por defecto en lugar de crashear.
    """
    try:
        fn_dep = om.MFnDependencyNode(m_obj)
        # Usamos findPlug con false para no crear atributos si no existen
        plug_enabled = fn_dep.findPlug('overrideEnabled', False)
        
        if not plug_enabled.isNull and plug_enabled.asBool():
            plug_color = fn_dep.findPlug('overrideColor', False)
            color_val = plug_color.asInt() if not plug_color.isNull else 0
            return True, color_val
        
        return False, None
    except RuntimeError:
        # Si la API falla al leer el nodo, asumimos que no tiene overrides
        return False, None

def get_dag_path_safe(node_name):
    """Convierte un nombre de nodo a MDagPath de forma segura."""
    sel = om.MSelectionList()
    try:
        sel.add(node_name)
        return sel.getDagPath(0)
    except RuntimeError:
        return None

# -----------------------------------------------------------------------------
# FUNCIÓN PRINCIPAL
# -----------------------------------------------------------------------------

def get_all_ctl_curves_data(path=None, root_filter=None):
    """
    Recopila datos de curvas de controladores.
    Args:
        path (str): Ruta de guardado manual.
        root_filter (str): Nombre de un grupo (ej: 'face_setup'). Si existe, solo exporta sus hijos.
    """
    
    # --- 1. CONFIGURACIÓN DE RUTAS Y NOMBRE ---
    try:
        char_name = rig_manager.get_character_name_from_scene()
    except:
        char_name = "UnknownCharacter"

    if path:
        save_file_path = os.path.normpath(path)
    else:
        # Lógica automática basada en tu estructura de carpetas
        curves_name = f"{char_name}_v001"
        current_script_path = os.path.realpath(__file__)
        # Asumiendo que este script está en /scripts/utils/ y queremos ir a /assets/
        root_path = current_script_path.split("scripts")[0] 
        assets_path = os.path.join(root_path, "assets", char_name, "curves")
        
        # Asegurar que el directorio existe
        if not os.path.exists(assets_path):
            try:
                os.makedirs(assets_path)
            except OSError:
                pass # Si no se puede crear, probablemente fallará al guardar, pero seguimos.

        save_file_path = os.path.join(assets_path, f"{curves_name}.curves")

    # --- 2. SELECCIÓN DE CONTROLADORES (FILTRADO) ---
    ctl_data = {}
    transforms = []

    if root_filter and cmds.objExists(root_filter):
        # Buscar solo dentro del grupo especificado
        found_nodes = cmds.listRelatives(root_filter, allDescendents=True, type="transform", fullPath=True) or []
        transforms = [t for t in found_nodes if t.endswith("_CTL")]
        om.MGlobal.displayInfo(f"--- Exportando controles bajo: '{root_filter}' ---")
    else:
        # Buscar en toda la escena
        transforms = cmds.ls("*_CTL", type="transform", long=True)
        om.MGlobal.displayInfo("--- Exportando TODOS los controles (_CTL) de la escena ---")

    # --- 3. PROCESAMIENTO DE DATOS ---
    for transform_name in transforms:
        
        # A. Obtener MDagPath del Transform
        transform_dag = get_dag_path_safe(transform_name)
        if not transform_dag:
            print(f"Skipping invalid transform: {transform_name}")
            continue
        
        transform_obj = transform_dag.node()

        # B. Obtener Overrides del Transform
        trans_ov_enabled, trans_ov_color = get_override_info_safe(transform_obj)

        # C. Buscar Shapes (Filtrando intermediate objects de mGear)
        # Usamos fullPath=True para evitar confusiones de nombres
        all_shapes = cmds.listRelatives(transform_name, shapes=True, fullPath=True) or []
        valid_shapes = []
        
        for shp in all_shapes:
            # Solo curvas NURBS y que NO sean objetos intermedios (fantasmas de mGear)
            if cmds.nodeType(shp) == "nurbsCurve" and not cmds.getAttr(f"{shp}.intermediateObject"):
                valid_shapes.append(shp)

        if not valid_shapes:
            continue

        shape_data_list = []

        # D. Procesar cada Shape
        for shape_name in valid_shapes:
            # -------------------------------------------------------------
            # BLOQUE DE SEGURIDAD MGEAR: Todo lo que toque la API va en try
            # -------------------------------------------------------------
            try:
                shape_dag = get_dag_path_safe(shape_name)
                if not shape_dag:
                    continue
                
                shape_obj = shape_dag.node()
                
                # 1. Overrides del Shape
                shp_ov_enabled, shp_ov_color = get_override_info_safe(shape_obj)

                # 2. Datos geométricos de la curva
                curve_fn = om.MFnNurbsCurve(shape_dag)
                
                # Obtener CVs (Intentamos en bloque, si falla, uno a uno)
                cvs = []
                try:
                    points = curve_fn.cvPositions(om.MSpace.kObject)
                    for p in points:
                        cvs.append((p.x, p.y, p.z))
                except:
                    for i in range(curve_fn.numCVs):
                        p = curve_fn.cvPosition(i, om.MSpace.kObject)
                        cvs.append((p.x, p.y, p.z))

                # 3. Datos de topología
                knots = list(curve_fn.knots())
                degree = curve_fn.degree
                
                form_map = {
                    om.MFnNurbsCurve.kOpen: "open",
                    om.MFnNurbsCurve.kClosed: "closed",
                    om.MFnNurbsCurve.kPeriodic: "periodic"
                }
                form = form_map.get(curve_fn.form, "unknown")

                # 4. Atributos extra (AlwaysOnTop, LineWidth)
                # AlwaysOnTop via API
                try:
                    fn_dep = om.MFnDependencyNode(shape_obj)
                    always_on_top = fn_dep.findPlug('alwaysDrawOnTop', False).asBool()
                except:
                    always_on_top = False

                # LineWidth via cmds (más seguro para atributos dinámicos)
                line_width = None
                if cmds.attributeQuery("lineWidth", node=shape_name, exists=True):
                    line_width = cmds.getAttr(f"{shape_name}.lineWidth")

                # Agregar datos a la lista
                shape_data_list.append({
                    "name": shape_name.split("|")[-1], # Nombre corto para el JSON
                    "overrideEnabled": shp_ov_enabled,
                    "overrideColor": shp_ov_color,
                    "alwaysDrawOnTop": always_on_top,
                    "lineWidth": line_width,
                    "curve": {
                        "cvs": cvs,
                        "form": form,
                        "knots": knots,
                        "degree": degree
                    }
                })

            except Exception as e:
                # Si falla este shape específico, lo ignoramos y seguimos con el siguiente.
                # Esto evita que una curva corrupta de mGear detenga todo el script.
                # print(f"Warning: Error procesando shape {shape_name}: {e}")
                continue

        # Solo añadimos el control si se logró extraer info de algún shape
        if shape_data_list:
            ctl_data[transform_name] = {
                "transform": {
                    "name": transform_name.split("|")[-1],
                    "overrideEnabled": trans_ov_enabled,
                    "overrideColor": trans_ov_color
                },
                "shapes": shape_data_list
            }

    # --- 4. GUARDADO DEL ARCHIVO ---
    try:
        folder = os.path.dirname(save_file_path)
        if not os.path.exists(folder):
            os.makedirs(folder)
            
        with open(save_file_path, "w") as f:
            json.dump(ctl_data, f, indent=4)
        
        om.MGlobal.displayInfo(f"Success: Curves saved to: {save_file_path}")
        
    except Exception as e:
        om.MGlobal.displayError(f"Error saving file: {e}")

# -----------------------------------------------------------------------------
# EJEMPLO DE USO (COMENTADO)
# -----------------------------------------------------------------------------
# Opción A: Exportar todo (filtrando automáticamente objetos corruptos de mGear)
# get_all_ctl_curves_data()

# Opción B: Exportar SOLO faciales
# get_all_ctl_curves_data(root_filter="face_setup_grp")

def build_curves_from_template(target_transform_name=None):
    """
    Builds controller curves from a predefined template JSON file.
    If a specific target transform name is provided, it filters the curves to only create those associated with that transform.
    If no target transform name is provided, it creates all curves defined in the template.
    Args:
        target_transform_name (str, optional): The name of the target transform to filter curves by. Defaults to None.
    Returns:
        list: A list of created transform names.
    """
    CHARACTER_NAME = rig_manager.get_character_name_from_build()

    # Set up the template file path
    complete_path = os.path.realpath(__file__)
    relative_path = complete_path.split("\scripts")[0]
    path = os.path.join(relative_path, "assets")
    character_path = os.path.join(path, CHARACTER_NAME)
    TEMPLATE_PATH = os.path.join(character_path, "curves")
    last_version = rig_manager.get_latest_version(TEMPLATE_PATH)

    TEMPLATE_FILE = os.path.join(TEMPLATE_PATH, f"{CHARACTER_NAME}_v001.curves")


    if not os.path.exists(TEMPLATE_FILE):
        TEMPLATE_FILE = os.path.join(path, "-", "new", "curves", "new.curves")

    with open(TEMPLATE_FILE, "r") as f:
        ctl_data = json.load(f)

    if target_transform_name:
        ctl_data = {k: v for k, v in ctl_data.items() if v["transform"]["name"] == target_transform_name}
        if not ctl_data:
            return

    created_transforms = []

    for transform_path, data in ctl_data.items():
        transform_info = data["transform"]
        shape_data_list = data["shapes"]

        dag_modifier = om.MDagModifier()
        transform_obj = dag_modifier.createNode("transform")
        dag_modifier.doIt()

        transform_fn = om.MFnDagNode(transform_obj)
        final_name = transform_fn.setName(transform_info["name"])
        created_transforms.append(final_name)

        if transform_info["overrideEnabled"]:
            fn_dep = om.MFnDependencyNode(transform_obj)
            fn_dep.findPlug('overrideEnabled', False).setBool(True)
            fn_dep.findPlug('overrideColor', False).setInt(transform_info["overrideColor"])

        created_shapes = []

        for shape_data in shape_data_list:
            curve_info = shape_data["curve"]
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
            shape_fn.setName(shape_data["name"])

            if shape_data["overrideEnabled"]:
                fn_dep = om.MFnDependencyNode(shape_obj)
                fn_dep.findPlug('overrideEnabled', False).setBool(True)
                fn_dep.findPlug('overrideColor', False).setInt(shape_data["overrideColor"])

            if shape_data.get("alwaysDrawOnTop", False):
                fn_dep = om.MFnDependencyNode(shape_obj)
                fn_dep.findPlug('alwaysDrawOnTop', False).setBool(True)

            line_width = shape_data.get("lineWidth", None)
            if line_width is not None:
                if cmds.attributeQuery("lineWidth", node=shape_fn.name(), exists=True):
                    try:
                        cmds.setAttr(shape_fn.name() + ".lineWidth", line_width)
                    except:
                        om.MGlobal.displayWarning(f"Could not set lineWidth for {shape_fn.name()}")

            created_shapes.append(shape_obj)


    return created_transforms


def create_controller(name, offset=["GRP"], parent=None, locked_attrs=[], match=None):
    """
    Creates a controller with a specific name and offset transforms and returns the controller and the groups.

    Args:
        name (str): Name of the controller.
        suffixes (list): List of suffixes for the groups to be created. Default is ["GRP"].
    """

    created_grps = []
    if offset:
        for suffix in offset:
            if cmds.ls(f"{name}_{suffix}"):
                om.MGlobal.displayWarning(f"{name}_{suffix} already exists.")
                if created_grps:
                    cmds.delete(created_grps[0])
                return
            tra = cmds.createNode("transform", name=f"{name}_{suffix}", ss=True)
            if created_grps:
                cmds.parent(tra, created_grps[-1])
            created_grps.append(tra)
    if parent and created_grps:
        cmds.parent(created_grps[0], parent)
    if match and created_grps:
        cmds.matchTransform(created_grps[0], match, pos=True, rot=True, scl=False)

    if cmds.ls(f"{name}_CTL"):
        om.MGlobal.displayWarning(f"{name}_CTL already exists.")
        if created_grps:
            cmds.delete(created_grps[0])
        return
    else:
        
        ctl = build_curves_from_template(f"{name}_CTL")

        if not ctl:
            ctl = cmds.circle(name=f"{name}_CTL", ch=False)
        else:
            ctl = [ctl[0]]  # make sure ctl is a list with one element for consistency
        
        if locked_attrs:
            for attr in locked_attrs:
                cmds.setAttr(f"{ctl[0]}.{attr}", lock=True, keyable=False)

        if created_grps:
            cmds.parent(ctl[0], created_grps[-1])
        
        return created_grps, ctl[0]
    

def text_curve(ctl_name):
    """
    Creates a text curve for a given controller name and letter.

    Args:
        ctl_name (str): The name of the controller.
        letter (str): The letter to use for the text curve.

    Returns:
        str: The name of the created text curve.
    """
    CHARACTER_NAME = rig_manager.get_character_name_from_build()
    letter = CHARACTER_NAME[0].upper()
    text_curve = cmds.textCurves(ch=False, t=letter)
    text_curve = cmds.rename(text_curve, ctl_name)
    relatives = cmds.listRelatives(text_curve, allDescendents=True, type="nurbsCurve")
  
    for i, relative in enumerate(relatives):
        cmds.parent(relative, text_curve, r=True, shape=True)
        cmds.rename(relative, f"{ctl_name}Shape{i+1:02d}")
    relatives_transforms = cmds.listRelatives(text_curve, allDescendents=True, type="transform")
    cmds.delete(relatives_transforms)

    pivot_world = cmds.xform(text_curve, q=True, ws=True, rp=True)
    
    cvs = cmds.ls(text_curve + ".cv[*]", fl=True)
    
    positions = [cmds.pointPosition(cv, w=True) for cv in cvs]
    
    avg_x = sum(p[0] for p in positions) / len(positions)
    avg_y = sum(p[1] for p in positions) / len(positions)
    avg_z = sum(p[2] for p in positions) / len(positions)
    center_cvs = (avg_x, avg_y, avg_z)
    
    offset = [pivot_world[0] - center_cvs[0],
            pivot_world[1] - center_cvs[1],
            pivot_world[2] - center_cvs[2]]
    
    cmds.move(offset[0], offset[1], offset[2], cvs, r=True, ws=True)
    return ctl_name

def mirror_curves():
    """
    Espeja controladores del lado L al R escalando a -1 en X y aplicando Freeze.
    Lógica de colores: L(18) -> R(4), L(6) -> R(13).
    """
    # Buscamos controladores del lado L
    left_controllers = cmds.ls("L_*_CTL", type="transform")

    if not left_controllers:
        om.MGlobal.displayWarning("No se encontraron controladores con prefijo 'L_'.")
        return

    for l_ctl in left_controllers:
        r_ctl = l_ctl.replace("L_", "R_", 1)

        if not cmds.objExists(r_ctl):
            continue

        # --- OPERACIÓN DE ESPEJADO (Escala -1 y Freeze) ---
        # Guardamos el padre actual para no perder la jerarquía
        parent = cmds.listRelatives(r_ctl, parent=True)
        
        # Desparentamos temporalmente para que el freeze no afecte a la jerarquía superior
        if parent:
            cmds.parent(r_ctl, world=True)

        # Aplicamos escala negativa en X
        cmds.setAttr(f"{r_ctl}.scaleX", -1)
        
        # Freeze Transformations (aplica escala, rotación y traslación)
        cmds.makeIdentity(r_ctl, apply=True, t=1, r=1, s=1, n=0, pn=1)

        # Re-parentamos a su sitio original
        if parent:
            cmds.parent(r_ctl, parent[0])

        # --- LÓGICA DE COLORES ---
        if cmds.getAttr(f"{l_ctl}.overrideEnabled"):
            l_color = cmds.getAttr(f"{l_ctl}.overrideColor")
            r_color = None

            # Mapeo de colores: 18 -> 4 | 6 -> 13
            if l_color == 18:
                r_color = 4
            elif l_color == 6:
                r_color = 13
            
            if r_color is not None:
                cmds.setAttr(f"{r_ctl}.overrideEnabled", True)
                cmds.setAttr(f"{r_ctl}.overrideColor", r_color)

    om.MGlobal.displayInfo("Mirror completado: Escala -1 aplicada y transformaciones freezadas.")

    
def scale_selected_controller(value):

    """
    Scales the selected controller to a specific size.
    The user is prompted to enter the desired scale value.
    """

    selected = cmds.ls(selection=True, type="nurbsCurve")

    if not selected:
        om.MGlobal.displayError("Please select a controller to scale.")
        return
    
    if selected.endswith("_CTL"):

        ctl = selected[0]
        cvs = cmds.ls(f"{ctl}.cv[*]", flatten=True)
        if not cvs:
            om.MGlobal.displayError("No CVs found on the selected controller.")
            return
        
        for cv in cvs:
            cmds.scale(value, value, value, cv, relative=True, ocp=True)
    
    else:

        om.MGlobal.displayError("Please select a controller with the suffix '_CTL'.")
        return

def scale_all_controllers(value):

    """
    Scales all controllers in the scene to a specific size.
    The user is prompted to enter the desired scale value.
    """

    all_controllers = cmds.ls("*_CTL", type="nurbsCurve")

    if not all_controllers:
        om.MGlobal.displayError("No controllers found in the scene.")
        return
    
    for controller in all_controllers:
        cvs = cmds.ls(f"{controller}.cv[*]", flatten=True)
        if not cvs:
            om.MGlobal.displayError(f"No CVs found on the controller: {controller}.")
            continue
        
        for cv in cvs:
            cmds.scale(value, value, value, cv, relative=True, ocp=True)


def replace_shapes():   
    
    """
    Replaces the shapes of selected controllers with those from the template file.
    """
    pass
    



