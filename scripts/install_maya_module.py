"""Install this checkout as a Maya module without hard-coded machine paths."""
import argparse
import ctypes
import os
from pathlib import Path
import shutil
from datetime import datetime


def default_modules_dir():
    if os.environ.get('MAYA_APP_DIR'):
        return Path(os.environ['MAYA_APP_DIR']) / 'modules'
    try:
        from maya import cmds
        return Path(cmds.internalVar(userAppDir=True)) / 'modules'
    except (ImportError, AttributeError):
        pass
    documents = Path.home() / 'Documents'
    if os.name == 'nt':
        buffer = ctypes.create_unicode_buffer(32768)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buffer) == 0:
            documents = Path(buffer.value)
    return documents / 'maya' / 'modules'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--modules-dir', type=Path, help='Override the Maya modules directory')
    parser.add_argument('--dry-run', action='store_true', help='Show the module without writing it')
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    module = repo / 'maya_tools'
    if not (module / 'scripts' / 'userSetup.py').is_file():
        parser.error('Run this installer from a complete autorig_tools checkout.')
    destination = (args.modules_dir or default_modules_dir()) / 'self_module.mod'
    content = ('+ self_module 1.0 ' + module.as_posix() + '\n'
               'PYTHONPATH += ' + repo.as_posix() + '\n'
               'XBMLANGPATH +:= icons\n')
    print(str(destination))
    if args.dry_run:
        print(content)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.read_text(encoding='utf-8') != content:
        backup = destination.with_name(destination.name + '.' + datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.bak')
        shutil.copy2(destination, backup)
        print('Previous module saved to ' + str(backup))
    destination.write_text(content, encoding='utf-8')
    print('AutoRig module installed. Restart Maya to load the menu and shelf.')


if __name__ == '__main__':
    main()
