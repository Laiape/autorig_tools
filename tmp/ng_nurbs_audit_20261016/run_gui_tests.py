import importlib
from ng_nurbs_bridge import ng_host
importlib.reload(ng_host)
from maya_tools.scripts.tools.tests import test_ng_nurbs_bridge_ui as tests
importlib.reload(tests)
result=tests.run('C:/proyectos/auto-rig/tmp/ng_nurbs_audit_20261016/gui_images')
