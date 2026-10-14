"""Portable poses by semantic binding, camera references and geometry review."""
import json
import math
from pathlib import Path
from maya import cmds
from maya_tools.scripts.tools import rig_roles as roles, rig_profiles as profiles, rig_validation as qa, pose_blendshapes as poses


def camera_snapshot(camera=None):
    if camera is None:
        panel = cmds.getPanel(withFocus=True)
        if not panel or cmds.getPanel(typeOf=panel) != 'modelPanel':
            panels=cmds.getPanel(type='modelPanel') or []
            visible=cmds.getPanel(visiblePanels=True) or []
            panel=next((p for p in panels if p in visible),None)
            if not panel:return None
        camera = cmds.modelPanel(panel, query=True, camera=True)
    camera = roles.path(camera)
    transform = cmds.listRelatives(camera, parent=True, fullPath=True)[0] if cmds.nodeType(camera) == 'camera' else camera
    shapes = cmds.listRelatives(transform, shapes=True, fullPath=True, type='camera') or []
    if len(shapes) != 1:
        raise ValueError('Choose a camera transform.')
    attrs = ('focalLength', 'horizontalFilmAperture', 'verticalFilmAperture', 'nearClipPlane', 'farClipPlane', 'orthographic', 'orthographicWidth')
    return {'matrix': cmds.xform(transform, query=True, worldSpace=True, matrix=True),
            'settings': {a: cmds.getAttr(shapes[0]+'.'+a) for a in attrs}}


def capture(root, name, camera=None):
    if not name or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in name):
        raise ValueError('Use an ASCII pose name.')
    root = roles.path(root)
    controls, skipped = qa._neutral_values(root)
    bound = {b['node']: b for b in roles.bindings(root) if b['kind']=='control'}
    channels = []
    for plug in controls:
        node, attribute = plug.rsplit('.',1)
        if node not in bound:
            continue
        b = bound[node]
        value = cmds.getAttr(plug)
        if not math.isfinite(value):
            raise ValueError('Nonfinite pose channel: '+plug)
        channels.append({**{f:b[f] for f in roles.FIELDS}, 'binding': b['key'], 'attribute': attribute, 'value': value})
    if not channels:
        raise ValueError('Bind at least one animator control before capturing a pose.')
    return {'name': name, 'channels': channels, 'camera': camera_snapshot(camera),
            'unbound_controls': sorted(set(p.rsplit('.',1)[0] for p in controls if p.rsplit('.',1)[0] not in bound)),
            'skipped_channels': skipped}


def library(items=None):
    return {'format':'autorig-pose-library', 'version':1, 'poses':list(items or [])}


def profile(bank):
    if bank.get('format') != 'autorig-pose-library' or bank.get('version') != 1:
        raise ValueError('Unsupported pose library.')
    result = profiles.preset('custom'); result['name']='pose_library'
    result['cases'] = [{'name': p['name'], 'channels': [{k:v for k,v in c.items() if k not in ('binding',)} for c in p['channels']]} for p in bank['poses']]
    if not result['cases']:
        raise ValueError('Capture at least one pose.')
    return profiles.validate(result)


def values(root, item):
    result={}
    for c in item['channels']:
        if c.get('binding') != roles.key(c):
            raise ValueError('Pose binding definition is inconsistent.')
        node=roles.resolve(root, binding_key=c['binding']);plug=node+'.'+c['attribute']
        if not cmds.objExists(plug) or not math.isfinite(c['value']):
            raise ValueError('Pose channel is missing or invalid: '+plug)
        result[plug]=c['value']
    return result


@poses.undoable
def apply(root, item):
    changes=values(root,item)
    if any(not cmds.getAttr(p,settable=True) or cmds.connectionInfo(p,sourceFromDestination=True) for p in changes):
        raise ValueError('Pose application needs free channels. Use a report to preview animated rigs without changing keys.')
    for p,v in changes.items():cmds.setAttr(p,v)


def capture_image(output, camera):
    """Temporary native camera; restore the previous model-panel camera on failure."""
    if cmds.about(batch=True):
        raise ValueError('Viewport captures require interactive Maya.')
    output=Path(output)
    if output.exists():raise ValueError('Use a new capture file.')
    panel=cmds.getPanel(withFocus=True)
    if not panel or cmds.getPanel(typeOf=panel)!='modelPanel':
        panels=cmds.getPanel(type='modelPanel') or []
        panel=panels[0] if panels else None
    if not panel:raise ValueError('A model panel is required for captures.')
    old_camera=cmds.modelPanel(panel,query=True,camera=True)
    transform,shape=cmds.camera(name='rigReviewCamera')
    try:
        cmds.xform(transform,worldSpace=True,matrix=camera['matrix'])
        for a,v in camera['settings'].items():cmds.setAttr(shape+'.'+a,v)
        cmds.modelPanel(panel,edit=True,camera=transform)
        output.parent.mkdir(parents=True,exist_ok=True)
        return cmds.playblast(format='image',completeFilename=str(output),frame=cmds.currentTime(query=True),
                             editorPanelName=panel,viewer=False,showOrnaments=False,compression='png',widthHeight=(960,720),percent=100)
    finally:
        cmds.modelPanel(panel,edit=True,camera=old_camera)
        cmds.delete(transform)


def review(root, meshes, bank, output, baseline=None, captures=True):
    result=profile(bank)
    cameras={p['name']:p.get('camera') for p in bank['poses']}
    return qa.run_report(root,meshes,output,baseline=baseline,cases=result,captures=captures,cameras=cameras)


@poses.undoable
def color_difference(root, mesh, report, baseline, pose_name, limit=.1):
    """Create a colored pose snapshot; source geometry and its color sets stay intact."""
    from maya_tools.scripts.tools import proximity_bake
    from maya.api import OpenMaya as om
    if limit<=0 or not math.isfinite(limit):raise ValueError('Use a positive finite color limit.')
    binding=next((b['key'] for b in roles.bindings(root) if b['node']==poses.mesh_transform(mesh) and b['kind']=='mesh'),poses.mesh_transform(mesh))
    comparison=next((c for c in qa.compare_reports(report,baseline) if c['pose']==pose_name and c['mesh']==binding),None)
    if not comparison or comparison['status']!='compared':raise ValueError('Reports have incompatible definitions or topology.')
    current=qa.mesh_data(mesh)
    a=next(p for p in report['poses'] if p['name']==pose_name)['meshes'][binding]
    b=next(p for p in baseline['poses'] if p['name']==pose_name)['meshes'][binding]
    if current['topology']!=a['topology']:raise ValueError('Current mesh topology differs from the report.')
    errors=[math.dist(p,q) for p,q in zip(a['points'],b['points'])]
    path=om.MSelectionList().add(poses.mesh_transform(mesh)).getDagPath(0);path.extendToShape()
    counts,indices=om.MFnMesh(path).getVertices()
    preview=cmds.createNode('transform',name='RigDifferencePreview')
    parent=om.MSelectionList().add(preview).getDependNode(0)
    om.MFnMesh().create([om.MPoint(*p) for p in a['points']],counts,indices,parent=parent)
    cmds.xform(preview,worldSpace=True,matrix=a.get('world_matrix',cmds.xform(mesh,q=True,worldSpace=True,matrix=True)))
    proximity_bake.error_colors(preview,errors,limit)
    return {'preview':preview,'max_difference':max(errors,default=0),'pose':pose_name}
