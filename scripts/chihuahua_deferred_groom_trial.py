"""Owned native prototype: keep Chihuahua groom as an unloaded reference."""
import ast
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import time
import argparse
os.environ['MAYA_SKIP_USERSETUP_PY']='1'
ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'autorig_tools'
sys.path[:0]=[str(RUNTIME),str(RUNTIME/'maya_tools/scripts')]
parser=argparse.ArgumentParser()
parser.add_argument('--release', action='store_true')
options=parser.parse_args()
FOLDER=ROOT/('tmp/chihuahua_deferred_groom_20261016_release' if options.release else 'tmp/chihuahua_deferred_groom_20261016_v001')
FOLDER.mkdir(parents=True,exist_ok=True)
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya.api import OpenMaya as om
from maya_tools.scripts.utils import model_cache
source=RUNTIME/'maya_tools/assets/chihuahua/models/chihuahua_v001.ma'
binary=model_cache._cache_record(source)['binary']
cmds.evaluationManager(mode='off')
report={'source':str(source),'source_sha256':model_cache.digest(source)}
def checkpoint(phase):
    report['phase']=phase
    (FOLDER/'progress.json').write_text(json.dumps(report,indent=2))
checkpoint('open_original')
cmds.file(str(binary),open=True,force=True,executeScriptNodes=False)
# Reuse the exact native mesh/material/UV/groom ownership snapshot implementation.
tree=ast.parse((ROOT/'scripts/chihuahua_prepare_fast_preview.py').read_text())
fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='signature')
exec(compile(ast.Module(body=[fn],type_ignores=[]),str(__file__),'exec'),globals())
original=signature()
assert cmds.getAttr('xgen.visibility') is False
report['original_mesh_count']=len(original['meshes'])
report['original_groom_count']=len(original['groom'])
report['groom_connections']=original['groom_connections']
assert len(cmds.ls(type='xgmPalette'))==0, 'Legacy palettes need separate ownership work'
assert not cmds.listConnections('xgen.visibility',source=True,destination=False)
checkpoint('export_reference')
groom=(RUNTIME/'maya_tools/assets/chihuahua/groom/Chihuahua_groom_v001.mb' if options.release else FOLDER/'Chihuahua_groom_v001.mb')
groom.parent.mkdir(parents=True,exist_ok=True)
assert not groom.exists(), 'Never overwrite a groom version'
cmds.setAttr('xgen.visibility',True)
cmds.select('xgen',replace=True)
cmds.file(str(groom),exportAsReference=True,type='mayaBinary',namespace=':')
refs=[n for n in cmds.ls(type='reference') if n!='sharedReferenceNode']
assert len(refs)==1, refs
ref=refs[0]
cmds.addAttr('chihuahua',longName=model_cache.GROOM_ATTRIBUTE,attributeType='message',hidden=True)
cmds.connectAttr(ref+'.message','chihuahua.'+model_cache.GROOM_ATTRIBUTE)
after=signature()
report['loaded_geometry_exact']=after['meshes']==original['meshes']
report['loaded_groom_exact']=after['groom']==original['groom'] and after['groom_connections']==original['groom_connections']
report['loaded_matrices_exact']=after['transforms']==original['transforms']
assert report['loaded_geometry_exact'] and report['loaded_groom_exact'] and report['loaded_matrices_exact']
report['reference']=ref
report['groom_bytes']=groom.stat().st_size
checkpoint('unload_reference')
cmds.file(unloadReference=ref)
assert not cmds.ls(type='xgmSplineDescription'), 'Heavy descriptions must be absent when unloaded'
light=(source.with_name('chihuahua_v002.mb') if options.release else FOLDER/'Chihuahua_model_preview_v001.mb')
assert not light.exists(), 'Never overwrite a model version'
cmds.file(rename=str(light))
cmds.file(save=True,type='mayaBinary')
report['preview_bytes']=light.stat().st_size
checkpoint('reopen_preview')
start=time.perf_counter()
cmds.file(str(light),open=True,force=True,executeScriptNodes=False)
report['native_preview_open_seconds']=time.perf_counter()-start
assert not cmds.referenceQuery(ref,isLoaded=True)
assert not cmds.ls(type='xgmSplineDescription')
light_geometry=signature()['meshes']
assert light_geometry=={name:record for name,record in original['meshes'].items() if not name.startswith('|xgen|')}
checkpoint('reload_groom')
assert model_cache.show_groom('chihuahua')==ref
restored=signature()
def canonical_groom_paths(data):
    # A message-owned reference can restore its xgen group under the character.
    # Compare the actual world data/matrices, retaining that ownership change.
    return {name.replace('|chihuahua|xgen','|xgen'): value for name,value in data.items()}
report['native_reopen_reload_geometry_exact']=canonical_groom_paths(restored['meshes'])==canonical_groom_paths(original['meshes'])
report['native_reopen_reload_groom_exact']=restored['groom']==original['groom'] and restored['groom_connections']==original['groom_connections']
report['native_reopen_reload_world_matrices_exact']=canonical_groom_paths(restored['transforms'])==canonical_groom_paths(original['transforms'])
assert report['native_reopen_reload_geometry_exact'] and report['native_reopen_reload_groom_exact']
assert model_cache.digest(source)==report['source_sha256']
report['preview']=str(light)
report['groom']=str(groom)
report['preview_sha256']=model_cache.digest(light)
report['groom_sha256']=model_cache.digest(groom)
cmds.file(unloadReference=ref)
# Exit with the heavy reference unloaded; earlier standalone teardown with a
# reloaded XGen graph crashed after writing its successful quality receipt.
checkpoint('complete')
(FOLDER/'result.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report),flush=True)
os._exit(0)
