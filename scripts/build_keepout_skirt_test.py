"""Create, validate and save an isolated KeepOut test scene using mayapy.

    mayapy scripts/build_keepout_skirt_test.py

Generated scenes and evaluation evidence stay in the ignored experiments folder.
The builder refuses to replace an interactive Maya scene or an existing version.
"""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'maya_tools/scripts'))


def main(repeats=3):
    import maya.standalone
    maya.standalone.initialize(name='python')
    from maya import cmds
    from tools import muscle_keepout_skirt as tool
    if not cmds.about(batch=True): raise RuntimeError('Run this builder with mayapy.')
    directory=ROOT/'maya_tools/assets/KeepOutSkirt/experiments'
    directory.mkdir(parents=True,exist_ok=True)
    version=1
    while (directory/'KeepOutSkirt_matrix_v{:03d}.ma'.format(version)).exists(): version+=1
    scene=directory/'KeepOutSkirt_matrix_v{:03d}.ma'.format(version)
    data=tool.build_demo()
    print('BUILD_DONE',flush=True)
    report=tool.validate_demo(data,repeats=repeats)
    graph=report.pop('scheduling_graph','')
    (directory/'scheduling_graph_v{:03d}.txt'.format(version)).write_text(graph,encoding='utf-8')
    report['scene']=str(scene)
    report_path=directory/'evaluation_report_v{:03d}.json'.format(version)
    report_path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    cmds.evaluationManager(mode='parallel')
    cmds.currentTime(25)
    cmds.setAttr('persp.translate',155,130,190,type='double3')
    cmds.setAttr('persp.rotate',-14,39,0,type='double3')
    cmds.file(rename=str(scene)); cmds.file(save=True,type='mayaAscii')
    brief={k:v for k,v in report.items() if k not in ('muscle_scheduling','cycle_clusters')}
    print('KEEPOUT_RESULT='+json.dumps(brief),flush=True)
    maya.standalone.uninitialize()
    if not report['passed']: raise SystemExit(2)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timing-repeats',type=int,default=3)
    arguments=parser.parse_args()
    if arguments.timing_repeats<1: parser.error('--timing-repeats must be positive')
    main(repeats=arguments.timing_repeats)
