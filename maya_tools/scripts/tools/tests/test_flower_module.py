"""Native flower integration: source appearance, skins, spaces and two rebuilds.

Run only in a disposable Maya session. The delivered neutral scene is reopened
after validation. No animation or source asset files are overwritten.
"""
import json
import hashlib
import os
from pathlib import Path
import sys
import tempfile
from importlib import reload

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT/'maya_tools/scripts')]


def run(output_dir=None):
    import numpy as np
    from maya import cmds
    from maya.api import OpenMaya as om, OpenMayaAnim as oma
    from maya_tools.scripts.utils import create_rig, scene_evaluation, data_manager, guides_manager
    from maya_tools.scripts.flower.autorig import common, stem_module, head_module, leaf_module, petal_module, flower_module
    from maya_tools.scripts.framework import registry
    cmds.optionVar(stringValue=('currentAssetRigName', 'flower'))
    for module in (common, stem_module, head_module, leaf_module, petal_module, flower_module, registry):
        reload(module)
    asset = ROOT/'maya_tools/assets/flower'
    scene = sorted((asset/'scenes').glob('flower_rig_v*.mb'))[-1]
    folder = Path(output_dir or tempfile.mkdtemp(prefix='flower_validation_'))
    folder.mkdir(parents=True, exist_ok=True)
    config = json.loads((asset/'rig_data/flower.json').read_text())
    names = {'msh_stem': 'C_stem_GEO', 'msh_in': 'C_flowerCore_GEO', 'msh_leaves': 'C_leaves_GEO',
             'msh_petals_A': 'C_petalsA_GEO', 'msh_petals_B': 'C_petalsB_GEO'}
    mesh_names = list(names.values())
    tolerance = 1e-4
    report = {'tolerance_cm': tolerance, 'cases': {}, 'rebuilds': []}
    report['maya_version'] = cmds.about(version=True)
    report['source'] = str(asset/'flower_v01.ma')
    report['delivered_scene'] = str(scene)
    inputs = [asset/'flower_v01.ma', asset/'models/flower_v001.ma', asset/'build/flower_v001.build',
              asset/'guides/flower_v001.guides', max((asset/'curves').glob('*.curves'),key=lambda p:p.stat().st_mtime_ns),
              max((asset/'skin_clusters').glob('*.skc'),key=lambda p:p.stat().st_mtime_ns), asset/'rig_data/flower.json', scene]
    code = list((ROOT/'maya_tools/scripts/flower/autorig').glob('*.py'))
    code += [ROOT/'maya_tools/scripts/utils/rig_manager.py', ROOT/'maya_tools/scripts/framework/registry.py',
             ROOT/'maya_tools/scripts/utils/curve_tool.py']
    report['sha256'] = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs+code}

    def fn(mesh):
        selected = om.MSelectionList(); selected.add(mesh)
        path = selected.getDagPath(0); path.extendToShape()
        return path, om.MFnMesh(path)

    def geometry(mapping=None):
        mapping = mapping or {m: m for m in mesh_names}
        result = {}
        for source, name in mapping.items():
            path, mesh = fn(source)
            counts, indices = mesh.getVertices()
            u, v = mesh.getUVs(); uv_counts, uv_indices = mesh.getAssignedUVs()
            shaders, assignments = mesh.getConnectedShaders(0)
            result[name] = {'points': np.array([[p.x, p.y, p.z] for p in mesh.getPoints(om.MSpace.kWorld)]),
                            'normals': np.array([[n.x, n.y, n.z] for n in mesh.getFaceVertexNormals(om.MSpace.kWorld)]),
                            'topology': [list(counts), list(indices)],
                            'uv': [list(u), list(v), list(uv_counts), list(uv_indices)],
                            'smooth_edges': [mesh.isEdgeSmooth(i) for i in range(mesh.numEdges)],
                            'shaders': [om.MFnDependencyNode(s).name() for s in shaders],
                            'shader_assignment': list(assignments)}
        return result

    def compare(a, b, appearance=False):
        errors = {}
        for mesh in a:
            assert a[mesh]['topology'] == b[mesh]['topology'], mesh+' topology'
            errors[mesh] = float(np.linalg.norm(a[mesh]['points']-b[mesh]['points'], axis=1).max())
            assert errors[mesh] <= tolerance, (mesh, errors[mesh])
            if appearance:
                assert a[mesh]['uv'] == b[mesh]['uv'], mesh+' UVs'
                assert a[mesh]['smooth_edges'] == b[mesh]['smooth_edges'], mesh+' hard edges'
                assert a[mesh]['shaders'] == b[mesh]['shaders'], mesh+' shading groups'
                assert a[mesh]['shader_assignment'] == b[mesh]['shader_assignment'], mesh+' assignments'
                normal_error = float(np.linalg.norm(a[mesh]['normals']-b[mesh]['normals'], axis=1).max())
                assert normal_error <= 1e-5, (mesh, normal_error)
        return errors

    def skins():
        result = {}
        for name in cmds.ls(type='skinCluster'):
            selected = om.MSelectionList(); selected.add(name)
            skin = oma.MFnSkinCluster(selected.getDependNode(0))
            path = skin.getOutputGeometry()[0]
            path = om.MDagPath.getAPathTo(path)
            component = om.MFnSingleIndexedComponent().create(om.MFn.kMeshVertComponent)
            om.MFnSingleIndexedComponent(component).addElements(range(om.MFnMesh(path).numVertices))
            weights, count = skin.getWeights(path, component)
            influences = skin.influenceObjects()
            order = sorted(range(count), key=lambda i: influences[i].partialPathName())
            values = np.array(weights).reshape(-1, count)[:, order]
            assert float(np.max(np.abs(values.sum(axis=1)-1.))) < 1e-12, name
            # Rabbit smoothing blends all three joints within each petal shell.
            limit = 3 if name in ('C_petalsA_SKC', 'C_petalsB_SKC') else 2
            assert int(np.max(np.count_nonzero(values, axis=1))) <= limit, name
            result[name] = (values, {p.partialPathName(): list(cmds.getAttr('%s.bindPreMatrix[%s]' %
                               (name, skin.indexForInfluenceObject(p)))) for p in influences})
        assert len(result) == 5
        return result

    def control_drawings():
        drawings = {}
        for ctl in cmds.ls('*_CTL', type='transform'):
            drawings[ctl] = [cmds.xform(shape+'.cv[*]', query=True, objectSpace=True, translation=True)
                             for shape in (cmds.listRelatives(ctl, shapes=True, fullPath=True, type='nurbsCurve') or [])]
        return drawings

    def structure():
        def parent(node):
            return (cmds.listRelatives(node,parent=True) or [None])[0]
        assert parent('flower') is None
        for node in ('rig_GRP','controls_GRP','geo_GRP','deformers_GRP'):
            assert parent(node) == 'flower',node
        for node in ('modules_GRP','skel_GRP','skeletonHierarchy_GRP'):
            assert parent(node) == 'rig_GRP',node
        prefixes=['C_stem','C_flowerHead']+[e['prefix'] for e in config['leaves']+config['petals']]
        for prefix in prefixes:
            assert parent(prefix+'Module_GRP') == 'modules_GRP',prefix
            assert parent(prefix+'Skinning_GRP') == 'skel_GRP',prefix
            assert parent(prefix+'Controllers_GRP') == 'C_masterwalk_CTL',prefix
            assert cmds.listRelatives(prefix+'Module_GRP',children=True),prefix+' empty mechanics'
        assert parent('C_freeze_ENV') == 'skeletonHierarchy_GRP'
        assert parent('C_flowerHead_ENV') == 'C_stem06_ENV'
        for entry in config['leaves']:
            assert parent(entry['prefix']+'00_ENV') == 'C_stem%02d_ENV' % entry['attachment']
        for entry in config['petals']:
            assert parent(entry['prefix']+'00_ENV') == 'C_flowerHead_ENV'
        source_joints=cmds.ls('*Skinning_JNT',type='joint')
        assert len(source_joints) == 104
        for joint in source_joints:
            env=joint.replace('Skinning_JNT','_ENV')
            assert cmds.ls(env,long=True)[0].startswith('|flower|rig_GRP|skeletonHierarchy_GRP|'),env
            a=np.array(cmds.getAttr(joint+'.worldMatrix[0]'))
            b=np.array(cmds.getAttr(env+'.worldMatrix[0]'))
            assert np.max(np.abs(a-b)) < 1e-9,env+' matrix'
        assert len(cmds.ls('*_ENV',type='joint')) == 105
        assert any('LetterShape' in s for s in cmds.listRelatives('C_settings_CTL',shapes=True)), 'F settings drawing'
        assert np.array_equal(np.array(cmds.xform('C_settings_CTL',query=True,matrix=True)),np.array(om.MMatrix.kIdentity))
        return {'modules':len(prefixes),'skinning_joints':104,'env_joints':105,'settings_drawing':'F'}

    poses = {
        'neutral': {},
        'stem_head': {'C_stem01_CTL.rz': 12., 'C_stem03_CTL.ry': -28., 'C_stem05_CTL.rz': 23.,
                      'C_flowerHead_CTL.rx': 18.},
        'curl_leaves': {'C_flowerHead_CTL.petalCurl': 36., 'C_flowerHead_CTL.petalSpread': -12.,
                        'C_flowerHead_CTL.petalTwist': 9., 'C_leaf0100_CTL.curl': 31.,
                        'C_leaf0200_CTL.rz': -22., 'C_petalA0101_CTL.ry': 20.},
        'combined_scaled': {'C_stem02_CTL.rz': 18., 'C_stem04_CTL.ry': -24.,
                            'C_flowerHead_CTL.rz': 15., 'C_flowerHead_CTL.petalCurl': 23.,
                            'C_masterwalk_CTL.tx': 3., 'C_masterwalk_CTL.ty': 2., 'C_masterwalk_CTL.tz': -4.,
                            'C_masterwalk_CTL.rx': 23., 'C_masterwalk_CTL.ry': 38., 'C_masterwalk_CTL.rz': -12.,
                            'C_masterwalk_CTL.globalScale': 1.6, 'C_leaf0200_CTL.curl': -25.}}
    channels = set().union(*(pose.keys() for pose in poses.values()))

    def pose(values):
        for channel in channels:
            cmds.setAttr(channel, 1. if channel.endswith('globalScale') else 0.)
        for channel, value in values.items():
            cmds.setAttr(channel, value)

    try:
        cmds.file(str(asset/'flower_v01.ma'), open=True, force=True, executeScriptNodes=False)
        source = geometry(names)
        cmds.file(str(scene), open=True, force=True, executeScriptNodes=False)
        scene_evaluation.apply()
        reference = geometry()
        baseline_drawings = control_drawings()
        report['structure'] = structure()
        report['source_appearance'] = compare(source, reference, appearance=True)
        baseline_skins = skins()
        report['guide_matrices'] = {}
        if not cmds.objExists('C_guides_GRP'):
            # A normal CREATE RIG scene need not retain the authoring guides.
            guides_manager.load_guides_info(str(asset/'guides/flower_v001.guides'),new_scene=False,load_settings=True)
        saved_guides = json.loads((asset/'guides/flower_v001.guides').read_text())['flower']
        for name, data in saved_guides.items():
            matrix = np.array(cmds.xform(name, query=True, worldSpace=True, matrix=True))
            maximum = float(np.max(np.abs(matrix-np.array(data['joint_matrix']))))
            assert maximum < 1e-9, name
            report['guide_matrices'][name] = maximum

        entry = config['petals'][0]; ctl = entry['prefix']+'00_CTL'
        cmds.setAttr(ctl+'.tz', 2.)
        moved = geometry()
        selected = set(entry['vertices']); mesh = entry['mesh']
        distances = np.linalg.norm(moved[mesh]['points']-reference[mesh]['points'], axis=1)
        assert min(distances[list(selected)]) > 1.99
        assert max(distances[i] for i in range(len(distances)) if i not in selected) == 0.
        for other in mesh_names:
            if other != mesh:
                assert np.array_equal(moved[other]['points'], reference[other]['points'])
        cmds.setAttr(ctl+'.tz', 0.)
        report['independent_petal'] = 'passed'

        captured = {}
        for name, values in poses.items():
            pose(values)
            captured[name] = geometry()
            if name != 'neutral':
                displacement = max(float(np.linalg.norm(captured[name][m]['points']-reference[m]['points'], axis=1).max()) for m in mesh_names)
                assert displacement > 0.1
            for mode in ('off', 'serial', 'parallel'):
                cmds.evaluationManager(mode=mode)
                report['cases'][name+'_'+mode] = compare(captured[name], geometry())
                structure()

        for layer in ('A', 'B'):
            pose(poses['combined_scaled'])
            ctl = 'C_petal%s0100_CTL' % layer
            before = geometry()
            petal_module.set_space([ctl], space='World', key=False)
            report['cases'][layer+'_release'] = compare(before, geometry())
            structure()
            ids = next(e['vertices'] for e in config['petals'] if e['prefix'] == 'C_petal'+layer+'01')
            mesh = 'C_petals%s_GEO' % layer
            released = geometry()[mesh]['points'][ids]
            cmds.setAttr('C_masterwalk_CTL.tx', 13.)
            cmds.setAttr('C_stem03_CTL.rx', 32.)
            drift = float(np.linalg.norm(geometry()[mesh]['points'][ids]-released, axis=1).max())
            assert drift < tolerance, drift
            before = geometry()
            petal_module.set_space([ctl], space='Head', key=False)
            compare(before, geometry())
            cmds.setAttr('C_stem03_CTL.rx', 0.)
            for attr in ('tx', 'ty', 'tz', 'rx', 'ry', 'rz', 'sx', 'sy', 'sz'):
                cmds.setAttr(ctl+'.'+attr, 1. if attr.startswith('s') else 0.)
            report['cases'][layer+'_world_drift'] = drift

        cmds.file(str(scene), open=True, force=True, executeScriptNodes=False)
        ctl = 'C_petalA0100_CTL'; cmds.currentTime(12)
        pose(poses['combined_scaled']); before = geometry()
        cmds.select(ctl)
        registry.invoke('flower_release')
        compare(before, geometry())
        cmds.setKeyframe(ctl+'.ty', time=40, value=cmds.getAttr(ctl+'.ty')-8.)
        cmds.currentTime(40); animated = geometry()
        native = folder/'flower_animated_space_test.mb'
        cmds.file(rename=str(native)); cmds.file(save=True, type='mayaBinary', force=True)
        cmds.file(str(native), open=True, force=True, executeScriptNodes=False)
        cmds.currentTime(40)
        report['animated_reopen'] = compare(animated, geometry())
        for frame in (12, 40, 11, 24, 40, 12):
            cmds.currentTime(frame)
        cmds.currentTime(40)
        compare(animated, geometry())
        report['keyed_space'] = 'passed'

        for iteration in range(2):
            cmds.optionVar(stringValue=('currentAssetRigName', 'flower'))
            build_result = create_rig.AutoRig().build()
            structure()
            drawings = control_drawings()
            assert drawings.keys() == baseline_drawings.keys()
            for ctl, shapes in baseline_drawings.items():
                assert len(shapes) == len(drawings[ctl])
                for expected, actual in zip(shapes, drawings[ctl]):
                    assert np.max(np.abs(np.array(expected)-actual)) < 1e-9, ctl+' drawing drift'
            pose({})
            compare(reference, geometry(), appearance=True)
            current_skins = skins()
            for name, (weights, bind) in baseline_skins.items():
                assert np.array_equal(weights, current_skins[name][0]), name+' lossless weights'
                assert bind.keys() == current_skins[name][1].keys()
                assert max(abs(a-b) for joint, values in bind.items() for a,b in zip(values, current_skins[name][1][joint])) < 1e-10
            checks = {}
            for name, values in poses.items():
                pose(values); checks[name] = compare(captured[name], geometry(), appearance=True)
            pose({})
            native = folder/('flower_rebuild_%s.mb' % (iteration+1))
            cmds.file(rename=str(native)); cmds.file(save=True, type='mayaBinary', force=True)
            cmds.file(str(native), open=True, force=True, executeScriptNodes=False)
            compare(reference, geometry(), appearance=True)
            structure()
            state = scene_evaluation.apply()
            assert state['mode'] == 'parallel' and not any(state['evaluators'].values())
            assert not (cmds.cycleCheck(all=True, list=True) or [])
            report['rebuilds'].append(dict(iteration=iteration+1, poses=checks, native_reopen='passed',
                                           lossless_skins='passed', timing=build_result['timing_report']))
        report['passed'] = True
    except BaseException:
        import traceback
        report['passed'] = False; report['error'] = traceback.format_exc()
        raise
    finally:
        (folder/'flower_validation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        cmds.file(str(scene), open=True, force=True, executeScriptNodes=False)
        scene_evaluation.apply()
        cmds.currentTime(1); cmds.select(clear=True)
    return report


if __name__ == '__main__':
    os.environ['MAYA_SKIP_USERSETUP_PY'] = '1'
    import maya.standalone
    maya.standalone.initialize(name='python')
    run()
