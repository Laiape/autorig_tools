"""Native detail connections, unchanged geometry, undo and batch guard."""
import os,sys,tempfile
from pathlib import Path
os.environ['MAYA_SKIP_USERSETUP_PY']='1'
sys.path.insert(0,str(Path(__file__).resolve().parents[4]))
import maya.standalone
from maya import cmds
maya.standalone.initialize(name='python')
try:
    from maya_tools.scripts.tools import rig_performance as p,rig_validation as qa
    root=cmds.createNode('transform',name='Character')
    high=cmds.polySphere()[0];low=cmds.polyCube()[0];cmds.parent(high,low,root)
    settings=cmds.createNode('network');cmds.addAttr(settings,ln='Envelope',at='double',defaultValue=.7)
    original=qa.mesh_data(high)['points'];p.create_detail_modes(root,[high],[low],[settings])
    for mode in (0,1,2):
        cmds.setAttr(root+'.detailMode',mode)
        assert cmds.getAttr(high+'.visibility')==bool(mode)
        assert cmds.getAttr(low+'.visibility')==(mode==0)
        assert abs(cmds.getAttr(settings+'.Envelope')-(.7 if mode else 0))<1e-6
        assert qa.mesh_data(high)['points']==original
    assert p.export_detail_modes()[0]['high']
    with tempfile.TemporaryDirectory() as tmp:
        try:p.benchmark(root,str(Path(tmp)/'bench.json'));raise AssertionError('Batch FPS claim accepted')
        except ValueError:pass
        scene=str(Path(tmp)/'detail.ma');cmds.file(rename=scene);cmds.file(save=True,type='mayaAscii')
        cmds.file(new=True,force=True);cmds.file(scene,open=True,force=True)
        assert cmds.getAttr(high+'.visibility') and not cmds.getAttr(low+'.visibility')
    print('PASS native detail modes, unchanged geometry, native reopen and batch guard')
finally:maya.standalone.uninitialize()
