"""Verified local binary copies of source models, invalidated by content and Maya API."""
import hashlib
import json
import os
from pathlib import Path
from maya import cmds
from .build_timing import measure

GROOM_ATTRIBUTE = 'autorigDeferredGroom'


def show_groom(character=None):
    """Explicitly load a model's optional groom; never runs during evaluation."""
    roots = cmds.ls('*.' + GROOM_ATTRIBUTE, objectsOnly=True, long=True, recursive=True) or []
    if character:
        roots = [root for root in roots if root.rsplit('|', 1)[-1].split(':')[-1].lower() == character.lower()]
    if len(roots) != 1:
        raise ValueError('Open one model with an optional groom first.')
    root = roots[0]
    references = cmds.listConnections(root + '.' + GROOM_ATTRIBUTE, source=True,
                                     destination=False, type='reference') or []
    if len(references) != 1:
        raise ValueError('The model has no valid optional groom reference.')
    reference = references[0]
    if not cmds.referenceQuery(reference, isLoaded=True):
        cmds.file(loadReference=reference)
    nodes = cmds.referenceQuery(reference, nodes=True, dagPath=True) or []
    groups = [node for node in (cmds.ls(nodes, long=True, type='transform') or [])
              if node.rsplit('|', 1)[-1].split(':')[-1] == 'xgen']
    final = [node for node in (cmds.listRelatives(root, allDescendents=True, fullPath=True, type='transform') or [])
             if node.rsplit('|', 1)[-1].split(':')[-1] == 'FINAL']
    for group in groups:
        # A rig built with the groom deferred must recover the same parent space
        # as an ordinary build that already contained its xgen group.
        if len(final) == 1 and (cmds.listRelatives(group, parent=True, fullPath=True) or []) != final:
            group = cmds.parent(group, final[0], relative=True)[0]
        cmds.setAttr(group + '.visibility', True)
    return reference


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            value.update(block)
    return value.hexdigest()


def _cache_record(source):
    """Resolve a derived binary without opening or replacing the current scene."""
    with measure('Check model cache'):
        sha = digest(source)
        api = cmds.about(apiVersion=True)
        identity = hashlib.sha256((str(source)+'|'+sha+'|'+str(api)).encode()).hexdigest()
        root = Path(os.environ.get('AUTORIG_MODEL_CACHE_DIR') or Path(__file__).resolve().parents[2]/'cache/models')
        binary, metadata = root/(identity+'.mb'), root/(identity+'.json')
        valid = False
        if binary.is_file() and metadata.is_file():
            try:
                record = json.loads(metadata.read_text(encoding='utf-8'))
                valid = (record['source_sha256'] == sha and record['maya_api'] == api
                         and record['binary_sha256'] == digest(binary))
            except (OSError, ValueError, KeyError):
                pass
    return dict(source=source, sha=sha, api=api, root=root, binary=binary,
                metadata=metadata, valid=valid)


def import_model(source, **options):
    """Import a verified existing binary, preserving the current scene and guides."""
    source = Path(source).resolve()
    record = _cache_record(source) if source.suffix.lower() == '.ma' else None
    hit = bool(record and record['valid'])
    chosen = record['binary'] if hit else source
    file_type = 'mayaBinary' if chosen.suffix.lower() == '.mb' else 'mayaAscii'
    options.setdefault('preserveReferences', True)
    cmds.file(str(chosen), i=True, type=file_type, **options)
    return dict(source=str(source), cache_hit=hit, imported=str(chosen))


def open_model(source):
    source = Path(source).resolve()
    if source.suffix.lower() != '.ma':
        cmds.file(str(source), open=True, force=True)
        return dict(source=str(source), cache_hit=False, cache_supported=False)
    record = _cache_record(source)
    sha, api = record['sha'], record['api']
    root, binary, metadata = record['root'], record['binary'], record['metadata']
    if record['valid']:
        with measure('Open cached binary model'):
            cmds.file(str(binary), open=True, force=True)
            # Keep Save and relative asset paths tied to the authored model,
            # never to the disposable binary inside the cache directory.
            modified = cmds.file(query=True, modified=True)
            cmds.file(rename=str(source))
            cmds.file(type='mayaAscii')
            cmds.file(modified=modified)
        return dict(source=str(source), cache_hit=True, binary=str(binary), source_sha256=sha)
    with measure('Open source model'):
        cmds.file(str(source), open=True, force=True)
    pending = root/(binary.stem+'.'+str(os.getpid())+'.pending.mb')
    try:
        with measure('Prepare binary model cache'):
            root.mkdir(parents=True, exist_ok=True)
            cmds.file(str(pending), exportAll=True, force=True, type='mayaBinary', preserveReferences=True)
            record = dict(version=1, source=str(source), source_sha256=sha,
                          maya_api=api, binary_sha256=digest(pending))
            os.replace(pending, binary)
            metadata.write_text(json.dumps(record, indent=2), encoding='utf-8')
    except (OSError, RuntimeError) as exc:
        cmds.warning('[AutoRig model cache] Using the source model: '+str(exc))
    finally:
        if pending.exists():
            pending.unlink()
    return dict(source=str(source), cache_hit=False, binary=str(binary), source_sha256=sha)
