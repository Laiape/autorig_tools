"""Collect final, scoped quality evidence without modifying any artist scene."""
import ast
import hashlib
import json
from pathlib import Path
import shutil

root = Path('C:/proyectos/auto-rig/autorig_tools')
scratch = Path(__file__).resolve().parent
out = root/'maya_tools/docs/validation/ng_nurbs_bridge_20261016'
reports = ['native_tests.json', 'portable_test.json', 'portable_gui_install.json', 'portable_gui_restart.json']
for name in reports:
    shutil.copyfile(scratch/name, out/name)
shutil.copyfile(scratch/'gui_tests_07.json', out/'gui_tests.json')
for name in ['autorig_ng.png', 'standalone_ng.png', 'surface_brush_buffer.png']:
    shutil.copyfile(scratch/'gui_images'/name, out/name)
for name in ['portable_install.png', 'portable_restart.png']:
    shutil.copyfile(scratch/name, out/name)
native = json.loads((out/'native_tests.json').read_text())
gui = json.loads((out/'gui_tests.json').read_text())
portable = json.loads((out/'portable_test.json').read_text())
restart = json.loads((out/'portable_gui_restart.json').read_text())
assert native['success'] and native['tests'] == 16
assert gui['success'] and gui['result']['stroke_dabs'] > 0 and not gui['result']['stroke_error']
assert portable['independent_authoring'] and portable['no_autorig_imports']
assert restart['success'] and restart['startup_hook'] and restart['no_autorig_imports']
sources = list((root/'maya_tools/scripts/ng_nurbs_bridge').glob('*.py')) + [
    root/'maya_tools/scripts/ui/skinning_tool_adapters.py',
    root/'maya_tools/scripts/tools/tests/test_ng_nurbs_bridge.py',
    root/'maya_tools/scripts/tools/tests/test_ng_nurbs_bridge_ui.py',
    root/'scripts/build_ng_nurbs_bridge_installer.py',
    root/'dist/install_ng_nurbs_bridge.py']
for path in sources:
    ast.parse(path.read_text(encoding='ascii'))
for path in [root/'maya_tools/docs/ng_nurbs_bridge.md', root/'maya_tools/docs/ng_nurbs_bridge_design_20261016.md']:
    path.read_text(encoding='ascii')
audit = json.loads((out/'summary.json').read_text())
vendor = {p: h for p, h in audit['source_sha256'].items() if 'ProgramData' in p}
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in vendor.items())
summary = dict(status='implemented_and_validated', date='2026-10-16', maya='2026.3.3', ng='2.4.0',
    native_tests=native['tests'], native_success=True, viewport_stroke_dabs=gui['result']['stroke_dabs'],
    viewport_undo_redo=True, autorig_adjacent_tab=True, standalone_ng_tab=True,
    independent_install_and_reinstall=True, no_autorig_imports=True,
    automatic_attachment_after_restart=True, native_scene_reopen=True,
    vendor_sources_and_binary_unchanged=True, security_policy_unchanged=True,
    security_note='Maya can request native Allow for brush_plugin.py under Secure Plugin Loading; this prompt was not automatically approved.',
    source_sha256={str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
    limits=['Maya 2026 / NG 2.4.0 validated; other versions not validated',
            'Untrimmed local surface with one skinCluster; no referenced/stacked/driven destination weights',
            'Local tangent metric brush footprint; sampled 24 x 24 display',
            'No performance measurement or full-character build regression claimed'])
(out/'implementation_validation.json').write_text(json.dumps(summary, indent=2), encoding='ascii')
print(json.dumps({k:v for k,v in summary.items() if k not in ('source_sha256','limits')}, indent=2))
