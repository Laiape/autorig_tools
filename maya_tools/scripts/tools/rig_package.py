"""Immutable local rig packages, hash verification and clean rebuild recipes."""
import hashlib,json,shutil,sys,tempfile
from datetime import datetime,timezone
from pathlib import Path

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def create(source_repo,asset,output,selected_files=None,reports=None,performance_policy=None):
    repo=Path(source_repo).resolve();output=Path(output).resolve()
    if output.exists():raise ValueError('Use a new package directory.')
    output.mkdir(parents=True)
    manifest={'format':'autorig-rig-package','version':1,'asset':asset,'status':'candidate',
        'created_utc':datetime.now(timezone.utc).isoformat(),'files':{},'inputs':{},
        'build':'A fresh working copy is used so generated cache files do not alter the frozen package.'}
    if performance_policy:
        manifest['performance_policy'] = dict(performance_policy)
    try:
        for source in (repo/'maya_tools/scripts').rglob('*'):
            if not source.is_file() or '__pycache__' in source.parts or source.suffix=='.pyc':continue
            relative=source.relative_to(repo);dest=output/relative
            dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
        for category in ('models','guides','curves','build','skin_clusters','wrinkles'):
            files=[p for p in (repo/'maya_tools/assets'/asset/category).glob('*') if p.is_file()]
            if not files and category=='wrinkles':continue
            source=Path(selected_files[category]) if selected_files and category in selected_files else max(files,key=lambda p:p.name)
            relative=Path('maya_tools/assets')/asset/category/source.name
            dest=output/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
            manifest['inputs'][category]=relative.as_posix()
        for source in (repo/'maya_tools/cache').glob('*.cache'):
            dest=output/'maya_tools/cache'/source.name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
        picker=repo/'maya_tools/assets'/asset/'picker'
        if picker.exists():shutil.copytree(picker,output/'maya_tools/assets'/asset/'picker',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        rig_data=repo/'maya_tools/assets'/asset/'rig_data'
        if rig_data.exists():shutil.copytree(rig_data,output/'maya_tools/assets'/asset/'rig_data',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        for source in reports or []:
            source=Path(source);dest=output/'validation'/source.name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
        for source in output.rglob('*'):
            if source.is_file():manifest['files'][source.relative_to(output).as_posix()]={'sha256':digest(source),'bytes':source.stat().st_size}
        (output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        verify(output)
        return manifest
    except Exception:
        # Keep the failed candidate available for inspection; never mark it validated.
        (output/'failed.json').write_text(json.dumps({'status':'failed','reason':'Package creation or verification failed.'}))
        raise

def verify(package,require_validated=False):
    root=Path(package).resolve();manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('format')!='autorig-rig-package' or manifest.get('version')!=1:raise ValueError('Unsupported rig package.')
    if require_validated and manifest['status']!='validated':raise ValueError('This package has not passed the publish validation.')
    for relative,record in manifest['files'].items():
        path=(root/relative).resolve()
        if root not in path.parents or not path.is_file() or digest(path)!=record['sha256']:
            raise ValueError('Rig package hash mismatch: '+relative)
    return manifest

def mark_validated(package,validation):
    if not validation.get('success') or validation.get('rebuild_max_difference',1)>1e-4 or validation.get('reopen_max_difference',1)>1e-4:
        raise ValueError('Successful rebuild and native reopen comparisons are required.')
    root=Path(package);manifest=verify(root)
    if manifest.get('performance_policy'):
        from maya_tools.scripts.tools import rig_performance_policy
        relative = validation.get('performance_report')
        if not relative or relative not in manifest['files']:
            raise ValueError('Attach the performance report before publish validation.')
        report = json.loads((root / relative).read_text(encoding='utf-8'))
        validation = dict(validation, performance=rig_performance_policy.validate(report, manifest['performance_policy']))
    for source in (root/'publish_checks').rglob('*'):
        if source.is_file():manifest['files'][source.relative_to(root).as_posix()]={'sha256':digest(source),'bytes':source.stat().st_size}
    manifest['status']='validated';manifest['validation']=validation
    (root/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return manifest

def prepare_workspace(package,require_validated=True):
    manifest=verify(package,require_validated)
    workspace=Path(tempfile.mkdtemp(prefix='autorig_rigpackage_'))
    shutil.copytree(package,workspace,dirs_exist_ok=True)
    return workspace,manifest

def build(package,require_validated=True):
    from maya import cmds
    if cmds.file(query=True,modified=True):raise ValueError('Save the current scene before rebuilding a rig package.')
    workspace,manifest=prepare_workspace(package,require_validated)
    # Reload only this project's Python modules for the explicitly selected recipe.
    prefixes=('maya_tools','biped','quadruped','tools','utils','ui')
    owned_names=[]
    for name,module in list(sys.modules.items()):
        owned_path = 'autorig' in str(getattr(module,'__file__','')).lower() or any('autorig' in str(p).lower() for p in getattr(module,'__path__',[]))
        if name.split('.')[0] in prefixes and (owned_path or name.startswith('maya_tools')):
            owned_names.append(name)
    for name in owned_names:
        sys.modules.pop(name,None)
    sys.path[:0]=[str(workspace),str(workspace/'maya_tools/scripts')]
    from maya_tools.scripts.utils import create_rig
    cmds.optionVar(stringValue=('currentAssetRigName',manifest['asset']))
    create_rig.AutoRig().build()
    return {'workspace':str(workspace),'asset':manifest['asset'],'manifest':manifest}
