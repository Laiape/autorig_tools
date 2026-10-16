"""Update loaded model-open functions without replacing an artist scene or UI."""
import ast
import importlib
from pathlib import Path
import sys
from maya import cmds

runtime = Path(__file__).resolve().parents[1]/'autorig_tools'
def state():
    return {'scene': cmds.file(q=True, sceneName=True), 'modified': cmds.file(q=True, modified=True),
            'frame': cmds.currentTime(q=True), 'selection': cmds.ls(selection=True, long=True)}
before = state()
updated = []
for name, module in list(sys.modules.items()):
    path = getattr(module, '__file__', None)
    if not path or runtime not in Path(path).resolve().parents:
        continue
    if name.endswith('model_cache'):
        importlib.reload(module)
        updated.append(name)
    elif name.endswith('character_manager') and hasattr(module, 'VersionTab'):
        tree = ast.parse(Path(path).read_text(encoding='utf-8'))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'VersionTab')
        function = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'import_file')
        namespace = {}
        exec(compile(ast.Module(body=[function], type_ignores=[]), path, 'exec'), module.__dict__, namespace)
        module.VersionTab.import_file.__code__ = namespace['import_file'].__code__
        updated.append(name)
after = state()
assert before == after, 'Artist scene state changed'
result = {'updated_modules': updated, 'before': before, 'after': after}
