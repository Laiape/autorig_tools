"""Build the Nini loop-skinning review scene in an isolated mayapy process."""
import colorsys
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def create_color_map(topology, display_colors):
    """Create independent geometry; duplicating a locked skinned mesh is unsafe."""
    from maya import cmds
    from maya.api import OpenMaya as om
    faces = [face for face in topology.faces if min(topology.points[v][1] for v in face) >= 105]
    vertices = sorted({v for face in faces for v in face})
    remap = {vertex:index for index,vertex in enumerate(vertices)}
    fn = om.MFnMesh()
    fn.create([om.MPoint(*topology.points[v]) for v in vertices], [len(face) for face in faces],
              [remap[v] for face in faces for v in face])
    transform = cmds.rename(om.MFnDagNode(fn.parent(0)).fullPathName(),'Nini_RAW_LOOP_MAP')
    fn.setVertexColors([display_colors[v] for v in vertices], list(range(len(vertices))))
    cmds.setAttr(fn.fullPathName()+'.displayColors',True)
    cmds.setAttr(transform+'.translateX',24)
    cmds.sets(transform,edit=True,forceElement='initialShadingGroup')
    return transform


def nini_lip_coverage(topology, upper_plan, eye_seeds):
    """Nini's corner loop and cheek coverage requested in the annotation."""
    from maya_tools.scripts.tools import facial_loop_skinning as tool
    mirror = tool.symmetry_map(topology.points)
    corner = max(upper_plan['columns'],key=lambda c:topology.points[c['anchor']][0])
    # The outward corner trace ends at a five-edge pole. Its continuation is
    # the horizontal cheek edge, not the branch returning toward the nose.
    outward = next(list(p) for p in corner['paths'] if p[-1] == 220)
    assert outward[0] == 27 and 701 in topology.neighbors[220]
    outward.append(701)
    while abs(topology.points[outward[-1]][0]) > 1e-5:
        following = topology.opposite(outward[-2],outward[-1])
        if following is None or following in outward:
            raise ValueError('Nini corner loop changed before the back midline.')
        outward.append(following)
    outer = outward + [mirror[v] for v in reversed(outward[:-1])]
    inner = next(list(p) for p in corner['paths'] if p[-1] != 220)
    inner = inner[:inner.index(outer[-1])+1]
    assert inner[-1] == outer[-1]
    loop = outer + list(reversed(inner))[1:-1]
    assert len(set(loop)) == len(loop)
    assert all(b in topology.neighbors[a] for a,b in zip(loop,loop[1:]+loop[:1]))
    # Front orthographic annotation: mouth midline (343,376), 35px/unit.
    # Restrict to the connected outer cheek below the eyelid boundary.
    pixels = [(367,127),(405,110),(550,115),(644,123),(661,136),
              (661,332),(649,355),(543,391),(487,403),(453,390),
              (443,363),(443,317),(433,285),(412,263),(377,246),(358,223),(356,155)]
    polygon = [((x-343)/35,111.72728729248047+(376-y)/35) for x,y in pixels]
    def inside(x,y):
        hit=False
        for a,b in zip(polygon,polygon[1:]+polygon[:1]):
            if (a[1]>y)!=(b[1]>y) and x < a[0]+(y-a[1])*(b[0]-a[0])/(b[1]-a[1]): hit=not hit
        return hit
    blocked=set(eye_seeds)
    front=set()
    for face in topology.faces:
        a,b,c=[topology.points[v] for v in face[:3]]
        nz=(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
        if nz > 1e-8: front.update(face)
    candidates={v for v,p in enumerate(topology.points) if v in front and v not in blocked
                and p[0]>0 and p[2]>0 and inside(p[0],p[1])}
    # Include only the surface connected to the corner's outer cheek path.
    seeds=candidates.intersection(outer)
    if not seeds: raise ValueError('The annotated cheek does not touch the corner loop.')
    cheek=set(seeds);queue=list(seeds)
    while queue:
        for other in topology.neighbors[queue.pop()].intersection(candidates)-cheek:
            cheek.add(other);queue.append(other)
    return {'anchor':corner['anchor'],'vertices':sorted(set(loop).union(cheek)),
            'corner_loop':loop,'cheek_vertices':sorted(cheek),
            'annotation_polygon':polygon,'pole_continuation':[220,701],
            'source':'User cheek annotation, 2026-10-14'}


def build(output=None):
    from maya import cmds
    from maya.api import OpenMaya as om
    if not cmds.about(batch=True):
        raise RuntimeError('Run this review builder with mayapy; it replaces its own batch scene.')
    from maya_tools.scripts.tools import facial_loop_skinning as tool
    assets = ROOT / 'maya_tools/assets/Nini'
    directory = assets / 'review/loop_rigger'
    directory.mkdir(parents=True, exist_ok=True)
    if output is None:
        version = 1
        while (directory / 'Nini_LoopRigger_review_v{:03d}.ma'.format(version)).exists(): version += 1
        output = directory / 'Nini_LoopRigger_review_v{:03d}.ma'.format(version)
    output = Path(output)
    if output.exists(): raise FileExistsError(output)
    ng_root = Path(os.environ.get('PROGRAMDATA', 'C:/ProgramData')) / 'Autodesk/ApplicationPlugins/ngskintools2/Contents'
    sys.path.insert(0, str(ng_root / 'scripts'))
    from ngSkinTools2 import api
    if not cmds.pluginInfo('ngSkinTools2', query=True, registered=True):
        binaries = [p for p in ng_root.rglob('ngSkinTools2.mll') if str(cmds.about(version=True)) in str(p)]
        if not binaries: raise RuntimeError('Install ngSkinTools2 for this Maya version.')
        cmds.loadPlugin(str(binaries[0]), quiet=True)
    api.plugin.load_plugin()
    cmds.evaluationManager(mode='off')
    cmds.file(str(assets / 'models/Nini_v003.ma'), open=True, force=True, executeScriptNodes=False)
    cmds.undoInfo(state=False)
    mesh, topology = tool.read_mesh('c_body_GEO')
    guides = json.loads((assets / 'guides/Nini_v010.guides').read_text(encoding='utf-8'))['Nini']
    root = cmds.createNode('transform', name='Nini_LoopReview_RIG')
    base = cmds.createNode('joint', name='C_loopBase_JNT', parent=root)
    cmds.setAttr(base + '.ty', 110)
    cmds.setAttr(base + '.visibility', False)
    skin = cmds.skinCluster(base, mesh, toSelectedBones=True, normalizeWeights=1, maximumInfluences=8,
                            obeyMaxInfluences=False, name='Nini_FacialLoopReview_SKC')[0]
    layers = api.init_layers(skin)
    layers.add('Base - neutral Nini')
    specs = [
        ('Lips_Upper', 'Lip Rigger', 'C_upperLipLinear_CRVShape', True),
        ('Lips_Lower', 'Lip Rigger', 'C_lowerLipLinear_CRVShape', True),
        ('L_Eye_Upper', 'Eye Rigger L', 'L_eyelidUpperLinear_CRVShape', False),
        ('L_Eye_Lower', 'Eye Rigger L', 'L_eyelidLowerLinear_CRVShape', False),
        ('R_Eye_Upper', 'Eye Rigger R', 'R_eyelidUpperLinear_CRVShape', False),
        ('R_Eye_Lower', 'Eye Rigger R', 'R_eyelidLowerLinear_CRVShape', False),
        ('L_Brow', 'Eyebrow Rigger L', 'L_eyebrow_CRVShape', False),
        ('R_Brow', 'Eyebrow Rigger R', 'R_eyebrow_CRVShape', False),
    ]
    records, controls, lip_sections = [], {}, []
    preview_root = cmds.createNode('transform', name='COMPLETE_LOOP_COLUMNS', parent=root)
    cmds.setAttr(preview_root + '.visibility', False)
    display_colors = [om.MColor((.24, .24, .24, 1)) for _ in topology.points]
    for region, parent_name, guide_name, paired in specs:
        cvs = guides[guide_name]['curve_data']['cvs']
        seed = [min(range(len(topology.points)), key=lambda i: sum((topology.points[i][a] - cv[a])**2 for a in range(3))) for cv in cvs]
        assert max(sum((topology.points[vertex][a] - cv[a])**2 for a in range(3)) for cv,vertex in zip(cvs,seed)) < 1e-8
        plan = tool.plan_columns(topology, seed)
        plan['mesh'] = mesh
        if region.endswith('Brow'):
            # Extend eyebrow00 inward across the two remaining columns,
            # stopping before the central midEyebrow loop.
            inward, previous, current = [], seed[1], seed[0]
            while True:
                following = topology.opposite(previous, current)
                if following is None: raise ValueError('Brow seed does not continue toward midEyebrow.')
                if abs(topology.points[following][0]) < 1e-5:
                    mid = following; break
                if abs(topology.points[following][0]) >= abs(topology.points[current][0]):
                    raise ValueError('Brow extension must move toward the midline.')
                inward.append(following); previous,current = current,following
            extended = tool.plan_columns(topology, [mid] + list(reversed(inward)) + seed)
            excluded = set(extended['columns'][0]['vertices'])
            first = plan['columns'][0]
            for column in extended['columns'][1:1+len(inward)]:
                first['vertices'] = sorted(set(first['vertices']).union(column['vertices']))
                first['paths'].extend(column['paths'])
            for column in plan['columns']:
                allowed = set(column['vertices']) - excluded
                reachable, queue = {column['anchor']}, [column['anchor']]
                while queue:
                    for other in topology.neighbors[queue.pop()].intersection(allowed) - reachable:
                        reachable.add(other); queue.append(other)
                column['vertices'] = sorted(reachable)
            plan['affected'] = sorted({v for c in plan['columns'] for v in c['vertices']})
            plan['brow_extension'] = {'inner_vertices':inward,'mid_vertex':mid,'excluded_mid_loop':sorted(excluded)}
        if paired:
            joint_group, rotate, non_rotate = tool.create_joint_pairs(plan, region)
        else:
            joint_group, rotate = tool.create_joints(plan, region)
            non_rotate = []
        if paired:
            middle = len(seed)//2
            for i,joint in enumerate(list(rotate)):
                side = 'C' if i == middle else ('L' if topology.points[seed[i]][0] > 0 else 'R')
                number = 0 if side == 'C' else min(i,len(seed)-1-i)
                label = '{}_{}Lip{:02d}'.format(side,'upper' if region.endswith('Upper') else 'lower',number)
                rotate[i] = cmds.rename(joint,label+'_JNT')
                non_rotate[i] = cmds.rename(non_rotate[i],label+'NonRot_JNT')
        elif region.endswith('Brow'):
            rotate = [cmds.rename(joint,'{}_eyebrow{:02d}_JNT'.format(region[0],i)) for i,joint in enumerate(rotate)]
        cmds.parent(joint_group, root)
        controls[region] = []
        for i, joint in enumerate(rotate):
            position = topology.points[seed[i]]
            zero = cmds.createNode('transform', name=region + '_{:02d}_ZERO'.format(i), parent=joint_group)
            cmds.xform(zero, worldSpace=True, translation=position)
            cmds.parent(joint, zero)
            control = cmds.circle(name=region + '_{:02d}_CTL'.format(i), normal=(0,0,1), radius=.12, constructionHistory=False)[0]
            cmds.parent(control, zero); cmds.setAttr(control + '.translate', 0,0,0)
            cmds.connectAttr(control + '.translate', joint + '.translate')
            cmds.connectAttr(control + '.rotate', joint + '.rotate')
            if paired:
                cmds.parent(non_rotate[i], zero)
                cmds.connectAttr(control + '.translate', non_rotate[i] + '.translate')
                for axis in 'XYZ': cmds.setAttr(non_rotate[i] + '.rotate' + axis, lock=True)
            shape = cmds.listRelatives(control, shapes=True)[0]
            cmds.setAttr(shape + '.overrideEnabled', True)
            cmds.setAttr(shape + '.overrideColor', 17 if paired else (18 if 'Eye' in region else 13))
            controls[region].append(control)
        if paired:
            lip_sections.append(dict(plan=plan,joints=rotate,non_rotate_joints=non_rotate))
        else:
            group, metadata = tool.create_ng_region(plan, rotate, skin, region)
            records.append(json.loads(cmds.getAttr(metadata + '.loopRegionData')))
        cmds.sets(['{}.vtx[{}]'.format(mesh,v) for v in seed], name=region + '_SEED_SET')
        overlay = tool.preview_columns(plan, prefix=region + '_FULL_LOOP')
        cmds.parent(overlay, preview_root)
        for i,column in enumerate(plan['columns']):
            color = om.MColor((*colorsys.hsv_to_rgb((i*.618034 + len(records)*.11)%1,.7,.95),1))
            for vertex in column['vertices']: display_colors[vertex] = color
        print('REGION {}: {} anchors, {} complete-loop vertices, paired={}'.format(region,len(seed),len(plan['affected']),paired),flush=True)
    first = lip_sections[0]
    eye_seeds=[v for record in records if '_Eye_' in record['layer_name'] for v in record['seed']]
    first['plan']['coverage_overrides']=[nini_lip_coverage(topology,first['plan'],eye_seeds)]
    group, metadata = tool.create_ng_region(first['plan'], first['joints'], skin, 'Lips',
        non_rotate_joints=first['non_rotate_joints'], additional_regions=lip_sections[1:], mirror=True)
    lips = json.loads(cmds.getAttr(metadata + '.loopRegionData'))
    records.insert(0,lips)
    display_colors = [om.MColor((.24,.24,.24,1)) for _ in topology.points]
    colors = {}
    for i,column in enumerate(lips['assignments']):
        color = colorsys.hsv_to_rgb((i*.618034)%1,.7,.95)
        for vertex,value in column['weights'].items():
            vertex = int(vertex)
            old = colors.get(vertex,(0,0,0))
            colors[vertex] = tuple(old[a]+color[a]*value for a in range(3))
    for vertex,color in colors.items(): display_colors[vertex] = om.MColor((*color,1))
    # Let the brows follow their review joints while keeping the original mesh.
    for side in ('L','R'):
        eyebrow = side.lower() + '_eyebrow_GEO'
        joints = [record for record in records if record['layer_name'] == side+'_Brow'][0]['joints'].values()
        cmds.skinCluster(list(joints), eyebrow, toSelectedBones=True, normalizeWeights=1, maximumInfluences=2,
                         name=side+'_eyebrowReview_SKC')
    for node in ('c_hood_GEO', 'c_eyelashes_GEO'):
        if cmds.objExists(node): cmds.setAttr(node + '.visibility', False)
    # A static colored head copy makes the complete-loop ownership inspectable.
    create_color_map(topology, display_colors)
    # Isolated, labelled timeline tests. Frame 1 is always neutral.
    poses = [('Upper lip translation',12,'Lips_Upper','ty',.35),
             ('Upper lip Rotate only',24,'Lips_Upper','rx',12),
             ('Lower lip translation',36,'Lips_Lower','ty',-.35),
             ('Left upper eyelid',48,'L_Eye_Upper','ty',-.45),
             ('Right upper eyelid',60,'R_Eye_Upper','ty',-.45),
             ('Left eyebrow00',72,'L_Brow','ty',.45),('Right eyebrow00',84,'R_Brow','ty',.45),
             ('Left corner upper00 half weight',90,'Lips_Upper','ty',.25)]
    pose_records=[]
    for label,frame,region,axis,value in poses:
        index = (-1 if frame == 90 else (0 if region.endswith('Brow') else len(controls[region])//2))
        control = controls[region][index]
        for time,number in ((1,0),(frame-5,0),(frame,value),(frame+5,0),(96,0)):
            cmds.setKeyframe(control,attribute=axis,time=time,value=number)
        pose_records.append({'label':label,'frame':frame,'control':control,'channel':axis,'value':value})
    cmds.playbackOptions(minTime=1,maxTime=96,animationStartTime=1,animationEndTime=96)
    cmds.currentTime(1)
    camera, shape = cmds.camera(name='Nini_LoopReview_CAM',orthographic=True)
    cmds.setAttr(camera+'.translate',12,118,65)
    cmds.setAttr(shape+'.orthographicWidth',48)
    cmds.setAttr(shape+'.farClipPlane',1000)
    report={'prototype':True,'source_model':'Nini_v003.ma','source_guides':'Nini_v010.guides',
            'mesh':mesh,'skin':skin,'complete_loops':True,'automatic_falloff':False,
            'schema':2,
            'mask_policy':'Binary full-loop coverage; edit the Lips parent mask to localize the region.',
            'lip_pair_policy':'Exactly Lips / Rotate / Non Rotate. Same distribution in each child; corner upper00/lower00 share 0.5 each.',
            'intersection_policy':'Nearest anchor along complete loops; shared corner anchors have priority. Positive X copied to negative X.',
            'regions':records,'poses':pose_records,'ng_layer_count':len(layers.list()),'camera':camera,
            'note':'Isolated facial skinning review on the original model. Production rig and saved skin files are untouched.'}
    note=cmds.createNode('network',name='Nini_LOOP_REVIEW_INFO')
    for region in records: tool.resolve_layer(skin, region).enabled = region['layer_name'] == 'Lips'
    report['default_solo_region'] = 'Lips'
    cmds.addAttr(note,longName='reviewData',dataType='string');cmds.setAttr(note+'.reviewData',json.dumps(report),type='string')
    tool.resolve_layer(skin,lips['weight_layers'][0]).set_current()
    cmds.select(mesh,replace=True)
    cmds.file(rename=str(output));cmds.file(save=True,type='mayaAscii',force=False)
    output.with_suffix('.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('SAVED_REVIEW='+str(output),flush=True)
    return output


if __name__ == '__main__':
    os.environ['MAYA_SKIP_USERSETUP_PY']='1'
    import maya.standalone
    maya.standalone.initialize(name='python')
    try: build(sys.argv[1] if len(sys.argv)>1 else None)
    finally: maya.standalone.uninitialize()
