"""Run with mayapy: verify spherical iris skinning before a body skinCluster."""
import ast
import math
import os
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("MAYA_SKIP_USERSETUP_PY", "1")
import maya.standalone
from maya import cmds
from maya.api import OpenMaya as om


def run():
    maya.standalone.initialize(name="python")
    try:
        source = Path(__file__).resolve().parents[2] / "biped/autorig/eyelid_module.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        method = next(node for node in ast.walk(tree)
                      if isinstance(node, ast.FunctionDef) and node.name == "create_iris_setup")
        scope = {"cmds": cmds, "om": om, "math": math,
                 "curve_tool": SimpleNamespace(lock_attributes=lambda *args: None),
                 "data_manager": SimpleNamespace(DataExportBiped=lambda: SimpleNamespace(
                     append_data=lambda *args: None))}
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), "exec"), scope)
        build = scope["create_iris_setup"]
        hierarchy_source = source.parents[2] / "utils/rig_manager.py"
        hierarchy_tree = ast.parse(hierarchy_source.read_text(encoding="utf-8"))
        hierarchy_functions = [node for node in hierarchy_tree.body
                               if isinstance(node, ast.FunctionDef)
                               and node.name in {"skeleton_hierarchy", "parented_chain"}]
        exec(compile(ast.Module(body=hierarchy_functions, type_ignores=[]),
                     str(hierarchy_source), "exec"), scope)
        for side, x in (("L", 3), ("R", -3)):
            cmds.file(new=True, force=True)
            cmds.createNode("transform", name="rig_GRP")
            skel_grp = cmds.createNode("transform", name="skel_GRP", p="rig_GRP")
            root = cmds.createNode("transform", name="bodyRoot")
            guide = cmds.createNode("transform")
            cmds.setAttr(guide + ".translate", x, 5, 2)
            cmds.setAttr(guide + ".rotate", 12, -20, 7)
            rest = cmds.xform(guide, q=True, ws=True, m=True)
            cmds.delete(guide)
            ctl = cmds.createNode("transform", name=side + "_eyeDirect_CTL", p=root)
            module = SimpleNamespace(side=side, eye_direct_ctl=ctl,
                                     eye_guide_matrix=rest, module_trn=root, skel_grp=skel_grp)
            fractions = (0.1, 0.2, 0.3, 0.4, 0.5)
            for invalid in ((), (0, 0.3), (0.5, 0.2), (0.2, 0.2), (float("nan"),), (1,)):
                try:
                    build(module, radius=2, ring_radii=invalid)
                except ValueError:
                    pass
                else:
                    raise AssertionError(f"Accepted invalid iris radii: {invalid}")
            module.linear_upper_curve = cmds.curve(d=1, p=[(x + 2, 5, 2), (x, 7, 2)])
            module.linear_lower_curve = cmds.curve(d=1, p=[(x - 2, 5, 2), (x, 3, 2)])
            joints = build(module, radius=2 if side == "L" else None, ring_radii=fractions)
            assert len(joints) == 6
            scope["skeleton_hierarchy"]()
            export_base = f"{side}_irisBase_ENV"
            assert cmds.listRelatives(export_base, p=True) == ["C_freeze_ENV"]
            export_rings = [f"{side}_iris{i:02d}_ENV" for i in range(5)]
            assert set(cmds.listRelatives(export_base, children=True, type="joint")) == set(export_rings)
            for joint, fraction in zip(module.iris_jnts, fractions):
                assert math.isclose(cmds.getAttr(joint + ".scaleX"), 1)
                assert math.isclose(cmds.getAttr(joint + ".translateZ"),
                                    2 * math.sqrt(1 - fraction**2), abs_tol=1e-6)

            # Five circular loops with exact weights, plus an unaffected rear loop.
            points = []
            for fraction in fractions + (0.7,):
                z = 2 * math.sqrt(1 - fraction**2)
                if fraction == 0.7:
                    z = -z
                for i in range(8):
                    a = i * math.tau / 8
                    points.append(om.MPoint(2 * fraction * math.cos(a),
                                           2 * fraction * math.sin(a), z) * om.MMatrix(rest))
            faces = []
            for row in range(5):
                for i in range(8):
                    j = (i + 1) % 8
                    faces.extend((row * 8 + i, row * 8 + j,
                                  (row + 1) * 8 + j, (row + 1) * 8 + i))
            mesh_fn = om.MFnMesh()
            mesh_fn.create(points, [4] * 40, faces)
            mesh = cmds.listRelatives(mesh_fn.fullPathName(), p=True, fullPath=True)[0]
            iris_skin = cmds.skinCluster([export_base] + export_rings, mesh, tsb=True, skinMethod=0)[0]
            for row in range(6):
                driver = export_rings[row] if row < 5 else export_base
                cmds.skinPercent(iris_skin, f"{mesh}.vtx[{row * 8}:{row * 8 + 7}]",
                                 transformValue=[(driver, 1)], zeroRemainingInfluences=True)
            body = cmds.createNode("joint", name="eyeBodySkinning_JNT", p=root)
            body_skin = cmds.skinCluster(body, mesh, tsb=True, multi=True, skinMethod=0)[0]
            cmds.skinPercent(body_skin, mesh, transformValue=[(body, 1)])
            cmds.setAttr(root + ".translate", 4, -2, 6)
            cmds.setAttr(root + ".rotate", -10, 35, 22)
            cmds.setAttr(root + ".scale", 1.5, 1.5, 1.5)
            body_inverse = om.MMatrix(cmds.getAttr(body + ".worldMatrix[0]")).inverse()
            rest_inverse = om.MMatrix(rest).inverse()
            for value in (1, 0.1, 0.5, 1.5, 1.998):
                cmds.setAttr(ctl + ".Iris_Scale", value)
                for original, exported in zip(joints, [export_base] + export_rings):
                    assert all(math.isclose(a, b, abs_tol=1e-5) for a, b in zip(
                        cmds.getAttr(original + ".worldMatrix[0]"),
                        cmds.getAttr(exported + ".worldMatrix[0]")))
                selection = om.MSelectionList()
                selection.add(mesh)
                dag = selection.getDagPath(0)
                dag.extendToShape()
                result = om.MFnMesh(dag).getPoints(om.MSpace.kWorld)
                for row, fraction in enumerate(fractions):
                    for point in result[row * 8:row * 8 + 8]:
                        local = point * body_inverse * rest_inverse
                        assert math.isclose(math.hypot(local.x, local.y), 2 * fraction * value, abs_tol=1e-5)
                        assert math.isclose(om.MVector(local.x, local.y, local.z).length(), 2, abs_tol=1e-5)
                for i in range(40, 48):
                    actual = result[i] * body_inverse
                    assert (actual - points[i]).length() < 1e-5
            assert cmds.listConnections(module.iris_grp + ".offsetParentMatrix", s=True, d=False) is None
            print(f"PASS {side}: skeleton hierarchy, sibling rings, ENV skinning, radius, contraction/expansion, stacked body skin and global scale")
    finally:
        maya.standalone.uninitialize()


if __name__ == "__main__":
    run()
