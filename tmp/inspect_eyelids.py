import sys
from maya import cmds
result = {
    'scene': cmds.file(q=True, sn=True),
    'modified': cmds.file(q=True, modified=True),
    'modules': {k: getattr(v, '__file__', None) for k, v in list(sys.modules.items())
                if k.endswith(('eyelid_module', 'create_rig'))},
    'direct': cmds.ls('*eyeDirect_CTL'),
    'controls': cmds.ls('*eyelid*CTL'),
}
result['details'] = {}
for side in ('L', 'R'):
    curves = [side + '_eyelid' + suffix + '_CRV' for suffix in ('Up', 'Down', 'UpRebuilded', 'DownRebuilded')]
    result['details'][side] = {
        'attrs': {attr: cmds.getAttr(side + '_eyeDirect_CTL.' + attr)
                  for attr in ('Upper_Blink', 'Lower_Blink', 'Blink_Height')},
        'history': {curve: cmds.listHistory(curve)[:15] for curve in curves},
        'surface': cmds.objExists(side + '_eyeSurface_NRB'),
        'locks': {ctl: [cmds.getAttr(ctl + '.r' + axis, lock=True) for axis in 'xyz']
                  for ctl in cmds.ls(side + '_eyelid*CTL')},
    }
