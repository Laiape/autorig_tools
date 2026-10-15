"""Real Bifrost: region edits, controls, presets, projection and rest recovery."""
import os,sys,json,tempfile
from pathlib import Path
os.environ.setdefault('MAYA_SKIP_USERSETUP_PY','1')
sys.path[:0]=[str(Path(__file__).resolve().parents[4]),str(Path(__file__).resolve().parents[2])]
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya.api import OpenMaya as om
import numpy as np
try:
    from maya_tools.scripts.tools import wrinkle_presets as presets,bifrost_wrinkles as wrinkles
    from maya_tools.scripts.tools.skin_manager_api import SkinManager
    cmds.undoInfo(state=True)
    root=cmds.createNode('transform',name='Character')
    mesh=cmds.polyPlane(width=8,height=8,subdivisionsX=8,subdivisionsY=8,constructionHistory=False)[0]
    cmds.parent(mesh,root)
    controls=[]
    for side,x in (('L',-2),('R',2)):
        offset=cmds.createNode('transform',parent=root);cmds.setAttr(offset+'.translateX',x)
        controls.append(cmds.createNode('transform',name=side+'_test_CTL',parent=offset))
    setup=presets.create(mesh,'Portable')
    source_points=np.asarray([[p.x,p.y,p.z] for p in wrinkles._mesh_fn(mesh)[2].getPoints()])
    region=[i for i,p in enumerate(source_points) if p[0]<0]
    pattern=presets.assign_region(setup['settings'],'Forehead',region,angle=35,wavelength=3,plane='XZ')
    assert all(v==0 for i,v in enumerate(pattern) if i not in region)
    assert any(abs(v)>1e-3 for v in pattern)
    cmds.setAttr(setup['settings']+'.ManualActivation',1)
    def points(mesh):
        shape,path,fn=wrinkles._mesh_fn(mesh);cmds.dgeval(shape+'.outMesh')
        return np.asarray([[p.x,p.y,p.z] for p in fn.getPoints()])
    before=points(setup['output'])
    setup=presets.assign_controls(setup['settings'],'Forehead',controls,radius=1.2)
    assert np.allclose(points(setup['output']),before,atol=2e-5)
    assert cmds.getAttr(mesh+'.visibility')
    cmds.setAttr(controls[0]+'.wrinkleValue',0)
    assert np.max(np.abs(points(setup['output'])-before))>.01
    cmds.setAttr(controls[0]+'.wrinkleValue',1)
    cmds.setAttr(setup['settings']+'.ManualActivation',0)
    with tempfile.TemporaryDirectory() as folder:
        path=str(Path(folder)/'character.wrinkles.json')
        presets.export_preset(setup['settings'],path)
        # Restore calibrated rest while the source is physically compressed.
        compressed=source_points.copy();compressed[:,[0,2]]*=.8
        wrinkles._mesh_fn(mesh)[2].setPoints(om.MPointArray([om.MPoint(*p) for p in compressed]))
        expected=points(setup['output'])
        setup=presets.apply_preset(path,mesh,prefix='Portable',replace_existing=True)
        assert np.allclose(points(setup['output']),expected,atol=2e-5)
        assert cmds.attributeQuery('wrinklePreset',node=setup['settings'],exists=True)
        # A different topology/size requires explicit projection and new rest.
        target=cmds.polyPlane(width=16,height=16,subdivisionsX=5,subdivisionsY=5,constructionHistory=False)[0]
        cmds.parent(target,root)
        try:
            presets.apply_preset(path,target,prefix='Variant')
            raise AssertionError('Implicit topology projection accepted')
        except ValueError:pass
        result=presets.apply_preset(path,target,prefix='Variant',remap_topology=True)
        assert result['projected']
        assert np.allclose(points(result['output']),points(target),atol=2e-5),'variant inherited source compression'
        data=presets.setup_record(result['settings'])
        assert len(data['patterns']['Forehead'])==36
        cmds.setAttr(result['settings']+'.ManualActivation',1)
        assert np.max(np.abs(points(result['output'])-points(target)))>.01
        manager=SkinManager.__new__(SkinManager);manager.k_skin_attrs=[];manager.tolerance=1e-5
        snapshot=str(Path(folder)/'wrinkles.skc');cmds.select(clear=True);manager.export_skins(snapshot)
        saved=json.loads(Path(snapshot).read_text())
        assert all(Path(r['preset']).resolve() == Path(path).resolve() for r in saved[manager.WRINKLES_KEY])
        scene=str(Path(folder)/'wrinkles.mb');cmds.file(rename=scene);cmds.file(save=True,type='mayaBinary',force=True)
        cmds.file(new=True,force=True);cmds.file(scene,open=True,force=True)
        assert Path(cmds.getAttr('Portable_Settings.wrinklePreset')).resolve() == Path(path).resolve()
    print('PASS wrinkle presets: signed region fields, support/falloff, scale-independent controls, source visibility, calibrated posed restore, explicit topology projection, new rest, SKC provenance and scene reopen',flush=True)
finally:maya.standalone.uninitialize()
