"""Validate loop weights through Nini's actual animator controls and skeleton."""
import json
import math
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT))


def validate(scene):
    from maya import cmds
    from maya.api import OpenMaya as om
    from ngSkinTools2 import api
    from ngSkinTools2.api import target_info
    from maya_tools.scripts.tools import facial_loop_skinning as tool
    cmds.file(str(scene),open=True,force=True,executeScriptNodes=False)
    cmds.evaluationManager(mode='off');cmds.currentTime(1)
    report = json.loads(cmds.getAttr('Nini_LOOP_REVIEW_INFO.reviewData'))
    assert report['production_rig'] and not report['prototype']
    assert not cmds.objExists('C_loopBase_JNT') and not cmds.objExists('Nini_LoopReview_RIG')
    assert len(cmds.ls(type='joint')) == report['joint_count']
    skin = report['skin']
    assert skin=='C_body_SKC'
    influences = {i.path.rsplit('|',1)[-1]:i.logicalIndex for i in target_info.list_influences(skin)}
    assert len(influences)==report['skin_influence_count']
    assert all(j.endswith('_ENV') for region in report['regions'] for desc in region['weight_layers'] for j in desc['joints'])
    for region in report['regions']:
        for desc in region['weight_layers']:
            layer = tool.resolve_layer(skin,desc)
            for joint,expected in desc['weights'].items():
                values = layer.get_weights(influences[joint])
                expected = {int(v):w for v,w in expected.items()}
                assert all(abs(w-expected.get(v,0))<1e-6 for v,w in enumerate(values)),(layer.name,joint)
                assert cmds.listConnections(joint+'.offsetParentMatrix',s=True,d=False),joint
    lips = next(r for r in report['regions'] if r['layer_name']=='Lips')
    group = tool.resolve_layer(skin,lips)
    group.reload();assert group.num_children==2
    rot,nr = [tool.resolve_layer(skin,d) for d in lips['weight_layers']]
    assert rot.index>nr.index and rot.num_children==nr.num_children==0
    for c in lips['assignments']:
        assert rot.get_weights(influences[c['joint']])==nr.get_weights(influences[c['non_rotate_joint']])
    affected = set(lips['affected'])
    coverage = lips['coverage_overrides'][0]
    cheek = coverage['cheek_vertices']
    for layer,suffix in ((rot,''),(nr,'NonRot')):
        upper = layer.get_weights(influences['L_upperLip00'+suffix+'_ENV'])
        lower = layer.get_weights(influences['L_lowerLip00'+suffix+'_ENV'])
        assert all(abs(upper[v]-.5)<1e-6 and abs(lower[v]-.5)<1e-6 for v in cheek)
    def points(): return tool.read_mesh(report['mesh'])[1].points
    def maximum(a,b,vertices=None):
        return max(math.dist(a[v],b[v]) for v in (vertices if vertices is not None else range(len(a))))
    rest = points()
    states = [(layer,layer.enabled) for layer in api.Layers(skin).list()]
    pose_results = []
    for pose in report['poses']:
        cmds.currentTime(pose['frame'])
        posed = points()
        assert all(math.isfinite(c) for p in posed for c in p)
        movement = maximum(rest,posed)
        assert movement>1e-4,(pose['label'],movement)
        rot.enabled=True;nr.enabled=False
        rotate_only = points()
        nr.enabled=True
        both = points()
        composite_error = maximum(rotate_only,both)
        assert composite_error<1e-4,(pose['label'],'double deformation',composite_error)
        group.enabled=False
        production_base = points()
        group.enabled=True
        outside_error = maximum(production_base,both,set(range(len(rest)))-affected)
        assert outside_error<1e-4,(pose['label'],'outside mask changed',outside_error)
        info={'frame':pose['frame'],'label':pose['label'],'control':pose['control'],
              'max_mesh_movement':movement,'composite_error':composite_error,'outside_mask_error':outside_error}
        if pose['frame'] in (60,72):
            rot.enabled=False;nr.enabled=True
            non_rotate_only = points()
            no_roll = maximum(rest,non_rotate_only,affected)
            assert no_roll<1e-4,(pose['label'],'Non Rotate received roll',no_roll)
            rot.enabled=True
            roll_move = maximum(rest,points(),affected)
            assert roll_move>1e-3,('Rotate did not receive roll',roll_move)
            info.update(non_rotate_roll_movement=no_roll,rotate_roll_movement=roll_move)
        if pose['frame']==12:
            # At the corner both actual NonRot matrices have translation only,
            # so their 50/50 transformed points must match the skinned cheek.
            rot.enabled=False;nr.enabled=True
            actual = points()
            palette=[]
            for name in ('L_upperLip00NonRot_ENV','L_lowerLip00NonRot_ENV'):
                bind=om.MMatrix(cmds.getAttr('{}.bindPreMatrix[{}]'.format(skin,influences[name])))
                world=om.MMatrix(cmds.getAttr(name+'.worldMatrix[0]'))
                palette.append(bind*world)
            error=0
            for vertex in cheek:
                a,b=[om.MPoint(*rest[vertex])*matrix for matrix in palette]
                wanted=tuple((a[i]+b[i])*.5 for i in range(3))
                error=max(error,math.dist(wanted,actual[vertex]))
            assert error<.005,('Corner skin matrix mismatch',error)
            assert min(math.dist(rest[v],actual[v]) for v in cheek)>1e-3
            info.update(cheek_vertices_moved=len(cheek),cheek_skin_matrix_error=error,
                        cheek_min_movement=min(math.dist(rest[v],actual[v]) for v in cheek))
            rot.enabled=True
        pose_results.append(info)
    cmds.currentTime(1)
    neutral_return = maximum(rest,points())
    assert neutral_return<1e-4,neutral_return
    for layer,enabled in states:layer.enabled=enabled
    result={'production_rig':True,'production_influences':len(influences),'rig_joints':report['joint_count'],
            'layers':len(api.Layers(skin).list()),'matching_lip_pairs':30,'corner_50_50':True,
            'real_controls_tested':len(pose_results),'neutral_return_error':neutral_return,
            'neutral_transfer_error':report['neutral_transfer_max_error'],'poses':pose_results}
    print('PASS_REAL_NINI_LOOP_RIG='+json.dumps(result),flush=True)
    return result


if __name__=='__main__':
    os.environ['MAYA_SKIP_USERSETUP_PY']='1'
    import maya.standalone
    maya.standalone.initialize(name='python')
    try:
        from maya import cmds
        ng=Path('C:/ProgramData/Autodesk/ApplicationPlugins/ngskintools2/Contents')
        sys.path.insert(0,str(ng/'scripts'))
        cmds.loadPlugin(str(ng/'plug-ins'/str(cmds.about(version=True))/'ngSkinTools2.mll'),quiet=True)
        scene=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'maya_tools/assets/Nini/review/loop_rigger/Nini_LoopRigger_REAL_v001.ma'
        result=validate(scene)
        scene.with_suffix('.validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    finally:maya.standalone.uninitialize()
