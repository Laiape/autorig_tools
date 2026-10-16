"""Run in mayapy: ordered guide paths, native modules, posing and persistence."""
import ast
import json
import math
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

os.environ.setdefault('MAYA_SKIP_USERSETUP_PY', '1')
import maya.standalone
from maya import cmds
from maya.api import OpenMaya as om

ROOT = Path(__file__).resolve().parents[4]
SCRIPTS = ROOT / 'maya_tools/scripts'


def functions(path, names, scope):
    source = ast.parse(path.read_text(encoding='utf-8'))
    body = [n for n in source.body if isinstance(n, ast.FunctionDef) and n.name in names]
    exec(compile(ast.Module(body=body, type_ignores=[]), str(path), 'exec'), scope)
    return SimpleNamespace(**{n: scope[n] for n in names})


def close(a, b, tolerance=1e-7):
    assert len(a) == len(b)
    assert max(abs(x-y) for x,y in zip(a,b)) < tolerance, (a,b)


def chain(kind, positions):
    nodes = []
    for i, p in enumerate(positions):
        node = cmds.createNode('joint', name='C_%s%02d_JNT' % (kind,i),
                               **({'parent':nodes[-1]} if nodes else {}))
        cmds.xform(node, ws=True, t=p)
        nodes.append(node)
    return nodes


def setup():
    scope = dict(cmds=cmds, om=om, math=math)
    guides = functions(SCRIPTS/'utils/guides_manager.py',
                       {'_axis_index_sign','_aim_matrix','_with_translation','sample_chain_matrices'}, scope)
    curve_scope = dict(cmds=cmds, om=om, build_curves_from_template=lambda name: None)
    curves = functions(SCRIPTS/'utils/curve_tool.py',
                       {'create_controller','lock_attributes'}, curve_scope)
    sys.path.insert(0, str(ROOT))
    from maya_tools.scripts.utils import ribbon
    from maya_tools.scripts.utils.module_nurbs import organize_module_nurbs
    return guides, curves, ribbon, organize_module_nurbs


def module(kind, positions, count, helpers):
    guides,curves,ribbon,organize = helpers
    cmds.file(new=True,force=True)
    roots={k:cmds.createNode('transform',name=k) for k in ('modules_GRP','skel_GRP','masterwalk_ctl','preferences_ctl')}
    cmds.addAttr(roots['masterwalk_ctl'],ln='globalScale',at='double',dv=1,k=True)
    for axis in 'XYZ':
        cmds.connectAttr(roots['masterwalk_ctl']+'.globalScale',roots['masterwalk_ctl']+'.scale'+axis)
    source = chain(kind, positions)
    def get_guides(name, parent=None):
        if name == 'C_localHip_JNT':
            return []
        assert name=='C_%s00_JNT'%kind
        if parent:
            cmds.parent(source[0],parent)
        return source
    guide_api=SimpleNamespace(**vars(guides),get_guides=get_guides)
    data=SimpleNamespace(get_data=lambda section,key:roots.get(key),append_data=lambda *args:None)
    path=SCRIPTS/'quadruped/autorig'/('%s_module.py'%kind)
    source_ast=ast.parse(path.read_text(encoding='utf-8'))
    cls=next(n for n in source_ast.body if isinstance(n,ast.ClassDef))
    scope=dict(cmds=cmds,om=om,math=math,curve_tool=curves,guides_manager=guide_api,
               data_manager=SimpleNamespace(DataExportBiped=lambda:data),ribbon=ribbon,
               organize_module_nurbs=organize)
    exec(compile(ast.Module(body=[cls],type_ignores=[]),str(path),'exec'),scope)
    rig=scope[cls.name]()
    rig.make('C',8,count)
    controls=rig.tail_controllers if kind=='tail' else rig.neck_ctls if kind=='neck' else rig.spine_ctls
    matrices=rig.tail_guides_matrices if kind=='tail' else rig.neck_guides_matrices if kind=='neck' else rig.spine_guides_matrices
    assert len(controls)==max(count,len(positions))
    for ctl,m in zip(controls,matrices):
        close(cmds.xform(ctl,q=True,ws=True,m=True),m)
        close(cmds.getAttr(ctl+'.translate')[0],(0,0,0))
        close(cmds.getAttr(ctl+'.rotate')[0],(0,0,0))
    measured=[m[12:15] for m in matrices]
    for p in positions:
        assert any((om.MVector(p)-om.MVector(q)).length()<1e-7 for q in measured), (kind,p,measured)
    # Independent ordered-segment check: no sample may cut across a corner.
    segment=0
    for p in measured:
        while segment<len(positions)-2 and (om.MVector(p)-om.MVector(positions[segment+1])).length()<1e-7:
            segment+=1
        a,b=map(om.MVector,(positions[segment],positions[segment+1]))
        vector=om.MVector(p)-a
        assert (vector ^ (b-a)).length()<1e-6
        assert -1e-7 <= vector*(b-a)/((b-a)*(b-a)) <= 1+1e-7
    for i,m in enumerate(matrices):
        # At a corner the frame must aim down the following authored segment.
        p=om.MVector(m[12:15])
        segment=0
        for anchor in range(1,len(positions)-1):
            if any((om.MVector(q)-om.MVector(positions[anchor])).length()<1e-7 for q in measured[:i+1]):
                segment=anchor
        direction=(om.MVector(positions[segment+1])-om.MVector(positions[segment])).normal()
        assert om.MVector(m[:3])*direction>1-1e-7
        x,y,z=(om.MVector(m[j:j+3]) for j in (0,4,8))
        assert abs(x.length()-1)<1e-7 and abs(y.length()-1)<1e-7
        assert (x ^ y)*z>1-1e-7
    joints=sorted(cmds.listRelatives(rig.skeleton_grp,ad=True,type='joint') or [])
    assert joints
    neutral=[cmds.xform(j,q=True,ws=True,m=True) for j in joints]
    cmds.setAttr(controls[len(controls)//2]+'.rz',18)
    cmds.setAttr(controls[0]+'.ry',12)
    if kind != 'tail':
        cmds.setAttr(controls[len(controls)//2]+'.ty',.8)
    posed=[cmds.xform(j,q=True,ws=True,m=True) for j in joints]
    assert max(abs(a-b) for m,n in zip(neutral,posed) for a,b in zip(m,n))>1e-3
    # Exercise live native deformation, rather than accepting static outputs.
    mesh=cmds.polyCube(name='test_skin',w=2,h=2,d=2,ch=False)[0]
    skin=cmds.skinCluster(joints,mesh,tsb=True)[0]
    bound_points=cmds.xform(mesh+'.vtx[*]',q=True,ws=True,t=True)
    cmds.setAttr(controls[len(controls)//2]+'.rz',-13)
    if kind != 'tail':
        cmds.setAttr(controls[len(controls)//2]+'.ty',-.6)
    deformed_points=cmds.xform(mesh+'.vtx[*]',q=True,ws=True,t=True)
    assert max(abs(a-b) for a,b in zip(bound_points,deformed_points))>1e-4
    signatures=[]
    for mode in ('off','serial','parallel'):
        cmds.evaluationManager(mode=mode)
        cmds.dgdirty(allPlugs=True)
        values=[v for j in joints for v in cmds.xform(j,q=True,ws=True,m=True)]
        points=cmds.xform(mesh+'.vtx[*]',q=True,ws=True,t=True)
        assert all(math.isfinite(x) for x in values+points)
        signatures.append(values+points)
    for sig in signatures[1:]:
        close(sig,signatures[0],1e-6)
    assert not cmds.cycleCheck(all=True,list=True), kind
    cmds.setAttr(roots['masterwalk_ctl']+'.globalScale',1.7)
    scaled=[v for j in joints for v in cmds.xform(j,q=True,ws=True,m=True)]
    assert all(math.isfinite(x) for x in scaled)
    state=[v for j in joints for v in cmds.xform(j,q=True,ws=True,m=True)] + cmds.xform(mesh+'.vtx[*]',q=True,ws=True,t=True)
    return dict(kind=kind,requested=count,actual=len(controls),guides=len(positions),
                controls=controls,joints=joints,mesh=mesh,state=state,rest=measured)


def run():
    maya.standalone.initialize(name='python')
    try:
        cmds.loadPlugin('lookdevKit',quiet=True)
        cmds.loadPlugin('matrixNodes',quiet=True)
        helpers=setup()
        guides=helpers[0]
        positions=[(0,0,0),(2,3,0),(4,3,2),(6,6,2)]
        # Counts smaller/equal/larger than the source, plus two-guide legacy spacing.
        cmds.file(new=True,force=True)
        source=chain('test',positions)
        for count in (2,4,5,9):
            before=set(cmds.ls())
            result=guides.sample_chain_matrices(source,count)
            assert len(result)==max(count,len(source))
            assert set(cmds.ls())==before
        try:
            guides.sample_chain_matrices([source[0],source[2]],3)
            raise AssertionError('Skipped guide accepted')
        except ValueError:
            pass
        cmds.file(new=True,force=True)
        source=chain('test',[(0,0,0),(10,0,0)])
        result=guides.sample_chain_matrices(source,5,spacing_bias=1.3)
        for i,m in enumerate(result):
            close(m[12:15],(10*(i/4)**1.3,0,0))
        cmds.xform(source[1],ws=True,t=(0,0,0))
        try:
            guides.sample_chain_matrices(source,5)
            raise AssertionError('Zero-length segment accepted')
        except ValueError:
            pass
        rows=[]
        with tempfile.TemporaryDirectory() as folder:
            for kind in ('tail','spine','neck'):
                for count in (2,4,7):
                    first=module(kind,positions,count,helpers)
                    second=module(kind,positions,count,helpers)
                    close(first['state'],second['state'],1e-6)
                    path=Path(folder)/('%s_%s.ma'%(kind,count))
                    cmds.file(rename=str(path));cmds.file(save=True,type='mayaAscii',force=True)
                    cmds.file(str(path),open=True,force=True)
                    state=[v for j in second['joints'] for v in cmds.xform(j,q=True,ws=True,m=True)] + cmds.xform(second['mesh']+'.vtx[*]',q=True,ws=True,t=True)
                    close(state,second['state'],1e-6)
                    rows.append({k:v for k,v in second.items() if k in ('kind','requested','actual','guides')})
                    print('PASS',rows[-1],flush=True)
            # Real Chihuahua authoring data catches the original three-guide tail.
            guide_file=sorted((ROOT/'maya_tools/assets/chihuahua/guides').glob('chihuahua_v*.guides'))[-1]
            asset=json.loads(guide_file.read_text())['chihuahua']
            for kind,count in (('tail',5),('spine',5),('neck',2)):
                root='C_%s00_JNT'%kind
                names=[root]+asset[root]['children']
                positions=[asset[n]['joint_matrix'][12:15] for n in names]
                row=module(kind,positions,count,helpers)
                rows.append({k:v for k,v in row.items() if k in ('kind','requested','actual','guides')})
                print('PASS Chihuahua',rows[-1],flush=True)
        if len(sys.argv)>1:
            Path(sys.argv[1]).write_text(json.dumps(dict(passed=True,cases=rows,
                maya=cmds.about(version=True),guide_file=str(guide_file),
                scope='Native module methods with fixture guide loading and fallback curves; not a full-character rebuild',
                checks=['all authored guide anchors','ordered segment sampling','local tangent frames',
                        'neutral controller channels','live skin deformation','DG/Serial/Parallel agreement',
                        'global scale','two reproducible builds','native save and reopen','no cycles']),indent=2))
    finally:
        cmds.file(new=True,force=True)
        maya.standalone.uninitialize()


if __name__=='__main__':
    run()
