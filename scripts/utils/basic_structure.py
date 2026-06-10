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

def create_basic_structure(character_name=None):

    # data_manager.DataExportBiped().new_build()
    print("--- CREATING BASIC STRUCTURE ---")

    character_name, scene_assemblies = rig_manager.prepare_rig_scene()
    data_manager.DataExportBiped().append_data("basic_structure", {"character_name": character_name})
    mgear = data_manager.DataExportBiped().get_data("rig_settings", "mGear_integration")

    # ─────────────────────────────────────────
    # MGEAR PATH
    # ─────────────────────────────────────────
    if mgear:

        masterwalk_ctl  = "masterWalk"
        character_ctl   = "C_global_CTL"
        settings_ctl    = "C_settings_CTL"  # lo creamos igualmente, lo metemos bajo global_C0_root
        rig_grp         = "setup"
        skel_grp        = "jnt_org"
        geo_grp         = "geo"
        modules_grp     = "modules_GRP"     # lo creamos bajo setup

        # Validar que los nodos de mGear existen
        for node in [masterwalk_ctl, character_ctl, rig_grp, skel_grp, geo_grp]:
            if not cmds.objExists(node):
                cmds.warning(f"mGear node '{node}' not found. Switching to standard build.")
                mgear = False
                break

    # ─────────────────────────────────────────
    # STANDARD PATH
    # ─────────────────────────────────────────
    if not mgear:

        structure_names = [character_name, "rig_GRP", "controls_GRP", "geo_GRP", "deformers_GRP"]
        nodes = {}

        for i, name in enumerate(structure_names):
            if any(cmds.objExists(n) for n in [name, name.upper(), name.lower(), name.capitalize()]):
                nodes[name] = name
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

        for assembly in scene_assemblies:
            if cmds.objExists(assembly):
                current_p = cmds.listRelatives(assembly, parent=True)
                if not current_p or current_p[0] != final_geo:
                    try: cmds.parent(assembly, final_geo)
                    except: pass

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
    add_attr_safe(settings_ctl, longName="PLAYBLAST_SEP", niceName="PLAYBLAST ------", attributeType="enum", enumName="------")
    cmds.setAttr(f"{settings_ctl}.PLAYBLAST_SEP", keyable=False, channelBox=True, lock=True)
    add_attr_safe(settings_ctl, longName="hideControllersOnPlayblast", niceName="Hide Controllers on Playblast", attributeType="bool", defaultValue=True, keyable=True)
    cmds.setAttr(f"{settings_ctl}.showSkeleton", lock=False, keyable=False, channelBox=True)
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
    safe_connect(f"{settings_ctl}.showModules",  f"{modules_grp}.visibility")
    cmds.setAttr(f"{settings_ctl}.showSkeleton", 0)
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