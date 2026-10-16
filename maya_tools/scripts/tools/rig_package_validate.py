"""Run in a fresh mayapy process to validate a frozen rig package."""
import os,sys,json,ctypes,traceback
from pathlib import Path
os.environ.setdefault('MAYA_SKIP_USERSETUP_PY','1');os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
try:
    from PySide6 import QtWidgets
except ImportError:
    from PySide2 import QtWidgets
app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya_tools.scripts.tools import rig_package
package=Path(sys.argv[1]).resolve();output=Path(sys.argv[2]).resolve();output.mkdir(parents=True,exist_ok=True)
exit_code=1
try:
    reports=[];manifest=rig_package.verify(package)
    for attempt in (1,2):
        cmds.file(new=True,force=True)
        rig_package.build(package,require_validated=False)
        from maya_tools.scripts.tools import rig_validation as qa
        root=manifest['asset']
        preferred=[n for n in ('cabeza_high','cuerpo_base','cabeza_low') if cmds.objExists(n)]
        meshes=preferred or [cmds.listRelatives(s,parent=True,fullPath=True)[0] for s in cmds.listRelatives(root,ad=True,type='mesh',fullPath=True) or [] if not cmds.getAttr(s+'.intermediateObject')]
        path=output/('build_%d.rigqa.json'%attempt)
        report=qa.run_report(root,meshes,str(path),baseline=str(output/'build_1.rigqa.json') if attempt==2 else None,repeats=1,captures=False)
        reports.append(report)
        if report['missing_channels']:
            raise ValueError('Rebuild validation has missing control channels.')
    if any(r['status']!='compared' for r in reports[1]['comparison']):raise ValueError('Rebuild pose definitions or topology differ.')
    rebuild_error=max(r['max'] for r in reports[1]['comparison'])
    scene=output/(manifest['asset']+'_validated.ma');cmds.file(rename=str(scene));cmds.file(save=True,type='mayaAscii')
    cmds.file(new=True,force=True);cmds.file(str(scene),open=True,force=True)
    reopen=qa.run_report(root,meshes,str(output/'reopened.rigqa.json'),baseline=str(output/'build_2.rigqa.json'),repeats=1,captures=False)
    if any(r['status']!='compared' for r in reopen['comparison']):raise ValueError('Reopen pose definitions or topology differ.')
    reopen_error=max(r['max'] for r in reopen['comparison'])
    validation={'success':rebuild_error<1e-4 and reopen_error<1e-4,'maya':cmds.about(version=True),'rebuild_max_difference':rebuild_error,
        'reopen_max_difference':reopen_error,'poses':len(reopen['poses']),'meshes':meshes,'scene':str(scene),
        'missing_channels':reopen['missing_channels'],'reports':[str(output/'build_1.rigqa.json'),str(output/'build_2.rigqa.json'),str(output/'reopened.rigqa.json')]}
    if manifest.get('performance_policy'):
        validation['performance_report'] = manifest['performance_policy']['report']
    rig_package.mark_validated(package,validation)
    (output/'result.json').write_text(json.dumps(validation,indent=2));exit_code=0
    print('PASS FROZEN RIG PACKAGE',json.dumps(validation),flush=True)
except Exception as exc:
    (output/'result.json').write_text(json.dumps({'success':False,'error':str(exc),'traceback':traceback.format_exc()},indent=2))
    traceback.print_exc()
finally:
    if os.name=='nt':
        kernel=ctypes.windll.kernel32;kernel.GetCurrentProcess.restype=ctypes.c_void_p
        kernel.TerminateProcess.argtypes=[ctypes.c_void_p,ctypes.c_uint];kernel.TerminateProcess(kernel.GetCurrentProcess(),exit_code)
    else:os._exit(exit_code)
