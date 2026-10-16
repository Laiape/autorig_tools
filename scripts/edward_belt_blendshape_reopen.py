"""Reopen the owned native review and check selector/persisted targets."""
import json
import os
from pathlib import Path
from maya import cmds
FOLDER=Path(r'C:/proyectos/auto-rig/maya_tools/assets/Edward/experiments/belt_blendshape_20261016_v001')
assert os.getpid()==json.loads((FOLDER/'owned_launch.json').read_text())['pid'], 'Use the owned trial process'
manifest=json.loads((FOLDER/'manifest.json').read_text())
cmds.evaluationManager(mode='off')
cmds.file(manifest['review']['scene'],open=True,force=True,prompt=False,executeScriptNodes=False)
result={'scene':cmds.file(q=True,sn=True),'variants':{},'selector':cmds.getAttr(manifest['review']['control']+'.beltVariant')}
assert result['selector']==0
for index,kind in enumerate(('blendshape_only_shared','blendshape_only_separate','shared','separate'),start=1):
    variant=manifest['variants'][kind]
    result['variants'][kind]={}
    cmds.setAttr(manifest['review']['control']+'.beltVariant',index)
    for belt,mesh in variant['meshes'].items():
        bs=variant['blendshapes'][belt]
        assert cmds.getAttr(mesh+'.visibility')
        assert not any(cmds.getAttr(b+'.visibility') for b in manifest['joints'])
        result['variants'][kind][belt]={'blendshape':bs,'targets':len(cmds.getAttr(bs+'.weight',multiIndices=True) or []),
                                      'geometry':cmds.blendShape(bs,q=True,geometry=True),
                                      'geometry_indices':cmds.blendShape(bs,q=True,geometryIndices=True)}
cmds.setAttr(manifest['review']['control']+'.beltVariant',0)
cmds.file(modified=False)
(FOLDER/'native_reopen_structure.json').write_text(json.dumps(result,indent=2))
