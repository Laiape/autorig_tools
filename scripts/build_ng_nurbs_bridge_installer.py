"""Build the portable installer exclusively from the independent extension."""
import base64
import hashlib
import io
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'maya_tools/scripts/ng_nurbs_bridge'
DESTINATION = ROOT / 'dist/install_ng_nurbs_bridge.py'

TEMPLATE = '''"""Drag this file into Maya to attach NURBS Skin to ngSkinTools 2.

Requires installed ngSkinTools 2. Tested in Maya 2026 / NG 2.4.0.
The embedded extension has no AutoRig dependency. Does not bundle NG itself.
"""
import base64
import hashlib
import io
from pathlib import Path
import sys
import zipfile

PAYLOAD = {payload!r}
SHA256 = {digest!r}
VERSION = '1.0.0'


def install(open_window=True, maya_directory=None):
    from maya import cmds
    import ngSkinTools2
    archive = base64.b64decode(PAYLOAD)
    if hashlib.sha256(archive).hexdigest() != SHA256:
        raise RuntimeError('NURBS Skin installer payload is damaged.')
    maya_root = Path(maya_directory or cmds.internalVar(userAppDir=True)).resolve()
    module_root = maya_root / 'ngNurbsBridge'
    scripts = module_root / 'scripts'
    scripts.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(archive)) as package:
        for entry in package.infolist():
            target = (scripts / entry.filename).resolve()
            if not target.is_relative_to(scripts.resolve()) or not entry.filename.startswith('ng_nurbs_bridge/'):
                raise RuntimeError('Invalid installer package path.')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(package.read(entry))
    bootstrap = ("def _ng_nurbs_startup():\\n"
                 "    try:\\n"
                 "        from ng_nurbs_bridge import attach\\n"
                 "        attach()\\n"
                 "    except Exception as error:\\n"
                 "        from maya import cmds\\n"
                 "        cmds.warning('NURBS Skin: ' + str(error))\\n"
                 "from maya import utils as _ng_nurbs_utils\\n"
                 "_ng_nurbs_utils.executeDeferred(_ng_nurbs_startup)\\n")
    (scripts / 'userSetup.py').write_text(bootstrap, encoding='ascii')
    modules = maya_root / 'modules'
    modules.mkdir(parents=True, exist_ok=True)
    (modules / 'ng_nurbs_bridge.mod').write_text(
        '+ ng_nurbs_bridge ' + VERSION + ' ' + module_root.as_posix() + '\\nPYTHONPATH +:= scripts\\n', encoding='utf-8')
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import ng_nurbs_bridge
    ng_nurbs_bridge.attach()
    if open_window:
        ng_nurbs_bridge.open_ui()
    restart = Path(ng_nurbs_bridge.__file__).resolve().parent != (scripts/'ng_nurbs_bridge').resolve()
    print('NURBS Skin installed. Open ngSkinTools 2 to use the NURBS Skin tab.' +
          (' Restart Maya to use the installed copy.' if restart else ''))
    return {{'module_root': str(module_root), 'restart_required': restart}}


def uninstall(maya_directory=None):
    """Remove automatic attachment. Runtime files remain for existing Undo commands."""
    from maya import cmds
    from ng_nurbs_bridge.ng_host import uninstall as detach_ui
    detach_ui()
    root = Path(maya_directory or cmds.internalVar(userAppDir=True)).resolve()
    for target in (root/'modules/ng_nurbs_bridge.mod', root/'ngNurbsBridge/scripts/userSetup.py'):
        if target.is_file():
            target.unlink()
    print('NURBS Skin automatic attachment removed. Runtime retained for Undo and scene recovery.')


def onMayaDroppedPythonFile(*args):
    try:
        return install()
    except Exception as error:
        from maya import cmds
        cmds.warning('NURBS Skin installation: ' + str(error))
        raise
'''


def build():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(PACKAGE.glob('*.py')):
            source = path.read_text(encoding='ascii')
            if 'maya_tools' in source or 'C:/proyectos' in source:
                raise ValueError('Portable runtime contains an AutoRig dependency: '+str(path))
            compile(source, str(path), 'exec')
            info = zipfile.ZipInfo('ng_nurbs_bridge/'+path.name, date_time=(2026, 10, 16, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, source.encode('ascii'))
    payload = buffer.getvalue()
    installer = TEMPLATE.format(payload=base64.b64encode(payload).decode('ascii'),
                                digest=hashlib.sha256(payload).hexdigest())
    compile(installer, str(DESTINATION), 'exec')
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    DESTINATION.write_text(installer, encoding='ascii')
    print(str(DESTINATION))
    return DESTINATION


if __name__ == '__main__':
    build()
