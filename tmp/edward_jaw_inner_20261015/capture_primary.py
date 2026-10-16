import runpy
from maya_tools.scripts.tools import bifrost_wrinkles
with bifrost_wrinkles.primary_inputs_for_skin_export():
    result=runpy.run_path(r'C:/proyectos/auto-rig/tmp/edward_jaw_inner_20261015/capture_neutral.py')['result']
