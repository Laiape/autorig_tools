"""Verified local binary copies of source models, invalidated by content and Maya API."""
import hashlib
import json
import os
from pathlib import Path
from maya import cmds
from .build_timing import measure


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            value.update(block)
    return value.hexdigest()


def open_model(source):
    source = Path(source).resolve()
    if source.suffix.lower() != '.ma':
        cmds.file(str(source), open=True, force=True)
        return dict(source=str(source), cache_hit=False, cache_supported=False)
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
    if valid:
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
    pending = root/(identity+'.'+str(os.getpid())+'.pending.mb')
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
