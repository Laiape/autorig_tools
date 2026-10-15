"""Pure topology checks plus saved Nini/NG integration with mayapy."""
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from maya_tools.scripts.tools import facial_loop_skinning as tool


def test_topology():
    width, height = 5, 17
    points = [(x, y, 0) for y in range(height) for x in range(width)]
    faces = [[y*width+x,y*width+x+1,(y+1)*width+x+1,(y+1)*width+x]
             for y in range(height-1) for x in range(width-1)]
    topology = tool.Topology(points, faces)
    seed = list(range(8*width, 9*width))
    plan = tool.plan_columns(topology, seed)
    assert len(plan['columns']) == width
    for index,column in enumerate(plan['columns']):
        assert column['vertices'] == [y*width+index for y in range(height)]
        assert len(column['vertices']) > 9, 'The old row limit must not truncate a full loop.'
    # Reversed input follows identical full columns.
    reversed_plan = tool.plan_columns(topology, list(reversed(seed)))
    assert {tuple(c['vertices']) for c in plan['columns']} == {tuple(c['vertices']) for c in reversed_plan['columns']}
    try:
        topology.order_edges([i for i,edge in enumerate(topology.edges) if 0 in edge or 44 in edge])
    except ValueError:
        pass
    else:
        raise AssertionError('Disconnected edge selections must be rejected.')


def validate_nini(scene):
    from maya import cmds
    from ngSkinTools2 import api
    from ngSkinTools2.api import target_info
    cmds.file(str(ROOT/'maya_tools/assets/Nini/models/Nini_v003.ma'),open=True,force=True,executeScriptNodes=False)
    _, original = tool.read_mesh('c_body_GEO')
    cmds.file(str(scene),open=True,force=True,executeScriptNodes=False)
    cmds.currentTime(1)
    report = json.loads(cmds.getAttr('Nini_LOOP_REVIEW_INFO.reviewData'))
    mesh, topology = tool.read_mesh(report['mesh'])
    neutral_error = max(math.dist(a,b) for a,b in zip(original.points,topology.points))
    assert len(original.points) == len(topology.points) and neutral_error < 1e-4, neutral_error
    skin = report['skin']
    influences = {i.path:i.logicalIndex for i in target_info.list_influences(skin)}
    def index(joint): return influences[cmds.ls(joint,long=True)[0]]
    def array(layer,joint):
        values = layer.get_weights(index(joint))
        return values or [0.0]*len(topology.points)
    lips = next(r for r in report['regions'] if r['layer_name'] == 'Lips')
    parent = tool.resolve_layer(skin,lips)
    parent.reload()
    assert parent.num_children == 2
    assert {child.name for child in parent.children} == {'Rotate','Non Rotate'}
    assert all(child.num_children == 0 for child in parent.children)
    rot,nr = [tool.resolve_layer(skin,r) for r in lips['weight_layers']]
    assert rot.index > nr.index, 'Rotate must be above Non Rotate in NG.'
    assert len(lips['assignments']) == 30
    assert len(api.Layers(skin).list()) == 10
    for region in report['regions']:
        weights = tool.column_distribution(topology,region['assignments'])
        if region['mirrored']: weights = tool.mirror_distribution(topology,region['assignments'],weights)
        overrides = [o for section in region['sections'] for o in section['plan'].get('coverage_overrides',[])]
        if overrides: weights = tool.override_coverage(topology,region['assignments'],weights,overrides,mirror=region['mirrored'])
        affected = {v for column in weights for v in column}
        for description in region['weight_layers']:
            layer = tool.resolve_layer(skin,description)
            mask = layer.get_weights(api.NamedPaintTarget.MASK)
            assert len(mask) == len(topology.points)
            assert all(value == (1.0 if v in affected else 0.0) for v,value in enumerate(mask))
            totals = [0.0]*len(topology.points)
            allowed = set()
            for column,expected in zip(region['assignments'],weights):
                joint = column['non_rotate_joint'] if description['kind']=='non_rotate' else column['joint']
                actual = array(layer,joint)
                error = max(abs(value-expected.get(v,0)) for v,value in enumerate(actual))
                assert error < 1e-6, (region['layer_name'],layer.name,joint,error)
                assert math.dist(cmds.xform(joint,q=True,ws=True,t=True),topology.points[column['anchor']]) < 1e-5
                allowed.add(index(joint))
                for v,value in enumerate(actual): totals[v] += value
            assert set(layer.get_used_influences()).issubset(allowed), (layer.name,layer.get_used_influences(),allowed)
            assert all(abs(total-(1 if v in affected else 0))<1e-6 for v,total in enumerate(totals))
    for column in lips['assignments']:
        assert array(rot,column['joint']) == array(nr,column['non_rotate_joint'])
    mirrors = tool.symmetry_map(topology.points)
    by_name = {c['joint'].rsplit('|',1)[-1]:c for c in lips['assignments']}
    for joint,column in by_name.items():
        partner = 'R_'+joint[2:] if joint.startswith('L_') else ('L_'+joint[2:] if joint.startswith('R_') else joint)
        a,b = array(rot,joint),array(rot,partner)
        assert all(abs(value-b[mirrors[v]])<1e-6 for v,value in enumerate(a) if mirrors[v]>=0)
    coverage = lips.get('coverage_overrides',[None])[0]
    lateral = set(coverage['corner_loop'] if coverage else by_name['L_upperLip00_JNT']['vertices'])
    upper = [array(rot,side+'_upperLip00_JNT') for side in ('L','R')]
    lower = [array(rot,side+'_lowerLip00_JNT') for side in ('L','R')]
    assert len(lateral) == (110 if coverage else 51)
    for v in lateral:
        assert abs(sum(a[v] for a in upper)-.5)<1e-6, ('upper corner',v)
        assert abs(sum(a[v] for a in lower)-.5)<1e-6, ('lower corner',v)
    if coverage:
        assert all(b in topology.neighbors[a] for a,b in zip(coverage['corner_loop'],coverage['corner_loop'][1:]+coverage['corner_loop'][:1]))
        assert len(coverage['cheek_vertices']) > 150
        assert all(abs(upper[0][v]-.5)<1e-6 and abs(lower[0][v]-.5)<1e-6 for v in coverage['cheek_vertices'])
        assert all(abs(upper[1][mirrors[v]]-.5)<1e-6 and abs(lower[1][mirrors[v]]-.5)<1e-6 for v in coverage['cheek_vertices'])
    for side in ('L','R'):
        region = next(r for r in report['regions'] if r['layer_name']==side+'_Brow')
        extension = region['brow_extension']
        assert len(extension['inner_vertices']) == 2
        layer = tool.resolve_layer(skin,region)
        values = array(layer,side+'_eyebrow00_JNT')
        assert all(abs(values[v]-1)<1e-6 for v in extension['inner_vertices'])
        assert all(values[v] == 0 for v in extension['excluded_mid_loop'])
    # Both child layers independently give the same translation. Enabling both
    # must preserve it because NG composites them, instead of adding movement.
    centre = by_name['C_upperLip00_JNT']
    centre_weights = array(rot,centre['joint'])
    states = [(layer,layer.enabled) for layer in api.Layers(skin).list()]
    for region in report['regions']: tool.resolve_layer(skin,region).enabled = region is lips
    translation_error = 0
    for rotate_on,non_rotate_on in ((True,False),(False,True),(True,True)):
        rot.enabled=rotate_on;nr.enabled=non_rotate_on
        cmds.currentTime(1);_,rest=tool.read_mesh(mesh)
        cmds.currentTime(12);_,posed=tool.read_mesh(mesh)
        for v,(a,b) in enumerate(zip(rest.points,posed.points)):
            wanted=(0,.35*centre_weights[v],0)
            delta=tuple(y-x for x,y in zip(a,b))
            error=max(abs(x-y) for x,y in zip(delta,wanted))
            translation_error=max(translation_error,error)
            assert error<2e-4,(rotate_on,non_rotate_on,v,delta,wanted)
    cmds.currentTime(24)
    assert cmds.getAttr(centre['non_rotate_joint']+'.rotate')[0] == (0.0,0.0,0.0)
    assert abs(cmds.getAttr(centre['joint']+'.rotateX')-12)<1e-5
    # Test the commissure through the skinned geometry, not just stored arrays.
    cmds.currentTime(1);_,rest=tool.read_mesh(mesh)
    cmds.currentTime(90);_,posed=tool.read_mesh(mesh)
    corner_weights=array(rot,'L_upperLip00_JNT')
    for v,(a,b) in enumerate(zip(rest.points,posed.points)):
        assert max(abs(b[k]-a[k]-(.25*corner_weights[v] if k==1 else 0)) for k in range(3))<2e-4
    cmds.currentTime(1)
    for layer,enabled in states: layer.enabled=enabled
    result={'regions':len(report['regions']),'ng_layers':len(api.Layers(skin).list()),
            'lip_layers':['Lips','Rotate','Non Rotate'],'identical_lip_pairs':30,
            'corner_vertices':len(lateral),'corner_upper_lower_50_50':True,'mirror_L_to_R':True,
            'annotated_cheek_vertices_L':len(coverage['cheek_vertices']) if coverage else 0,
            'brow00_extended_to_mid_neighbor':True,'full_coverage_normalized':True,
            'translation_max_error':translation_error,'nonrotate_stays_unrotated':True,
            'neutral_model_max_error':neutral_error}
    print('PASS_NINI_LOOP_REVIEW='+json.dumps(result),flush=True)
    return result


def run_ui():
    import json,traceback
    from importlib import reload
    from maya import cmds
    from PySide6 import QtCore,QtWidgets
    from maya_tools.scripts.ui import skinning_manager_UI as ui
    from maya_tools.scripts.ui import skinning_tool_adapters as adapters
    from maya_tools.scripts.ui import facial_loop_skinning_UI as loop_ui
    from maya_tools.scripts.tools import facial_loop_skinning as tool
    from ngSkinTools2 import api
    selection=cmds.ls(selection=True,long=True)
    context=cmds.currentCtx();modified=cmds.file(query=True,modified=True)
    namespace=cmds.namespaceInfo(currentNamespace=True);undo=cmds.undoInfo(query=True,state=True)
    ns=None;result={}
    try:
        if cmds.workspaceControl(ui.WORKSPACE,exists=True):
            cmds.workspaceControl(ui.WORKSPACE,edit=True,close=True)
            QtWidgets.QApplication.processEvents()
            QtCore.QCoreApplication.sendPostedEvents(None,QtCore.QEvent.DeferredDelete)
        reload(tool);reload(loop_ui);reload(adapters);reload(ui)
        panel=ui.show();ng=panel.pages[0].content
        assert ng, panel.pages[0].message.text()
        cmds.undoInfo(stateWithoutFlush=False)
        ns=cmds.namespace(add='facialLoopUiTest');cmds.namespace(set=ns)
        mesh=cmds.polyPlane(name='grid',subdivisionsX=4,subdivisionsY=16,width=4,height=16)[0]
        base=cmds.createNode('joint',name='base')
        skin=cmds.skinCluster(base,mesh,toSelectedBones=True)[0]
        cmds.select(mesh,replace=True);panel.load_selection();ng.refresh()
        _,topology=tool.read_mesh(mesh)
        seed=set(range(40,45))
        edges=[i for i,(a,b) in enumerate(topology.edges) if a in seed and b in seed]
        cmds.select(['{}.e[{}]'.format(mesh,i) for i in edges],replace=True)
        ng.editor_tabs.setCurrentIndex(1)
        widget=ng.loop_rigger
        widget.load_seed()
        assert len(widget.plan['seed'])==5
        assert all(len(c['vertices'])==17 for c in widget.plan['columns'])
        widget.preview()
        assert cmds.objExists(widget.preview_group)
        widget.create_joints();assert len(widget.joints)==10
        widget.create_layers()
        assert ng.editor_tabs.currentIndex()==0
        groups=[layer for layer in api.Layers(skin).list() if layer.name=='Lips']
        assert len(groups)==1 and groups[0].num_children==2
        assert 'Updated 2 weight layers' in widget.details.toPlainText()
        before_layers = len(api.Layers(skin).list())
        rotate_layer = next(layer for layer in api.Layers(skin).list() if layer.name == 'Rotate')
        mask = rotate_layer.get_weights(api.NamedPaintTarget.MASK)
        mask[0] = .3
        rotate_layer.set_weights(api.NamedPaintTarget.MASK,mask)
        widget.create_joints()
        widget.create_layers()
        assert len(api.Layers(skin).list()) == before_layers, 'Appending lower lips must reuse the two child layers.'
        assert abs(rotate_layer.get_weights(api.NamedPaintTarget.MASK)[0]-.3)<1e-6
        from ngSkinTools2.api import target_info
        for layer in api.Layers(skin).list():
            if layer.name not in ('Rotate','Non Rotate'): continue
            for influence in layer.get_used_influences():
                values = layer.get_weights(influence)
                assert set(values).issubset({0.0,.5}), 'Shared anchors must split upper/lower equally within each layer.'
        # Updating a painted region must not let NG normalize partial writes
        # against the previous owners of explicitly reassigned vertices.
        widget.plan['coverage_overrides']=[{'anchor':widget.plan['seed'][0],
                                           'vertices':widget.plan['columns'][1]['vertices']}]
        widget.create_layers()
        nodes=cmds.ls('*.loopRegionData',objectsOnly=True,recursive=True)
        record=next(json.loads(cmds.getAttr(n+'.loopRegionData')) for n in nodes
                    if json.loads(cmds.getAttr(n+'.loopRegionData')).get('skin') == skin)
        indices={i.path:i.logicalIndex for i in target_info.list_influences(skin)}
        for desc in record['weight_layers']:
            layer=tool.resolve_layer(skin,desc)
            for column in record['assignments']:
                joint=column['non_rotate_joint'] if desc['kind']=='non_rotate' else column['joint']
                values=layer.get_weights(indices[cmds.ls(joint,long=True)[0]])
                wanted=.5 if column['anchor']==widget.plan['seed'][0] else 0
                assert all(abs(values[v]-wanted)<1e-6 for v in widget.plan['columns'][1]['vertices'])
        widget.select_vertices();assert len(cmds.ls(selection=True,flatten=True))==85
        widget.clear_preview()
        result={'integrated_ui':True,'full_columns':True,'paired_lip_joints':True,'preview_and_create':True,'selected_vertices':85}
    except Exception:
        result={'error':traceback.format_exc()}
    finally:
        cmds.setToolTo(context);cmds.namespace(set=namespace)
        if ns and cmds.namespace(exists=ns):cmds.namespace(removeNamespace=ns,deleteNamespaceContent=True)
        cmds.select(selection,replace=True) if selection else cmds.select(clear=True)
        cmds.undoInfo(stateWithoutFlush=undo)
        cmds.file(modified=modified)
        if ui._panel:ui._panel.scene_changed()
    if "error" in result: raise AssertionError(result["error"])
    return result


if __name__ == '__main__':
    import os
    os.environ['MAYA_SKIP_USERSETUP_PY']='1'
    import maya.standalone
    maya.standalone.initialize(name='python')
    try:
        from maya import cmds
        ng_root = Path(os.environ.get('PROGRAMDATA','C:/ProgramData'))/'Autodesk/ApplicationPlugins/ngskintools2/Contents'
        sys.path.insert(0,str(ng_root/'scripts'))
        cmds.loadPlugin(str(ng_root/'plug-ins'/str(cmds.about(version=True))/'ngSkinTools2.mll'),quiet=True)
        test_topology()
        scene = Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'maya_tools/assets/Nini/review/loop_rigger/Nini_LoopRigger_review_v003.ma'
        validate_nini(scene)
    finally:
        maya.standalone.uninitialize()
