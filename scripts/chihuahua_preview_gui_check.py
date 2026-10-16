"""Measure the delivered lightweight model in an owned interactive viewport."""
import json
import os
from pathlib import Path
import statistics
import sys
import time
import traceback
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'autorig_tools'),str(ROOT/'autorig_tools/maya_tools/scripts')]
FOLDER=Path(os.environ['AUTORIG_CHIHUAHUA_TRIAL_FOLDER'])
from maya import cmds,mel
from maya_tools.scripts.utils import model_cache
source=ROOT/'autorig_tools/maya_tools/assets/chihuahua/models/chihuahua_v002.mb'
report={'scene':str(source),'pid':os.getpid(),'samples':[]}
def checkpoint(phase):
    report['phase']=phase
    (FOLDER/'progress.json').write_text(json.dumps(report,indent=2))
try:
    cmds.evaluationManager(mode='off')
    mel.eval('setNamedPanelLayout "Single Perspective View";')
    cmds.modelEditor('modelPanel4',edit=True,displayAppearance='smoothShaded',rendererName='vp2Renderer')
    for index in range(4):
        checkpoint('open_%s'%index)
        start=time.perf_counter()
        model_cache.open_model(source)
        opened=time.perf_counter()
        checkpoint('redraw_%s'%index)
        drawstart=time.perf_counter()
        cmds.refresh(force=True)
        drawn=time.perf_counter()
        assert not cmds.ls(type='xgmSplineDescription')
        report['samples'].append({'cold':index==0,'open_seconds':opened-start,
                                  'redraw_seconds':drawn-drawstart,'total_seconds':(opened-start)+(drawn-drawstart)})
        checkpoint('sample_%s_complete'%index)
    report['median']={k:statistics.median(s[k] for s in report['samples'][1:])
                      for k in ('open_seconds','redraw_seconds','total_seconds')}
    checkpoint('show_groom')
    reference=model_cache.show_groom('chihuahua')
    assert len(cmds.ls(type='xgmSplineDescription'))==4
    report['groom_loaded']=cmds.referenceQuery(reference,isLoaded=True)
    report['groom_visible']=cmds.getAttr('xgen.visibility')
    checkpoint('draw_groom')
    cmds.refresh(force=True)
    cmds.playblast(format='image',compression='png',completeFilename=str(FOLDER/'groom_enabled.png'),
                   forceOverwrite=True,viewer=False,showOrnaments=False,widthHeight=(960,720),
                   frame=cmds.currentTime(q=True),percent=100,offScreen=True)
    checkpoint('unload_groom')
    cmds.file(unloadReference=reference)
    checkpoint('complete')
    (FOLDER/'result.json').write_text(json.dumps(report,indent=2))
except BaseException:
    (FOLDER/'failure.txt').write_text(traceback.format_exc())
finally:
    cmds.quit(force=True)
