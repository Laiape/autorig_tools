import maya.cmds as cmds
from importlib import reload

from maya.scripts.utils import data_manager
from maya.scripts.utils import curve_tool
from maya.scripts.utils import surface_pin

reload(curve_tool)
reload(surface_pin)


class WingModule(object):

    """
    Membrana de ala driveada por una NURBS surface.

    Dos capas, sin ciclo:
      1. Drivers -> surface: se loftea una NURBS entre las cadenas del ala
         (brazo + dedos, ya construidas por sus módulos) y se skinnea a esas
         cadenas MÁS los joints de los controles de membrana. Un control de
         membrana deforma la surface con el falloff del skinCluster, así que
         su ajuste se reparte suave por la zona en vez de arrastrar en rígido
         a los joints siguientes (que era el arreglo por cadena de
         multMatrix/inverseMatrix del módulo de referencia).
      2. Surface -> skinning joints: un único uvPin proyecta la rejilla de
         joints de skinning sobre la surface por offsetParentMatrix.

    Los controles siguen al esqueleto por un blendMatrix al 50% entre los dos
    joints de cadena que flanquean su hueco (entrada = cadenas, salida =
    surface: sin dependencia circular con la surface que deforman).
    """

    def __init__(self):

        self.modules = data_manager.DataExportBiped().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExportBiped().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExportBiped().get_data("basic_structure", "masterwalk_ctl")

    def make(self, side, chains, joints_along=None, joints_across=None, controls_per_gap=3):

        """
        Create the wing membrane module from already-built driver chains.

        Args:
            side (str): 'L' or 'R'.
            chains (list[list[str]]): driver joint chains root->tip, ordered
                across the wing (leading edge first, trailing edge last).
            joints_along (int): skinning joints along each chain (V). Default
                2x the longest chain.
            joints_across (int): skinning joint rows across the chains (U).
                Default one row per chain plus one per gap.
            controls_per_gap (int): membrane controls between each pair of
                adjacent chains.
        """

        self.side = side
        self.chains = chains

        self.module_trn = cmds.createNode("transform", name=f"{self.side}_wingModule_GRP", ss=True, p=self.modules)
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.side}_wingSkinning_GRP", ss=True, p=self.skel_grp)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.side}_wingControllers_GRP", ss=True, p=self.masterwalk_ctl)

        self.surface_setup()
        self.membrane_controls(controls_per_gap)
        self.skin_setup()
        self.projection_setup(joints_along, joints_across)

        data_manager.DataExportBiped().append_data(f"{self.side}_wing_module",
                            {
                                "membrane_ctls": self.membrane_ctls,
                                "surface": self.surface,
                            })

    def surface_setup(self):

        """
        Loft the driver surface through the chains. U cruza entre cadenas,
        V corre a lo largo de cada cadena (ver surface_pin.loft_from_chains).
        """

        self.surface = surface_pin.loft_from_chains(self.chains, name=f"{self.side}_wing", degree=3)
        self.surface = cmds.parent(self.surface, self.module_trn)[0]

    def membrane_controls(self, controls_per_gap):

        """
        Create the membrane controls between each pair of adjacent chains and
        their driver joints (influences of the surface skinCluster).
        """

        self.membrane_ctls = []
        self.membrane_joints = []

        for gap in range(len(self.chains) - 1):
            chain_a = self.chains[gap]
            chain_b = self.chains[gap + 1]

            for k in range(controls_per_gap):
                fraction = (k + 1) / (controls_per_gap + 1)
                joint_a = chain_a[round(fraction * (len(chain_a) - 1))]
                joint_b = chain_b[round(fraction * (len(chain_b) - 1))]

                name = f"{self.side}_wingMembrane{gap}{k}"

                nodes, ctl = curve_tool.create_controller(name=name, offset=["GRP", "ANM"],
                                                          parent=self.controllers_grp,
                                                          locked_attrs=["sx", "sy", "sz", "v"])

                blend = cmds.createNode("blendMatrix", name=f"{name}_BLM", ss=True)
                cmds.connectAttr(f"{joint_a}.worldMatrix[0]", f"{blend}.inputMatrix")
                cmds.connectAttr(f"{joint_b}.worldMatrix[0]", f"{blend}.target[0].targetMatrix")
                cmds.setAttr(f"{blend}.target[0].translateWeight", 0.5)
                cmds.setAttr(f"{blend}.target[0].rotateWeight", 0.5)
                cmds.setAttr(f"{blend}.target[0].scaleWeight", 0)
                cmds.setAttr(f"{blend}.target[0].shearWeight", 0)

                cmds.setAttr(f"{nodes[0]}.inheritsTransform", 0)
                cmds.connectAttr(f"{blend}.outputMatrix", f"{nodes[0]}.offsetParentMatrix")

                joint = cmds.createNode("joint", name=f"{name}_JNT", ss=True, parent=self.module_trn)
                cmds.setAttr(f"{joint}.inheritsTransform", 0)
                cmds.connectAttr(f"{ctl}.worldMatrix[0]", f"{joint}.offsetParentMatrix")

                self.membrane_ctls.append(ctl)
                self.membrane_joints.append(joint)

    def skin_setup(self):

        """
        Bind the surface to the driver chains and the membrane control joints.
        """

        influences = [joint for chain in self.chains for joint in chain] + self.membrane_joints
        self.skincluster = cmds.skinCluster(influences, self.surface, toSelectedBones=True,
                                            maximumInfluences=3, normalizeWeights=1,
                                            name=f"{self.side}_wing_SKN")[0]

    def projection_setup(self, joints_along, joints_across):

        """
        Pin the skinning joint grid onto the surface with a single uvPin.
        """

        joints_along = joints_along or 2 * max(len(chain) for chain in self.chains)
        joints_across = joints_across or 2 * len(self.chains) - 1

        uvs = [(u / (joints_across - 1), v / (joints_along - 1))
               for u in range(joints_across) for v in range(joints_along)]

        self.uv_pin, self.skinning_joints = surface_pin.pin_to_surface(
            self.surface, name=f"{self.side}_wingSkinning", uvs=uvs,
            parent=self.skeleton_grp, side=self.side)
