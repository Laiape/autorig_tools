"""Open the included Edward rig and resolve its textures in this checkout.

Run inside Maya with runpy.run_path(..., run_name="__main__").
"""
from pathlib import Path
import json
from maya import cmds


def relink_scene_textures(asset_root=None):
    asset = Path(asset_root) if asset_root else Path(__file__).resolve().parents[1] / 'maya_tools/assets/Edward'
    manifest = json.loads((asset / 'portable_assets.json').read_text(encoding='utf-8'))
    bundled = {Path(name).name: asset / name for name in manifest['textures']}
    missing = [str(path) for path in bundled.values() if not path.is_file()]
    if missing:
        raise RuntimeError('Bundled textures are missing; run git lfs pull: ' + ', '.join(missing))
    updated = []
    for node in cmds.ls(type='file') or []:
        current = cmds.getAttr(node + '.fileTextureName') or ''
        path = bundled.get(Path(current).name)
        if path:
            cmds.setAttr(node + '.fileTextureName', path.as_posix(), type='string')
            updated.append(node)
    return updated


def main():
    if cmds.file(query=True, modified=True):
        raise RuntimeError('Save the current scene before opening the included Edward rig.')
    asset = Path(__file__).resolve().parents[1] / 'maya_tools/assets/Edward'
    scene = asset / 'scenes/Edward_working_v005.mb'
    if not scene.is_file() or scene.stat().st_size < 1024:
        raise RuntimeError('Edward scene is missing; run git lfs pull before opening it.')
    cmds.workspace(str(asset), openWorkspace=True)
    cmds.evaluator(name='cache', enable=False)
    cmds.file(str(scene), open=True)
    nodes = relink_scene_textures(asset)
    print('Edward opened; %d texture nodes resolved in this checkout.' % len(nodes))


if __name__ == '__main__':
    main()
