import maya.cmds as cmds
import maya.api.OpenMaya as om
from utils import data_manager
from utils import curve_tool
from utils import rig_manager
from utils import guides_manager
from importlib import reload

# Recarga de módulos para desarrollo
reload(data_manager)
reload(curve_tool)
reload(rig_manager)
reload(guides_manager)

def lock_attributes(ctl, attrs):
    """Bloquea y oculta atributos en un controlador."""
    for attr in attrs:
        cmds.setAttr(f"{ctl}.{attr}", lock=True, keyable=False, channelBox=False)

def create_basic_structure(character_name=None):
    """Crea la estructura del rig con control de visibilidad centralizado."""

    character_name, scene_assemblies = rig_manager.prepare_rig_scene()
    data_manager.DataExportBiped().append_data("basic_structure", {"character_name": character_name})

    structure_names = [character_name, "rig_GRP", "controls_GRP", "geo_GRP", "deformers_GRP"]
    nodes = {}

    for i, name in enumerate(structure_names):
        if cmds.objExists(name) or cmds.objExists(name.upper()) or cmds.objExists(name.lower()) or cmds.objExists(name.capitalize()):
            nodes[name] = name
        else:
            res = cmds.createNode("transform", name=name, ss=True)
            nodes[name] = res
            if i != 0:
                cmds.parent(res, nodes[character_name])


    def create_sub_geo(name, parent):
        if cmds.objExists(name): return name
        return cmds.createNode("transform", name=name, ss=True, p=parent)

    proxy = create_sub_geo("PROXY", nodes["geo_GRP"])
    final_geo = create_sub_geo("FINAL", nodes["geo_GRP"])
    local = create_sub_geo("LOCAL", nodes["geo_GRP"])
    
    cmds.setAttr(f"{local}.visibility", 0)

    for assembly in scene_assemblies:
        if cmds.objExists(assembly): 
            # Evitar re-emparentar si ya está ahí
            current_p = cmds.listRelatives(assembly, parent=True)
            if not current_p or current_p[0] != final_geo:
                try:
                    cmds.parent(assembly, final_geo)
                except:
                    pass

    # C_character
    if not cmds.objExists("C_character_CTL"):
        character_node, character_ctl = curve_tool.create_controller(name="C_character", offset=["GRP", "ANM"])
        try:
            cmds.parent(character_node[0], nodes["controls_GRP"])
        except:
            pass
    else:
        character_ctl = "C_character_CTL"
        character_node = [cmds.listRelatives(character_ctl, parent=True)[0]]

    # C_masterwalk
    if not cmds.objExists("C_masterwalk_CTL"):
        masterwalk_node, masterwalk_ctl = curve_tool.create_controller(name="C_masterwalk", offset=["GRP", "ANM"])
        try:
            cmds.parent(masterwalk_node[0], character_ctl)
        except:
            pass
    else:
        masterwalk_ctl = "C_masterwalk_CTL"
        masterwalk_node = [cmds.listRelatives(masterwalk_ctl, parent=True)[0]]

    # C_settings
    if not cmds.objExists("C_settings_CTL"):
        settings_node, settings_ctl = curve_tool.create_controller(name="C_settings", offset=["GRP"])
        try:
            cmds.parent(settings_node[0], character_ctl)
        except:
            pass
    else:
        settings_ctl = "C_settings_CTL"
        settings_node = [cmds.listRelatives(settings_ctl, parent=True)[0]]

    # 5. ATRIBUTOS (Solo si no existen)
    def add_attr_safe(node, **kwargs):
        if not cmds.attributeQuery(kwargs['longName'], node=node, exists=True):
            cmds.addAttr(node, **kwargs)

    add_attr_safe(settings_ctl, longName="GEO_SEP", niceName="GEOMETRY ------", attributeType="enum", enumName="------")
    cmds.setAttr(f"{settings_ctl}.GEO_SEP", keyable=False, channelBox=True, lock=True)
    
    add_attr_safe(settings_ctl, longName="geometryType", niceName="Geo Type", attributeType="enum", enumName="Final:Proxy", keyable=True)
    add_attr_safe(settings_ctl, longName="geoDisplay", niceName="Geo Display", attributeType="enum", enumName="Locked:Selectable:Off", keyable=True)
    add_attr_safe(settings_ctl, longName="geoSmooth", niceName="Geo Smooth", attributeType="float", defaultValue=0, minValue=0, maxValue=2, keyable=True)
    add_attr_safe(settings_ctl, longName="showSkeleton", niceName="Show Skeleton", attributeType="bool", defaultValue=True, keyable=True)
    add_attr_safe(settings_ctl, longName="showModules", niceName="Show Modules", attributeType="bool", defaultValue=True, keyable=True)
    add_attr_safe(settings_ctl, longName="hideControllersOnPlayblast", niceName="Hide Controllers on Playblast", attributeType="bool", defaultValue=True, keyable=True)

    # (Nota: He omitido la repetición de addAttr por brevedad, aplica add_attr_safe a los demás)

    # 6. LÓGICA DE CONEXIONES (Usar try/except o check para evitar errores de conexión existente)
    def safe_connect(src, dest):
        if not cmds.isConnected(src, dest):
            cmds.connectAttr(src, dest, f=True)

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
    

    # --- 6. LÓGICA DE CONEXIONES Y NODOS AUXILIARES ---

    def get_or_create(node_type, name, parent=None):
        if cmds.objExists(name):
            return name
        return cmds.createNode(node_type, name=name, ss=True)

    def safe_connect(src, dest):
        if not cmds.isConnected(src, dest):
            cmds.connectAttr(src, dest, f=True)

    # Reference (Override Display Type)
    # 0 = Locked, 1 = Selectable, 2 = Off
    ref_cond = get_or_create("condition", "C_reference_COND")
    cmds.setAttr(f"{ref_cond}.secondTerm", 0)
    cmds.setAttr(f"{ref_cond}.colorIfTrueR", 1)  # Selectable
    cmds.setAttr(f"{ref_cond}.colorIfFalseR", 2) # Locked
    safe_connect(f"{settings_ctl}.geoDisplay", f"{ref_cond}.firstTerm")

    ref_cond_vis = get_or_create("condition", "C_referenceVis_COND")
    cmds.setAttr(f"{ref_cond_vis}.secondTerm", 1)
    cmds.setAttr(f"{ref_cond_vis}.colorIfTrueR", 2) # Off
    cmds.setAttr(f"{ref_cond_vis}.colorIfFalseR", 1) # On
    safe_connect(f"{settings_ctl}.geoDisplay", f"{ref_cond_vis}.firstTerm")

    plus_minus_avg = get_or_create("plusMinusAverage", "C_settings_PMA")
    safe_connect(f"{ref_cond}.outColorR", f"{plus_minus_avg}.input1D[0]")
    safe_connect(f"{ref_cond_vis}.outColorR", f"{plus_minus_avg}.input1D[1]")

    # Aplicar al grupo de geometría real (nodes['geo_GRP'])
    geo_root = nodes["geo_GRP"]
    cmds.setAttr(f"{geo_root}.overrideEnabled", 1)
    safe_connect(f"{plus_minus_avg}.output1D", f"{geo_root}.overrideDisplayType")

    ref_off = get_or_create("condition", "C_referenceOff_COND")
    cmds.setAttr(f"{ref_off}.secondTerm", 2)
    cmds.setAttr(f"{ref_off}.colorIfTrueR", 0)  # Visibility Off
    cmds.setAttr(f"{ref_off}.colorIfFalseR", 1) # Visibility On
    safe_connect(f"{settings_ctl}.geoDisplay", f"{ref_off}.firstTerm")
    safe_connect(f"{ref_off}.outColorR", f"{geo_root}.visibility")
    
    # --- GEO SMOOTH ---
    all_meshes = cmds.ls(type="mesh", long=True, noIntermediate=True)
    mesh_transforms = list(set(cmds.listRelatives(all_meshes, parent=True, fullPath=True) or []))

    for mesh in mesh_transforms:
        m_name = mesh.split('|')[-1]
        cond_node = get_or_create("condition", f"{m_name}_smooth_COND")
        
        cmds.setAttr(f"{cond_node}.operation", 2) # Greater Than
        cmds.setAttr(f"{cond_node}.secondTerm", 0)
        
        safe_connect(f"{settings_ctl}.geoSmooth", f"{cond_node}.firstTerm")
        safe_connect(f"{settings_ctl}.geoSmooth", f"{cond_node}.colorIfTrueR")
        cmds.setAttr(f"{cond_node}.colorIfFalseR", 0)

        shapes = cmds.listRelatives(mesh, shapes=True, fullPath=True) or []
        for shape in shapes:
            safe_connect(f"{cond_node}.outColorR", f"{shape}.displaySmoothMesh")
            safe_connect(f"{settings_ctl}.geoSmooth", f"{shape}.smoothLevel")

    # --- PLAYBLAST HIDE ---
    pb_rev = get_or_create("reverse", "C_playblast_REV")
    safe_connect(f"{settings_ctl}.hideControllersOnPlayblast", f"{pb_rev}.inputX")
    # nodes["controls_GRP"] es la variable que definimos en la parte 1
    safe_connect(f"{pb_rev}.outputX", f"{nodes['controls_GRP']}.hideOnPlayback")

    # --- RIG VISIBILITY ---
    skel_grp = get_or_create("transform", "skel_GRP")
    if not cmds.listRelatives(skel_grp, parent=True):
        cmds.parent(skel_grp, nodes["rig_GRP"])
        
    modules_grp = get_or_create("transform", "modules_GRP")
    if not cmds.listRelatives(modules_grp, parent=True):
        cmds.parent(modules_grp, nodes["rig_GRP"])

    safe_connect(f"{settings_ctl}.showSkeleton", f"{skel_grp}.visibility")
    safe_connect(f"{settings_ctl}.showModules", f"{modules_grp}.visibility")

    cmds.setAttr(f"{settings_ctl}.showSkeleton", 0)
    cmds.setAttr(f"{settings_ctl}.showModules", 0)

    # --- 7. BLOQUEOS ---
    lock_attributes(character_ctl, ["tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz", "v"])
    lock_attributes(settings_ctl, ["tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz", "v"])
    
    # Global Scale en Masterwalk
    if not cmds.attributeQuery("globalScale", node=masterwalk_ctl, exists=True):
        cmds.addAttr(masterwalk_ctl, longName="GLOBAL_SCALE_SEP", niceName="EXTRA ATTRIBUTES ------", attributeType="enum", enumName="------")
        cmds.setAttr(f"{masterwalk_ctl}.GLOBAL_SCALE_SEP", keyable=False, channelBox=True, lock=True)
        cmds.addAttr(masterwalk_ctl, longName="globalScale", attributeType="float", defaultValue=1, minValue=0.01, keyable=True)
        for axis in ["X", "Y", "Z"]: 
            safe_connect(f"{masterwalk_ctl}.globalScale", f"{masterwalk_ctl}.scale{axis}")
    
    lock_attributes(masterwalk_ctl, ["sx", "sy", "sz", "v"])

    # --- 8. FREEZE JOINT ---
    freeze_jnt = get_or_create("joint", "C_freeze_JNT")
    if not cmds.listRelatives(freeze_jnt, parent=True):
        cmds.parent(freeze_jnt, skel_grp)

    mgear = data_manager.DataExportBiped().get_data("rig_settings", "mgear_integration")
    print(f"--- MGEAR INTEGRATION: {mgear} ---")
    if mgear:
        cmds.delete(nodes["controls_GRP"])

    # --- 9. EXPORTACIÓN ---
    data_manager.DataExportBiped().append_data("basic_structure", {
        "skel_GRP" : skel_grp,
        "modules_GRP" : modules_grp,
        "masterwalk_ctl" : masterwalk_ctl,
        "character_ctl" : character_ctl,
        "preferences_ctl" : settings_ctl,
        "rig_GRP" : nodes["rig_GRP"],
    })

    return character_name