"""Check production node types and import every rig module in native Maya.

Run in a disposable mayapy process through scripts/run_maya_test.py.
"""
import ast
import importlib
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT / 'maya_tools/scripts')]


def run():
    import maya.standalone
    maya.standalone.initialize(name='python')
    from maya import cmds

    scripts = ROOT / 'maya_tools/scripts'
    calls = []
    for path in sorted(scripts.rglob('*.py')):
        if 'tests' in path.parts or '__pycache__' in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr in ('createNode', 'shadingNode')
                    and node.args and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                calls.append((path, node.lineno, node.args[0].value))

    # These production helpers load their own plugins before creating a node.
    for plugin in ('matrixNodes', 'lookdevKit', 'quatNodes',
                   'poseInterpolator', 'bifrostGraph'):
        cmds.loadPlugin(plugin, quiet=True)
    cmds.loadPlugin(str(scripts / 'tools/proxy_locator.py'), quiet=True)
    registered = set(cmds.allNodeTypes() or [])
    missing = ['%s:%d: %s' % (path.relative_to(ROOT), line, kind)
               for path, line, kind in calls if kind not in registered]
    assert not missing, 'Unregistered production node types:\n' + '\n'.join(missing)

    modules = []
    import_errors = []
    for family in ('biped', 'quadruped', 'flower'):
        for path in sorted((scripts / family / 'autorig').glob('*.py')):
            if path.name == '__init__.py':
                continue
            name = '.'.join(path.relative_to(ROOT).with_suffix('').parts)
            try:
                importlib.import_module(name)
                modules.append(name)
            except Exception as error:
                import_errors.append('%s: %s: %s' % (name, type(error).__name__, error))
    assert not import_errors, 'Rig module import errors:\n' + '\n'.join(import_errors)

    cmds.file(new=True, force=True)
    scalar = cmds.createNode('multiply', name='auditMultiply')
    cmds.setAttr(scalar + '.input[0]', 3.)
    cmds.setAttr(scalar + '.input[1]', -.5)
    quotient = cmds.createNode('divide', name='auditDivide')
    cmds.setAttr(quotient + '.input1', 3.)
    cmds.setAttr(quotient + '.input2', 2.)
    matrix = [1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1., 0., 4., 5., 6., 1.]
    for kind, name in (('multiplyPointByMatrix', 'auditPoint'),
                       ('multiplyVectorByMatrix', 'auditVector')):
        node = cmds.createNode(kind, name=name)
        cmds.setAttr(node + '.input', 1., 2., 3.)
        cmds.setAttr(node + '.matrix', matrix, type='matrix')

    def outputs():
        assert cmds.getAttr(scalar + '.output') == -1.5
        assert cmds.getAttr(quotient + '.output') == 1.5
        assert cmds.getAttr('auditPoint.output')[0] == (5., 7., 9.)
        assert cmds.getAttr('auditVector.output')[0] == (1., 2., 3.)
        assert not (cmds.ls(type='unknown') or [])

    outputs()
    with tempfile.TemporaryDirectory() as folder:
        scene = str(Path(folder) / 'native_math.ma')
        cmds.file(rename=scene)
        cmds.file(save=True, type='mayaAscii', force=True)
        cmds.file(scene, open=True, force=True, executeScriptNodes=False)
        outputs()
    print('PASS %d literal node creations, %d rig module imports, standalone math and native reopen'
          % (len(calls), len(modules)))


if __name__ == '__main__':
    run()
