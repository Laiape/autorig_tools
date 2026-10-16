"""Two isolated full builds compare the new default with its explicit opt-out."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
ROOT=Path(__file__).resolve().parents[1]
ACTIVE=ROOT/'autorig_tools'


def worker(mode,folder,reopen_from=None,active_probe=False):
    os.environ.update(MAYA_SKIP_USERSETUP_PY='1',QT_QPA_PLATFORM='offscreen',
                      MAYA_APP_DIR=str(folder/'preferences'),AUTORIG_BUILD_CACHE_DIR=str(folder/'cache'),
                      AUTORIG_MODEL_CACHE_DIR=str(folder/'model_cache'))
    (folder/'preferences').mkdir()
    sys.path[:0]=[str(ACTIVE),str(ACTIVE/'maya_tools/scripts'),str(ROOT/'scripts')]
    status=1;result={'mode':mode,'success':False}
    try:
        from PySide6 import QtWidgets
        app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        import maya.standalone
        maya.standalone.initialize(name='python')
        import numpy as np
        from maya import cmds
        from maya.api import OpenMaya as om
        from maya_tools.scripts.utils import create_rig
        from maya_tools.scripts.framework import context
        from maya_tools.scripts.tools import rig_validation as qa,rig_roles,rig_benchmark as rb,pose_blendshapes as pb
        context.service().set_asset('Edward');cmds.optionVar(stringValue=('currentAssetRigName','Edward'))
        started=time.perf_counter()
        if reopen_from:
            from maya_tools.scripts.utils import scene_evaluation
            cmds.file(reopen_from.as_posix(),open=True,force=True,prompt=False,executeScriptNodes=False)
            scene_evaluation.apply()
            build=json.loads((reopen_from.parent/'result.json').read_text())['build']
            result['native_reopen']=True
        else:
            build=create_rig.AutoRig().build(exact_optimizations=mode=='optimized')
        result.update(build=build,build_seconds=time.perf_counter()-started,nodes=len(cmds.ls()),
                      skins=len(cmds.ls(type='skinCluster')),joints=len(cmds.ls(type='joint')))
        if not reopen_from:Path(folder/'buildtiming.json').write_bytes(Path(build['timing_report']).read_bytes())
        result['unknown_source_nodes']=cmds.ls(type='unknown') or []
        # Preserve the source format and unsupported metadata; do not delete
        # artist data just to make a test-only binary conversion succeed.
        if not reopen_from:
            cmds.file(rename=(folder/'built.ma').as_posix());cmds.file(save=True,type='mayaAscii')
        import edward_rig_audit as audit
        cases,coverage=audit.audit_cases()
        extras=[{'C_spine03_CTL.rotateZ':25,'C_localChest_CTL.rotateY':-30,'C_neck_CTL.rotateY':40,'C_jaw_CTL.rotateX':35},
                {'L_shoulderFk_CTL.rotateZ':95,'R_shoulderFk_CTL.rotateZ':75,'L_elbowFk_CTL.rotateY':100,'R_hipFk_CTL.rotateZ':85,'R_kneeFk_CTL.rotateZ':100},
                {'C_jaw_CTL.rotateX':20,'C_jaw_CTL.stickyLips':.5,'L_lipCorner_CTL.translateX':4,'R_lipCorner_CTL.translateY':-2},
                {'L_upperLip02_CTL.translateX':.2,'R_lowerLip02_CTL.translateX':-.2,'C_upperLip_CTL.Roll':6,'C_lowerLip_CTL.Roll':-6},
                {'L_eyeDirect_CTL.Upper_Blink':1,'R_eyeDirect_CTL.Upper_Blink':.5,'R_eyeDirect_CTL.Lower_Blink':1,'L_eyebrowIn_CTL.translateY':2,'R_eyebrowIn_CTL.translateY':-2},
                {'L_thumb01_CTL.rotateZ':20,'R_thumb01_CTL.rotateZ':-15,'L_ring01_CTL.rotateZ':50,'R_pinky01_CTL.rotateZ':45},
                {'C_masterwalk_CTL.globalScale':1.15}]
        for index,values in enumerate(extras):
            valid={p:v for p,v in values.items() if cmds.objExists(p) and cmds.getAttr(p,settable=True)}
            if valid:cases.append(('heldout%d'%index,valid))
        original=rig_roles.bindings;bindings=original('Edward')
        try:
            rig_roles.bindings=lambda root:bindings
            resolved,missing,skipped=qa.resolve_cases('Edward',cases)
        finally:rig_roles.bindings=original
        if missing:raise RuntimeError(missing)
        shapes=sorted(cmds.ls('Edward',dag=True,type='mesh',noIntermediate=True,long=True) or [])
        joints=sorted(cmds.ls('Edward',dag=True,type='joint',long=True) or [])
        paths=[om.MSelectionList().add(s).getDagPath(0) for s in shapes]
        joint_paths=[om.MSelectionList().add(s).getDagPath(0) for s in joints]
        topology={s:hashlib.sha256(json.dumps([list(v) for v in om.MFnMesh(p).getVertices()]).encode()).hexdigest() for s,p in zip(shapes,paths)}
        frames=np.linspace(1,48,len(resolved)).tolist();frames+=list(reversed(frames))
        original_input=cmds.connectionInfo('cabeza_high_Shape.inMesh',sourceFromDestination=True)
        primary=cmds.connectionInfo('EdwardWrinklesGraphShape.AnimatedFace',sourceFromDestination=True)
        assert primary and original_input
        if active_probe:
            # Test-only activation: saved scene/preset settings stay untouched.
            settings='EdwardWrinkles_Settings'
            result['authored_wrinkle_settings']={a:cmds.getAttr(settings+'.'+a) for a in ('Envelope','Depth','ManualActivation')}
            def probe_value(plug,value):
                cmds.setAttr(plug,lock=False)
                source=cmds.connectionInfo(plug,sourceFromDestination=True)
                if source:cmds.disconnectAttr(source,plug)
                cmds.setAttr(plug,value)
            for attr,value in {'Envelope':1.,'Depth':1.,'ManualActivation':1.}.items():probe_value(settings+'.'+attr,value)
            for attr in ('Forehead','Eyes','Cheeks','Nose','Chin'):
                probe_value(settings+'.'+attr,1.)
            for control in cmds.ls('*_CTL',type='transform') or []:
                for attr in ('wrinkleDepth','wrinkleValue'):
                    plug=control+'.'+attr
                    if cmds.objExists(plug):probe_value(plug,1.)
            frames=[1,16,32,48,24,1]
            result['test_only_active_wrinkles']=True
        payload={}
        cmds.undoInfo(stateWithoutFlush=False);cmds.autoKeyframe(state=False)
        with pb._temporary_values(resolved[0]['values']),rb.temporal_workload(resolved,(1,48)) as workload:
            if active_probe:
                # Neutral preparation also resets published wrinkleDepth defaults.
                # Activate after that scope enters, before evaluating the probe.
                for attr,value in {'Envelope':1.,'Depth':1.,'ManualActivation':1.}.items():probe_value(settings+'.'+attr,value)
                for attr in ('Forehead','Eyes','Cheeks','Nose','Chin'):probe_value(settings+'.'+attr,1.)
                for control in cmds.ls('*_CTL',type='transform') or []:
                    for attr in ('wrinkleDepth','wrinkleValue'):
                        plug=control+'.'+attr
                        if cmds.objExists(plug):probe_value(plug,1.)
                result['active_depth_verified']=cmds.getAttr('C_eyebrowMid_CTL.wrinkleDepth')
            for enabled in (0,1):
                cmds.evaluationManager(mode='off')
                cmds.connectAttr(original_input if enabled else primary,'cabeza_high_Shape.inMesh',force=True)
                cmds.evaluationManager(mode='parallel')
                rb._play_once((1,48))
                for index,frame in enumerate(frames):
                    (folder/'progress.json').write_text(json.dumps({'mode':mode,'wrinkles':enabled,'index':index,'poses':len(frames)}))
                    cmds.currentTime(frame);cmds.refresh(force=True)
                    for mesh_index,path in enumerate(paths):
                        # A standalone refresh has no viewport to demand the
                        # Bifrost converter. Pull each native output explicitly.
                        cmds.dgeval(path.fullPathName()+'.outMesh')
                        fn=om.MFnMesh(path)
                        payload['p_%d_%d_%d'%(enabled,index,mesh_index)]=np.asarray(fn.getPoints(om.MSpace.kWorld))[:,:3].copy()
                        payload['n_%d_%d_%d'%(enabled,index,mesh_index)]=np.asarray(fn.getVertexNormals(True,om.MSpace.kWorld)).copy()
                    payload['j_%d_%d'%(enabled,index)]=np.asarray([list(p.inclusiveMatrix()) for p in joint_paths])
        np.savez_compressed(folder/'quality.npz',**payload)
        result.update(success=True,shapes=shapes,joint_names=joints,topology=topology,coverage=coverage,
                      cases=len(resolved),samples=len(frames)*2*len(shapes),wrinkles_original_input=original_input)
        status=0
    except BaseException:result['error']=traceback.format_exc();traceback.print_exc()
    finally:
        (folder/'result.json').write_text(json.dumps(result,indent=2,default=str))
        sys.stdout.flush();sys.stderr.flush()
        kernel=ctypes.windll.kernel32;kernel.GetCurrentProcess.restype=ctypes.c_void_p
        kernel.TerminateProcess.argtypes=[ctypes.c_void_p,ctypes.c_uint]
        kernel.TerminateProcess(kernel.GetCurrentProcess(),status)


def main(args):
    output=args.output.resolve()
    if args.worker:return worker(args.worker,output,args.reopen_from,args.active_probe)
    output.mkdir(parents=True,exist_ok=False)
    asset=ACTIVE/'maya_tools/assets/Edward'
    inputs={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for directory in ('models','build','guides','curves','skin_clusters','corrective_blendshapes','wrinkles','rig_data') for p in (asset/directory).glob('*') if p.is_file()}
    (output/'input_hashes.json').write_text(json.dumps(inputs,indent=2))
    for mode in ('baseline','optimized'):
        target=output/mode;target.mkdir()
        with (target/'maya.log').open('wb') as log:
            command=[str(args.mayapy),'-u',str(Path(__file__).resolve()),'--worker',mode,'--output',str(target)]
            process=subprocess.run(command,cwd=ACTIVE,stdout=log,stderr=subprocess.STDOUT,timeout=600,creationflags=subprocess.CREATE_NO_WINDOW)
        result=json.loads((target/'result.json').read_text()) if (target/'result.json').exists() else {'success':False,'error':'No worker receipt'}
        print(json.dumps({'mode':mode,'exit':process.returncode,'success':result['success'],'build_seconds':result.get('build_seconds'),'optimizations':result.get('build',{}).get('optimizations',{}),'error':result.get('error')}),flush=True)
        assert process.returncode==0 and result['success'],result
    import numpy as np
    before=json.loads((output/'baseline/result.json').read_text());after=json.loads((output/'optimized/result.json').read_text())
    assert before['shapes']==after['shapes'] and before['joint_names']==after['joint_names'] and before['topology']==after['topology']
    first=np.load(output/'baseline/quality.npz');second=np.load(output/'optimized/quality.npz')
    errors={'p':0.,'n':0.,'j':0.}
    for key in first.files:
        difference=first[key]-second[key]
        error=float(np.abs(difference).max()) if key.startswith('j') else float(np.linalg.norm(difference,axis=-1).max())
        errors[key[0]]=max(errors[key[0]],error)
    unchanged=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==value for p,value in inputs.items())
    summary={'accepted':max(errors.values())<=1e-4 and unchanged,'max_errors':errors,'inputs_unchanged':unchanged,
             'baseline_build_seconds':before['build_seconds'],'optimized_build_seconds':after['build_seconds'],
             'samples':after['samples'],'meshes':len(after['shapes']),'joints':len(after['joint_names']),
             'optimizations':after['build']['optimizations'],'scope':'Two full CREATE RIG builds from the same current inputs. CPU quality, not viewport FPS.'}
    (output/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)
    assert summary['accepted']


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--worker',choices=('baseline','optimized'))
    parser.add_argument('--reopen-from',type=Path)
    parser.add_argument('--active-probe',action='store_true')
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--mayapy',type=Path)
    main(parser.parse_args())
