"""Selection-driven rigger integration on the real Nini skin in isolated Maya."""
import json
import math
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from maya_tools.scripts.tools import facial_loop_riggers as riggers
from maya_tools.scripts.tools import facial_loop_skinning as loops


def test_roles():
    assert riggers.influence_role('|rig|nini:L_upperLip00NonRot_ENV','lips')['non_rotate']
    assert riggers.influence_role('R_downEyelid03_ENV','eyelid')['part'] == 'lower'
    assert riggers.influence_role('L_eyebrowSkinning00_ENV','eyebrow')['number'] == 0
    assert riggers.influence_role('C_eyebrowMidSkinning_ENV','eyebrow') is None
    assert riggers.influence_role('L_upperLip00_CTL','lips') is None


def run_real(scene):
    from maya import cmds
    from ngSkinTools2 import api
    from ngSkinTools2.api import target_info
    cmds.file(str(scene),open=True,force=True,executeScriptNodes=False)
    cmds.evaluationManager(mode='off');cmds.currentTime(1)
    cmds.currentTime(2,update=True);cmds.currentTime(1,update=True)
    cmds.dgdirty(allPlugs=True)
    mesh, topology = loops.read_mesh('c_body_GEO')
    skin='C_body_SKC';before_joints=cmds.ls(type='joint')
    before_influences=cmds.skinCluster(skin,q=True,influence=True)
    guides=json.loads((ROOT/'maya_tools/assets/Nini/guides/Nini_v010.guides').read_text())['Nini']
    def seed(name):
        cvs=guides[name]['curve_data']['cvs']
        return [min(range(len(topology.points)),key=lambda v:math.dist(topology.points[v],cv)) for cv in cvs]
    def select_path(vertices, closed=False):
        pairs=list(zip(vertices,vertices[1:]))
        if closed:pairs.append((vertices[-1],vertices[0]))
        lookup={tuple(sorted(e)):i for i,e in enumerate(topology.edges)}
        indices=[lookup[tuple(sorted(e))] for e in pairs]
        cmds.select(['{}.e[{}]'.format(mesh,i) for i in indices],replace=True)
        return cmds.ls(sl=True,long=True)
    def records(kind):
        name=riggers.REGION_NAMES[kind]
        nodes=cmds.ls('*.loopRegionData',objectsOnly=True,recursive=True) or []
        return next(json.loads(cmds.getAttr(n+'.loopRegionData')) for n in nodes
                    if json.loads(cmds.getAttr(n+'.loopRegionData'))['layer_name']==name)
    def check_black():
        for layer in api.Layers(skin).list():
            if layer.name!='Base weights':
                assert len(layer.get_weights(api.NamedPaintTarget.MASK))==len(topology.points)
                assert not any(layer.get_weights(api.NamedPaintTarget.MASK)),layer.name
    def weights(layer,joint):
        index=next(i.logicalIndex for i in target_info.list_influences(skin)
                   if i.path==cmds.ls(joint,long=True)[0])
        return layer.get_weights(index) or [0.0]*len(topology.points)
    def paired_weights(record):
        parent=loops.resolve_layer(skin,record)
        assert parent.num_children==2
        rot,nr=[loops.resolve_layer(skin,d) for d in record['weight_layers']]
        assert rot.name=='Rotate' and nr.name=='Non Rotate' and rot.index>nr.index
        for column in record['assignments']:
            assert weights(rot,column['joint'])==weights(nr,column['non_rotate_joint'])
        return rot,nr

    upper,lower=seed('C_upperLipLinear_CRVShape'),seed('C_lowerLipLinear_CRVShape')
    lip_contour=upper+list(reversed(lower[1:-1]))
    selection=select_path(lip_contour,True)
    results={'lips':riggers.apply('lips',skin)}
    assert cmds.ls(sl=True,long=True)==selection,'The backend changed the edge selection.'
    lips=records('lips');rot,nr=paired_weights(lips)
    assert len(lips['assignments'])==30, [a['joint'].rsplit('|',1)[-1] for a in lips['assignments']]
    assert len(api.Layers(skin).list())==4
    check_black()
    # Repeating the action reuses the exact same hierarchy.
    riggers.apply('lips',skin)
    assert len(api.Layers(skin).list())==4
    # Older review scenes store a whole upper/lower row in each section.
    # Replacing only their corners must retain every other joint assignment.
    legacy_sections=[]
    for part,vertices in (('upper',upper),('lower',lower)):
        by_anchor={a['anchor']:a for a in lips['assignments'] if riggers.influence_role(a['joint'],'lips')['part']==part}
        plan=loops.plan_columns(topology,vertices)
        plan.update(mesh=mesh,space='skin_bind')
        legacy_sections.append(dict(plan=plan,joints=[by_anchor[v]['joint'] for v in vertices],
            non_rotate_joints=[by_anchor[v]['non_rotate_joint'] for v in vertices]))
    lips['sections']=legacy_sections
    cmds.setAttr(results['lips']['metadata']+'.loopRegionData',json.dumps(lips),type='string')
    # Literal full corner loop, including its pole continuation, must be 50/50.
    reference=json.loads((ROOT/'maya_tools/assets/Nini/review/loop_rigger/Nini_LoopRigger_REAL_v001.json').read_text())
    coverage=reference['regions'][0]['sections'][0]['plan']['coverage_overrides'][0]
    corner=coverage['corner_loop']
    select_path(corner,True)
    results['corner']=riggers.apply('lips',skin)
    assert results['corner']['mode']=='transverse'
    lips=records('lips');rot,nr=paired_weights(lips)
    assert len(lips['assignments'])==30,'Updating a corner removed another joint from a legacy section.'
    left=[v for v in corner if topology.points[v][0]>1e-5]
    for layer in (rot,nr):
        suffix='NonRot' if layer.name=='Non Rotate' else ''
        a=weights(layer,'L_upperLip00'+suffix+'_ENV')
        b=weights(layer,'L_lowerLip00'+suffix+'_ENV')
        assert all(abs(a[v]-.5)<1e-6 and abs(b[v]-.5)<1e-6 for v in left)

    eye_upper,eye_lower=seed('L_eyelidUpperLinear_CRVShape'),seed('L_eyelidLowerLinear_CRVShape')
    select_path(eye_upper+list(reversed(eye_lower[1:-1])),True)
    results['eyelid']=riggers.apply('eyelid',skin)
    assert results['eyelid']['mirrored']
    eyelids=records('eyelid')
    assert len(eyelids['assignments'])==36
    for column in eyelids['assignments']:
        assert column['weights'],column['joint']

    select_path(seed('L_eyebrow_CRVShape'))
    results['eyebrow']=riggers.apply('eyebrow',skin)
    assert results['eyebrow']['mirrored'] and results['eyebrow']['brow_extensions']
    brows=records('eyebrow')
    assert len(brows['assignments'])==12,[a['joint'].rsplit('|',1)[-1] for a in brows['assignments']]
    layer=loops.resolve_layer(skin,brows)
    brow00=weights(layer,'L_eyebrowSkinning00_ENV')
    extension=results['eyebrow']['brow_extensions'][0]
    assert all(abs(brow00[v]-1)<1e-6 for v in extension['inner_vertices'])
    assert all(brow00[v]==0 for v in extension['excluded_mid_loop'])
    # Each action also supports selecting a single complete transverse loop.
    for kind,record,needle in (('eyelid',eyelids,'L_upperEyelid04_ENV'),('eyebrow',brows,'L_eyebrowSkinning02_ENV')):
        column=next(a for a in record['assignments'] if a['joint'].endswith('|'+needle))
        paths=column['paths']
        vertices=list(reversed(paths[0]))+paths[1][1:] if len(paths)==2 else paths[0]
        if len(set(vertices))!=len(vertices):
            # A closed trace can return to the anchor from either side.
            vertices=list(dict.fromkeys(vertices))
        select_path(vertices,vertices[0] in topology.neighbors[vertices[-1]])
        update=riggers.apply(kind,skin)
        assert update['mode']=='transverse',(kind,update)
        assert len(records(kind)['assignments'])==len(record['assignments'])
        results[kind+'_transverse']=True
    select_path(eye_upper+list(reversed(eye_lower[1:-1])),True)
    eyelid_layer=loops.resolve_layer(skin,records('eyelid'))
    mask=eyelid_layer.get_weights(api.NamedPaintTarget.MASK);mask[0]=.25
    eyelid_layer.set_weights(api.NamedPaintTarget.MASK,mask)
    riggers.apply('eyelid',skin)
    assert abs(eyelid_layer.get_weights(api.NamedPaintTarget.MASK)[0]-.25)<1e-6
    mask[0]=0;eyelid_layer.set_weights(api.NamedPaintTarget.MASK,mask)
    check_black()
    assert len(api.Layers(skin).list())==6
    # Masks prevent any new deformation; the real skeleton and influence list remain.
    _,after=loops.read_mesh(mesh)
    neutral=max(math.dist(a,b) for a,b in zip(topology.points,after.points))
    assert neutral<1e-5,neutral
    assert cmds.ls(type='joint')==before_joints
    assert cmds.skinCluster(skin,q=True,influence=True)==before_influences
    # Reject a wrong target before creating any NG layers there.
    other_mesh=cmds.polyPlane(name='wrongMesh')[0]
    other_joint=cmds.createNode('joint',name='wrongBase')
    other_skin=cmds.skinCluster(other_joint,other_mesh,toSelectedBones=True)[0]
    select_path(seed('L_eyebrow_CRVShape'))
    try:riggers.apply('lips',other_skin)
    except ValueError as exc:assert 'different mesh' in str(exc)
    else:raise AssertionError('A foreign edge selection was accepted.')
    # The saved hierarchy and metadata must still update after NG renumbers IDs.
    output=ROOT/'.git/ng_rigger_test_result.ma'
    cmds.file(rename=str(output));cmds.file(save=True,type='mayaAscii',force=True)
    cmds.file(str(output),open=True,force=True,executeScriptNodes=False)
    select_path(seed('L_eyebrow_CRVShape'))
    riggers.apply('eyebrow',skin)
    assert len(api.Layers(skin).list())==6
    check_black()
    results.update(neutral_max_error=neutral,joints=len(before_joints),influences=len(before_influences),
                   black_masks=True,paired_weights_identical=True,corner_50_50=True,
                   repeat_and_reopen=True,wrong_target_rejected=True)
    return results


if __name__=='__main__':
    os.environ['MAYA_SKIP_USERSETUP_PY']='1'
    import maya.standalone
    maya.standalone.initialize(name='python')
    try:
        from maya import cmds
        ng=Path(os.environ.get('PROGRAMDATA','C:/ProgramData'))/'Autodesk/ApplicationPlugins/ngskintools2/Contents'
        sys.path.insert(0,str(ng/'scripts'))
        cmds.loadPlugin(str(ng/'plug-ins'/cmds.about(version=True)/'ngSkinTools2.mll'),quiet=True)
        test_roles()
        scene=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'maya_tools/assets/Nini/review/loop_rigger/Nini_ManualLoops_v001.ma'
        result=run_real(scene)
        (ROOT/'.git/ng_rigger_validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print('PASS_FACIAL_RIGGERS='+json.dumps(result),flush=True)
    finally:maya.standalone.uninitialize()
