import array, hashlib, json, os
from pathlib import Path
from importlib import reload
from maya import cmds
from maya.api import OpenMaya as om, OpenMayaAnim as oma
from maya_tools.scripts.biped.autorig import leg_module_custom

WORK = Path('C:/proyectos/auto-rig/tmp/nini_foot_reach_20261015')
WORK.mkdir(exist_ok=True)
assert os.getpid() == 40344
scene = cmds.file(q=True, sn=True)
assert scene.endswith('/Nini_dress_chains_v005.ma'), scene
assert not cmds.ls('*_legFootReachDelta_PMA')
backup = WORK / 'Before_NiniFootReach.mb'
assert not backup.exists()
target = Path(scene).with_name('Nini_dress_chains_v006.ma')
assert not target.exists()

def weights(skin):
    sel = om.MSelectionList(); sel.add(skin)
    fn = oma.MFnSkinCluster(sel.getDependNode(0))
    path = om.MDagPath.getAPathTo(fn.getOutputGeometry()[0])
    component = om.MFnSingleIndexedComponent()
    obj = component.create(om.MFn.kMeshVertComponent)
    component.setCompleteData(om.MFnMesh(path).numVertices)
    values, _ = fn.getWeights(path, obj)
    return hashlib.sha256(array.array('d', values).tobytes()).hexdigest()

def output(side):
    return [cmds.getAttr(side + '_' + name + '_BM.outputMatrix') for name in ('ankle','ball','tip')]

def lengths(side):
    positions = [m[12:15] for m in output(side)]
    return [(om.MVector(*a)-om.MVector(*b)).length() for a,b in zip(positions, positions[1:])]

def reachable():
    values = {s:cmds.getAttr(s+'_ankleIk_CTL.translateX') for s in ('L','R')}
    try:
        for s in values: cmds.setAttr(s+'_ankleIk_CTL.translateX',0)
        return {s:output(s) for s in values}
    finally:
        for s,v in values.items(): cmds.setAttr(s+'_ankleIk_CTL.translateX',v)

skins = ['C_body_SKC','skinCluster__c_bootBase_GEO']
before_weights = {s:weights(s) for s in skins}
before_lengths = {s:lengths(s) for s in ('L','R')}
cmds.file(str(backup), exportAll=True, type='mayaBinary', preserveReferences=True, force=False)
selection = cmds.ls(sl=True, long=True)
reload(leg_module_custom)
cmds.undoInfo(openChunk=True, chunkName='Repair Nini foot reach')
try:
    neutral_before = reachable()
    for side in ('L','R'):
        rig = leg_module_custom.LegModule.__new__(leg_module_custom.LegModule)
        rig.side = side
        rig.ik_matrices = [None,None,side+'_legIkEffectorWM_MMT.matrixSum']
        rig.ball_ik = cmds.connectionInfo(side+'_ball_BM.inputMatrix',sourceFromDestination=True)
        rig.toe_ik = cmds.connectionInfo(side+'_tip_BM.inputMatrix',sourceFromDestination=True)
        assert rig.ball_ik == side+'_ballIkSC_MMT.matrixSum', rig.ball_ik
        assert rig.toe_ik == side+'_toeIkSC_MMT.matrixSum', rig.toe_ik
        rig.foot_reach_setup()
        cmds.connectAttr(rig.ball_ik,side+'_ball_BM.inputMatrix',force=True)
        cmds.connectAttr(rig.toe_ik,side+'_tip_BM.inputMatrix',force=True)
    neutral_after = reachable()
    error = max(abs(a-b) for s in neutral_before for ma,mb in zip(neutral_before[s],neutral_after[s]) for a,b in zip(ma,mb))
    assert error < 1e-4, error
    after_lengths = {s:lengths(s) for s in ('L','R')}
    for side in ('L','R'):
        expected = [(om.MVector(*a[12:15])-om.MVector(*b[12:15])).length()
                    for a,b in zip(neutral_before[side],neutral_before[side][1:])]
        assert max(abs(a-b) for a,b in zip(after_lengths[side],expected)) < 1e-4, (side,after_lengths,expected)
    assert before_weights == {s:weights(s) for s in skins}
    cmds.select(selection,replace=True) if selection else cmds.select(clear=True)
except BaseException:
    cmds.undoInfo(closeChunk=True)
    cmds.undo()
    raise
else:
    cmds.undoInfo(closeChunk=True)

cmds.refresh(force=True)
cmds.file(rename=str(target))
cmds.file(save=True,type='mayaAscii',force=False)
result = dict(scene=str(target),backup=str(backup),before_lengths=before_lengths,
              after_lengths=after_lengths,reachable_matrix_error=error,
              weights_unchanged=True,weights_sha256=before_weights)
(WORK/'repair.json').write_text(json.dumps(result,indent=2))
try:
    panel = cmds.getPanel(withFocus=True)
    if cmds.getPanel(typeOf=panel)!='modelPanel':
        panel = next(p for p in cmds.getPanel(visiblePanels=True) if cmds.getPanel(typeOf=p)=='modelPanel')
    cmds.playblast(completeFilename=str(WORK/'NiniFootReach_after.png'),format='image',compression='png',
        startTime=cmds.currentTime(q=True),endTime=cmds.currentTime(q=True),viewer=False,
        forceOverwrite=True,showOrnaments=False,offScreen=True,widthHeight=(1280,900),percent=100,
        editorPanelName=panel)
except Exception as exc:
    result['preview_error']=str(exc)
