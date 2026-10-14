"""Hash tampering, publish gates and immutable working-copy preparation."""
import sys,tempfile,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[4]))
from maya_tools.scripts.tools import rig_package as p
with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);repo=root/'repo';script=repo/'maya_tools/scripts/tool.py';script.parent.mkdir(parents=True);script.write_text('value = 1\n')
    for category in ('models','guides','curves','build','skin_clusters'):
        path=repo/'maya_tools/assets/Test'/category/('Test_v001.'+category);path.parent.mkdir(parents=True);path.write_text('{}')
    data=repo/'maya_tools/assets/Test/rig_data/roles.roles.json';data.parent.mkdir(parents=True);data.write_text('{"bindings": []}')
    package=root/'package';p.create(repo,'Test',package)
    assert (package/'maya_tools/assets/Test/rig_data/roles.roles.json').read_text()==data.read_text()
    try:p.verify(package,True);raise AssertionError('Unvalidated package accepted')
    except ValueError:pass
    try:p.mark_validated(package,{'success':True});raise AssertionError('Missing comparisons accepted')
    except ValueError:pass
    p.mark_validated(package,{'success':True,'rebuild_max_difference':0,'reopen_max_difference':0})
    workspace,manifest=p.prepare_workspace(package);assert manifest['status']=='validated'
    (workspace/'maya_tools/scripts/tool.py').write_text('changed')
    p.verify(package,True)
    frozen=package/'maya_tools/scripts/tool.py';frozen.write_text('tampered')
    try:p.verify(package,True);raise AssertionError('Tampered source accepted')
    except ValueError:pass
print('PASS package hashes, publish gate and immutable working copy')
