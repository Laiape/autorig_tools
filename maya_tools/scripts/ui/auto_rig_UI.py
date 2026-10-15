from utils import data_manager
import maya.cmds as cmds
from importlib import reload
from maya_tools.scripts.framework.registry import icon_path

from tools import skin_manager_api
from ui import skin_transfer_UI
from utils import curve_tool
from utils import rig_manager
from utils import guides_manager
from utils import create_rig
from quadruped.autorig import leg_module_self

reload(skin_manager_api)
reload(curve_tool)
reload(rig_manager)
reload(guides_manager)
reload(create_rig)
reload(data_manager)

def open_character_picker():
    from tools import character_picker
    return character_picker.show()


def create_custom_menu():
    """Use the same ordered categories and sections as the dockable catalogue."""
    from maya_tools.scripts.framework import registry

    menu_id = "autorig_menu"
    if cmds.menu(menu_id, exists=True):
        cmds.deleteUI(menu_id)
    cmds.menu(menu_id, label="AutoRig Tools", parent='MayaWindow', tearOff=True)
    cmds.menuItem(parent=menu_id, label="Reload UI", command=lambda x: rebuild_ui(), image=icon_path('reload'))
    cmds.menuItem(parent=menu_id, label="Tool Framework", command=lambda x: open_tool_framework(),
                  annotation="Dockable catalogue, search, favorites and recent tools.",
                  image=icon_path('framework'))

    for group in registry.GROUPS:
        cmds.menuItem(parent=menu_id, divider=True, dividerLabel=group)
        for section in registry.SECTIONS.get(group, ('',)):
            members = [tool for tool in registry.TOOLS if tool.group == group and tool.section == section]
            if not members:
                continue
            parent = menu_id
            if section:
                parent = cmds.menuItem(parent=menu_id, label=section, subMenu=True, tearOff=True,
                                       image=icon_path(members[0].icon))
            for tool in members:
                cmds.menuItem(parent=parent, label=tool.label, annotation=tool.unavailable or tool.description,
                              image=icon_path(tool.icon), enable=not bool(tool.unavailable),
                              boldFont=tool.replaces_scene,
                              command=lambda unused=False, tool_id=tool.id: _run_menu_tool(tool_id))


def _run_menu_tool(tool_id):
    from maya_tools.scripts.framework import execution
    from maya_tools.scripts.ui import tool_framework_UI
    result = execution.run(tool_id, confirm=tool_framework_UI.ToolFramework._allow_scene_replacement)
    if result['status'] in ('blocked', 'failed'):
        cmds.warning(result['message'])
    return result


def open_tool_framework():
    from maya_tools.scripts.ui import tool_framework_UI
    return tool_framework_UI.show()


def open_skinning_manager_ui():
    from maya_tools.scripts.ui import skinning_manager_UI
    return skinning_manager_UI.show()


def rebuild_ui():
    from ui import auto_rig_UI
    reload(auto_rig_UI)
    auto_rig_UI.create_custom_menu()
    from maya_tools.scripts.utils import ui_theme, ui_utils
    reload(ui_theme)
    reload(ui_utils)
    ui_utils.restyle_open_tools()


def open_rig_package_ui():
    from maya_tools.scripts.ui import rig_package_UI
    reload(rig_package_UI)
    rig_package_UI.show()


def create_new_asset():
    from utils import rig_manager
    reload(rig_manager)
    rig_manager.create_new_asset()
    cmds.inViewMessage(amg='New Asset Created.', pos='midCenter', fade=True)

def create_new_guides():
    reload(guides_manager)
    guides_manager.create_new_guides()
    cmds.inViewMessage(amg='New Guides Created.', pos='midCenter', fade=True)

def import_guides():
    reload(guides_manager)
    guides_manager.load_guides_info()

def export_guides():
    reload(guides_manager)
    guides_manager.get_guides_info()
    cmds.inViewMessage(amg='Guides Exportados.', pos='midCenter', fade=True)

def mirror_guides():
    reload(guides_manager)
    guides_manager.mirror_guides()
    cmds.inViewMessage(amg='Guides Espejados.', pos='midCenter', fade=True)

def export_all_controllers():
    reload(curve_tool)
    curve_tool.get_all_ctl_curves_data()
    cmds.inViewMessage(amg='Controladores Exportados.', pos='midCenter', fade=True)

def mirror_controllers():
    reload(curve_tool)
    curve_tool.mirror_curves()
    cmds.inViewMessage(amg='Controladores Espejados.', pos='midCenter', fade=True)

def open_library():
    print("Funcionalidad para abrir la librería de controladores.")

def replace_shapes():
    print("Funcionalidad para reemplazar formas de controladores.")

def tag_scene_curves():
    reload(curve_tool)
    curve_tool.tag_scene_curves()
    cmds.inViewMessage(amg='Curves Taggeadas.', pos='midCenter', fade=True)

def export_corrective_blendshapes():
    from tools import corrective_blendshape_manager
    reload(corrective_blendshape_manager)
    path = corrective_blendshape_manager.CorrectiveBlendshapeManager().export()
    if path:
        cmds.inViewMessage(amg='Corrective Blendshapes Exportados.', pos='midCenter', fade=True)

def import_corrective_blendshapes():
    from tools import corrective_blendshape_manager
    reload(corrective_blendshape_manager)
    corrective_blendshape_manager.CorrectiveBlendshapeManager().import_from()
    cmds.inViewMessage(amg='Corrective Blendshapes Importados.', pos='midCenter', fade=True)

def mirror_corrective_blendshapes():
    from tools import corrective_blendshape_manager
    reload(corrective_blendshape_manager)
    corrective_blendshape_manager.CorrectiveBlendshapeManager().mirror_in_scene()
    cmds.inViewMessage(amg='Corrective Blendshapes Espejados.', pos='midCenter', fade=True)

def mirror_corrective_blendshape_targets():
    from tools import corrective_blendshape_manager
    reload(corrective_blendshape_manager)
    corrective_blendshape_manager.CorrectiveBlendshapeManager().mirror_targets()
    cmds.inViewMessage(amg='Targets Espejados.', pos='midCenter', fade=True)

def export_skin_cluster():
    reload(skin_manager_api)
    skinner = skin_manager_api.SkinManager()
    skinner.export_skins()
    cmds.inViewMessage(amg='Skins Exportadas.', pos='midCenter', fade=True)

def import_skin_cluster():
    reload(skin_manager_api)
    skinner = skin_manager_api.SkinManager()
    skinner.import_skins()
    cmds.inViewMessage(amg='Skins y Deformadores Importados.', pos='midCenter', fade=True)

def copy_skin_cluster():
    skinner = skin_manager_api.SkinManager()
    reload(skin_manager_api)
    skinner.copy_skin_cluster()
    cmds.inViewMessage(amg='Skin Cluster Copiado.', pos='midCenter', fade=True)

def open_skin_transfer_ui():
    from ui import skin_transfer_UI
    reload(skin_transfer_UI)
    skin_transfer_UI.show()

def proxy_skinning():
    """
    Proxy skinning del cuerpo con la cadena recomendada (Geodesic Voxel Binding -> transferir
    con copySkinWeights -> optimizar -> Delta Mush). No usa auto_skin_transfer.

    Selección esperada (en cualquier orden): la malla PROXY, la malla de ALTA y la RAÍZ del
    esqueleto (joint). El PRIMER mesh seleccionado es el proxy; el segundo, la alta.
    """
    from tools import proxy_skinning as ps
    reload(ps)

    # A nivel de objeto la selección activa ya conserva el orden de clic
    # (proxy primero, alta después). No usar orderedSelection junto a sl:
    # los flags -sl/-os son excluyentes y ls lanza RuntimeError.
    sel = cmds.ls(sl=True) or []
    meshes, joints, seen = [], [], set()
    for node in sel:
        nt = cmds.nodeType(node)
        if nt == "joint":
            if node not in seen:
                seen.add(node); joints.append(node)
            continue
        # normaliza a transform tanto si se seleccionó la malla como su shape
        xform = None
        if nt == "mesh":
            par = cmds.listRelatives(node, parent=True, type="transform")
            xform = par[0] if par else None
        elif cmds.listRelatives(node, shapes=True, type="mesh"):
            xform = node
        if xform and xform not in seen:
            seen.add(xform); meshes.append(xform)

    if len(meshes) != 2 or len(joints) != 1:
        cmds.inViewMessage(
            amg="Proxy Skinning: selecciona <hl>PROXY</hl>, <hl>ALTA</hl> y la <hl>raíz del "
                "esqueleto</hl> en ese orden (2 mallas + 1 joint).",
            pos='midCenter', fade=True, fadeStayTime=2500)
        return

    proxy, high, root = meshes[0], meshes[1], joints[0]
    cmds.undoInfo(openChunk=True)
    try:
        res = ps.proxy_skin(proxy, high, root, max_influences=4, uv_space=False,
                            use_labels=True, delta_mush=True, bake=False)
    finally:
        cmds.undoInfo(closeChunk=True)

    rep = res.get("report", {})
    cmds.inViewMessage(
        amg=f"Proxy Skinning: proxy <hl>{proxy}</hl> → alta <hl>{high}</hl> · máx "
            f"influencias/vértice: <hl>{rep.get('max_per_vertex', '?')}</hl>.",
        pos='midCenter', fade=True, fadeStayTime=2500)

def export_source_skin_data():
    from tools import mesh_data_exporter
    reload(mesh_data_exporter)
    exported = mesh_data_exporter.SourceSkinExporter().export_all()
    n = len(exported)
    cmds.inViewMessage(
        amg=f"Source skin data exported: <hl>{n}</hl> mesh(es).",
        pos="midCenter", fade=True
    )
    
def test_rig_by_guide():
    """Construye solo el módulo de la guía raíz seleccionada (test de guías)."""
    reload(rig_manager)
    rig_manager.test_rig_by_guide()


def rig(leg_impl="self", leg_solver=None):
    """
    Crea el rig completo. leg_impl elige la implementación de pata de
    cuadrúpedo: "reference" (quadruped/leg_module) o "self"
    (quadruped/leg_module_self). leg_solver fuerza el preset de solver de las
    patas (SELF MATH -> "nodes"); a None usa el de los rig settings.
    """
    cmds.file(new=True, force=True)
    data_manager.DataExportBiped().new_build()
    reload(create_rig)
    rig = create_rig.AutoRig()
    rig.build(leg_impl=leg_impl, leg_solver=leg_solver)

def leg_rig():
    """Función para crear el rig bipedal"""

    reload(leg_module_self)
    leg_rig = leg_module_self.LegModule()
    leg_rig.make() # Hay que poner los argumentos todavia

def open_model_checker():
    from tools import model_checker
    reload(model_checker)
    model_checker.show()

def show_character_manager_ui():
    from utils import character_manager
    reload(character_manager)
    pro_asset_manager = character_manager.AssetManagerUI()
    pro_asset_manager.show()

def show_curve_library():
    from tools import curve_library
    reload(curve_library)
    curve_library.show()

def show_rig_tools():
    from tools import rig_tools
    reload(rig_tools)
    rig_tools.show()

def open_adonis_copy_weights():
    from adonis import copyWeightsAdonis
    reload(copyWeightsAdonis)
    copyWeightsAdonis.show()


def open_pose_blendshapes_ui():
    from ui import pose_blendshapes_UI
    return pose_blendshapes_UI.show()


def open_joint_correctives_ui():
    from ui import joint_correctives_UI
    return joint_correctives_UI.show()


def open_wrinkle_regions_ui():
    from maya_tools.scripts.ui import wrinkle_regions_UI
    reload(wrinkle_regions_UI)
    return wrinkle_regions_UI.show()


def open_corrective_curve_ui():
    from ui import corrective_curve_UI
    reload(corrective_curve_UI)
    corrective_curve_UI.show()


def setup_corrective_skin():
    from utils import correctives
    reload(correctives)
    sel = cmds.ls(selection=True) or []
    meshes = [s for s in sel
              if (cmds.listRelatives(s, shapes=True, noIntermediate=True) or [])
              and cmds.nodeType((cmds.listRelatives(s, shapes=True, noIntermediate=True))[0]) == "mesh"]
    joints = [s for s in sel if cmds.nodeType(s) == "joint"]
    if not meshes:
        cmds.inViewMessage(amg="Selecciona la MALLA (+ joints correctivas).", pos='midCenter', fade=True)
        return
    result = correctives.corrective_skin_setup(meshes[0], joints)
    cmds.inViewMessage(
        amg=f"Corrective skin <hl>{result['skin']}</hl>: {len(result['added'])} nuevas, "
            f"{result['localized']} localizadas.",
        pos='midCenter', fade=True)


def open_pose_tester():
    from tools import pose_tester
    reload(pose_tester)
    from ui import pose_tester_UI
    reload(pose_tester_UI)
    pose_tester_UI.show()


def open_proximity_wrap_ui():
    from tools import proximity_wrap
    reload(proximity_wrap)
    proximity_wrap.show_window()


def open_proximity_bake_ui():
    from ui import proximity_bake_UI
    reload(proximity_bake_UI)
    proximity_bake_UI.show()
