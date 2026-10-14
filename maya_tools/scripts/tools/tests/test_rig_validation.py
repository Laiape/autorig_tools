"""Real Maya: report comparisons, evaluation consistency and state restoration."""
import os, sys, tempfile
from pathlib import Path
os.environ.setdefault("MAYA_SKIP_USERSETUP_PY", "1")
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
import maya.standalone
maya.standalone.initialize(name="python")
from maya import cmds
try:
    from maya_tools.scripts.tools import rig_validation as qa
    cmds.undoInfo(state=True)
    root = cmds.createNode("transform", name="Character")
    ctl = cmds.createNode("transform", name="L_shoulderFk_CTL", parent=root)
    joint = cmds.createNode("joint", parent=root)
    cmds.connectAttr(ctl + ".rotate", joint + ".rotate")
    mesh = cmds.polySphere(subdivisionsX=12, subdivisionsY=8)[0]
    cmds.parent(mesh, root)
    cmds.skinCluster(joint, mesh, toSelectedBones=True)
    for f,v in ((1, 10), (10, 20)):
        cmds.setKeyframe(ctl, attribute="rotateZ", time=f, value=v)
    cmds.currentTime(5)
    source = cmds.connectionInfo(ctl + ".rotateZ", sourceFromDestination=True)
    keys = cmds.keyframe(ctl, query=True, timeChange=True)
    value = cmds.getAttr(ctl + ".rotateZ")
    cmds.select(ctl)
    cmds.evaluationManager(mode="serial")
    cases = [("neutral", {}), ("combination", {"L_shoulderFk_CTL.rotateZ": 60, "L_shoulderFk_CTL.rotateX": 45}),
             ("missing", {"absent_CTL.rotateX": 30})]
    with tempfile.TemporaryDirectory() as directory:
        first = str(Path(directory) / "first.rigqa.json")
        second = str(Path(directory) / "second.rigqa.json")
        baseline = qa.run_report(root, [mesh], first, cases=cases, repeats=2, captures=False)
        report = qa.run_report(root, [mesh], second, baseline=first, cases=cases, repeats=2, captures=False)
        assert report["missing_channels"] == ["absent_CTL.rotateX"]
        assert len(report["poses"]) == 2
        assert all(c["max"] < 1e-6 for c in report["comparison"])
        assert all(e["max"] < 1e-5 for m in report["timings"].values() for e in m["geometry_difference"])
        assert cmds.connectionInfo(ctl + ".rotateZ", sourceFromDestination=True) == source
        assert cmds.keyframe(ctl, query=True, timeChange=True) == keys
        assert abs(cmds.getAttr(ctl + ".rotateZ") - value) < 1e-7
        assert cmds.currentTime(query=True) == 5
        assert cmds.evaluationManager(query=True, mode=True)[0] == "serial"
        assert cmds.ls(selection=True) == [ctl]
        # Geometry changes must appear in the report; topology changes are flagged.
        reference = report["poses"][0]["meshes"]
        shape_data = next(iter(reference.values()))
        shape_data["points"][0][0] += .25
        differences = qa.compare_reports(report, baseline)
        assert any(c.get("max", 0) >= .25 - 1e-7 for c in differences)
        shape_data["topology"] = "changed"
        assert qa.compare_reports(report, baseline)[0]["status"] == "topology_changed"
        try:
            qa.run_report(root, [mesh], first, cases=cases)
            raise AssertionError("Overwrite accepted")
        except ValueError:
            pass
        # A failure during evaluation must also restore animation and selection.
        original_mesh_data = qa.mesh_data
        qa.mesh_data = lambda mesh: (_ for _ in ()).throw(RuntimeError("injected evaluation failure"))
        try:
            qa.run_report(root, [mesh], str(Path(directory) / "failed.json"), cases=cases)
            raise AssertionError("Failure not propagated")
        except RuntimeError:
            pass
        finally:
            qa.mesh_data = original_mesh_data
        assert cmds.connectionInfo(ctl + ".rotateZ", sourceFromDestination=True) == source
        assert abs(cmds.getAttr(ctl + ".rotateZ") - value) < 1e-7
        assert cmds.evaluationManager(query=True, mode=True)[0] == "serial"
    print("PASS Rig QA: combined poses, missing controls, equal builds, geometric regression, topology guard, DG/Serial/Parallel, preserved animation/time/selection, failure restoration")
finally:
    maya.standalone.uninitialize()
