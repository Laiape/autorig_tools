"""Read a saved Edward scene in a separate Maya process, without saving it."""
import json
from collections import Counter
from pathlib import Path
import maya.standalone

maya.standalone.initialize(name="python")
from maya import cmds

scene = Path(r"C:\proyectos\auto-rig\maya_tools\assets\Edward\scenes\Edward_working_v001.mb")
output = Path(r"C:\proyectos\auto-rig\maya_tools\assets\Edward\validation\performance_static_20261014.json")
cmds.file(str(scene), open=True, force=True, prompt=False, executeScriptNodes=False)

def visible(node):
    for current in [node] + (cmds.listRelatives(node, allParents=True, fullPath=True) or []):
        if cmds.attributeQuery("visibility", node=current, exists=True) and not cmds.getAttr(current + ".visibility"):
            return False
    parent = cmds.listRelatives(node, parent=True, fullPath=True) or []
    return visible(parent[0]) if parent else True

nodes = cmds.ls() or []
types = Counter(cmds.nodeType(n) for n in nodes)
meshes = []
for mesh in cmds.ls(type="mesh", noIntermediate=True, long=True) or []:
    history = cmds.listHistory(mesh, pruneDagObjects=True) or []
    filters = [n for n in history if "geometryFilter" in cmds.nodeType(n, inherited=True)]
    meshes.append({"mesh": mesh, "vertices": cmds.polyEvaluate(mesh, vertex=True),
                   "visible": visible(mesh), "deformers": [{"node": n, "type": cmds.nodeType(n)} for n in filters],
                   "outMesh_consumers": cmds.listConnections(mesh + ".outMesh", source=False, destination=True, plugs=True) or [],
                   "worldMesh_consumers": cmds.listConnections(mesh + ".worldMesh", source=False, destination=True, plugs=True) or []})
graphs = []
for graph in cmds.ls(type="bifrostGraphShape") or []:
    item = {"graph": graph, "input": cmds.listConnections(graph + ".AnimatedFace", source=True, destination=False, plugs=True) or [],
            "outputs": cmds.listConnections(graph + ".WrinkledFace", source=False, destination=True, plugs=True) or []}
    try:
        internal = cmds.vnnCompound(graph, "/", listNodes=True) or []
        item["internal_nodes"] = internal
        item["internal_node_count"] = len(internal)
    except Exception as exc:
        item["graph_query_error"] = str(exc)
    graphs.append(item)
settings = []
for node in cmds.ls("*_Settings", type="transform") or []:
    if cmds.attributeQuery("sourceMesh", node=node, exists=True):
        settings.append({"node":node, "values": {a:cmds.getAttr(node + "." + a) for a in ["Envelope", "Depth", "CompressionStart", "CompressionRange", "ManualActivation"] if cmds.attributeQuery(a, node=node, exists=True)}})
skins = [{"skin": n, "influences":len(cmds.skinCluster(n, query=True, influence=True) or []),
          "geometry":cmds.skinCluster(n, query=True, geometry=True) or [],
          "method":cmds.getAttr(n + ".skinningMethod"), "maxInfluences":cmds.getAttr(n + ".maxInfluences"),
          "maintainMaxInfluences":cmds.getAttr(n + ".maintainMaxInfluences")} for n in cmds.ls(type="skinCluster") or []]
report={"scope":"Static inventory in standalone Maya; no interactive timing or GPU residency measurement.",
        "scene":str(scene), "maya":cmds.about(version=True), "api":cmds.about(apiVersion=True),
        "nodes":len(nodes), "node_types":dict(types), "meshes":meshes, "bifrost":graphs,
        "wrinkle_settings":settings, "skins":skins, "unknown_plugins":cmds.unknownPlugin(query=True,list=True) or [],
        "detail_roots":[n for n in cmds.ls(type="transform") or [] if cmds.attributeQuery("detailMode",node=n,exists=True)],
        "script_jobs":cmds.scriptJob(listJobs=True) or []}
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(report, indent=2), encoding="ascii")
print("AUDIT_SAVED", str(output))
maya.standalone.uninitialize()
