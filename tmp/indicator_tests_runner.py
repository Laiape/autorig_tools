import runpy
import unittest
scope=runpy.run_path('C:/proyectos/auto-rig/autorig_tools/maya_tools/scripts/tools/tests/test_module_nurbs.py',run_name='module_nurbs_regression')
suite=unittest.defaultTestLoader.loadTestsFromTestCase(scope['ModuleNurbsTests'])
result=unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
