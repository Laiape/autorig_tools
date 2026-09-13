import maya.cmds as cmds
import maya.api.OpenMaya as om
from importlib import reload

from maya_tools.scripts.utils import data_manager
from maya_tools.scripts.utils import guides_manager
from maya_tools.scripts.utils import curve_tool
from maya_tools.scripts.utils import matrix_manager

reload(data_manager)
reload(guides_manager)
reload(curve_tool)
reload(matrix_manager)

# Cup weight per finger at Cup=10 (pinky=full, index=none, linear in between).
# Drives rz on the metacarpal SDK (sdk[0]) of each non-thumb finger.
_CUP_WEIGHTS = {
    "index":  0.00,
    "middle": 0.33,
    "ring":   0.67,
    "pinky":  1.00,
}
_CUP_MAX_RZ = -45  # degrees at Cup=10 for pinky

# Fila de SDK por joint del dedo:
# [Curl+, Curl-, Spread+, Spread-, Twist+, Twist-, Fan+, Fan-].
# La fila 0 es el metacarpiano (en los dedos largos solo lo mueve Cup, de ahi el
# None). Si un dedo trae menos guias las filas se toman desde la primera falange,
# asi un dedo de una sola guia se anima como el 01; si trae mas, las de sobra
# repiten la fila de la ultima falange.
_MID_PHALANX = [-80, 18, 0, 0, 10, -10, 0, 0]
_TIP_PHALANX = [-80, 15, 0, 0,  5,  -5, 0, 0]
_SDK_ROWS = {
    "thumb":  [[0, 0, 0, 0, 0, 0, 10, -10],
               [-90, 20, -20,  20, 20, -20,   0,   0], _MID_PHALANX],
    "index":  [None, [-90, 20, -25,  15, 20, -20,  30, -30], _MID_PHALANX, _TIP_PHALANX],
    "middle": [None, [-90, 20,   2,  -2, 20, -20,  -2,   2], _MID_PHALANX, _TIP_PHALANX],
    "ring":   [None, [-90, 20,  15, -10, 20, -20, -20,  20], _MID_PHALANX, _TIP_PHALANX],
    "pinky":  [None, [-90, 20,  30, -15, 20, -20, -50,  50], _MID_PHALANX, _TIP_PHALANX],
}


def _fit_rows(rows, n):
    """Ajusta la tabla de filas SDK a los niveles de falange que trae el dedo."""
    extra = n - len(rows)
    return rows + [rows[-1]] * extra if extra >= 0 else rows[1:1 + n]


def _rows_for_depths(rows, depths):
    """Fila SDK para cada joint segun su profundidad en el dedo. Las ramas
    comparten fila: un 03 y un 13 cuelgan los dos del 02 y son falange 3."""
    fitted = _fit_rows(rows, max(depths) + 1)
    return [fitted[d] for d in depths]


class FingersModule(object):

    FINGER_NAMES = ["thumb", "index", "middle", "ring", "pinky"]

    def __init__(self):
        self.modules         = data_manager.DataExportBiped().get_data("basic_structure", "modules_GRP")
        self.skel_grp        = data_manager.DataExportBiped().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl  = data_manager.DataExportBiped().get_data("basic_structure", "masterwalk_ctl")

    def make(self, side):
        self.side = side
        self.wrist_jnt       = data_manager.DataExportBiped().get_data("arm_module", f"{self.side}_wrist_JNT")
        self.module_trn      = cmds.createNode("transform", name=f"{self.side}_fingersModule_GRP",      ss=True, p=self.modules)
        self.skeleton_grp    = cmds.createNode("transform", name=f"{self.side}_fingersSkinning_GRP",    ss=True, p=self.skel_grp)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.side}_fingersControllers_GRP", ss=True, p=self.masterwalk_ctl)
        cmds.setAttr(f"{self.controllers_grp}.inheritsTransform", 0)

        self.load_guides()
        self.fk_fingers()
        self.parent_fingers_to_wrist()
        self.attributes_setup()

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────
    def _lock(self, ctl, attrs):
        for attr in attrs:
            cmds.setAttr(f"{ctl}.{attr}", lock=True, keyable=False, channelBox=False)

    # ─────────────────────────────────────────────────────────────────────────
    # Build
    # ─────────────────────────────────────────────────────────────────────────
    def load_guides(self):
        self.fingers = []
        for name in self.FINGER_NAMES:
            cmds.select(clear=True)
            guides = guides_manager.get_guides(f"{self.side}_{name}00_JNT")
            cmds.parent(guides[0], self.module_trn)
            setattr(self, name, guides)
            self.fingers.append(guides)
        cmds.select(clear=True)

    def fk_fingers(self):
        self._ctl   = {n: [] for n in self.FINGER_NAMES}
        self._nodes = {n: [] for n in self.FINGER_NAMES}
        self._sdk   = {n: [] for n in self.FINGER_NAMES}
        self._depth = {n: [] for n in self.FINGER_NAMES}
        self.skinning_joints = {n: [] for n in self.FINGER_NAMES}

        skin_trns = {
            name: cmds.createNode("transform", name=f"{self.side}_{name}Skinning_GRP", ss=True, p=self.skeleton_grp)
            for name in self.FINGER_NAMES
        }

        for finger in self.fingers:
            fname      = next(n for n in self.FINGER_NAMES if n in finger[0])
            ctl_list   = self._ctl[fname]
            nodes_list = self._nodes[fname]
            sdk_list   = self._sdk[fname]

            # The imported guides become the skinning chain: drop the End
            # guides and move the chain under the skeleton group.
            chain      = [jnt for jnt in finger if "End" not in jnt]
            end_joints = [jnt for jnt in finger if "End" in jnt]
            if end_joints:
                cmds.delete(end_joints)
            cmds.parent(chain[0], skin_trns[fname])

            # El dedo puede bifurcarse (dos falanges terminales sobre el mismo
            # padre), asi que cada control cuelga del control de SU padre en la
            # guia, no del anterior de la lista.
            ctl_of, depth_of = {}, {}

            for joint in chain:
                cmds.select(clear=True)

                parent = (cmds.listRelatives(joint, parent=True) or [None])[0]
                if parent not in ctl_of:   # la raiz cuelga del grupo de skinning
                    parent = None

                fk_node, fk_ctl = curve_tool.create_controller(
                    name=joint.replace("_JNT", ""), offset=["GRP", "SDK"]
                )
                cmds.matchTransform(fk_node[0], joint, pos=True, rot=True)

                if parent:
                    cmds.parent(fk_node[0], ctl_of[parent])

                ctl_of[joint]   = fk_ctl
                depth_of[joint] = 0 if parent is None else depth_of[parent] + 1

                ctl_list.append(fk_ctl)
                nodes_list.append(fk_node[0])
                sdk_list.append(fk_node[1])
                self._depth[fname].append(depth_of[joint])

                matrix_manager.fk_constraint(joint, parent, False, None)

                self._lock(fk_ctl, ["sx", "sy", "sz", "v"])
                cmds.xform(joint, m=om.MMatrix.kIdentity)

            # Tag the guides with the "Skinning" suffix once the constraints
            # are wired so the weight import finds the expected influences.
            self.skinning_joints[fname] = [
                cmds.rename(jnt, jnt.replace("_JNT", "Skinning_JNT")) for jnt in chain
            ]


        # Named attributes for external access
        for name in self.FINGER_NAMES:
            setattr(self, f"fk_{name}_ctl",   self._ctl[name])
            setattr(self, f"fk_{name}_nodes", self._nodes[name])
            setattr(self, f"fk_{name}_sdk",   self._sdk[name])

        for name in self.FINGER_NAMES:
            cmds.parent(self._nodes[name][0], self.controllers_grp)

        self.finger_attributes_nodes, self.finger_attributes_ctl = curve_tool.create_controller(
            name=f"{self.side}_fingersAttributes", offset=["GRP"]
        )
        cmds.parent(self.finger_attributes_nodes[0], self.controllers_grp)
        temp = cmds.pointConstraint(
            *self._ctl["middle"][:2], self.finger_attributes_nodes[0], mo=False
        )
        cmds.delete(temp)
        self._lock(self.finger_attributes_ctl, ["tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz", "v"])

    def parent_fingers_to_wrist(self):
        targets = [self._nodes[n][0] for n in self.FINGER_NAMES] + [self.finger_attributes_nodes[0]]
        for finger in targets:
            cmds.select(clear=True)
            temp_loc = cmds.spaceLocator(name=finger.replace("GRP", "LOC"))[0]
            cmds.matchTransform(temp_loc, finger, pos=True, rot=True)
            pm = cmds.createNode("parentMatrix", name=finger.replace("GRP", "PM"), ss=True)
            cmds.connectAttr(f"{temp_loc}.worldMatrix[0]",      f"{pm}.inputMatrix")
            cmds.connectAttr(f"{self.wrist_jnt}.worldMatrix[0]", f"{pm}.target[0].targetMatrix")
            cmds.setAttr(f"{pm}.target[0].offsetMatrix", matrix_manager.get_offset_matrix(finger, self.wrist_jnt), type="matrix")
            cmds.connectAttr(f"{pm}.outputMatrix", f"{finger}.offsetParentMatrix")
            cmds.xform(finger, m=om.MMatrix.kIdentity)
            cmds.delete(temp_loc)

    # ─────────────────────────────────────────────────────────────────────────
    # Attributes
    # ─────────────────────────────────────────────────────────────────────────
    def attributes_setup(self):
        ctl = self.finger_attributes_ctl
        sdk = self._sdk

        def sep(ln):
            cmds.addAttr(ctl, longName=ln, attributeType="enum", enumName="____")
            cmds.setAttr(f"{ctl}.{ln}", lock=True, keyable=False, channelBox=True)

        def flt(ln):
            cmds.addAttr(ctl, longName=ln, attributeType="float",
                         defaultValue=0, max=10, min=-10, keyable=True)

        sep("FINGER_ATTRIBUTES")
        flt("Curl"); flt("Spread"); flt("Twist"); flt("Fan"); flt("Cup")

        sep("THUMB_ATTRIBUTES")
        flt("Thumb_Curl"); flt("Thumb_Spread"); flt("Thumb_Twist"); flt("Thumb_Fan")

        for fname in self.FINGER_NAMES:
            prefix = "Thumb_" if fname == "thumb" else ""
            rows   = _rows_for_depths(_SDK_ROWS[fname], self._depth[fname])
            for node, row in zip(self._sdk[fname], rows):
                if row is not None:
                    self._sdk_cb(node, row, prefix)

        # Cup - metacarpiano (sdk[0]) de los dedos que lo conserven. Un dedo con
        # menos falanges no tiene metacarpiano que abarquillar.
        for fname, weight in _CUP_WEIGHTS.items():
            if max(self._depth[fname]) + 1 < len(_SDK_ROWS[fname]):
                continue
            rz_max = _CUP_MAX_RZ * weight
            cmds.select(sdk[fname][0])
            cmds.setDrivenKeyframe(at="rz", dv=0,   cd=f"{ctl}.Cup", v=0)
            cmds.setDrivenKeyframe(at="rz", dv=10,  cd=f"{ctl}.Cup", v=rz_max)
            cmds.setDrivenKeyframe(at="rz", dv=-10, cd=f"{ctl}.Cup", v=-rz_max)

    def _sdk_cb(self, node, values, prefix=""):
        fa = self.finger_attributes_ctl
        cmds.select(node)

        for attr, cd, pos, neg in [
            ("rz", "Curl",   values[0], values[1]),
            ("ry", "Spread", values[2], values[3]),
            ("rx", "Twist",  values[4], values[5]),
            ("rz", "Fan",    values[6], values[7]),
        ]:
            cmds.setDrivenKeyframe(at=attr, dv=0,   cd=f"{fa}.{prefix}{cd}", v=0)
            cmds.setDrivenKeyframe(at=attr, dv=10,  cd=f"{fa}.{prefix}{cd}", v=pos)
            cmds.setDrivenKeyframe(at=attr, dv=-10, cd=f"{fa}.{prefix}{cd}", v=neg)
