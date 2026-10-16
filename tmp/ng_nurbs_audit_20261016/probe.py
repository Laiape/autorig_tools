"""Disposable Maya/NG capability probes. Never run in an artist session."""
import json
from pathlib import Path
import sys
import traceback

import maya.standalone
maya.standalone.initialize(name="python")
from maya import cmds
from maya.api import OpenMaya as om, OpenMayaAnim as oma

NG = Path("C:/ProgramData/Autodesk/ApplicationPlugins/ngskintools2/Contents")
sys.path.insert(0, str(NG / "scripts"))
cmds.loadPlugin(str(NG / "plug-ins/2026/ngSkinTools2.mll"), quiet=True)
from ngSkinTools2 import api
from ngSkinTools2.api import target_info

result = {"maya": cmds.about(version=True), "ng": cmds.pluginInfo("ngSkinTools2", q=True, version=True), "cases": []}

def dag(name):
    return om.MSelectionList().add(name).getDagPath(0)

def skinfn(name):
    return oma.MFnSkinCluster(om.MSelectionList().add(name).getDependNode(0))

def attempt(fn):
    try:
        return {"ok": True, "value": fn()}
    except Exception as error:
        return {"ok": False, "error": str(error)}

def weights(skin, shape, comp):
    values, count = skinfn(skin).getWeights(dag(shape), comp)
    return list(values), count

for kind in ("open", "closed_u", "periodic_v", "periodic_uv"):
    try:
        cmds.file(new=True, force=True)
        cmds.select(clear=True)
        j0 = cmds.joint(name="influenceA", position=(-2, 0, 0))
        cmds.select(clear=True)
        j1 = cmds.joint(name="influenceB", position=(2, 0, 0))
        if kind == "open":
            surface = cmds.nurbsPlane(name="auditSurface", patchesU=2, patchesV=4, degree=3, constructionHistory=False)[0]
        elif kind == "closed_u":
            surface = cmds.createNode("transform", name="auditSurface")
            parent = om.MSelectionList().add(surface).getDependNode(0)
            closed_points = [om.MPoint(x, v, z) for x,z in [(1,0), (0,1), (-1,0), (0,-1), (1,0)] for v in range(3)]
            om.MFnNurbsSurface().create(closed_points, [0,1,2,3,4], [0,1,2], 1, 1, om.MFnNurbsSurface.kClosed, om.MFnNurbsSurface.kOpen, False, parent)
        elif kind == "periodic_v":
            surface = cmds.cylinder(name="auditSurface", sections=8, spans=3, constructionHistory=False)[0]
        else:
            surface = cmds.torus(name="auditSurface", sections=8, spans=6, constructionHistory=False)[0]
        shape = cmds.listRelatives(surface, shapes=True, noIntermediate=True, fullPath=True)[0]
        n = om.MFnNurbsSurface(dag(shape))
        nu, nv = n.numCVsInU, n.numCVsInV
        skin = cmds.skinCluster([j0, j1], surface, toSelectedBones=True, normalizeWeights=1)[0]
        compfn = om.MFnDoubleIndexedComponent()
        comp = compfn.create(om.MFn.kSurfaceCVComponent)
        compfn.addElements([(u, v) for u in range(nu) for v in range(nv)])
        count = nu * nv
        seeded = [w for i in range(count) for w in ((i+1.0)/(count+1), 1-(i+1.0)/(count+1))]
        skinfn(skin).setWeights(dag(shape), comp, om.MIntArray([0, 1]), om.MDoubleArray(seeded), False)
        read, _ = weights(skin, shape, comp)
        it = om.MItSurfaceCV(dag(shape), om.MObject.kNullObj, True)
        index_rows = []
        while not it.isDone():
            while not it.isRowDone():
                u, v = it.uvIndices()
                index_rows.append([u, v, it.index()])
                it.next()
            it.nextRow()
        # MItGeometry traverses deformer membership, rather than display CVs.
        geo = om.MItGeometry(dag(shape))
        members = []
        while not geo.isDone():
            members.append(geo.index())
            geo.next()
        del it, geo
        case = {"kind": kind, "nu": nu, "nv": nv, "forms": [n.formInU, n.formInV],
                "requested_closed_form_retained": n.formInU == om.MFnNurbsSurface.kClosed if kind == "closed_u" else None,
                "degrees": [n.degreeInU, n.degreeInV], "grid_count": count,
                "index_rows": index_rows, "membership": members,
                "weight_array_length": len(read), "input_component_elements": list(compfn.getElements()),
                "weightList_indices": cmds.getAttr(skin+".weightList", multiIndices=True),
                "nonzero_weight_array_rows": [i for i in range(len(read)//2) if any(read[i*2:i*2+2])],
                "ng_target_transform": attempt(lambda: target_info.get_related_skin_cluster(surface)),
                "ng_target_shape": attempt(lambda: target_info.get_related_skin_cluster(shape)),
                "ng_target_skin": attempt(lambda: target_info.get_related_skin_cluster(skin)),
                "ng_init_surface": attempt(lambda: str(api.init_layers(skin).data_node))}
        result["cases"].append(case)
        def probe_nurbs_layer():
            layer = api.Layers(skin).add("NURBS audit base")
            influences = target_info.list_influences(skin)
            initial = layer.get_weights(influences[0].logicalIndex)
            write = attempt(lambda: layer.set_weights(influences[0].logicalIndex, [0.25]*count))
            return {"layer": layer.id, "initial_weights_count": len(initial), "set_weights": write}
        case["ng_nurbs_layer"] = attempt(probe_nurbs_layer)
        node = target_info.get_related_data_node(skin)
        if node:
            cmds.delete(node)
        if kind != "open":
            del n
            Path(__file__).with_name("probe.json").write_text(json.dumps(result, indent=2), encoding="ascii")
            continue
        points = n.cvPositions(om.MSpace.kObject)
        del n
        counts, connects = [], []
        for u in range(nu-1):
            for v in range(nv-1):
                counts.append(4)
                connects.extend([u*nv+v, (u+1)*nv+v, (u+1)*nv+v+1, u*nv+v+1])
        mesh = cmds.createNode("transform", name="auditProxy")
        parent = om.MSelectionList().add(mesh).getDependNode(0)
        mesh_obj = om.MFnMesh().create(points, counts, connects, parent=parent)
        mesh_shape = om.MFnDagNode(mesh_obj).fullPathName()
        mesh = cmds.listRelatives(mesh_shape, parent=True, fullPath=True)[0]
        proxy_skin = cmds.skinCluster([j0, j1], mesh, toSelectedBones=True, normalizeWeights=1)[0]
        mf = om.MFnSingleIndexedComponent()
        mc = mf.create(om.MFn.kMeshVertComponent)
        mf.addElements(list(range(count)))
        skinfn(proxy_skin).setWeights(dag(mesh_shape), mc, om.MIntArray([0, 1]), om.MDoubleArray(seeded), False)
        ng = api.init_layers(proxy_skin)
        layer = ng.add("Audit base")
        case["proxy_init"] = {"skin": proxy_skin, "data": ng.data_node, "layer": layer.id}
        link = attempt(lambda: cmds.connectAttr(proxy_skin+".weightList", skin+".weightList"))
        case["parent_weightList_connection"] = link
        if not link["ok"]:
            case["row_connections"] = attempt(lambda: [cmds.connectAttr(proxy_skin+".weightList[%d].weights"%i, skin+".weightList[%d].weights"%i) for i in range(count)])
        before, _ = weights(skin, shape, comp)
        cmds.flushUndo()
        cmds.undoInfo(state=True)
        logical = target_info.list_influences(proxy_skin)[0].logicalIndex
        layer.set_weights(logical, [0.25]*count)
        source, _ = weights(proxy_skin, mesh_shape, mc)
        after, _ = weights(skin, shape, comp)
        case["ng_edit_transfer"] = {"max_delta_from_proxy": max(abs(a-b) for a,b in zip(after,source)), "before_first": before[:4], "after_first": after[:4], "source_first": source[:4], "undo_name": cmds.undoInfo(q=True, undoName=True)}
        cmds.undo()
        undone, _ = weights(skin, shape, comp)
        case["undo_transfer_error"] = max(abs(a-b) for a,b in zip(before,undone))
        cmds.redo()
        redone, _ = weights(skin, shape, comp)
        case["redo_transfer_error"] = max(abs(a-b) for a,b in zip(after,redone))
        cmds.setAttr(j1+".translateY", 2.0)
        live_cvs = om.MFnNurbsSurface(dag(shape)).cvPositions(om.MSpace.kWorld)
        cmds.disconnectAttr(proxy_skin+".weightList", skin+".weightList")
        skinfn(skin).setWeights(dag(shape), comp, om.MIntArray([0,1]), om.MDoubleArray(source), False)
        reference_cvs = om.MFnNurbsSurface(dag(shape)).cvPositions(om.MSpace.kWorld)
        case["open_linear_pose_cv_error"] = max((a-b).length() for a,b in zip(live_cvs,reference_cvs))
        cmds.connectAttr(proxy_skin+".weightList", skin+".weightList")
        scene = str(Path(__file__).with_name("native_link_probe.ma"))
        cmds.file(rename=scene)
        cmds.file(save=True, type="mayaAscii")
        cmds.file(scene, open=True, force=True)
        reopened, _ = weights(skin, shape, comp)
        case["reopen_transfer_error"] = max(abs(a-b) for a,b in zip(after,reopened))
        Path(__file__).with_name("probe.json").write_text(json.dumps(result, indent=2), encoding="ascii")
    except Exception:
        result["cases"].append({"kind": kind, "traceback": traceback.format_exc()})

Path(__file__).with_name("probe.json").write_text(json.dumps(result, indent=2), encoding="ascii")
print(json.dumps(result, default=str))
maya.standalone.uninitialize()
