import maya.cmds as cmds
import maya.api.OpenMaya as om
from biped.utils import data_manager
from biped.utils import curve_tool
from biped.utils import rig_manager
from biped.utils import guides_manager
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

    # 1. PREPARACIÓN
    character_name, imported_files = rig_manager.prepare_rig_scene()
    data_manager.DataExportBiped().append_data("basic_structure", {"character_name": character_name})

    # 2. NODOS
    nodes = [character_name, "rig_GRP", "controls_GRP", "geo_GRP", "deformers_GRP"]
    for i, node in enumerate(nodes):
        nod = cmds.createNode("transform", name=node, ss=True)
        if i != 0: cmds.parent(nod, nodes[0])

    # 3. GEOMETRÍA
    proxy = cmds.createNode("transform", name="PROXY", ss=True, p=nodes[3])
    final_geo = cmds.createNode("transform", name="FINAL", ss=True, p=nodes[3])
    local = cmds.createNode("transform", name="LOCAL", ss=True, p=nodes[3])
    
    # Ocultar LOCAL por defecto
    cmds.setAttr(f"{local}.visibility", 0)

    for imported_file in imported_files:
        if cmds.objExists(imported_file): cmds.parent(imported_file, final_geo)

    # 4. CONTROLES
    character_node, character_ctl = curve_tool.create_controller(name="C_character", offset=["GRP", "ANM"])
    masterwalk_node, masterwalk_ctl = curve_tool.create_controller(name="C_masterwalk", offset=["GRP", "ANM"])
    preferences_node, preferences_ctl = curve_tool.create_controller(name="C_preferences", offset=["GRP"])

    cmds.parent(character_node[0], nodes[2])
    cmds.parent(masterwalk_node[0], character_ctl)
    cmds.parent(preferences_node[0], masterwalk_ctl)

    # 5. ATRIBUTOS EN PREFERENCES
    
    # --- SECCIÓN GEO ---
    cmds.addAttr(preferences_ctl, longName="GEO_SEP", niceName="GEOMETRY", attributeType="enum", enumName="----")
    cmds.setAttr(f"{preferences_ctl}.GEO_SEP", keyable=False, channelBox=True, lock=True)

    cmds.addAttr(preferences_ctl, longName="geometryType", niceName="Geometry Type", attributeType="enum", enumName="Final:Proxy", keyable=True)
    
    cmds.addAttr(preferences_ctl, longName="reference", niceName="Reference", attributeType="bool", keyable=True, defaultValue=1)
    cmds.setAttr(f"{preferences_ctl}.reference", keyable=False, channelBox=True)

    # --- SECCIÓN RIG VISIBILITY ---
    cmds.addAttr(preferences_ctl, longName="RIG_VIS_SEP", niceName="RIG VISIBILITY", attributeType="enum", enumName="----")
    cmds.setAttr(f"{preferences_ctl}.RIG_VIS_SEP", keyable=False, channelBox=True, lock=True)

    cmds.addAttr(preferences_ctl, longName="showSkeleton", niceName="Show Skeleton", attributeType="bool", keyable=True, defaultValue=0)
    cmds.addAttr(preferences_ctl, longName="showModules", niceName="Show Modules", attributeType="bool", keyable=True, defaultValue=0)

    # --- SECCIÓN PLAYBLAST ---
    cmds.addAttr(preferences_ctl, longName="PLAYBLAST_SEP", niceName="PLAYBLAST", attributeType="enum", enumName="----")
    cmds.setAttr(f"{preferences_ctl}.PLAYBLAST_SEP", keyable=False, channelBox=True, lock=True)

    cmds.addAttr(preferences_ctl, longName="hideControllersOnPlayblast", niceName="Hide Controllers on Playblast", attributeType="bool", keyable=True)

    

    # 6. LÓGICA DE CONEXIONES

    # Visibilidad Final vs Proxy (Enum)
    # 0 = Final, 1 = Proxy. Usamos un condition node para alternar.
    geo_cond = cmds.createNode("condition", name="C_geoVis_COND")
    cmds.setAttr(f"{geo_cond}.secondTerm", 0) # Si el valor es 0...
    cmds.connectAttr(f"{preferences_ctl}.geometryType", f"{geo_cond}.firstTerm")
    
    # Salidas: Final visible si 0, Proxy visible si 1
    cmds.setAttr(f"{geo_cond}.colorIfTrueR", 1) # Final On
    cmds.setAttr(f"{geo_cond}.colorIfTrueG", 0) # Proxy Off
    cmds.setAttr(f"{geo_cond}.colorIfFalseR", 0) # Final Off
    cmds.setAttr(f"{geo_cond}.colorIfFalseG", 1) # Proxy On
    
    cmds.connectAttr(f"{geo_cond}.outColorR", f"{final_geo}.visibility")
    cmds.connectAttr(f"{geo_cond}.outColorG", f"{proxy}.visibility")

    # Reference (Override Display Type)
    cmds.connectAttr(f"{preferences_ctl}.reference", f"{nodes[3]}.overrideEnabled")
    cmds.setAttr(f"{nodes[3]}.overrideDisplayType", 2)

    # Hide Controllers (Reverse node)
    pb_rev = cmds.createNode("reverse", name="C_playblast_REV")
    cmds.connectAttr(f"{preferences_ctl}.hideControllersOnPlayblast", f"{pb_rev}.inputX")
    cmds.connectAttr(f"{pb_rev}.outputX", f"{nodes[2]}.visibility")

    # Rig Visibility
    skel_grp = cmds.createNode("transform", name="skel_GRP", ss=True, p=nodes[1])
    modules_grp = cmds.createNode("transform", name="modules_GRP", ss=True, p=nodes[1])
    cmds.connectAttr(f"{preferences_ctl}.showSkeleton", f"{skel_grp}.visibility")
    cmds.connectAttr(f"{preferences_ctl}.showModules", f"{modules_grp}.visibility")

    # 7. CIERRE Y BLOQUEOS
    lock_attributes(character_ctl, ["translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ", "scaleX", "scaleY", "scaleZ", "visibility"])
    lock_attributes(preferences_ctl, ["translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ", "scaleX", "scaleY", "scaleZ", "visibility"])
    
    # Global Scale en Masterwalk
    cmds.addAttr(masterwalk_ctl, longName="globalScale", attributeType="float", defaultValue=1, minValue=0.01, keyable=True)
    for axis in ["X", "Y", "Z"]: cmds.connectAttr(f"{masterwalk_ctl}.globalScale", f"{masterwalk_ctl}.scale{axis}")
    lock_attributes(masterwalk_ctl, ["scaleX", "scaleY", "scaleZ", "visibility"])

    # 10. EXPORTACIÓN DE DATA FINAL
    data_manager.DataExportBiped().append_data("basic_structure", {
        "skel_GRP" : skel_grp,
        "modules_GRP" : modules_grp,
        "masterwalk_ctl" : masterwalk_ctl,
        "character_ctl" : character_ctl,
        "preferences_ctl" : preferences_ctl
    })

    return character_name