import json
from pathlib import Path
import numpy as np
from maya import cmds
from maya_tools.scripts.tools import bifrost_wrinkles as bw, pose_blendshapes as poses, rig_validation as qa

ROOT=Path(r'C:/proyectos/auto-rig')
WORK=ROOT/'tmp/edward_wrinkles_20261015'
config=json.loads((WORK/'cases.json').read_text())
def capture():
    data={}
    with qa._session(),poses._temporary_values(config['neutral']):
        for name,values in config['cases'].items():
            with poses._temporary_values(values):
                data[name]=np.array(bw._mesh_fn('cabeza_high')[2].getPoints())[:,:3].copy()
    return data
if not cmds.about(batch=True):
    assert cmds.file(q=True,sn=True).endswith('/Edward_working_v005.mb')
    np.savez_compressed(str(WORK/'final_expected.npz'),**capture())
    result={'scene':cmds.file(q=True,sn=True),'modified':cmds.file(q=True,modified=True)}
else:
    from maya_tools.scripts.tools import wrinkle_presets as wp
    cmds.file(str(ROOT/'maya_tools/assets/Edward/scenes/Edward_working_v005.mb'),open=True,force=True,prompt=False,executeScriptNodes=False)
    cmds.evaluator(name='cache',enable=False)
    expected=np.load(str(WORK/'final_expected.npz'))
    def compare(label):
        actual=capture()
        errors={k:float(np.linalg.norm(v-expected[k],axis=1).max()) for k,v in actual.items()}
        assert max(errors.values())<1e-4,(label,errors)
        return errors
    report={'scene_reopen_max_error_cm':compare('scene reopen')}
    (WORK/'roundtrip_reopen.json').write_text(json.dumps(report,indent=2))
    # Native Bifrost graph deletion/build is unsafe in standalone undo history.
    cmds.undoInfo(state=False)
    wp.apply_preset(str(ROOT/'autorig_tools/maya_tools/assets/Edward/wrinkles/Edward_v004.wrinkles.json'),
                    'cabeza_high',prefix='EdwardWrinkles',replace_existing=True)
    report['preset_restore_max_error_cm']=compare('preset restore')
    record=bw.export_setups()[0]
    assert len(record['controls'])==19
    assert not any(record['patterns']['Eyes']) and not any(record['patterns']['Chin'])
    (WORK/'roundtrip.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
