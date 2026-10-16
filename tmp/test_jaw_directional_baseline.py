import sys,runpy
from pathlib import Path
root=Path(r'C:/proyectos/auto-rig/autorig_tools')
sys.path[:0]=[str(root),str(root/'maya_tools/scripts/tools/tests')]
from fixtures import jaw_scene
original=jaw_scene.build
jaw_scene.build=lambda:original(Path(r'C:/proyectos/auto-rig/tmp/jaw_orientation_20261015/baseline.py'))
runpy.run_path(str(root/'maya_tools/scripts/tools/tests/test_jaw_directional_defaults.py'),run_name='__main__')
