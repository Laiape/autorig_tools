"""Run with mayapy: independent spine/chest guide anchors and persistence."""
import math
import os
from pathlib import Path
import tempfile

os.environ.setdefault("MAYA_SKIP_USERSETUP_PY", "1")
import maya.standalone
from maya import cmds

from test_biped_spine_and_foot import load_spine, check_spine


def position(node):
    return cmds.xform(node, q=True, ws=True, t=True)


def close(actual, expected):
    assert max(abs(a-b) for a,b in zip(actual, expected)) < 1e-4, (actual, expected)


def run():
    maya.standalone.initialize(name="python")
    try:
        cmds.loadPlugin("matrixNodes", quiet=True)
        cmds.loadPlugin("lookdevKit", quiet=True)
        # Existing count/curve-driver coverage also checks Edward's distinct anchors.
        for count in (3, 4, 5, 7, 10):
            check_spine(count, 8)
        snapshots=[]
        for iteration in range(2):
            cmds.file(new=True, force=True)
            cmds.optionVar(sv=("currentAssetRigName", "Girl"))
            cls=load_spine(character="Girl", guide_version="007")
            rig=cls.__new__(cls)
            rig.modules=cmds.createNode("transform", name="modules")
            rig.skel_grp=cmds.createNode("transform", name="skeleton")
            rig.masterwalk_ctl=cmds.createNode("transform", name="masterwalk")
            cmds.addAttr(rig.masterwalk_ctl, ln="globalScale", at="double", dv=1, k=True)
            for axis in "XYZ":
                cmds.connectAttr(rig.masterwalk_ctl+".globalScale",rig.masterwalk_ctl+".scale"+axis)
            rig.make("C",8,5)
            end=rig.spine_end_guide_matrix[12:15]
            chest=rig.chest_guide_matrix[12:15]
            assert math.dist(end,chest)>1, (end,chest)
            for follow in (0,1):
                cmds.setAttr(rig.spine_ctls[-1]+".follow",follow)
                for scale in (0.5,1,2):
                    cmds.setAttr(rig.masterwalk_ctl+".globalScale",scale)
                    close(position(rig.spine_ctls[-1]),[v*scale for v in end])
                    close(position(rig.spine_chain[-1]),[v*scale for v in end])
                    close(position(rig.local_chest_ctl),[v*scale for v in chest])
            cmds.setAttr(rig.masterwalk_ctl+".globalScale",1)
            cmds.setAttr(rig.spine_ctls[-1]+".follow",0)
            nodes=[rig.spine_ctls[-1],rig.spine_chain[-1],rig.local_chest_ctl]
            snapshot={n:cmds.getAttr(n+".worldMatrix[0]") for n in nodes}
            snapshots.append(snapshot)
            with tempfile.TemporaryDirectory(prefix="spine_guide_endpoints_") as directory:
                path=Path(directory)/"guide_endpoints.mb"
                cmds.file(rename=path.as_posix())
                cmds.file(save=True,type="mayaBinary",force=True)
                cmds.file(path.as_posix(),open=True,force=True,executeScriptNodes=False)
                for n,expected in snapshot.items():close(cmds.getAttr(n+".worldMatrix[0]"),expected)
            assert not (cmds.cycleCheck(all=True,list=True) or [])
        for n in snapshots[0]:close(snapshots[0][n],snapshots[1][n])
        print("PASS Girl: independent terminal-spine/chest anchors, Local/World, global scale, two builds and native reopen",flush=True)
    finally:
        maya.standalone.uninitialize()


if __name__=="__main__":
    run()
