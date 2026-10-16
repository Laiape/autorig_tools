"""Flower family orchestrator called by the normal AutoRig build pipeline."""
from pathlib import Path
import json
from maya import cmds
from maya.api import OpenMaya as om
from maya.api import OpenMayaAnim as oma
from maya_tools.scripts.utils import data_manager, rig_manager
from .stem_module import StemModule
from .head_module import HeadModule
from .leaf_module import LeafModule
from .petal_module import PetalModule
from . import common


def bind_mesh(mesh, chains, guides):
    """Bind shells independently with two normalized adjacent influences per vertex."""
    path, points = common.point_list(mesh)
    influences = [joint for chain in chains for joint in chain['joints']]
    weights = [[0.] * len(influences) for _ in points]
    column = 0
    for chain in chains:
        entry = chain['entry']
        ids = entry.get('vertices', list(range(len(points))))
        if entry.get('vertex_count', len(points)) != len(points):
            raise ValueError('Flower shell topology changed: '+mesh)
        positions = [om.MVector(*guides[name]['joint_matrix'][12:15]) for name in entry['guides']]
        for vertex in ids:
            point = om.MVector(points[vertex])
            if len(positions) == 1:
                weights[vertex][column] = 1.
                continue
            nearest = None
            for index in range(len(positions)-1):
                vector = positions[index+1]-positions[index]
                t = max(0., min(1., ((point-positions[index])*vector)/max(vector*vector, 1e-12)))
                distance = (point-(positions[index]+vector*t)).length()
                if nearest is None or distance < nearest[0]:
                    nearest = (distance, index, t)
            _, index, t = nearest
            weights[vertex][column+index] = 1.-t
            weights[vertex][column+index+1] = t
        column += len(chain['joints'])
    if any(abs(sum(row)-1.) > 1e-9 for row in weights):
        raise ValueError('Flower shell coverage is incomplete or overlapping: '+mesh)
    skin = cmds.skinCluster(influences, mesh, toSelectedBones=True, normalizeWeights=1,
                            maximumInfluences=2, obeyMaxInfluences=False, skinMethod=0,
                            name=mesh.replace('_GEO', '_SKC'))[0]
    selection = om.MSelectionList(); selection.add(skin)
    fn = oma.MFnSkinCluster(selection.getDependNode(0))
    component = om.MFnSingleIndexedComponent().create(om.MFn.kMeshVertComponent)
    om.MFnSingleIndexedComponent(component).addElements(range(len(points)))
    fn.setWeights(path, component, om.MIntArray(range(len(influences))),
                  om.MDoubleArray([value for row in weights for value in row]), normalize=False)
    return skin


def make(character_name, settings, guides, on_step=None):
    # Shell membership is asset data, independent of the guide settings editor.
    config = settings.get('flower')
    if config is None:
        config_path = Path(rig_manager.asset_path(character_name, 'rig_data'))/'flower.json'
        config = json.loads(config_path.read_text(encoding='utf-8'))
    if config.get('schema_version') != 1:
        raise ValueError('Unsupported flower build schema.')
    stem = StemModule().make('C', config['stem'], guides)
    head = HeadModule().make('C', config['head'], guides, stem)
    leaves = [LeafModule().make('C', entry, guides, stem, head) for entry in config['leaves']]
    petals = [PetalModule().make('C', entry, guides, head) for entry in config['petals']]
    common.settings_drawing(common.structure('preferences_ctl'), letter='F')
    skin_dir = Path(rig_manager.asset_path(character_name, 'skin_clusters'))
    skins = []
    if not list(skin_dir.glob('*.skc')):
        skins.append(bind_mesh(config['stem']['mesh'], [stem], guides))
        head_chain = {'entry': {'guides': [config['head']['guide']]}, 'joints': [head['joint']]}
        skins.append(bind_mesh(config['head']['mesh'], [head_chain], guides))
        for mesh in sorted({chain['entry']['mesh'] for chain in leaves+petals}):
            chains = [chain for chain in leaves+petals if chain['entry']['mesh'] == mesh]
            skins.append(bind_mesh(mesh, chains, guides))
    controls = stem['controls']+[head['control']]+[ctl for c in leaves+petals for ctl in c['controls']]
    skeleton_chains = [{'joints': stem['joints'], 'parent': 'C_freeze_JNT'},
                       {'joints': [head['joint']], 'parent': stem['joints'][-1]}]
    skeleton_chains += [{'joints': leaf['joints'], 'parent': stem['joints'][leaf['entry']['attachment']]} for leaf in leaves]
    skeleton_chains += [{'joints': petal['joints'], 'parent': head['joint']} for petal in petals]
    data_manager.DataExportBiped().append_data('flower_module', {
        'head_ctl': head['control'], 'stem_controls': stem['controls'],
        'petal_controls': [c['controls'][0] for c in petals],
        'leaf_controls': [c['controls'][0] for c in leaves], 'controls': controls,
        'skinning_joints': stem['joints']+[head['joint']]+[j for c in leaves+petals for j in c['joints']],
        'skeleton_chains': skeleton_chains})
    # The common framework's root and geometry/skeleton visibility remain in use.
    return {'controls': controls, 'skins_created': skins, 'petals': len(petals), 'leaves': len(leaves),
            'skeleton_chains': skeleton_chains}
