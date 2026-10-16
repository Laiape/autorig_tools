"""Bounded CPU eyelid setup comparison, separate quality and native evidence.

Run with mayapy via the outer scripts/run_maya_test.py. No artist Maya changes.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import statistics
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT),str(ROOT/'maya_tools/scripts/tools/tests')]
os.environ['MAYA_SKIP_USERSETUP_PY']='1'


def run(output, scene=None, samples=7, timing_frames=48, demand_head=False, exact=False):
    import maya.standalone
    maya.standalone.initialize(name='python')
    from maya import cmds
    from maya.api import OpenMaya as om
    import numpy as np
    from test_eyelid_blink import build
    from maya_tools.scripts.tools import eyelid_rotation, eyelid_candidates
    from maya_tools.scripts.tools import eyelid_deboor_exact
    from maya_tools.scripts.tools.rig_benchmark import statistics_ms
    output.mkdir(parents=True,exist_ok=False)
    report={'complete':False,'cohort':'full_scene' if scene else 'isolated_eye',
            'measurement':'CPU currentTime(update=True) plus demand of a native matrix sum of eyelid output joints. No vertex extraction, Profiler or viewport in timing; not FPS.',
            'maya':cmds.about(version=True),'platform':platform.platform(),'logical_cpus':os.cpu_count(),
            'scene':str(scene) if scene else None,'guide_samples_per_lid':samples,
            'quality_tolerance':1e-4,'rows':[],'quality':{},'install_ms':{},
            'variants':{'reference':'Curves/skin + Y-preserving analytic sphere projection; whole-lid roll',
                        'aim':'Same curves/skin; aim longitude and preserved latitude on sphere instead of scalar XZ projection',
                        'deboor':'Direct De Boor matrix moments; approximate partial-blink moving U',
                        'deboor_aim':'Direct De Boor moments plus radial aim sphere'},
            'excluded':['GPU','Cached Playback','interactive VP2 FPS','production adoption of prototypes']}
    if exact:
        report['variants']={'reference':report['variants']['reference'],'aim':report['variants']['aim'],
                            'deboor_exact':'Exact moving-U De Boor cubic coefficients and direct linear-skin moments',
                            'deboor_exact_aim':'Exact direct De Boor and aim latitude attachment'}
    try:
        for plugin in ('matrixNodes','lookdevKit'):
            cmds.loadPlugin(plugin,quiet=True)
        cmds.evaluationManager(mode='off')
        if scene:
            report['scene_sha256']=hashlib.sha256(scene.read_bytes()).hexdigest()
            cmds.file(str(scene),open=True,force=True,prompt=False,executeScriptNodes=False)
            prefixes=['L','R']
            for prefix in prefixes:
                eyelid_rotation.install(prefix)
        else:
            build('L',True,samples=samples)
            prefixes=['L']
        cmds.evaluationManager(mode='off')
        for evaluator in ('cache','deformer'):
            if evaluator in cmds.evaluator(q=True):
                cmds.evaluator(name=evaluator,enable=False)
        cmds.undoInfo(state=True)
        joints=sorted(cmds.ls('*Eyelid*Skinning_JNT',type='joint'))
        report['output_joints']=joints
        report['guide_sample_counts_per_lid']={prefix+'_'+label:sum(n.startswith(prefix+'_'+label) for n in joints)
            for prefix in prefixes for label in ('upper','down')}
        counts=set(report['guide_sample_counts_per_lid'].values())
        report['guide_samples_per_lid']=next(iter(counts)) if len(counts)==1 else report['guide_sample_counts_per_lid']
        report['units']=cmds.currentUnit(q=True,linear=True)
        report['time_unit']=cmds.currentUnit(q=True,time=True)
        channels=[]
        for prefix in prefixes:
            for label in ('Up','Down','InUp','OutDown'):
                ctl=prefix+'_eyelid'+label+'_CTL'
                for attr in ('translateX','translateY','translateZ','rotateX','rotateY','rotateZ'):
                    plug=ctl+'.'+attr
                    if cmds.getAttr(plug,settable=True):
                        channels.append(plug)
            for attr in ('Upper_Blink','Lower_Blink','Blink_Height'):
                channels.append(prefix+'_eyeDirect_CTL.'+attr)
        # One keyed workload with independent lid edits and asymmetric blinks.
        for frame in range(1,49):
            phase=2*math.pi*(frame-1)/47
            for plug in channels:
                offset=.4 if plug.startswith('R') else 0
                p=phase+offset
                if plug.endswith('Upper_Blink'):value=(1-math.cos(p))*.5
                elif plug.endswith('Lower_Blink'):value=(1-math.cos(p+.2))*.5
                elif plug.endswith('Blink_Height'):value=.5+.4*math.sin(p*.7)
                elif '.rotate' in plug:value=12*math.sin(p+(1 if 'Down' in plug else 0))
                else:value=.12*math.sin(p+('XYZ'.index(plug[-1])*.7))
                cmds.setKeyframe(plug,time=frame,value=value)
        # Held-out closure/contact frames include whole-lid tilt.
        for frame in (60,61,62):
            for plug in channels:
                if plug.endswith(('Upper_Blink','Lower_Blink')):value=1
                elif plug.endswith('Blink_Height'):value=(frame-60)*.5
                elif plug.endswith('rotateZ'):value=25 if 'Down' in plug else -10
                else:value=0
                cmds.setKeyframe(plug,time=frame,value=value)
        cmds.keyTangent(channels,inTangentType='linear',outTangentType='linear')
        sink=cmds.createNode('wtAddMatrix',name='eyelidTrialDemand_WAM')
        for index,joint in enumerate(joints):
            cmds.connectAttr(joint+'.worldMatrix[0]',sink+'.wtMatrix[%d].matrixIn'%index)
            cmds.setAttr(sink+'.wtMatrix[%d].weightIn'%index,1/len(joints))
        selection=om.MSelectionList();selection.add(sink+'.matrixSum')
        sink_plug=selection.getPlug(0)
        matrix_plugs=[]
        for joint in joints:
            selection=om.MSelectionList();selection.add(joint+'.worldMatrix[0]')
            matrix_plugs.append(selection.getPlug(0))
        head_plugs=[]
        if demand_head:
            for mesh in ('cabeza_low','cabeza_high','EdwardWrinkles_Face'):
                if not cmds.objExists(mesh):continue
                for shape in cmds.listRelatives(mesh,shapes=True,noIntermediate=True,fullPath=True) or []:
                    if cmds.nodeType(shape)=='mesh':
                        selection=om.MSelectionList();selection.add(shape+'.outMesh')
                        head_plugs.append(selection.getPlug(0))
            if not head_plugs:raise RuntimeError('No requested native final head mesh output found')
            report['head_mesh_demand']=[p.name() for p in head_plugs]
            report['measurement']+=' Also demands listed final head outMesh data handles without extracting vertices.'
        def demand():
            sink_plug.asMObject()
            for plug in head_plugs:plug.asMObject()
        def matrices():
            return np.array([list(om.MFnMatrixData(p.asMObject()).matrix()) for p in matrix_plugs]).reshape((-1,4,4))
        report['animated_channels']=channels
        report['baseline_scene_nodes']=len(cmds.ls())
        baseline={}
        active='reference'
        cmds.undoInfo(stateWithoutFlush=False)
        def switch(variant):
            nonlocal active
            if variant==active:return
            prior_mode=cmds.evaluationManager(q=True,mode=True)[0]
            # As in CREATE RIG, graph construction/undo must remain lazy DG.
            # Building thousands of keyed nodes under EM can evaluate a
            # partially constructed candidate and retain stale graph state.
            cmds.evaluationManager(mode='off')
            cmds.undoInfo(stateWithoutFlush=True)
            if active!='reference':cmds.undo()
            if variant!='reference':
                started=time.perf_counter()
                cmds.undoInfo(openChunk=True,chunkName='Eyelid offline candidate')
                try:
                    for prefix in prefixes:
                        if 'exact' in variant:eyelid_deboor_exact.install(prefix)
                        elif 'deboor' in variant:eyelid_candidates.deboor(prefix)
                        if 'aim' in variant:eyelid_candidates.aim(prefix)
                finally:cmds.undoInfo(closeChunk=True)
                report['install_ms'].setdefault(variant,[]).append((time.perf_counter()-started)*1000)
            active=variant
            cmds.undoInfo(stateWithoutFlush=False)
            cmds.dgdirty(allPlugs=True)
            cmds.evaluationManager(mode=prior_mode)
        quality_frames=(1,4,9,15,22,30,39,48,60,61,62,39,9,1)
        for mode in ('off','serial','parallel'):
            cmds.evaluationManager(mode=mode)
            for variant in report['variants']:
                switch(variant)
                row={'matrix_max_error':0.,'position_max_error':0.,'contact_max_distance':0.,'finite':True}
                for frame in quality_frames:
                    cmds.currentTime(frame,update=True)
                    actual=matrices()
                    row['finite'] &= bool(np.isfinite(actual).all())
                    if not row['finite']:
                        row['matrix_max_error']=None
                        row['position_max_error']=None
                        break
                    if mode=='off' and variant=='reference':baseline[frame]=actual
                    reference=baseline[frame]
                    row['matrix_max_error']=max(row['matrix_max_error'],float(np.max(abs(actual-reference))))
                    row['position_max_error']=max(row['position_max_error'],float(np.max(np.linalg.norm(actual[:,3,:3]-reference[:,3,:3],axis=1))))
                    if frame>=60:
                        points={joint:actual[i,3,:3] for i,joint in enumerate(joints)}
                        for prefix in prefixes:
                            ups=sorted([n for n in joints if n.startswith(prefix+'_upper')],key=lambda n:int(n.split('Eyelid0')[1].split('Skinning')[0]))
                            downs=sorted([n for n in joints if n.startswith(prefix+'_down')],key=lambda n:int(n.split('Eyelid0')[1].split('Skinning')[0]))
                            if len(ups)==len(downs):
                                row['contact_max_distance']=max(row['contact_max_distance'],max(float(np.linalg.norm(points[a]-points[b])) for a,b in zip(ups,downs)))
                row['equivalent_to_reference']=row['finite'] and row['matrix_max_error']<=1e-4
                report['quality'][mode+'_'+variant]=row
                report.setdefault('scene_nodes',{})[variant]=len(cmds.ls())
                print('QUALITY',mode,variant,row,flush=True)
                (output/'comparison.json').write_text(json.dumps(report,indent=2),encoding='ascii')
        frames=list(range(1,49,48//timing_frames))
        report['timed_frames']=frames
        report['warmup_frames']=len(frames)
        report['discarded_frames_per_pass']=8
        for mode in ('off','parallel'):
            cmds.evaluationManager(mode=mode)
            candidates=[name for name in report['variants'] if name!='reference']
            sequence=['reference']
            for name in candidates:sequence.extend((name,'reference'))
            for block,variant in enumerate(sequence):
                switch(variant)
                for frame in frames:
                    cmds.currentTime(frame,update=True);demand()
                for run_index in range(3):
                    values=[]
                    for frame_index,frame in enumerate(frames):
                        started=time.perf_counter()
                        cmds.currentTime(frame,update=True);demand()
                        elapsed=(time.perf_counter()-started)*1000
                        if frame_index>=8:values.append(elapsed)
                    report['rows'].append({'mode':mode,'variant':variant,'block':block,'pass':run_index,
                                           'statistics':statistics_ms(values),'raw_ms':values})
                print('TIMED',mode,variant,flush=True)
                (output/'comparison.json').write_text(json.dumps(report,indent=2),encoding='ascii')
        switch('reference')
        report['complete']=True
        for mode in ('off','parallel'):
            for variant in report['variants']:
                values=[v for row in report['rows'] if row['mode']==mode and row['variant']==variant for v in row['raw_ms']]
                report.setdefault('summary',{})[mode+'_'+variant]=statistics_ms(values)
        report['code_sha256']={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in (
            'maya_tools/scripts/tools/eyelid_rotation.py','maya_tools/scripts/tools/eyelid_candidates.py',
            'maya_tools/scripts/tools/eyelid_deboor_exact.py',
            'maya_tools/scripts/biped/autorig/eyelid_module.py','scripts/eyelid_setup_trial.py')}
    except BaseException:
        report['error']=traceback.format_exc()
        raise
    finally:
        (output/'comparison.json').write_text(json.dumps(report,indent=2),encoding='ascii')
    print('COMPLETE',output,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--scene',type=Path)
    parser.add_argument('--samples',type=int,default=7)
    parser.add_argument('--frames',type=int,choices=(24,48),default=48)
    parser.add_argument('--demand-head',action='store_true')
    parser.add_argument('--exact',action='store_true')
    args=parser.parse_args()
    status=0
    try:
        run(args.output,args.scene,args.samples,args.frames,args.demand_head,args.exact)
    except BaseException:
        traceback.print_exc()
        status=1
    finally:
        sys.stdout.flush();sys.stderr.flush()
        if os.name=='nt':
            import ctypes
            kernel=ctypes.windll.kernel32
            kernel.GetCurrentProcess.restype=ctypes.c_void_p
            kernel.TerminateProcess.argtypes=[ctypes.c_void_p,ctypes.c_uint]
            kernel.TerminateProcess(kernel.GetCurrentProcess(),status)
        else:os._exit(status)
