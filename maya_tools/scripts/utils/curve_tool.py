import maya.cmds as cmds
import maya.api.OpenMaya as om
import json
import os
import math

# Intentamos importar tus utilidades. Si fallan, el script no se romperá inmediatamente,
# pero necesitarás que existan para que funcione la lógica de rutas automática.
try:
    from maya_tools.scripts.utils import rig_manager
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

def get_all_ctl_curves_data(path=None, root_filter=None):
    """
    Recopila datos de curvas de controladores.
    CENTRALIZACIÓN: Fuerza que el color y los overrides residan en el Transform
    para evitar que Maya seleccione el nodo Shape por error.
    """
    
    try:
        char_name = rig_manager.get_character_name_from_scene()
    except:
        char_name = "UnknownCharacter"

    if path:
        save_file_path = os.path.normpath(path)
    else:
        curves_name = f"{char_name}_v001"
        current_script_path = os.path.realpath(__file__)
        root_path = current_script_path.split("scripts")[0] 
        assets_path = os.path.join(root_path, "assets", char_name, "curves")
        
        if not os.path.exists(assets_path):
            try:
                os.makedirs(assets_path)
            except OSError:
                pass

        save_file_path = os.path.join(assets_path, f"{curves_name}.curves")

    ctl_data = {}
    transforms = []

    if root_filter and cmds.objExists(root_filter):
        found_nodes = cmds.listRelatives(root_filter, allDescendents=True, type="transform", fullPath=True) or []
        transforms = [t for t in found_nodes if t.endswith("_CTL")]
        om.MGlobal.displayInfo(f"--- Exportando bajo: '{root_filter}' ---")
    else:
        transforms = cmds.ls("*_CTL", type="transform", long=True)

    for transform_name in transforms:

        try:
            if cmds.attributeQuery('isCtl', node=transform_name, exists=True):
                continue
            if cmds.attributeQuery('isCurvesTag', node=transform_name, exists=True):
                continue
        except Exception:
            continue

        transform_dag = get_dag_path_safe(transform_name)
        if not transform_dag:
            continue

        transform_obj = transform_dag.node()

        trans_ov_enabled, trans_ov_color = get_override_info_safe(transform_obj)

        all_shapes = cmds.listRelatives(transform_name, shapes=True, fullPath=True) or []
        valid_shapes = []
        
        for shp in all_shapes:
            if cmds.nodeType(shp) == "nurbsCurve" and not cmds.getAttr(f"{shp}.intermediateObject"):
                valid_shapes.append(shp)

        if not valid_shapes:
            continue

        final_enabled = trans_ov_enabled
        final_color = trans_ov_color

        if not final_enabled:
            for shp in valid_shapes:
                s_dag = get_dag_path_safe(shp)
                s_enabled, s_color = get_override_info_safe(s_dag.node())
                if s_enabled:
                    final_enabled = True
                    final_color = s_color
                    break

        shape_data_list = []
        for shape_name in valid_shapes:
            try:
                shape_dag = get_dag_path_safe(shape_name)
                if not shape_dag: continue
                
                curve_fn = om.MFnNurbsCurve(shape_dag)
                
                cvs = []
                try:
                    points = curve_fn.cvPositions(om.MSpace.kObject)
                    for p in points: cvs.append((p.x, p.y, p.z))
                except:
                    for i in range(curve_fn.numCVs):
                        p = curve_fn.cvPosition(i, om.MSpace.kObject)
                        cvs.append((p.x, p.y, p.z))

                knots = list(curve_fn.knots())
                degree = curve_fn.degree
                form_map = {
                    om.MFnNurbsCurve.kOpen: "open",
                    om.MFnNurbsCurve.kClosed: "closed",
                    om.MFnNurbsCurve.kPeriodic: "periodic"
                }
                form = form_map.get(curve_fn.form, "unknown")
                shape_obj = shape_dag.node()
                try:
                    fn_dep = om.MFnDependencyNode(shape_obj)
                    always_on_top = fn_dep.findPlug('alwaysDrawOnTop', False).asBool()
                except:
                    always_on_top = False

                line_width = None
                if cmds.attributeQuery("lineWidth", node=shape_name, exists=True):
                    line_width = cmds.getAttr(f"{shape_name}.lineWidth")

                shape_data_list.append({
                    "name": shape_name.split("|")[-1],
                    "overrideEnabled": False, 
                    "overrideColor": 0,
                    "alwaysDrawOnTop": always_on_top,
                    "lineWidth": line_width,
                    "curve": {
                        "cvs": cvs,
                        "form": form,
                        "knots": knots,
                        "degree": degree
                    }
                })

            except Exception:
                continue

        if shape_data_list:
            ctl_data[transform_name] = {
                "transform": {
                    "name": transform_name.split("|")[-1],
                    "overrideEnabled": final_enabled,
                    "overrideColor": final_color
                },
                "shapes": shape_data_list
            }

    try:
        folder = os.path.dirname(save_file_path)
        if not os.path.exists(folder):
            os.makedirs(folder)
            
        with open(save_file_path, "w") as f:
            json.dump(ctl_data, f, indent=4)
        
        om.MGlobal.displayInfo(f"Success: Curves data exported to: {save_file_path}")
        
    except Exception as e:
        om.MGlobal.displayError(f"Error saving file: {e}")



def load_all_ctl_curves_data(path):
    """
    Applies saved curve shapes to existing controllers in the scene.
    Unlike build_curves_from_template, this does NOT create new transforms —
    it replaces the shapes on controllers that already exist.
    Skips mGear controllers (nodes with the isCtl attribute).
    """
    if not os.path.exists(path):
        om.MGlobal.displayError(f"Curves file not found: {path}")
        return

    with open(path, "r") as f:
        ctl_data = json.load(f)

    updated = 0
    skipped = 0

    for _transform_path, data in ctl_data.items():
        transform_info = data["transform"]
        short_name = transform_info["name"]

        existing = cmds.ls(short_name, type="transform")
        if not existing:
            skipped += 1
            continue

        transform_name = existing[0]

        try:
            if cmds.attributeQuery('isCtl', node=transform_name, exists=True):
                skipped += 1
                continue
            if cmds.attributeQuery('isCurvesTag', node=transform_name, exists=True):
                skipped += 1
                continue
        except Exception:
            skipped += 1
            continue

        # Remove existing non-intermediate nurbsCurve shapes
        old_shapes = cmds.listRelatives(transform_name, shapes=True, fullPath=True) or []
        for shp in old_shapes:
            try:
                if cmds.nodeType(shp) == "nurbsCurve" and not cmds.getAttr(f"{shp}.intermediateObject"):
                    cmds.delete(shp)
            except Exception:
                pass

        transform_dag = get_dag_path_safe(transform_name)
        if not transform_dag:
            skipped += 1
            continue
        transform_obj = transform_dag.node()

        if transform_info.get("overrideEnabled"):
            fn_dep = om.MFnDependencyNode(transform_obj)
            fn_dep.findPlug('overrideEnabled', False).setBool(True)
            fn_dep.findPlug('overrideColor', False).setInt(transform_info["overrideColor"])

        for shape_data in data["shapes"]:
            curve_info = shape_data["curve"]
            form_flags = {
                "open": om.MFnNurbsCurve.kOpen,
                "closed": om.MFnNurbsCurve.kClosed,
                "periodic": om.MFnNurbsCurve.kPeriodic
            }
            form_flag = form_flags.get(curve_info["form"], om.MFnNurbsCurve.kOpen)

            points = om.MPointArray()
            for pt in curve_info["cvs"]:
                points.append(om.MPoint(pt[0], pt[1], pt[2]))

            curve_fn = om.MFnNurbsCurve()
            shape_obj = curve_fn.create(
                points, curve_info["knots"], curve_info["degree"],
                form_flag, False, True, transform_obj
            )

            shape_fn = om.MFnDagNode(shape_obj)
            shape_fn.setName(shape_data["name"])

            if shape_data.get("overrideEnabled"):
                fn_dep = om.MFnDependencyNode(shape_obj)
                fn_dep.findPlug('overrideEnabled', False).setBool(True)
                fn_dep.findPlug('overrideColor', False).setInt(shape_data["overrideColor"])

            if shape_data.get("alwaysDrawOnTop", False):
                fn_dep = om.MFnDependencyNode(shape_obj)
                fn_dep.findPlug('alwaysDrawOnTop', False).setBool(True)

            line_width = shape_data.get("lineWidth")
            if line_width is not None:
                shape_name = shape_fn.name()
                if cmds.attributeQuery("lineWidth", node=shape_name, exists=True):
                    try:
                        cmds.setAttr(f"{shape_name}.lineWidth", line_width)
                    except Exception:
                        pass

        updated += 1

    om.MGlobal.displayInfo(f"Curves applied: {updated} updated, {skipped} skipped.")


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
    # la version mas reciente de la carpeta (por mtime); _v001 solo de fallback
    last_version = rig_manager.get_latest_version(TEMPLATE_PATH)
    if last_version and str(last_version).endswith(".curves"):
        TEMPLATE_FILE = str(last_version)
    else:
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


def lock_attributes(ctl, attrs):
    """
    Lock and hide attributes, updating rotateOrder to match visible rotations.
    Args:
        ctl (str): The name of the controller.
        attrs (list): A list of attributes to lock and hide.
    """
    transform_channels = {
        "translate": ("tx", "ty", "tz"), "t": ("tx", "ty", "tz"),
        "rotate": ("rx", "ry", "rz"), "r": ("rx", "ry", "rz"),
        "scale": ("sx", "sy", "sz"), "s": ("sx", "sy", "sz"),
    }
    for attr in attrs:
        for channel in transform_channels.get(attr, (attr,)):
            cmds.setAttr(f"{ctl}.{channel}", lock=True, keyable=False, channelBox=False)

    # Read the final channel state: modules can lock rotations after creation,
    # in several calls, and with either short or long attribute names.
    rotation_visible = any(
        cmds.getAttr(f"{ctl}.{attr}", keyable=True)
        or cmds.getAttr(f"{ctl}.{attr}", channelBox=True)
        for attr in ("rx", "ry", "rz")
    )
    cmds.setAttr(
        f"{ctl}.rotateOrder", keyable=False,
        channelBox=rotation_visible and not cmds.getAttr(f"{ctl}.rotateOrder", lock=True)
    )


def create_controller(name, offset=["GRP"], parent=None, locked_attrs=[], match=None, matrix=None):
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
            # Saved CVs already include the artist's final placement. Modules
            # must not apply offsets intended only for their fallback shape.
            cmds.addAttr(ctl[0], longName='autorigTemplateShape', attributeType='bool',
                         defaultValue=True, hidden=True)
        
        lock_attributes(ctl[0], locked_attrs or [])

        if created_grps:
            cmds.parent(ctl[0], created_grps[-1])
        if matrix:
            # matrix llega en world: a local del padre y al offsetParentMatrix,
            # canales a 0
            target = created_grps[0] if created_grps else ctl[0]
            m = om.MMatrix(matrix)
            target_parent = cmds.listRelatives(target, parent=True)
            if target_parent:
                m = m * om.MMatrix(cmds.getAttr(f"{target_parent[0]}.worldInverseMatrix[0]"))
            cmds.setAttr(f"{target}.offsetParentMatrix", list(m), type="matrix")
            cmds.xform(target, m=om.MMatrix.kIdentity)

        # shapes fuera del channel box
        for shape in cmds.listRelatives(ctl[0], shapes=True) or []:
            cmds.setAttr(f"{shape}.isHistoricallyInteresting", 0)

        return created_grps, ctl[0]
    

def create_text_shape(text, name="C_text_CTL", height=1.0, font=None):
    """Create a centered XY text controller with identity transform channels.

    All glyph outlines (including holes) become NURBS shapes on one transform.
    Height is the visible text height in scene units; spaces retain their layout.
    No character/build context is required. Return the actual unique Maya name.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Enter a letter or word.")
    height = float(height)
    if not math.isfinite(height) or height <= 0:
        raise ValueError("Text height must be a positive finite number.")
    if not isinstance(name, str) or not name.strip() or any(c in name for c in "|.\n\r"):
        raise ValueError("Enter a valid controller name without a DAG path.")

    previous_selection = cmds.ls(selection=True, long=True) or []
    root = None
    cmds.undoInfo(openChunk=True, chunkName="Create Text Controller")
    try:
        options = {"text": text, "constructionHistory": False}
        if font:
            options["font"] = font
        root = cmds.textCurves(**options)[0]
        root = cmds.rename(root, name.strip())
        shapes = cmds.listRelatives(root, allDescendents=True, type="nurbsCurve",
                                    fullPath=True) or []
        if not shapes:
            raise ValueError("The text/font produced no curve outlines.")
        bounds = cmds.exactWorldBoundingBox(root)
        visible_height = bounds[4] - bounds[1]
        if visible_height <= 1e-10:
            raise ValueError("The text/font produced no visible height.")
        center = [(bounds[i] + bounds[i + 3]) * 0.5 for i in range(3)]
        scale = height / visible_height
        for index, shape in enumerate(shapes, 1):
            # Keep each glyph's placement when removing its parent transform.
            positions = cmds.xform(shape + ".cv[*]", query=True, worldSpace=True,
                                   translation=True)
            shape = cmds.parent(shape, root, shape=True, relative=True)[0]
            shape = cmds.rename(shape, root.rsplit("|", 1)[-1] + "Shape%02d" % index)
            for cv in range(len(positions) // 3):
                point = [(positions[3 * cv + axis] - center[axis]) * scale
                         for axis in range(3)]
                cmds.xform("%s.cv[%d]" % (shape, cv), objectSpace=True,
                           translation=point)
        children = cmds.listRelatives(root, children=True, type="transform",
                                      fullPath=True) or []
        if children:
            cmds.delete(children)
        cmds.select(root, replace=True)
        return root
    except Exception:
        if root and cmds.objExists(root):
            cmds.delete(root)
        if previous_selection:
            cmds.select(previous_selection, replace=True)
        else:
            cmds.select(clear=True)
        raise
    finally:
        cmds.undoInfo(closeChunk=True)


def text_curve(ctl_name, letter=None):
    """
    Creates a text curve for a given controller name and letter.

    Args:
        ctl_name (str): The name of the controller.
        letter (str): The letter to use for the text curve.

    Returns:
        str: The name of the created text curve.
    """
    CHARACTER_NAME = rig_manager.get_character_name_from_build()
    letter = letter or CHARACTER_NAME[0].upper()
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

def mirror_shapes(controllers=None):
    """Mirror L_ controller shapes to R_ using the puiastre adaptation."""
    from maya_tools.scripts.utils.controller_shapes import mirror_shapes as mirror
    return mirror(controllers)


def mirror_curves():
    """Compatibility entry point for the transform-preserving shape mirror."""
    return mirror_shapes()


def replace_shape_colored():
    """Copy the first selected controller's shapes to subsequent targets."""
    from maya_tools.scripts.utils.controller_shapes import replace_shape_colored as replace
    return replace()


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
    """Compatibility entry point for selection-based shape replacement."""
    return replace_shape_colored()


def tag_scene_curves():
    """
    Adds a isCurvesTag boolean attribute to every *_CTL transform currently
    in the scene. Call this before saving the model so those curves are
    ignored by get_all_ctl_curves_data and load_all_ctl_curves_data.
    """
    transforms = cmds.ls("*_CTL", type="transform", long=True) or []
    tagged = 0

    for t in transforms:
        try:
            if not cmds.attributeQuery('isCurvesTag', node=t, exists=True):
                cmds.addAttr(t, longName='isCurvesTag', attributeType='bool', defaultValue=True)
                cmds.setAttr(f"{t}.isCurvesTag", True, lock=True)
            tagged += 1
        except Exception:
            continue

    om.MGlobal.displayInfo(f"tag_scene_curves: {tagged} controllers tagged.")

