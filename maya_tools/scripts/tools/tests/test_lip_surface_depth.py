"""Run with mayapy: depth attenuation must preserve neutral and full following."""
import os
import sys
import unittest

os.environ["MAYA_SKIP_USERSETUP_PY"] = "1"
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
import maya.standalone
maya.standalone.initialize(name="python")
import maya.cmds as cmds
from utils import lip_surface_depth


class SurfaceDepthTests(unittest.TestCase):
    def setUp(self):
        cmds.file(new=True, force=True)
        self.controller = cmds.createNode("transform", name="lip_CTL")
        self.raw = cmds.createNode("transform", name="raw")
        self.projected = cmds.createNode("transform", name="projected")
        self.target = cmds.createNode("transform", name="target")
        cmds.setAttr(self.raw + ".tz", 12)
        cmds.setAttr(self.projected + ".tz", 11)
        cmds.connectAttr(self.projected + ".tz", self.target + ".tz")
        lip_surface_depth.install(self.controller, self.raw + ".tz", self.projected + ".tz",
                                  [self.target + ".tz"])

    def test_neutral_and_depth_endpoints(self):
        self.assertAlmostEqual(cmds.getAttr(self.target + ".tz"), 11)
        # A tangential move projects 2 units backwards without a raw depth move.
        cmds.setAttr(self.projected + ".tz", 9)
        self.assertAlmostEqual(cmds.getAttr(self.target + ".tz"), 10)
        cmds.setAttr(self.controller + ".SurfaceDepthFollow", 1)
        self.assertAlmostEqual(cmds.getAttr(self.target + ".tz"), 9)
        cmds.setAttr(self.controller + ".SurfaceDepthFollow", 0)
        self.assertAlmostEqual(cmds.getAttr(self.target + ".tz"), 11)

    def test_explicit_forward_motion_and_retrofit_calibration(self):
        cmds.setAttr(self.raw + ".tz", 13)
        cmds.setAttr(self.projected + ".tz", 12)
        self.assertAlmostEqual(cmds.getAttr(self.target + ".tz"), 12)
        second = cmds.createNode("transform", name="posedLip_CTL")
        output = cmds.createNode("transform", name="posedOutput")
        cmds.setAttr(self.raw + ".tz", 12)
        cmds.setAttr(self.projected + ".tz", 9)
        cmds.connectAttr(self.projected + ".tz", output + ".tz")
        lip_surface_depth.install(second, self.raw + ".tz", self.projected + ".tz",
                                  [output + ".tz"], rest_offset=1)
        self.assertAlmostEqual(cmds.getAttr(output + ".tz"), 10)


if __name__ == "__main__":
    try:
        unittest.main(exit=False)
    finally:
        maya.standalone.uninitialize()
