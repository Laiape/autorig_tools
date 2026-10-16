"""Inspect the installed dress reference in an owned Maya batch process."""
import os
import sys
import json
from pathlib import Path

os.environ['MAYA_SKIP_USERSETUP_PY'] = '1'
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya_tools.scripts.tools import dress_keepout_chains as dress
from maya_tools.scripts.tools import muscle_keepout_skirt as core

scene = ROOT/'maya_tools/assets/Nini/scenes/Nini_dress_chains_v006.ma'
cmds.file(str(scene), open=True, force=True)
data = json.loads(cmds.getAttr('NiniDress_Module_GRP.dressRigData'))
print(json.dumps({
    'runtime': [dress.__file__, core.__file__], 'scene': str(scene),
    'keys': list(data), 'settings': {a: cmds.getAttr(data['settings']+'.'+a)
        for a in ('collisionEnable', 'collisionBlend', 'collisionMargin',
                  'L_thighRadius', 'L_calfRadius', 'R_thighRadius', 'R_calfRadius')},
    'station_3': data['stations_local'][3], 'rest_sample': data.get('rest_contacts', [])[:1],
    'orientation_sample': data.get('rest_orientations', [])[:1],
    'goals_sample': list(data['goals'].items())[:2],
    'linear_unit': cmds.currentUnit(q=True, linear=True),
    'time_unit': cmds.currentUnit(q=True, time=True),
    'ankles': {s: cmds.xform(s+'_ankleIk_CTL', q=True, ws=True, t=True) for s in ('L','R')}
}, indent=2), flush=True)
maya.standalone.uninitialize()
