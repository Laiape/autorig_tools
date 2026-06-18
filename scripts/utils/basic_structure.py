import maya.cmds as cmds
import maya.api.OpenMaya as om
from utils import data_manager
from utils import curve_tool
from utils import rig_manager
from utils import guides_manager
from importlib import reload

reload(data_manager)
reload(curve_tool)
reload(rig_manager)
reload(guides_manager)

def lock_attributes(ctl, attrs):
    for attr in attrs:
        cmds.setAttr(f"{ctl}.{attr}", lock=True, keyable=False, channelBox=False)


def _suspend_eval():
    """
    Suspende refresco y evaluation manager para operaciones en bloque (p.ej.
    reparentar cientos de nodos de geo). Devuelve un callable que restaura el
    estado previo. En headless (sin viewport) el suspend es no-op, así que es
    seguro llamarlo siempre.
    """
    prev = {}
    try:
        prev["em"] = (cmds.evaluationManager(q=True, mode=True) or ["parallel"])[0]
        cmds.evaluationManager(mode="off")
    except Exception:
        prev["em"] = None
    try:
        cmds.refresh(suspend=True)
        prev["refresh"] = True
    except Exception:
        prev["refresh"] = False

    def restore():
        if prev.get("refresh"):
            try: cmds.refresh(suspend=False)
            except Exception: pass
        if prev.get("em"):
            try: cmds.evaluationManager(mode=prev["em"])
            except Exception: pass

    return restore


def _parent_model_under_final(main_xf, geo_grp, final_geo, character_name):
    """
    Organiza TODO el contenido del modelo bajo geo_GRP: lo que cuelga del main
    transform (cuando el root del modelo se reutiliza como main) y las mallas /
    grupos sueltos a nivel raíz. Excluye estructura de rig, controladores, cámaras
    por defecto y guías, y evita el ciclo de emparentar el propio main transform.

    Enruta por tipo según el nombre:
        - hueso/esqueleto (skel/_BONE/_SKEL)  -> geo_GRP/skeleton_GRP
        - músculo (muscle/_MSCL)              -> geo_GRP/muscles_GRP
        - el resto (render geo)               -> geo_GRP/FINAL
    Los buckets _GRP solo se crean si hay contenido de ese tipo; si el modelo ya
    trae un grupo con ese nombre (p.ej. skeleton_GRP) se reutiliza. Además se crea
    un renderGeo_GRP vacío (placeholder de la copia de render). Sesión rápida.
    """
    def short(n):
        return n.rsplit("|", 1)[-1]

    rig_sys = {character_name, "rig_GRP", "controls_GRP", "geo_GRP", "deformers_GRP",
               "skel_GRP", "modules_GRP", "PROXY", "FINAL", "LOCAL"}
    rig_prefixes = ("C_character", "C_masterwalk", "C_settings", "C_freeze")
    default_cams = {"persp", "top", "front", "side"}
    ignore = {"C_guides_GRP", "Mechanic_sets_grp"}

    def is_rig_or_system(node):
        s = short(node)
        if s in rig_sys or s in default_cams or s in ignore:
            return True
        if any(s.startswith(p) for p in rig_prefixes):
            return True
        if cmds.listRelatives(node, type="camera", noIntermediate=True):
            return True
        return False

    geo_roots = []
    for c in (cmds.listRelatives(main_xf, children=True, type="transform", fullPath=True) or []):
        if not is_rig_or_system(c):
            geo_roots.append(c)
    for a in (cmds.ls(assemblies=True, transforms=True, long=True) or []):
        if short(a) == short(main_xf):
            continue
        if not is_rig_or_system(a):
            geo_roots.append(a)

    geo_roots = [g for g in geo_roots if cmds.objExists(g)]
    if not geo_roots:
        return {}

    def is_skeleton(node):
        s = short(node).lower()
        return ("skel" in s) or s.endswith("_bone")

    def is_muscle(node):
        s = short(node).lower()
        return ("muscle" in s) or s.endswith("_mscl")

    def bulk_parent(nodes_list, dest):
        nodes_list = [n for n in nodes_list if cmds.objExists(n)]
        if not nodes_list:
            return 0
        try:  # en bloque (rápido); fallback a uno a uno
            cmds.parent(*(nodes_list + [dest]))
        except Exception:
            for n in nodes_list:
                try: cmds.parent(n, dest)
                except Exception: pass
        return len(nodes_list)

    skeleton_nodes = [g for g in geo_roots if is_skeleton(g)]
    muscle_nodes   = [g for g in geo_roots if is_muscle(g) and not is_skeleton(g)]
    render_nodes   = [g for g in geo_roots if g not in skeleton_nodes and g not in muscle_nodes]

    def get_bucket(name):
        for k in (cmds.listRelatives(geo_grp, children=True, type="transform", fullPath=True) or []):
            if short(k) == name:
                return k
        match = cmds.ls(name, type="transform", long=True) or []
        if match:
            try: return cmds.parent(match[0], geo_grp)[0]
            except Exception: pass
        return cmds.createNode("transform", name=name, ss=True, p=geo_grp)

    moved = {}
    restore = _suspend_eval()
    try:
        if skeleton_nodes:
            bucket = get_bucket("skeleton_GRP")
            others = [g for g in skeleton_nodes if short(g) != "skeleton_GRP"]
            moved["skeleton"] = bulk_parent(others, bucket)
        if muscle_nodes:
            bucket = get_bucket("muscles_GRP")
            others = [g for g in muscle_nodes if short(g) != "muscles_GRP"]
            moved["muscles"] = bulk_parent(others, bucket)

        final_count = 0
        for g in render_nodes:
            if not cmds.objExists(g):
                continue
            kids = cmds.listRelatives(g, children=True, type="transform", fullPath=True) or []
            if "render" in short(g).lower() and kids:
                final_count += bulk_parent(kids, final_geo)
                if not (cmds.listRelatives(g, children=True) or []):
                    try: cmds.delete(g)
                    except Exception: pass
            else:
                final_count += bulk_parent([g], final_geo)
        if final_count:
            moved["FINAL"] = final_count

        if not any(short(k) == "renderGeo_GRP"
                   for k in (cmds.listRelatives(geo_grp, children=True, type="transform", fullPath=True) or [])):
            cmds.createNode("transform", name="renderGeo_GRP", ss=True, p=geo_grp)
    finally:
        restore()

    return moved

def _create_display_layers(geo_grp):
    """
    Crea display layers para la geo organizada y prepara las capas de AdonisFX.
    Solo actúa si existen los grupos 'muscles_GRP' y 'skeleton_GRP' bajo geo_GRP.
    Las layers van con nombre LIMPIO (los transforms llevan _GRP, así no chocan):

        - muscles_GRP   -> layer 'muscles' (ROJO)
        - skeleton_GRP  -> layer 'skeleton'
        - renderGeo_GRP -> layer 'renderGeo'
        - AdonisFX: transform 'mummy_GRP' + layer 'mummy', y layers 'fat'/'skin'/
          'fascia' SOLO si existen nodos de esa capa en la escena.
    """
    def child_path(name):
        for k in (cmds.listRelatives(geo_grp, children=True, type="transform", fullPath=True) or []):
            if k.rsplit("|", 1)[-1] == name:
                return k
        return None

    muscles = child_path("muscles_GRP")
    skeleton = child_path("skeleton_GRP")
    if not (muscles and skeleton):
        return  # sin muscles_GRP+skeleton_GRP no se crean layers

    def get_layer(name):
        if cmds.objExists(name) and cmds.nodeType(name) == "displayLayer":
            return name
        return cmds.createDisplayLayer(name=name, empty=True)

    def layer_add(name, members, color_index=None):
        members = [m for m in members if m and cmds.objExists(m)]
        lyr = get_layer(name)
        if members:
            cmds.editDisplayLayerMembers(lyr, *members, noRecurse=True)
        if color_index is not None:
            try: cmds.setAttr(f"{lyr}.color", color_index)
            except Exception: pass
        return lyr

    RED = 13  # índice de color rojo de Maya
    YELLOW = 17
    GREEN = 14
    BLUE = 6

    # ----- Layers de geo -----
    layer_add("muscles", [muscles], color_index=RED)
    layer_add("skeleton", [skeleton], color_index=YELLOW)
    render = child_path("renderGeo_GRP")
    

    # ----- AdonisFX -----
    def find_adonis(term):
        wanted = {term, f"{term}_grp", f"{term}grp", f"{term}_geo"}
        return [t for t in (cmds.ls(type="transform", long=True) or [])
                if t.rsplit("|", 1)[-1].lower() in wanted]

    mummy = child_path("mummy_GRP")
    if not mummy:
        mummy = cmds.createNode("transform", name="mummy_GRP", ss=True, p=geo_grp)
    layer_add("mummy", [mummy] + find_adonis("mummy"), color_index=GREEN)

    if render:
        layer_add("renderGeo", [render], color_index=BLUE)

    for term in ("fat", "skin", "fascia"):
        nodes = find_adonis(term)
        if nodes:
            layer_add(term, nodes)


def create_basic_structure(character_name=None):

    character_name, scene_assemblies = rig_manager.prepare_rig_scene()
    data_manager.DataExportBiped().append_data("basic_structure", {"character_name": character_name})
    mgear = data_manager.DataExportBiped().get_data("rig_settings", "mGear_integration")

    if mgear:

        masterwalk_ctl  = "masterWalk"
        character_ctl   = "C_global_CTL"
        settings_ctl    = "C_settings_CTL"
        rig_grp         = "setup"
        skel_grp        = "jnt_org"
        geo_grp         = "geo"
        modules_grp     = "modules_GRP"

        # Validar que los nodos de mGear existen
        for node in [masterwalk_ctl, character_ctl, rig_grp, skel_grp, geo_grp]:
            if not cmds.objExists(node):
                cmds.warning(f"mGear node '{node}' not found. Switching to standard build.")
                mgear = False
                break

    if not mgear:

        structure_names = [character_name, "rig_GRP", "controls_GRP", "geo_GRP", "deformers_GRP"]
        nodes = {}

        for i, name in enumerate(structure_names):
            existing = next((n for n in [name, name.upper(), name.lower(), name.capitalize()] if cmds.objExists(n)), None)
            if existing:
                nodes[name] = existing  # guarda la variante REAL (p.ej. "Jamal")
            else:
                res = cmds.createNode("transform", name=name, ss=True)
                nodes[name] = res
                if i != 0:
                    cmds.parent(res, nodes[character_name])

        def create_sub_geo(name, parent):
            if cmds.objExists(name): return name
            return cmds.createNode("transform", name=name, ss=True, p=parent)

        proxy     = create_sub_geo("PROXY",  nodes["geo_GRP"])
        final_geo = create_sub_geo("FINAL",  nodes["geo_GRP"])
        local     = create_sub_geo("LOCAL",  nodes["geo_GRP"])
        cmds.setAttr(f"{local}.visibility", 0)

        moved = _parent_model_under_final(nodes[character_name], nodes["geo_GRP"], final_geo, character_name)
        print(f"--- Geo organizada en geo_GRP: {moved} ---")
        _create_display_layers(nodes["geo_GRP"])

        # Controllers
        if not cmds.objExists("C_character_CTL"):
            character_node, character_ctl = curve_tool.create_controller(name="C_character", offset=["GRP", "ANM"])
            try: cmds.parent(character_node[0], nodes["controls_GRP"])
            except: pass
        else:
            character_ctl  = "C_character_CTL"
            character_node = [cmds.listRelatives(character_ctl, parent=True)[0]]

        if not cmds.objExists("C_masterwalk_CTL"):
            masterwalk_node, masterwalk_ctl = curve_tool.create_controller(name="C_masterwalk", offset=["GRP", "ANM"])
            try: cmds.parent(masterwalk_node[0], character_ctl)
            except: pass
        else:
            masterwalk_ctl  = "C_masterwalk_CTL"
            masterwalk_node = [cmds.listRelatives(masterwalk_ctl, parent=True)[0]]

        if not cmds.objExists("C_settings_CTL"):
            settings_node, settings_ctl = curve_tool.create_controller(name="C_settings", offset=["GRP"])
            try: cmds.parent(settings_node[0], character_ctl)
            except: pass
        else:
            settings_ctl  = "C_settings_CTL"
            settings_node = [cmds.listRelatives(settings_ctl, parent=True)[0]]

        rig_grp   = nodes["rig_GRP"]
        geo_grp   = nodes["geo_GRP"]

    # ─────────────────────────────────────────
    # SHARED: settings_ctl + modules_grp + skel_grp (ambos paths)
    # ─────────────────────────────────────────

    def get_or_create(node_type, name, parent=None):
        if cmds.objExists(name): return name
        node = cmds.createNode(node_type, name=name, ss=True)
        if parent and not cmds.listRelatives(node, parent=True):
            cmds.parent(node, parent)
        return node

    def safe_connect(src, dest):
        if not cmds.isConnected(src, dest):
            cmds.connectAttr(src, dest, f=True)

    def add_attr_safe(node, **kwargs):
        if not cmds.attributeQuery(kwargs['longName'], node=node, exists=True):
            cmds.addAttr(node, **kwargs)

    # Settings CTL (en mGear lo creamos bajo global_C0_root)
    if mgear and not cmds.objExists("C_settings_CTL"):
        settings_node, settings_ctl = curve_tool.create_controller(name="C_settings", offset=["GRP"])
        cmds.parent(settings_node[0], character_ctl)

    # modules_GRP y skel_GRP
    if mgear:
        skel_grp    = get_or_create("transform", "jnt_org")        # ya existe en mGear
        modules_grp = get_or_create("transform", "modules_GRP", parent=rig_grp)
        geo_grp     = "geo"
        final_geo   = get_or_create("transform", "FINAL", parent=geo_grp)
        proxy       = get_or_create("transform", "PROXY", parent=geo_grp)
    else:
        skel_grp    = get_or_create("transform", "skel_GRP", parent=rig_grp)
        modules_grp = get_or_create("transform", "modules_GRP", parent=rig_grp)
        skeleton_grp = get_or_create("transform", "skeletonHierarchy_GRP", parent=rig_grp)

    # globalScale en masterwalk (ambos paths)
    if not cmds.attributeQuery("globalScale", node=masterwalk_ctl, exists=True):
        cmds.addAttr(masterwalk_ctl, longName="GLOBAL_SCALE_SEP", niceName="EXTRA ATTRIBUTES ------", attributeType="enum", enumName="------")
        cmds.setAttr(f"{masterwalk_ctl}.GLOBAL_SCALE_SEP", keyable=False, channelBox=True, lock=True)
        cmds.addAttr(masterwalk_ctl, longName="globalScale", attributeType="float", defaultValue=1, minValue=0.01, keyable=True)
        for axis in ["X", "Y", "Z"]:
            safe_connect(f"{masterwalk_ctl}.globalScale", f"{masterwalk_ctl}.scale{axis}")

    # ─────────────────────────────────────────
    # SHARED: Atributos settings_ctl
    # ─────────────────────────────────────────
    add_attr_safe(settings_ctl, longName="GEO_SEP", niceName="GEOMETRY ------", attributeType="enum", enumName="------")
    cmds.setAttr(f"{settings_ctl}.GEO_SEP", keyable=False, channelBox=True, lock=True)
    add_attr_safe(settings_ctl, longName="geometryType", niceName="Type", attributeType="enum", enumName="Final:Proxy", keyable=True)
    add_attr_safe(settings_ctl, longName="geoDisplay", niceName="Display", attributeType="enum", enumName="Locked:Selectable:Off", keyable=True)
    add_attr_safe(settings_ctl, longName="RIG_SEP", niceName="RIG ------", attributeType="enum", enumName="------")
    cmds.setAttr(f"{settings_ctl}.RIG_SEP", keyable=False, channelBox=True, lock=True)
    add_attr_safe(settings_ctl, longName="showModules", niceName="Show Modules", attributeType="bool", defaultValue=True, keyable=True)
    add_attr_safe(settings_ctl, longName="showSkeleton", niceName="Show Skeleton", attributeType="bool", defaultValue=True, keyable=True)
    add_attr_safe(settings_ctl, longName="showSkeletonHierarchy", niceName="Show Skeleton Hierarchy", attributeType="bool", defaultValue=True, keyable=True)
    add_attr_safe(settings_ctl, longName="PLAYBLAST_SEP", niceName="PLAYBLAST ------", attributeType="enum", enumName="------")
    cmds.setAttr(f"{settings_ctl}.PLAYBLAST_SEP", keyable=False, channelBox=True, lock=True)
    add_attr_safe(settings_ctl, longName="hideControllersOnPlayblast", niceName="Hide Controllers on Playblast", attributeType="bool", defaultValue=True, keyable=True)
    cmds.setAttr(f"{settings_ctl}.showSkeleton", lock=False, keyable=False, channelBox=True)
    cmds.setAttr(f"{settings_ctl}.showSkeletonHierarchy", lock=False, keyable=False, channelBox=True)
    cmds.setAttr(f"{settings_ctl}.showModules", lock=False, keyable=False, channelBox=True)
    cmds.setAttr(f"{settings_ctl}.hideControllersOnPlayblast", lock=False, keyable=False, channelBox=True)
    cmds.setAttr(f"{settings_ctl}.geometryType", lock=False, keyable=False, channelBox=True)
    cmds.setAttr(f"{settings_ctl}.geoDisplay", lock=False, keyable=False, channelBox=True)

    # ─────────────────────────────────────────
    # SHARED: Conexiones geo visibility
    # ─────────────────────────────────────────
    if not cmds.objExists("C_geoVis_COND"):
        geo_cond = cmds.createNode("condition", name="C_geoVis_COND", ss=True)
        cmds.setAttr(f"{geo_cond}.secondTerm", 0)
        cmds.connectAttr(f"{settings_ctl}.geometryType", f"{geo_cond}.firstTerm")
        cmds.setAttr(f"{geo_cond}.colorIfTrueR", 1)
        cmds.setAttr(f"{geo_cond}.colorIfTrueG", 0)
        cmds.setAttr(f"{geo_cond}.colorIfFalseR", 0)
        cmds.setAttr(f"{geo_cond}.colorIfFalseG", 1)
        safe_connect(f"{geo_cond}.outColorR", f"{final_geo}.visibility")
        safe_connect(f"{geo_cond}.outColorG", f"{proxy}.visibility")

    ref_cond = get_or_create("condition", "C_reference_COND")
    cmds.setAttr(f"{ref_cond}.secondTerm", 0)
    cmds.setAttr(f"{ref_cond}.colorIfTrueR", 1)
    cmds.setAttr(f"{ref_cond}.colorIfFalseR", 2)
    safe_connect(f"{settings_ctl}.geoDisplay", f"{ref_cond}.firstTerm")

    ref_cond_vis = get_or_create("condition", "C_referenceVis_COND")
    cmds.setAttr(f"{ref_cond_vis}.secondTerm", 1)
    cmds.setAttr(f"{ref_cond_vis}.colorIfTrueR", 2)
    cmds.setAttr(f"{ref_cond_vis}.colorIfFalseR", 1)
    safe_connect(f"{settings_ctl}.geoDisplay", f"{ref_cond_vis}.firstTerm")

    plus_minus_avg = get_or_create("plusMinusAverage", "C_settings_PMA")
    safe_connect(f"{ref_cond}.outColorR",     f"{plus_minus_avg}.input1D[0]")
    safe_connect(f"{ref_cond_vis}.outColorR", f"{plus_minus_avg}.input1D[1]")

    cmds.setAttr(f"{geo_grp}.overrideEnabled", 1)
    safe_connect(f"{plus_minus_avg}.output1D", f"{geo_grp}.overrideDisplayType")

    ref_off = get_or_create("condition", "C_referenceOff_COND")
    cmds.setAttr(f"{ref_off}.secondTerm", 2)
    cmds.setAttr(f"{ref_off}.colorIfTrueR", 0)
    cmds.setAttr(f"{ref_off}.colorIfFalseR", 1)
    safe_connect(f"{settings_ctl}.geoDisplay", f"{ref_off}.firstTerm")
    safe_connect(f"{ref_off}.outColorR", f"{geo_grp}.visibility")


    # --- PLAYBLAST HIDE ---
    pb_rev = get_or_create("reverse", "C_playblast_REV")
    safe_connect(f"{settings_ctl}.hideControllersOnPlayblast", f"{pb_rev}.inputX")
    # En mGear el grupo de controls es global_C0_root, en standard es controls_GRP
    controls_grp_for_playblast = character_ctl if mgear else nodes["controls_GRP"]
    safe_connect(f"{pb_rev}.outputX", f"{controls_grp_for_playblast}.hideOnPlayback")

    # --- RIG VISIBILITY ---
    safe_connect(f"{settings_ctl}.showSkeleton", f"{skel_grp}.visibility")
    safe_connect(f"{settings_ctl}.showSkeletonHierarchy", f"{skel_grp}.visibility")
    safe_connect(f"{settings_ctl}.showModules",  f"{modules_grp}.visibility")
    cmds.setAttr(f"{settings_ctl}.showSkeleton", 0)
    cmds.setAttr(f"{settings_ctl}.showSkeletonHierarchy", 0)
    cmds.setAttr(f"{settings_ctl}.showModules",  0)

    # --- LOCKS ---
    if not mgear:
        lock_attributes(character_ctl, ["tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz", "v"])
    lock_attributes(settings_ctl,  ["tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz", "v"])
    lock_attributes(masterwalk_ctl, ["sx", "sy", "sz", "v"])

    # --- FREEZE JOINT ---
    freeze_jnt = get_or_create("joint", "C_freeze_JNT")
    if not cmds.listRelatives(freeze_jnt, parent=True):
        cmds.parent(freeze_jnt, skel_grp)

    # ─────────────────────────────────────────
    # EXPORT
    # ─────────────────────────────────────────
    print(f"--- MGEAR INTEGRATION: {mgear} ---")

    data_manager.DataExportBiped().append_data("basic_structure", {
        "skel_GRP"       : skel_grp,
        "modules_GRP"    : modules_grp,
        "masterwalk_ctl" : masterwalk_ctl,
        "character_ctl"  : character_ctl,
        "preferences_ctl": settings_ctl,
        "rig_GRP"        : rig_grp,
    })

    return character_name