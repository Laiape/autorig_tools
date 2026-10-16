"""Component inventory, explicit storage payloads and controlled Edward ablations."""
from contextlib import contextmanager
from collections import Counter, defaultdict, deque
import ctypes
import hashlib
import json
from pathlib import Path
import re
import sys
import time
import numpy as np
from maya import cmds
from maya.api import OpenMaya as om, OpenMayaAnim as oma
sys.path.insert(0,str(Path(__file__).resolve().parent))
import edward_driver_routing_trial as routing
from maya_tools.scripts.tools import rig_benchmark as rb, rig_validation as qa, pose_blendshapes as pb
from maya_tools.scripts.tools import bifrost_wrinkles as bw

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'maya_tools/assets/Edward/experiments/full_audit_20261015_v001'
FOLDER.mkdir(parents=True,exist_ok=True)

def write(name,data):
    (FOLDER/name).write_text(json.dumps(data,indent=2,default=str),encoding='utf-8')

def memory():
    class Counters(ctypes.Structure):
        _fields_=[('cb',ctypes.c_ulong),('PageFaultCount',ctypes.c_ulong)]+[(n,ctypes.c_size_t) for n in ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage','PrivateUsage')]
    c=Counters();c.cb=ctypes.sizeof(c)
    kernel=ctypes.windll.kernel32;kernel.GetCurrentProcess.restype=ctypes.c_void_p
    ctypes.windll.psapi.GetProcessMemoryInfo.argtypes=[ctypes.c_void_p,ctypes.POINTER(Counters),ctypes.c_ulong]
    if not ctypes.windll.psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(c),c.cb):raise ctypes.WinError()
    return {'working_set_bytes':c.WorkingSetSize,'private_bytes':c.PrivateUsage,'peak_working_set_bytes':c.PeakWorkingSetSize}

def dag(node):
    s=om.MSelectionList();s.add(node);return s.getDagPath(0)

def component(path):
    if path.node().hasFn(om.MFn.kMesh):
        f=om.MFnMesh(path);c=om.MFnSingleIndexedComponent();obj=c.create(om.MFn.kMeshVertComponent);c.setCompleteData(f.numVertices);return obj,f.numVertices
    if path.node().hasFn(om.MFn.kNurbsCurve):
        f=om.MFnNurbsCurve(path);c=om.MFnSingleIndexedComponent();obj=c.create(om.MFn.kCurveCVComponent);c.setCompleteData(f.numCVs);return obj,f.numCVs
    if path.node().hasFn(om.MFn.kNurbsSurface):
        f=om.MFnNurbsSurface(path);c=om.MFnDoubleIndexedComponent();obj=c.create(om.MFn.kSurfaceCVComponent);c.setCompleteData(f.numCVsInU,f.numCVsInV);return obj,f.numCVsInU*f.numCVsInV
    raise TypeError(path.fullPathName())

def catalog():
    routing.load('original');cmds.evaluationManager(mode='off');cmds.refresh(force=True)
    nodes={};edges=[];it=om.MItDependencyNodes()
    while not it.isDone():
        obj=it.thisNode();f=om.MFnDependencyNode(obj);n=f.name()
        row={'type':f.typeName,'uuid':f.uuid().asString(),'frozen_supported':f.hasAttribute('frozen')}
        if obj.hasFn(om.MFn.kDagNode):row['path']=om.MFnDagNode(obj).fullPathName()
        nodes[n]=row
        for p in f.getConnections():
            if p.isDestination:
                for s in p.connectedTo(True,False):
                    if p.attribute().hasFn(om.MFn.kMessageAttribute):continue
                    edges.append([om.MFnDependencyNode(s.node()).name(),n,s.partialName(useLongNames=True),p.partialName(useLongNames=True)])
        it.next()
    groups=cmds.ls('*Module_GRP',long=True,type='transform') or []
    modules={}
    for group in groups:
        stem=group.rsplit('|',1)[-1].replace('Module_GRP','')
        roots=[group]+(cmds.ls(stem+'Skinning_GRP',stem+'Controllers_GRP',long=True) or [])
        owned=set()
        for root in roots:
            owned.update([root.rsplit('|',1)[-1]]+[p.rsplit('|',1)[-1] for p in cmds.listRelatives(root,ad=True,fullPath=True) or []])
        modules[stem]={'group':group,'roots':roots,'dag_nodes':sorted(owned)}
    # A neck controller hierarchy contains facial module hierarchies. The most
    # specific root owns each DAG node; nesting does not make all face nodes neck.
    ownership={}
    for n,row in nodes.items():
        path=row.get('path','')
        candidates=[(len(root),key) for key,m in modules.items() for root in m['roots'] if path==root or path.startswith(root+'|')]
        if candidates:ownership[n]=max(candidates)[1]
    for key,m in modules.items():m['dag_nodes']=sorted(n for n,owner in ownership.items() if owner==key)
    # A DG utility belongs to the modules whose DAG inputs it feeds. Traversal
    # stops at other DAG nodes and deformation boundaries; overlaps remain shared.
    incoming=defaultdict(set)
    for s,d,*_ in edges:incoming[d].add(s)
    boundaries={'skinCluster','blendShape','proximityWrap','bifrostGraphShape','bifrostGeoToMaya','shadingEngine','objectSet','network','time','sequenceManager'}
    claims=defaultdict(set)
    for key,m in modules.items():
        owned=set(m['dag_nodes']);todo=deque(owned)
        while todo:
            d=todo.popleft()
            for s in incoming[d]:
                if s in owned or s not in nodes:continue
                row=nodes[s]
                if 'path' in row or row['type'] in boundaries:continue
                owned.add(s);todo.append(s)
        for n in owned:claims[n].add(key)
        m['claimed_nodes']=sorted(owned)
    for key,m in modules.items():
        m['exclusive_nodes']=sorted(n for n in m['claimed_nodes'] if len(claims[n])==1)
        m['shared_nodes']=sorted(n for n in m['claimed_nodes'] if len(claims[n])>1)
        m['types']=dict(Counter(nodes[n]['type'] for n in m['exclusive_nodes']))
    meshes=[]
    for s in cmds.ls(type='mesh',long=True):
        path=dag(s);f=om.MFnMesh(path)
        counts,indices=f.getVertices()
        uv={name:f.numUVs(name) for name in f.getUVSetNames()}
        meshes.append({'name':s.rsplit('|',1)[-1],'path':s,'intermediate':f.isIntermediateObject,'visible':path.isVisible(),'vertices':f.numVertices,'polygons':f.numPolygons,'face_vertices':len(indices),'normals':f.numNormals,'uv_sets':uv,'raw_float32_payload_lower_bound_bytes':f.numVertices*12+f.numNormals*12+sum(uv.values())*8+len(indices)*4+len(counts)*4,'input':routing.source(s+'.inMesh'),'consumers':cmds.listConnections(s,s=False,d=True,p=True) or []})
    skins=[]
    with bw.primary_inputs_for_skin_export():
        for n in cmds.ls(type='skinCluster'):
            sl=om.MSelectionList();sl.add(n);fn=oma.MFnSkinCluster(sl.getDependNode(0))
            influence=fn.influenceObjects();outputs=[]
            for obj in fn.getOutputGeometry():
                path=om.MDagPath.getAPathTo(obj)
                if not any(path.node().hasFn(k) for k in (om.MFn.kMesh,om.MFn.kNurbsCurve,om.MFn.kNurbsSurface)):continue
                try:
                    comp,count=component(path);weights,ninf=fn.getWeights(path,comp)
                    a=np.asarray(weights).reshape((count,ninf));nonzero=int(np.count_nonzero(a));perv=np.count_nonzero(a,axis=1)
                    outputs.append({'shape':path.fullPathName(),'components':count,'dense_weight_values':int(a.size),'nonzero_weights':nonzero,'maximum_actual_influences':int(perv.max()),'mean_actual_influences':float(perv.mean()),'nonzero_weights_double_payload_bytes':nonzero*8,'dense_double_array_bytes':int(a.size*8)})
                except Exception as e:outputs.append({'shape':path.fullPathName(),'error':str(e)})
            skins.append({'name':n,'influences':len(influence),'influence_names':[p.partialPathName() for p in influence],'geometry':outputs,'skinning_method':cmds.getAttr(n+'.skinningMethod'),'max_influences_setting':cmds.getAttr(n+'.maxInfluences'),'maintain_max_influences':cmds.getAttr(n+'.maintainMaxInfluences'),'envelope':cmds.getAttr(n+'.envelope')})
    blends=[]
    for n in cmds.ls(type='blendShape'):
        targets=[]
        for base in cmds.getAttr(n+'.inputTarget',multiIndices=True) or []:
            root='%s.inputTarget[%d].inputTargetGroup'%(n,base)
            for target in cmds.getAttr(root,multiIndices=True) or []:
                group=root+'[%d]'%target
                for item in cmds.getAttr(group+'.inputTargetItem',multiIndices=True) or []:
                    plug=group+'.inputTargetItem[%d]'%item
                    pts=cmds.getAttr(plug+'.inputPointsTarget') or []
                    targets.append({'base':base,'target':target,'item':item,'stored_points':len(pts),'raw_point_array_double4_bytes':len(pts)*32,'live_geometry':routing.source(plug+'.inputGeomTarget')})
        blends.append({'name':n,'aliases':cmds.aliasAttr(n,q=True),'weight_indices':cmds.getAttr(n+'.weight',multiIndices=True),'targets':targets,'outputs':cmds.listConnections(n+'.outputGeometry',s=False,d=True,p=True) or []})
    result={'source_scene':cmds.file(q=True,sn=True),'source_sha256':hashlib.sha256(Path(cmds.file(q=True,sn=True)).read_bytes()).hexdigest(),'scene_bytes':Path(cmds.file(q=True,sn=True)).stat().st_size,'node_types':dict(Counter(r['type'] for r in nodes.values())),'nodes':nodes,'edges':edges,'modules':modules,'meshes':meshes,'skins':skins,'blendShapes':blends,'prx':routing.INVENTORY['prx'],'memory':memory(),'frozen_configuration':rb._query(lambda:cmds.evaluator(name='frozen',q=True,configuration=True)),'frozen_help':rb._query(lambda:cmds.evaluator(name='frozen',q=True,info=True))}
    write('catalog.json',result)
    return {'nodes':len(nodes),'modules':list(modules),'skins':len(skins),'meshes':len(meshes),'scene_bytes':result['scene_bytes'],'memory':result['memory']}

def storage_current_scene():
    data=json.loads((FOLDER/'catalog.json').read_text())
    out=FOLDER/'storage_payloads';out.mkdir(exist_ok=True)
    rows=[]
    def export(label,names,kind):
        names=sorted(set(n for n in names if cmds.objExists(n)))
        if not names:return
        path=out/(re.sub('[^A-Za-z0-9_.-]','_',label)+'.mb')
        cmds.select(names,r=True,noExpand=True)
        cmds.file(path.as_posix(),exportSelectedStrict=True,type='mayaBinary',force=True)
        rows.append({'label':label,'kind':kind,'nodes':len(names),'bytes':path.stat().st_size,'file':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        write('storage_progress.json',rows[-1])
    def baked(label,shapes):
        root=cmds.createNode('transform',name='auditBakedPayload_GRP')
        try:
            for i,shape in enumerate(shapes):
                t=cmds.createNode('transform',name='auditBaked%d'%i,parent=root)
                path=dag(shape);om.MFnMesh().copy(path.node(),dag(t).node())
                cmds.xform(t,matrix=list(path.inclusiveMatrix()),worldSpace=True)
            export(label,[root]+(cmds.listRelatives(root,ad=True,fullPath=True) or []),'baked_geometry_without_history_or_materials')
        finally:cmds.delete(root)
    model=[m for m in data['meshes'] if '|geo_GRP|' in m['path'] and not m['intermediate']]
    baked('model_all_display_outputs',[m['path'] for m in model])
    baked('model_visible_outputs',[m['path'] for m in model if m['visible']])
    for name in ('cabeza_high','cabeza_low','cuerpo_base','cabello_geo'):
        shapes=cmds.listRelatives(name,shapes=True,noIntermediate=True,fullPath=True,type='mesh') or []
        if shapes:baked('model_'+name,shapes)
    for n,m in data['modules'].items():export('module_'+n,m['exclusive_nodes'],'module_exclusive_native_nodes')
    for skin in data['skins']:export('skin_'+skin['name'],[skin['name']],'isolated_skin_payload')
    for row in data['blendShapes']:export('blend_'+row['name'],[row['name']],'isolated_blendShape_payload')
    for n in data['prx']:export('prx_'+n,[n],'isolated_proximityWrap_payload')
    export('all_skinClusters',[s['name'] for s in data['skins']],'isolated_skin_payload')
    export('all_PRX',data['prx'],'isolated_proximityWrap_payload')
    export('all_corrective_blendShapes',[s['name'] for s in data['blendShapes'] if 'poseCorrectives' in s['name']],'isolated_corrective_payload')
    wrinkle_nodes=[n for n in data['nodes'] if n.startswith('EdwardWrinkles')]
    export('wrinkles',wrinkle_nodes,'isolated_wrinkle_nodes_and_native_data')
    exports=[]
    for n in cmds.ls(type='file') or []:
        value=cmds.getAttr(n+'.fileTextureName') or ''
        p=Path(value);exports.append({'node':n,'path':value,'exists':p.is_file(),'bytes':p.stat().st_size if p.is_file() else None})
    report={'measurement':'Native strict exports are data payload snapshots, not standalone functional rigs; inter-component connections and per-file headers differ from the combined scene. Baked geometry contains evaluated polygon data without materials/history. Bytes are measured, not process RAM.','payloads':rows,'textures':exports,'memory_after_export':memory()}
    write('storage.json',report)
    return {'exports':len(rows),'largest':sorted(rows,key=lambda r:r['bytes'],reverse=True)[:8]}

def storage():
    if cmds.about(batch=True):
        cmds.file((routing.FOLDER/'Edward_baseline.mb').as_posix(),open=True,force=True,prompt=False,executeScriptNodes=False)
    else:routing.load('original')
    cmds.evaluationManager(mode='off')
    with bw.primary_inputs_for_skin_export():return storage_current_scene()

def audit_cases(only_module=None):
    specs={
      'C_spine':[('C_spine03_CTL.rotateZ',-15,15),('C_localChest_CTL.rotateY',-12,12)],
      'C_neck':[('C_neck_CTL.rotateY',-25,25),('C_head_CTL.rotateZ',-10,10)],
      'C_jaw':[('C_jaw_CTL.rotateX',0,30),('L_lipCorner_CTL.translateX',-2,5),('R_lipCorner_CTL.translateY',-3,3)],
      'C_eyebrow':[('L_eyebrowIn_CTL.translateY',-2,1),('R_eyebrowMain_CTL.translateY',-1,1)],
      'C_eyelid':[('L_eyeDirect_CTL.Upper_Blink',0,1),('R_eyeDirect_CTL.Lower_Blink',0,1)],
      'C_cheekbone':[('L_cheek_CTL.translateY',-1,1),('R_cheek_CTL.translateY',-1,1)],
      'C_ear':[('L_ear00_CTL.rotateZ',-15,15),('R_ear00_CTL.rotateZ',-15,15)],
      'C_nose':[('C_noseMain_CTL.translateY',-.4,.4)],
      'C_teeth':[('C_lowerTeeth_CTL.translateY',-.15,.15),('C_upperTeeth_CTL.translateY',-.15,.15)],
      'C_tongue':[('C_tongue00_CTL.rotateY',-10,10),('C_tongue02_CTL.rotateZ',-10,10)]}
    for side in ('L','R'):
        specs[side+'_arm']=[(side+'_shoulderFk_CTL.rotateZ',0,60),(side+'_elbowFk_CTL.rotateY',0,70)]
        specs[side+'_leg']=[(side+'_hipFk_CTL.rotateZ',0,55),(side+'_kneeFk_CTL.rotateZ',0,70)]
        specs[side+'_clavicle']=[(side+'_clavicle_CTL.rotateZ',-10,15)]
        specs[side+'_fingers']=[(side+'_index01_CTL.rotateZ',0,35),(side+'_middle01_CTL.rotateZ',0,35)]
    selected={};missing={}
    for module,plugs in specs.items():
        if only_module and module!=only_module:continue
        valid=[(p,a,b) for p,a,b in plugs if cmds.objExists(p) and cmds.getAttr(p,settable=True)]
        if not valid:missing[module]=[p for p,_,_ in plugs]
        selected[module]=valid
    if missing:raise RuntimeError('No controllable audit channels: '+str(missing))
    import math
    cases=[('all_neutral',{p:0 for values in selected.values() for p,_,_ in values})]
    for step in range(8):
        values={}
        for index,(module,plugs) in enumerate(selected.items()):
            for j,(p,lo,hi) in enumerate(plugs):
                factor=(math.sin(2*math.pi*step/7+index*.37+j*.4)+1)*.5
                values[p]=lo+(hi-lo)*factor
        cases.append(('all_modules_%02d'%step,values))
    cases.append(('all_neutral_end',dict(cases[0][1])))
    return cases,selected

@contextmanager
def bypass_deformers(names):
    replacements={};originals={}
    for n in names:
        for index in cmds.getAttr(n+'.outputGeometry',multiIndices=True) or [0]:
            output='%s.outputGeometry[%d]'%(n,index)
            upstream=routing.source('%s.input[%d].inputGeometry'%(n,index))
            if not upstream:raise RuntimeError('Missing native deformer input: '+output)
            replacements[output]=upstream
    def upstream(plug):
        seen=set()
        while plug in replacements:
            if plug in seen:raise RuntimeError('Ablation dependency cycle')
            seen.add(plug);plug=replacements[plug]
        return plug
    try:
        cmds.evaluator(name='deformer',enable=False);cmds.evaluationManager(mode='off')
        for output in replacements:
            for destination in cmds.listConnections(output,s=False,d=True,p=True) or []:
                originals[destination]=routing.source(destination)
                routing.connect(upstream(output),destination)
        yield {'mechanism':'Native input-to-output routing; algorithms omitted without deleting weights or targets.','nodes':names,'routes':originals,'replacements':replacements}
    finally:
        cmds.evaluator(name='deformer',enable=False);cmds.evaluationManager(mode='off')
        for destination,original in originals.items():routing.connect(original,destination)

@contextmanager
def freeze_module(module):
    data=json.loads((FOLDER/'catalog.json').read_text());m=data['modules'][module]
    nodes=[n for n in m['exclusive_nodes'] if not n.endswith('_CTL') and 'Controllers_GRP' not in data['nodes'][n].get('path','')]
    prior={};skipped=[];enabled=cmds.evaluator(name='frozen',q=True,enable=True)
    def set_frozen(n,value):
        sl=om.MSelectionList();sl.add(n);om.MFnDependencyNode(sl.getDependNode(0)).findPlug('frozen',False).setBool(value)
    try:
        write('freeze_progress.json',{'module':module,'stage':'materialize_parallel_cpu','nodes':len(nodes)})
        cmds.evaluator(name='deformer',enable=False);cmds.evaluationManager(mode='parallel');cmds.refresh(force=True)
        cmds.evaluator(name='frozen',enable=True)
        for index,n in enumerate(nodes):
            if index%100==0:write('freeze_progress.json',{'module':module,'stage':'set_frozen','index':index,'nodes':len(nodes)})
            if not cmds.getAttr(n+'.frozen',settable=True):skipped.append(n);continue
            prior[n]=cmds.getAttr(n+'.frozen');set_frozen(n,True)
        yield {'mechanism':'Native frozen attribute on exclusive computation nodes; input controls stay animated.','module':module,'frozen_nodes':list(prior),'skipped':skipped,'shared_nodes_kept':m['shared_nodes']}
    finally:
        cmds.evaluator(name='deformer',enable=False);cmds.evaluationManager(mode='off')
        for n,value in prior.items():set_frozen(n,value)
        cmds.evaluator(name='frozen',enable=enabled)

def measure(label,intervention=None,module_workload=None,variant='original',wrinkles=False,state='C',reload_scene=True):
    if reload_scene:routing.load(variant)
    routing.wrinkle(wrinkles,variant)
    cases,channels=audit_cases(module_workload)
    output=FOLDER/(label+'.performance.json')
    from contextlib import nullcontext
    context=nullcontext({'mechanism':'Reference with all normal deformation'})
    if intervention:
        if intervention['kind']=='module':context=freeze_module(intervention['module'])
        elif intervention['kind']=='deformers':context=bypass_deformers(intervention['nodes'])
        else:raise ValueError(intervention)
    initial_memory=memory()
    with context as changed:
        report=rb.run_state('Edward',output,state=state,cases=cases,frames=(1,48),repeats=3,allow_unsaved=True)
        report['audit']={'label':label,'variant':variant,'wrinkles':wrinkles,'intervention':changed,'channels_by_module':channels,'module_workload':module_workload,'pid':__import__('os').getpid(),'memory_before':initial_memory,'memory_after':memory(),'meaning':'Marginal scene cost under this workload; parallel and downstream effects make component deltas non-additive. Disabled systems are diagnostic ablations, not equivalent full-quality optimizations.'}
        output.write_text(json.dumps(report,indent=2))
    return {'label':label,'timing':report['timing'],'runs':[r['median_ms'] for r in report['runs']],'changed_nodes':len(changed.get('nodes',changed.get('frozen_nodes',[])))}

def component_scenarios():
    d=json.loads((FOLDER/'catalog.json').read_text())
    high=[s['name'] for s in d['skins'] if any('|cabeza_high|' in g['shape'] for g in s['geometry'])]
    low=[s['name'] for s in d['skins'] if any('|cabeza_low|' in g['shape'] for g in s['geometry'])]
    skins=[s['name'] for s in d['skins']]
    correctives=[s['name'] for s in d['blendShapes'] if 'poseCorrectives' in s['name']]
    eyelid=[s['name'] for s in d['blendShapes'] if 'poseCorrectives' not in s['name']]
    rows=[('reference_start',None),('all_skinning',{'kind':'deformers','nodes':skins}),('all_facial_high_skinning',{'kind':'deformers','nodes':high}),('all_facial_low_skinning',{'kind':'deformers','nodes':low}),('all_PRX',{'kind':'deformers','nodes':list(d['prx'])}),('all_correctives',{'kind':'deformers','nodes':correctives}),('eyelid_curve_blendShapes',{'kind':'deformers','nodes':eyelid})]
    rows += [('skin_'+n,{'kind':'deformers','nodes':[n]}) for n in high+low]
    rows += [('module_'+n,{'kind':'module','module':n}) for n in d['modules']]
    rows += [('prx_'+n,{'kind':'deformers','nodes':[n]}) for n in d['prx']]
    result=[]
    for i,row in enumerate(rows):
        if i and i%8==0:result.append(('reference_%02d'%i,None))
        result.append(row)
    result.append(('reference_end',None))
    return result

def batch_components(labels=None):
    from contextlib import nullcontext
    routing.load('original');routing.wrinkle(False,'original')
    cases,channels=audit_cases();resolved,missing,_=qa.resolve_cases('Edward',cases)
    if missing:raise RuntimeError(missing)
    initial={p:cmds.getAttr(p) for p in resolved[0]['values']}
    scenarios=[r for r in component_scenarios() if labels is None or r[0] in labels]
    environment=rb.environment('Edward');reports=[];begin=time.perf_counter()
    with rb.evaluation_session(),pb._temporary_values(initial):
        cmds.evaluationManager(mode='parallel');cmds.evaluator(name='cache',enable=False);cmds.evaluator(name='deformer',enable=False)
        with rb.temporal_workload(resolved,(1,48)):
            write('batch_progress.json',{'stage':'native_animation_preparation','scenarios':len(scenarios)})
            cmds.currentTime(1);cmds.refresh(force=True)
            animation_preparation=time.perf_counter()-begin
            for index,(label,intervention) in enumerate(scenarios):
                output=FOLDER/('component_'+label+'.performance.json')
                if output.exists():continue
                write('batch_progress.json',{'stage':'prepare_scenario','scenario':label,'index':index+1,'total':len(scenarios)})
                context=nullcontext({'mechanism':'Normal reference'})
                if intervention and intervention['kind']=='module':context=freeze_module(intervention['module'])
                elif intervention:context=bypass_deformers(intervention['nodes'])
                with context as changed:
                    cmds.evaluationManager(mode='parallel');cmds.evaluator(name='deformer',enable=False)
                    cmds.currentTime(1);cmds.refresh(force=True)
                    cmds.evaluator(name='deformer',enable=True)
                    start=time.perf_counter();rb._play_once((1,48));warmup=time.perf_counter()-start
                    runs=[]
                    for repeat in range(3):
                        write('batch_progress.json',{'stage':'timing','scenario':label,'pass':repeat+1,'index':index+1,'total':len(scenarios)})
                        runs.append(rb._play_once((1,48))[8:])
                    report={'format':'edward-component-audit','label':label,'state':'C','wrinkles':False,'environment':environment,'audit':{'intervention':changed,'channels_by_module':channels,'pid':__import__('os').getpid(),'marginal_non_additive':True},'frames':[1,48],'warmup_frames':8,'repeats':3,'measurement':'currentTime plus forced VP2 refresh; 3 measured passes after a complete warm-up; no geometry extraction or Profiler within samples','raw_runs_ms':runs,'runs':[rb.statistics_ms(r) for r in runs],'timing':rb.statistics_ms([s for r in runs for s in r]),'warmup_seconds':warmup,'one_time_animation_preparation_seconds':animation_preparation,'diagnostics':rb.diagnostics(),'memory':memory()}
                    output.write_text(json.dumps(report,indent=2));reports.append({'label':label,'timing':report['timing']})
    write('batch_progress.json',{'complete':True,'reports':len(reports),'seconds':time.perf_counter()-begin})
    return reports

args=globals().get('TRIAL_ARGUMENTS',{})
if args.get('action')=='catalog':result=catalog()
elif args.get('action')=='storage':result=storage()
elif args.get('action')=='measure':result=measure(**{k:v for k,v in args.items() if k!='action'})
elif args.get('action')=='workload':
    cases,channels=audit_cases();result={'cases':cases,'channels':channels};write('workload.json',result)
elif args.get('action')=='batch_components':result=batch_components(args.get('labels'))
