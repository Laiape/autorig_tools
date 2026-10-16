"""Declarative tool entry points. Importing this module never imports Maya."""
from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path

GROUPS = ('PIPELINE', 'MODELING', 'RIGGING', 'ANIMATION', 'DEFORMERS', 'SIMULATION')
SECTIONS = {
    'RIGGING': ('Guides', 'Build', 'Controllers', 'Utilities'),
    'DEFORMERS': ('Skinning', 'Blendshapes', 'Correctives', 'Wrinkles', 'Wrap', 'Bake'),
}
ICON_ROOT = Path(__file__).resolve().parents[2] / 'icons' / 'red'
MENU = 'maya_tools.scripts.ui.auto_rig_UI:'


@dataclass(frozen=True)
class Tool:
    id: str
    label: str
    group: str
    icon: str
    entrypoint: str
    description: str
    keywords: str = ''
    kwargs: dict = field(default_factory=dict)
    replaces_scene: bool = False
    unavailable: str = ''
    section: str = ''
    kind: str = 'editor'
    requirements: tuple = ()


def _menu(id, label, group, icon, function, description, **options):
    adapters = {'skinning': 'skinning', 'pose_blendshapes': 'pose_blendshapes', 'pose_tester': 'pose_tester',
                'picker': 'picker', 'skin_export': 'skin_export', 'skin_source_export': 'skin_source_export', 'create_rig': 'build',
                'create_rig_self': 'build', 'create_rig_math': 'build'}
    entry = 'maya_tools.scripts.framework.adapters:' + adapters[id] if id in adapters else MENU + function
    return Tool(id, label, group, icon, entry, description, **options)


TOOLS = (
    _menu('characters', 'Character Manager', 'PIPELINE', 'character', 'show_character_manager_ui',
          'Browse character scenes, guides, curves, build settings and skin files.', keywords='asset files versions'),
    _menu('packages', 'Validated Rig Packages', 'PIPELINE', 'package', 'open_rig_package_ui',
          'Freeze rig inputs, verify hashes and validate rebuilds before delivery.', keywords='publish manifest'),
    _menu('model_checker', 'Model Checker', 'MODELING', 'model', 'open_model_checker',
          'Inspect topology and model readiness before rigging.', keywords='mesh geometry quality QC'),
    _menu('create_rig', 'CREATE RIG', 'RIGGING', 'rig', 'rig',
          'Build the complete character from saved guides and build settings. Replaces the current scene.',
          kwargs={'leg_impl': 'reference'}, replaces_scene=True, section='Build', kind='action', requirements=('asset', 'build_inputs')),
    _menu('create_rig_self', 'CREATE RIG SELF', 'RIGGING', 'rig', 'rig',
          'Build with the quadruped SELF leg implementation. Replaces the current scene.',
          kwargs={'leg_impl': 'self'}, replaces_scene=True, section='Build', kind='action', requirements=('asset', 'build_inputs')),
    _menu('create_rig_math', 'CREATE RIG SELF MATH', 'RIGGING', 'rig', 'rig',
          'Build SELF legs using the native node solver. Replaces the current scene.',
          kwargs={'leg_impl': 'self', 'leg_solver': 'nodes'}, replaces_scene=True, section='Build', kind='action', requirements=('asset', 'build_inputs')),
    _menu('build_leg', 'BUILD LEG', 'RIGGING', 'rig', 'leg_rig',
          'Legacy isolated leg entry point.',
          unavailable='This legacy entry has unfinished arguments. Use Test Rig by Guide.', section='Build', kind='action'),
    _menu('guides_create', 'Create New Guides', 'RIGGING', 'guide', 'create_new_guides',
          'Create character guides through the existing Guides Manager.', section='Guides', kind='action', requirements=('asset',)),
    _menu('guides_import', 'Import Guides', 'RIGGING', 'import', 'import_guides', 'Load a saved .guides file.', section='Guides', kind='action', requirements=('asset',)),
    _menu('guides_export', 'Export Guides', 'RIGGING', 'export', 'export_guides', 'Save current character guides.', section='Guides', kind='action', requirements=('asset', 'scene_guides')),
    _menu('guides_mirror', 'Mirror Guides', 'RIGGING', 'mirror', 'mirror_guides', 'Mirror the selected guide setup.', section='Guides', kind='action', requirements=('scene_guides',)),
    _menu('guides_test', 'Test Rig by Guide', 'RIGGING', 'guide', 'test_rig_by_guide',
          'Build only the module of the selected root guide.', section='Build', kind='action', requirements=('guide',)),
    _menu('controllers_export', 'Export All Controllers', 'RIGGING', 'export', 'export_all_controllers',
          'Save controller curve shapes to the existing character data workflow.', section='Controllers', kind='action', requirements=('asset', 'controllers')),
    _menu('controllers_mirror', 'Mirror Controllers', 'RIGGING', 'mirror', 'mirror_controllers',
          'Mirror L_ controller shapes to R_ across world X without changing transforms.', section='Controllers', kind='action', requirements=('controllers',)),
    _menu('controllers_replace', 'Replace Controller Shapes', 'RIGGING', 'controller', 'replace_shapes',
          'Select the source first, then targets. Copy curve shapes with L/R/C colors.',
          keywords='curves replace shapes colored puiastre', section='Controllers', kind='action'),
    _menu('curve_library', 'Controller Shape Library', 'RIGGING', 'controller', 'show_curve_library',
          'Browse built-in and saved curve shapes; apply them to selected controls.', keywords='curves shapes', section='Controllers'),
    _menu('rig_tools', 'Rig Utilities', 'RIGGING', 'tools', 'show_rig_tools',
          'Arc tracer, world bake, control colors, parent shapes, channel reset and rotation order.', section='Utilities'),
    Tool('ribbon', 'De Boor Ribbon', 'RIGGING', 'curve', 'maya_tools.scripts.ui.deboor_tools_UI:show',
         'Build a ribbon using the existing De Boor editor.', kwargs={'tab': 0}, section='Build'),
    _menu('pose_tester', 'Test Rig', 'ANIMATION', 'pose', 'open_pose_tester',
          'ROM tests, rig roles, validation profiles, pose library, surface contact, migration and performance.',
          keywords='QA quality validation semantic contact migration benchmark'),
    _menu('picker', 'Character Picker', 'ANIMATION', 'picker', 'open_character_picker',
          'Open the native body and face picker for the selected character.', requirements=('root', 'asset', 'rig')),
    _menu('joint_correctives', 'Joint Corrective Targets', 'DEFORMERS', 'corrective', 'open_joint_correctives_ui',
          'Edit joint-based targets, masks and automatic pose drivers.', section='Correctives'),
    _menu('wrinkles', 'Wrinkle Regions / Presets', 'DEFORMERS', 'wrinkle', 'open_wrinkle_regions_ui',
          'Author procedural wrinkle regions and portable Bifrost presets.', keywords='Bifrost masks', section='Wrinkles',
          requirements=('plugin:bifrostGraph',)),
    _menu('pose_blendshapes', 'Pose Blendshapes', 'DEFORMERS', 'corrective', 'open_pose_blendshapes_ui',
          'Capture poses, sculpt targets and edit orientation or combination correctives.', keywords='sculpt blendshape transfer LOD', section='Blendshapes'),
    _menu('correctives_export', 'Export Corrective Blendshapes', 'DEFORMERS', 'export', 'export_corrective_blendshapes',
          'Export corrective targets through the existing file dialog.', section='Blendshapes', kind='action'),
    _menu('correctives_import', 'Import Corrective Blendshapes', 'DEFORMERS', 'import', 'import_corrective_blendshapes',
          'Import saved corrective targets.', section='Blendshapes', kind='action'),
    _menu('correctives_mirror', 'Mirror Corrective Blendshapes', 'DEFORMERS', 'mirror', 'mirror_corrective_blendshapes',
          'Mirror corrective blendshapes in the current scene.', section='Blendshapes', kind='action'),
    _menu('targets_mirror', 'Mirror Corrective Targets', 'DEFORMERS', 'mirror', 'mirror_corrective_blendshape_targets',
          'Mirror corrective target geometry.', section='Blendshapes', kind='action'),
    _menu('corrective_skin', 'Corrective Skin - Setup / Localize', 'DEFORMERS', 'skin', 'setup_corrective_skin',
          'Select a mesh and corrective joints in neutral pose to create the extra corrective skin layer.', section='Correctives', kind='action', requirements=('mesh_joints',)),
    Tool('split_blendshape', 'Split Blendshape', 'DEFORMERS', 'corrective', 'maya_tools.scripts.ui.deboor_tools_UI:show',
         'Split a blendshape using the existing De Boor editor.', kwargs={'tab': 1}, section='Blendshapes'),
    _menu('skinning', 'Skinning Manager', 'DEFORMERS', 'skin', 'open_skinning_manager_ui',
          'Dockable NG, Smooth, Transfer, Ramp and corrective blendshape editors.', keywords='ngSkinTools brSmoothWeights rampWeights', section='Skinning'),
    _menu('skin_export', 'Export Skin Cluster', 'DEFORMERS', 'export', 'export_skin_cluster',
          'Export skin weights and supported deformation metadata to .skc.', section='Skinning', kind='action', requirements=('asset', 'mesh', 'skin')),
    _menu('skin_import', 'Import Skin Cluster', 'DEFORMERS', 'import', 'import_skin_cluster',
          'Restore skin weights and supported deformation metadata from .skc.', section='Skinning', kind='action', requirements=('asset', 'root', 'saved_skin')),
    _menu('skin_copy', 'Copy Skin Cluster', 'DEFORMERS', 'transfer', 'copy_skin_cluster',
          'Copy skin weights using the existing Skin Manager selection workflow.', section='Skinning', kind='action', requirements=('two_meshes',)),
    _menu('proxy_skin', 'Proxy Skinning', 'DEFORMERS', 'skin', 'proxy_skinning',
          'Select the proxy mesh, high-resolution mesh and skeleton root, in that order.', section='Skinning', kind='action', requirements=('proxy',)),
    _menu('skin_source_export', 'Export Source Skin Data', 'DEFORMERS', 'export', 'export_source_skin_data',
          'Export source skin data using the existing mesh data exporter.', section='Skinning', kind='action', requirements=('asset', 'mesh', 'skin')),
    _menu('corrective_curve', 'Corrective Curve', 'DEFORMERS', 'curve', 'open_corrective_curve_ui',
          'Author pose-driven curve and joint corrections.', section='Correctives'),
    _menu('skin_transfer', 'Auto Skin Transfer (Clothes)', 'DEFORMERS', 'transfer', 'open_skin_transfer_ui',
          'Map and transfer skin weights onto clothing meshes.', section='Skinning'),
    _menu('proximity_wrap', 'Proximity Wrap (Multiple Drivers)', 'DEFORMERS', 'wrap', 'open_proximity_wrap_ui',
          'Configure multiple drivers with the native proximity wrap editor.', section='Wrap'),
    _menu('deformation_bake', 'Bake Deformation to Skin', 'DEFORMERS', 'bake', 'open_proximity_bake_ui',
          'Fit skin weights and validate held-out poses, with optional residual corrective bake.', keywords='hybrid error validation', section='Bake'),
    Tool('skin_curve', 'Skin Along Curve', 'DEFORMERS', 'curve', 'maya_tools.scripts.ui.deboor_tools_UI:show',
         'Skin using a De Boor curve.', kwargs={'tab': 2}, section='Skinning'),
    Tool('skin_surface', 'Skin Along Surface', 'DEFORMERS', 'wrap', 'maya_tools.scripts.ui.deboor_tools_UI:show',
         'Skin using a De Boor surface.', kwargs={'tab': 3}, section='Skinning'),
    _menu('adonis', 'AdonisFX Copy Weights', 'SIMULATION', 'simulation', 'open_adonis_copy_weights',
          'Open the installed AdonisFX weight-copy workflow. Requires AdonisFX.', keywords='muscle simulation'),
)
BY_ID = {tool.id: tool for tool in TOOLS}
if len(BY_ID) != len(TOOLS):
    raise ValueError('Duplicate framework tool id.')
for tool in TOOLS:
    if tool.section not in SECTIONS.get(tool.group, ('',)):
        raise ValueError('Invalid tool section: ' + tool.id)


def icon_path(name, extension='png'):
    return str(ICON_ROOT / (name + '.' + extension))


def search(query='', group=None, ids=None, section=None):
    """Match all words across labels, descriptions, groups and keywords."""
    words = query.casefold().split()
    matches = [tool for tool in TOOLS
            if (group is None or tool.group == group)
            and (section is None or tool.section == section)
            and (ids is None or tool.id in ids)
            and all(word in ' '.join((tool.label, tool.group, tool.section, tool.description, tool.keywords)).casefold()
                    for word in words)]
    if words:
        phrase = ' '.join(words)

        def rank(tool):
            label = tool.label.casefold()
            score = 0 if label == phrase else 1 if label.startswith(phrase) else 2 if all(word in label for word in words) else 3
            return GROUPS.index(tool.group), score

        matches.sort(key=rank)
    return matches


def invoke(tool_id):
    """Resolve only the requested entry point; never evaluate command strings."""
    tool = BY_ID[tool_id]
    if tool.unavailable:
        raise RuntimeError(tool.unavailable)
    module_name, function = tool.entrypoint.split(':', 1)
    return getattr(import_module(module_name), function)(**tool.kwargs)
