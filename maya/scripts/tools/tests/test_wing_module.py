"""
Check headless del wing module: mayapy scripts/tools/tests/test_wing_module.py

Monta tres cadenas en abanico, construye el módulo y verifica que los joints
de skinning quedan clavados a la surface (en reposo y posada) y que el control
de membrana empuja su zona con falloff. No toca el cache real del repo.
"""
import os
import sys
import tempfile

import maya.standalone
maya.standalone.initialize()

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ""))

from maya import cmds
import maya.api.OpenMaya as om

from maya.scripts.utils import data_manager

# cache falso: no pisar cache/biped.cache
_fake_cache = os.path.join(tempfile.mkdtemp(), "biped.cache")
data_manager.DataExportBiped.__init__ = lambda self: setattr(self, "build_path", _fake_cache)
data_manager.DataExportBiped().new_build()

# basic structure falsa
rig = cmds.createNode("transform", name="rig_GRP")
modules = cmds.createNode("transform", name="modules_GRP", parent=rig)
skel = cmds.createNode("transform", name="skel_GRP", parent=rig)
masterwalk = cmds.circle(name="masterwalk_CTL", ch=False)[0]
cmds.parent(masterwalk, rig)
data_manager.DataExportBiped().append_data("basic_structure", {
    "modules_GRP": modules, "skel_GRP": skel, "masterwalk_ctl": masterwalk})


def chain(name, positions):
    cmds.select(clear=True)
    joints = []
    for i, pos in enumerate(positions):
        joints.append(cmds.joint(name=f"{name}0{i}_JNT", position=pos))
    return joints


lead = chain("L_wingArm", [(0, 0, 0), (4, 0, 0), (8, 0, 0), (12, 0, 0), (16, 0, 0)])
mid = chain("L_wingFingerA", [(0, 0, -1), (4, 0, -3), (8, 0, -5), (12, 0, -7), (16, 0, -9)])
trail = chain("L_wingFingerB", [(0, 0, -2), (3, 0, -6), (6, 0, -10), (9, 0, -14)])

from maya.scripts.biped.autorig import wing_module  # su reload(curve_tool) va antes del parche
from maya.scripts.utils import curve_tool
curve_tool.build_curves_from_template = lambda name: None  # sin personaje: cae al circle

module = wing_module.WingModule()
module.make("L", [lead, mid, trail], controls_per_gap=1)

surface_shape = cmds.listRelatives(module.surface, shapes=True, noIntermediate=True)[0]

# closestPoint de la API es impreciso (~0.02) junto a los pliegues de grado 1;
# comparamos contra pointOnSurface en la UV propia de cada pin: exacto y además
# verifica que el joint está en SU parámetro, no en cualquier punto
max_u = cmds.getAttr(f"{surface_shape}.maxValueU")
max_v = cmds.getAttr(f"{surface_shape}.maxValueV")


def max_distance_to_surface(joints):
    worst = 0.0
    for i, joint in enumerate(joints):
        pos = om.MPoint(cmds.xform(joint, q=True, ws=True, t=True))
        u, v = cmds.getAttr(f"{module.uv_pin}.coordinate[{i}]")[0]
        expected = om.MPoint(cmds.pointOnSurface(surface_shape, u=u * max_u, v=v * max_v, position=True))
        worst = max(worst, pos.distanceTo(expected))
    return worst


# 1. conteo: across=5, along=10 -> 50 joints, 2 controles (1 por hueco)
assert len(module.skinning_joints) == 50, len(module.skinning_joints)
assert len(module.membrane_ctls) == 2, module.membrane_ctls

# 2. en reposo, todos los joints sobre la surface
rest = max_distance_to_surface(module.skinning_joints)
assert rest < 1e-4, rest
print(f"PASS reposo: 50 joints sobre la surface (max dist {rest:.2e})")

# 3. posar un dedo: la surface deforma y los joints la siguen
before = {j: cmds.xform(j, q=True, ws=True, t=True) for j in module.skinning_joints}
cmds.setAttr(f"{mid[1]}.rotateY", 35)
posed = max_distance_to_surface(module.skinning_joints)
assert posed < 1e-4, posed
moved = [j for j, pos in before.items()
         if (om.MVector(cmds.xform(j, q=True, ws=True, t=True)) - om.MVector(pos)).length() > 0.1]
assert len(moved) > 10, len(moved)
print(f"PASS pose: {len(moved)} joints siguen la surface deformada (max dist {posed:.2e})")
cmds.setAttr(f"{mid[1]}.rotateY", 0)

# 4. control de membrana: su ajuste deforma la zona con falloff
ctl = module.membrane_ctls[0]
before = {j: cmds.xform(j, q=True, ws=True, t=True) for j in module.skinning_joints}
cmds.setAttr(f"{ctl}.translateY", 3)
deltas = sorted((om.MVector(cmds.xform(j, q=True, ws=True, t=True)) - om.MVector(pos)).length()
                for j, pos in before.items())
assert deltas[-1] > 1.0, deltas[-1]      # la zona del control se mueve de verdad
assert deltas[0] < 0.2, deltas[0]        # lejos del control apenas se mueve (falloff)
on_surface = max_distance_to_surface(module.skinning_joints)
assert on_surface < 1e-4, on_surface
print(f"PASS control membrana: empuje max {deltas[-1]:.2f}, min {deltas[0]:.2f}, joints sobre surface (max dist {on_surface:.2e})")

print("TODO OK")
maya.standalone.uninitialize()
