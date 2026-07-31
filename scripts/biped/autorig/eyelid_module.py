import maya.cmds as cmds
import maya.api.OpenMaya as om
from importlib import reload
import os
import math

from utils import data_manager
from utils import guides_manager
from utils import curve_tool
from utils import matrix_manager
from utils import ribbon

reload(data_manager)
reload(guides_manager)
reload(curve_tool)
reload(matrix_manager)
reload(ribbon)

def socket_positions_from_ring(curve, side, socket_names, samples=64):

    """
    Deriva las posiciones de los sockets desde UNA curva-anillo dibujada
    alrededor del ojo (como la guía de la ceja: da igual cuántos CVs tenga y
    por dónde empiece). Cada socket se busca por su dirección alrededor del
    centro del anillo en el plano XY: up=+Y, in=hacia la nariz (x=0), y las
    diagonales entre medias. Se muestrea la curva y se toma el punto cuya
    dirección mejor casa con la del socket.

    Args:
        curve (str): curva-anillo (shape o transform).
        side (str): 'L' o 'R', decide hacia dónde cae "in".
        socket_names (list[str]): nombres de socket a resolver.
        samples (int): puntos muestreados a lo largo de la curva.

    Returns:
        dict: {socket_name: posición mundo [x, y, z]}
    """

    points = [cmds.pointOnCurve(curve, pr=i / samples, top=True, position=True) for i in range(samples)]
    center = [sum(axis) / len(points) for axis in zip(*points)]

    in_x = -1.0 if side == "L" else 1.0  # "in" mira a la nariz (x=0)
    directions = {
        "upperSocket": (0, 1), "lowerSocket": (0, -1),
        "inSocket": (in_x, 0), "outSocket": (-in_x, 0),
        "upInSocket": (in_x, 1), "upOutSocket": (-in_x, 1),
        "downInSocket": (in_x, -1), "downOutSocket": (-in_x, -1),
    }

    positions = {}
    for name in socket_names:
        dir_x, dir_y = directions[name]
        length = math.sqrt(dir_x * dir_x + dir_y * dir_y)
        dir_x, dir_y = dir_x / length, dir_y / length

        def alignment(point):
            off_x, off_y = point[0] - center[0], point[1] - center[1]
            off_len = math.sqrt(off_x * off_x + off_y * off_y) or 1.0
            return (off_x * dir_x + off_y * dir_y) / off_len

        positions[name] = max(points, key=alignment)

    return positions


class EyelidModule(object):

    def __init__(self):

        """
        Initialize the eyelidModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExportBiped().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExportBiped().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExportBiped().get_data("basic_structure", "masterwalk_ctl")
        self.settings_ctl = data_manager.DataExportBiped().get_data("basic_structure", "preferences_ctl")
        self.head_ctl = data_manager.DataExportBiped().get_data("neck_module", "head_ctl")
        self.face_ctl = data_manager.DataExportBiped().get_data("neck_module", "face_ctl")
        self.head_guide_matrix = data_manager.DataExportBiped().get_data("neck_module", "head_guide_matrix")

    def make(self, side, sockets=True, surface=False):

        """
        Create the eyelid module structure and controllers. Call this method with the side ('L' or 'R') to create the respective eyelid module.
        Args:
            side (str): The side of the eyelid ('L' or 'R').
            sockets (bool): construir los sockets del párpado (dependen de la ceja
                y de las guías de socket). En cuadrúpedo se pasa False: no hay
                cejas/sockets, así que no se crean.
            surface (bool): si es True, las joints de skinning del párpado se
                PROYECTAN sobre una NURBS surface esférica centrada en el ojo (del
                tamaño del ojo), así siempre van por encima del globo ocular y el
                blink no se rompe (no se hunden dentro al cerrar). Flag por
                personaje.

        """
        self.side = side
        self.surface = surface
        self.module_name = f"C_eyelid"
        if cmds.objExists(f"{self.module_name}Module_GRP"):
            self.module_trn = f"{self.module_name}Module_GRP"
            self.skeleton_grp = f"{self.module_name}Skinning_GRP"
            self.controllers_grp = f"{self.module_name}Controllers_GRP"
            self.local_jnts_grp = f"{self.module_name}Local_GRP"
            self.curves_grp = f"{self.module_name}Curves_GRP"
        else:
            self.module_trn = cmds.createNode("transform", name=f"{self.module_name}Module_GRP", ss=True, p=self.modules)
            cmds.setAttr(f"{self.module_trn}.inheritsTransform", 0)
            self.skeleton_grp = cmds.createNode("transform", name=f"{self.module_name}Skinning_GRP", ss=True, p=self.skel_grp)
            self.controllers_grp = cmds.createNode("transform", name=f"{self.module_name}Controllers_GRP", ss=True, p=self.face_ctl)
            self.local_jnts_grp = cmds.createNode("transform", name=f"{self.module_name}Local_GRP", ss=True, p=self.module_trn)
            self.curves_grp = cmds.createNode("transform", name=f"{self.module_name}Curves_GRP", ss=True, p=self.module_trn)
            cmds.addAttr(self.face_ctl, longName="Eyes", attributeType="long", defaultValue=2, max=3, min=0, keyable=True)
            cmds.addAttr(self.face_ctl, longName="Sockets", attributeType="long", defaultValue=1, max=2, min=0, keyable=True)
        self.extra_controllers_grp = cmds.createNode("transform", name=f"{self.side}_eyelidExtraControllers_GRP", ss=True, p=self.controllers_grp)

        # Call methods to build the eyelid module
        self.create_curves()
        self.load_guides()
        self.curve_cvs_into_guides()
        self.create_main_eye_setup()
        self.create_controllers()
        self.eye_direct()
        self.create_blink_setup()
        self.fleshy_setup()
        if self.surface:
            self.create_eye_surface()
        self.skinning_joints()

        if sockets:
            socket_main_controllers = self.sockets()
            if socket_main_controllers:  # sin guías de socket se omiten, no se para el build
                data_manager.DataExportBiped().append_data("eyelid_module",
                                    {
                                        f"{self.side}_lower_socket_ctl": socket_main_controllers[1]
                                    })

    def lock_attributes(self, ctl, attrs):

        """
        Lock and hide attributes on a controller.
        Args:
            ctl (str): The name of the controller.
            attrs (list): A list of attributes to lock and hide.
        """
        
        for attr in attrs:
            cmds.setAttr(f"{ctl}.{attr}", lock=True, keyable=False, channelBox=False)

    def local(self, ctl):

        """
        Create a local transform node for a controller.
        Args:
            ctl (str): The name of the controller.
        Returns:
            str: The name of the local transform node.
        """
        local_mmx = cmds.createNode("multMatrix", name=ctl.replace("_CTL", "Local_MMX"), ss=True)
        cmds.connectAttr(f"{ctl}.matrix", f"{local_mmx}.matrixIn[0]")
        cmds.setAttr(f"{local_mmx}.matrixIn[1]", cmds.getAttr(f"{ctl}.worldMatrix[0]"), type="matrix")

        if "01" in ctl:
            local_jnt = cmds.createNode("joint", name=ctl.replace("01_CTL", "01Local_JNT"), ss=True, p=self.local_jnts_grp)
            cmds.delete(local_jnt.replace("01Local_JNT", "Local_JNT"))
        else:
            local_jnt = cmds.createNode("joint", name=ctl.replace("_CTL", "Local_JNT"), ss=True, p=self.local_jnts_grp)
        cmds.connectAttr(f"{local_mmx}.matrixSum", f"{local_jnt}.offsetParentMatrix")

        return local_mmx, local_jnt
    
    def create_curves(self):

        """
        Create curves for the blink setup.
        """
        # Get the guide curves
        self.linear_upper_curve = guides_manager.get_guides(guide_export=f"{self.side}_eyelidUpperLinear_CRVShape", parent=self.curves_grp)
        self.linear_lower_curve = guides_manager.get_guides(guide_export=f"{self.side}_eyelidLowerLinear_CRVShape", parent=self.curves_grp)
        # Rebuild the curves to have proper CV count and degree
        self.eyelid_up_curve = cmds.rebuildCurve(self.linear_upper_curve, n=f"{self.side}_eyelidUp_CRV", ch=False, rpo=False, rt=0, end=1, kr=0, kcp=0, kep=1, kt=0, tol=0.01, d=3, s=4)[0]
        self.eyelid_down_curve = cmds.rebuildCurve(self.linear_lower_curve, n=f"{self.side}_eyelidDown_CRV", ch=False, rpo=False, rt=0, end=1, kr=0, kcp=0, kep=1, kt=0, tol=0.01, d=3, s=4)[0]

        self.blink_ref_curve = cmds.duplicate(self.eyelid_up_curve, n=f"{self.side}_eyelidBlinkRef_CRV")[0]

        self.eyelid_up_curve_rebuild = cmds.rebuildCurve(self.eyelid_up_curve, n=f"{self.side}_eyelidUpRebuilded_CRV", ch=False, rpo=False, rt=0, end=1, kr=0, kcp=1, kep=1, kt=0, tol=0.01)[0]
        self.eyelid_down_curve_rebuild = cmds.rebuildCurve(self.eyelid_down_curve, n=f"{self.side}_eyelidDownRebuilded_CRV", ch=False, rpo=False, rt=0, end=1, kr=0, kcp=1, kep=1, kt=0, tol=0.01)[0]

        cmds.parent(self.eyelid_up_curve, self.eyelid_down_curve, self.blink_ref_curve, self.eyelid_up_curve_rebuild, self.eyelid_down_curve_rebuild, self.curves_grp)

    def load_guides(self):

        """
        Load the guide locators for the eyelid module.
        """
        cmds.select(clear=True)
        self.eye_joint = guides_manager.get_guides(f"{self.side}_eye_JNT", parent=self.module_trn)
        # Matrices horneadas de las guías del ojo (estáticas), sin transforms _GUIDE vivos
        self.eye_guide_matrix = cmds.getAttr(f"{self.eye_joint[0]}.worldMatrix[0]")
        self.eye_end_guide_matrix = cmds.getAttr(f"{self.eye_joint[1]}.worldMatrix[0]")
        cmds.delete(self.eye_joint[0])

        self.eye_aim_matrix = cmds.createNode("aimMatrix", name=f"{self.side}_eye_AIM", ss=True)
        cmds.setAttr(f"{self.eye_aim_matrix}.inputMatrix", self.eye_guide_matrix, type="matrix")
        cmds.setAttr(f"{self.eye_aim_matrix}.primary.primaryTargetMatrix", self.eye_end_guide_matrix, type="matrix")
        cmds.setAttr(f"{self.eye_aim_matrix}.primaryInputAxis", 0, 0, 1)

    def curve_cvs_into_guides(self):

        """
        Convert curve CVs into guides for the eyelid module.
        """

        names = [
            "eyelidIn",
            "eyelidInUp",
            "eyelidUp",
            "eyelidOutUp",
            "eyelidInDown",
            "eyelidDown",
            "eyelidOutDown",
            "eyelidOut",
        ]

        self.guides_matrices = []

        for i, name in enumerate(names):
            if i == 0:
                # Must connect in and out with blend matrices to upper and lower curve cvs
                four_by_four_matrix_00 = cmds.createNode("fourByFourMatrix", name=f"{self.side}_{name}00_FFX", ss=True)
                four_by_four_matrix_01 = cmds.createNode("fourByFourMatrix", name=f"{self.side}_{name}01_FFX", ss=True)
                cmds.connectAttr(f"{self.eyelid_up_curve}.editPoints[{i}].xValueEp", f"{four_by_four_matrix_00}.in30")
                cmds.connectAttr(f"{self.eyelid_up_curve}.editPoints[{i}].yValueEp", f"{four_by_four_matrix_00}.in31")
                cmds.connectAttr(f"{self.eyelid_up_curve}.editPoints[{i}].zValueEp", f"{four_by_four_matrix_00}.in32")
                cmds.connectAttr(f"{self.eyelid_down_curve}.editPoints[{i}].xValueEp", f"{four_by_four_matrix_01}.in30")
                cmds.connectAttr(f"{self.eyelid_down_curve}.editPoints[{i}].yValueEp", f"{four_by_four_matrix_01}.in31")
                cmds.connectAttr(f"{self.eyelid_down_curve}.editPoints[{i}].zValueEp", f"{four_by_four_matrix_01}.in32")
                blend_matrix = cmds.createNode("blendMatrix", name=f"{self.side}_{name}_BMX", ss=True)
                cmds.connectAttr(f"{four_by_four_matrix_00}.output", f"{blend_matrix}.inputMatrix")
                cmds.connectAttr(f"{four_by_four_matrix_01}.output", f"{blend_matrix}.target[0].targetMatrix")
                cmds.setAttr(f"{blend_matrix}.envelope", 0.5) # Blend equally between upper and lower
                self.guides_matrices.append(f"{blend_matrix}.outputMatrix")
            if i == 7:
                # Must connect in and out with blend matrices to upper and lower curve cvs
                four_by_four_matrix_00 = cmds.createNode("fourByFourMatrix", name=f"{self.side}_{name}00_FFX", ss=True)
                four_by_four_matrix_01 = cmds.createNode("fourByFourMatrix", name=f"{self.side}_{name}01_FFX", ss=True)
                j = i - 3
                cmds.connectAttr(f"{self.eyelid_up_curve}.editPoints[{j}].xValueEp", f"{four_by_four_matrix_00}.in30")
                cmds.connectAttr(f"{self.eyelid_up_curve}.editPoints[{j}].yValueEp", f"{four_by_four_matrix_00}.in31")
                cmds.connectAttr(f"{self.eyelid_up_curve}.editPoints[{j}].zValueEp", f"{four_by_four_matrix_00}.in32")
                cmds.connectAttr(f"{self.eyelid_down_curve}.editPoints[{j}].xValueEp", f"{four_by_four_matrix_01}.in30")
                cmds.connectAttr(f"{self.eyelid_down_curve}.editPoints[{j}].yValueEp", f"{four_by_four_matrix_01}.in31")
                cmds.connectAttr(f"{self.eyelid_down_curve}.editPoints[{j}].zValueEp", f"{four_by_four_matrix_01}.in32")
                blend_matrix = cmds.createNode("blendMatrix", name=f"{self.side}_{name}_BMX", ss=True)
                cmds.connectAttr(f"{four_by_four_matrix_00}.output", f"{blend_matrix}.inputMatrix")
                cmds.connectAttr(f"{four_by_four_matrix_01}.output", f"{blend_matrix}.target[0].targetMatrix")
                cmds.setAttr(f"{blend_matrix}.envelope", 0.5) # Blend equally between upper and lower
                self.guides_matrices.append(f"{blend_matrix}.outputMatrix")

            elif i != 0 and i != 7:
                j = i - 3
                four_by_four_matrix = cmds.createNode("fourByFourMatrix", name=f"{self.side}_{name}_FFX", ss=True)
                if i < 4:
                    cmds.connectAttr(f"{self.eyelid_up_curve}.editPoints[{i}].xValueEp", f"{four_by_four_matrix}.in30")
                    cmds.connectAttr(f"{self.eyelid_up_curve}.editPoints[{i}].yValueEp", f"{four_by_four_matrix}.in31")
                    cmds.connectAttr(f"{self.eyelid_up_curve}.editPoints[{i}].zValueEp", f"{four_by_four_matrix}.in32")
                else:
                    cmds.connectAttr(f"{self.eyelid_down_curve}.editPoints[{j}].xValueEp", f"{four_by_four_matrix}.in30")
                    cmds.connectAttr(f"{self.eyelid_down_curve}.editPoints[{j}].yValueEp", f"{four_by_four_matrix}.in31")
                    cmds.connectAttr(f"{self.eyelid_down_curve}.editPoints[{j}].zValueEp", f"{four_by_four_matrix}.in32")
                self.guides_matrices.append(f"{four_by_four_matrix}.output")


    def create_main_eye_setup(self):

        """
        Create the main eye setup for the eyelid module.
        """
        self.eye_skinning_jnt = cmds.createNode("joint", name=f"{self.side}_eyeSkinning_JNT", p=self.skeleton_grp)

        if self.side == "L":
            self.main_aim_nodes, self.main_aim_ctl = curve_tool.create_controller(name=f"C_eyeMain", offset=["GRP"])
            cmds.parent(self.main_aim_nodes[0], self.head_ctl)
            self.lock_attributes(self.main_aim_ctl, ["sx", "sy", "sz", "v", "rx", "ry", "rz"])
            # C_eyeMain en el PUNTO MEDIO de los aim de los DOS ojos (cada aim va a 30
            # DELANTE de su ojo por su mirada = eje Z del ojo). Se leen las matrices
            # de guía de ambos ojos del archivo (las guías pueden ser asimétricas, p.
            # ej. el cuadrúpedo), así el medio es correcto aunque no haya simetría.
            # Orientado a la CABEZA (antes usaba la orientación LATERAL del ojo +
            # mover por su Z, que en cuadrúpedos mandaba el control de lado). En biped
            # (ojos al frente, simétricos) equivale al comportamiento anterior.
            def _eye_aim(eye_matrix):
                z = om.MVector(eye_matrix[8], eye_matrix[9], eye_matrix[10]).normal()
                c = om.MVector(eye_matrix[12], eye_matrix[13], eye_matrix[14])
                return c + z * 30.0
            aim_l = _eye_aim(self.eye_guide_matrix)
            aim_r = None
            try:
                r_chain = guides_manager.get_guides("R_eye_JNT")  # crea R_eye_JNT (+End) temporal
                aim_r = _eye_aim(cmds.getAttr(f"{r_chain[0]}.worldMatrix[0]"))
                cmds.delete(r_chain[0])  # borra (con su hijo) -> el build de R la recrea
            except Exception:
                aim_r = None
            if aim_r is not None:
                mid = (aim_l + aim_r) * 0.5
            else:
                # fallback: simétrico en X (centro del personaje), altura/profundidad del aim L
                mid = om.MVector(0.0, aim_l.y, aim_l.z)
            h = self.head_guide_matrix
            main_matrix = [h[0], h[1], h[2], 0, h[4], h[5], h[6], 0, h[8], h[9], h[10], 0, mid.x, mid.y, mid.z, 1]
            cmds.xform(self.main_aim_nodes[0], ws=True, m=main_matrix)

        side_aim_nodes, self.side_aim_ctl = curve_tool.create_controller(name=f"{self.side}_eye", offset=["GRP"])
        cmds.parent(side_aim_nodes[0], self.controllers_grp)
        cmds.xform(side_aim_nodes[0], ws=True, m=self.eye_guide_matrix)
        cmds.select(side_aim_nodes[0])
        cmds.move(0, 0,30, relative=True, objectSpace=True, worldSpaceDistance=True)
        self.lock_attributes(self.side_aim_ctl, ["sx", "sy", "sz", "v", "rx", "ry", "rz"])
        cmds.parent(side_aim_nodes[0], "C_eyeMain_CTL")


    def create_controllers(self):

        """
        Create controllers for the eyelid module.
        """

        self.upper_local_jnt = []
        self.lower_local_jnt = []
        self.upper_local_trn = []
        self.lower_local_trn = []

        self.controllers = []
        self.nodes = []

        for i, matrix in enumerate(self.guides_matrices):
            suffix = matrix.split("_")[-1]
            node, ctl = curve_tool.create_controller(name=matrix.replace(f"_{suffix}", ""), offset=["GRP", "OFF"])
            local_trn, local_jnt = self.local(ctl)
            self.lock_attributes(ctl, ["sx", "sy", "sz", "v"])
            
            # if "eyelidIn_" in matrix or "eyelidOut_" in matrix or "eyelidDown_" in matrix or "eyelidUp_" in matrix:
            #     node_01, ctl_01 = curve_tool.create_controller(name=matrix.replace("_FFX", "01"), offset=["GRP"])
            #     local_jnt = self.local(ctl_01)

            #     cmds.parent(node_01, ctl)
            
            if "Up" in matrix:
                self.upper_local_jnt.append(local_jnt)
                self.upper_local_trn.append(local_trn)
            elif "Down" in matrix:
                self.lower_local_jnt.append(local_jnt)
                self.lower_local_trn.append(local_trn)
            elif "In" not in matrix or "Out" not in matrix:
                self.upper_local_jnt.append(local_jnt)
                self.lower_local_jnt.append(local_jnt)
                self.upper_local_trn.append(local_trn)
                self.lower_local_trn.append(local_trn)

            self.lock_attributes(ctl, ["sx", "sy", "sz", "v"])

            cmds.connectAttr(matrix, f"{node[0]}.offsetParentMatrix")
            cmds.parent(node[0], self.controllers_grp)
            self.controllers.append(ctl)
            self.nodes.append(node[0])
        
        self.upper_guides = [matrix for matrix in self.guides_matrices if "Up" in matrix or ("eyelidIn_" in matrix) or ("eyelidOut_" in matrix)]
        self.lower_guides = [matrix for matrix in self.guides_matrices if "Down" in matrix or ("eyelidIn_" in matrix) or ("eyelidOut_" in matrix)]
        self.upper_nodes = [matrix for matrix in self.nodes if "Up" in matrix or ("eyelidIn_" in matrix) or ("eyelidOut_" in matrix)]
        self.lower_nodes = [matrix for matrix in self.nodes if "Down" in matrix or ("eyelidIn_" in matrix) or ("eyelidOut_" in matrix)]
        self.upper_controllers = [matrix for matrix in self.controllers if "Up" in matrix or ("eyelidIn_" in matrix) or ("eyelidOut_" in matrix)]
        self.lower_controllers = [matrix for matrix in self.controllers if "Down" in matrix or ("eyelidIn_" in matrix) or ("eyelidOut_" in matrix)]

    
        #Constraints between controllers
        self.constraints_callback(guide=self.upper_guides[1], driven=self.upper_nodes[1], drivers=[self.upper_controllers[2], self.upper_controllers[0]], local_jnt=self.upper_local_jnt[1])
        self.constraints_callback(guide=self.upper_guides[-2], driven=self.upper_nodes[-2], drivers=[self.upper_controllers[2], self.upper_controllers[-1]] , local_jnt=self.upper_local_jnt[-2])
        self.constraints_callback(guide=self.lower_guides[1], driven=self.lower_nodes[1], drivers=[self.lower_controllers[2], self.lower_controllers[0]], local_jnt=self.lower_local_jnt[1])
        self.constraints_callback(guide=self.lower_guides[-2], driven=self.lower_nodes[-2], drivers=[self.lower_controllers[2], self.lower_controllers[-1]], local_jnt=self.lower_local_jnt[-2])

        # Re-bake the bind matrix of every local network now that the controllers
        # are in place (what the old matchTransform on the Local_GRPs did)
        for local_mmx in set(self.upper_local_trn + self.lower_local_trn):
            ctl = local_mmx.replace("Local_MMX", "_CTL")
            cmds.setAttr(f"{local_mmx}.matrixIn[1]", cmds.getAttr(f"{ctl}.worldMatrix[0]"), type="matrix")

        self.local_constraints_callback(driven_jnt=self.upper_local_trn[1], drivers=[self.upper_controllers[2], self.upper_controllers[0]])
        self.local_constraints_callback(driven_jnt=self.upper_local_trn[-2], drivers=[self.upper_controllers[2], self.upper_controllers[-1]])
        self.local_constraints_callback(driven_jnt=self.lower_local_trn[1], drivers=[self.lower_controllers[2], self.lower_controllers[0]])
        self.local_constraints_callback(driven_jnt=self.lower_local_trn[-2], drivers=[self.lower_controllers[2], self.lower_controllers[-1]])

        self.primary_controller = [self.upper_controllers[0].replace("CTL", "GRP"), self.upper_controllers[2].replace("CTL", "GRP"), self.upper_controllers[-1].replace("CTL", "GRP"), self.lower_controllers[2].replace("CTL", "GRP")]
        self.secondary_controller = [self.upper_controllers[1].replace("CTL", "GRP"), self.upper_controllers[-2].replace("CTL", "GRP"), self.lower_controllers[1].replace("CTL", "GRP"), self.lower_controllers[-2].replace("CTL", "GRP")]
    
    def eye_direct(self):

        """
        Add custom attributes to the eyelid controllers.
        """

        self.eye_direct_nodes, self.eye_direct_ctl = curve_tool.create_controller(name=f"{self.side}_eyeDirect", offset=["GRP", "OFF"])
        if self.surface:
            # Gizmo DELANTE del ojo (a lo largo de la mirada = Z local del control)
            # para agarrarlo, pero el pivote/transform queda en el CENTRO del ojo, así
            # rotarlo rota el ojo sobre su centro (no lo orbita). En cuadrúpedos el ojo
            # mira de lado, así que 'delante' es la Z del ojo, no el frente de la cara.
            cmds.move(0, 0, 2, f"{self.eye_direct_ctl}.cv[*]", relative=True, objectSpace=True, worldSpaceDistance=True)
        cmds.parent(self.eye_direct_nodes[0], self.head_ctl)
        mult_matrix_negate_head = cmds.createNode("multMatrix", name=f"{self.side}_eyeDirectNegateHead_MMX", ss=True)
        cmds.setAttr(f"{mult_matrix_negate_head}.matrixIn[0]", self.eye_guide_matrix, type="matrix")
        cmds.setAttr(f"{mult_matrix_negate_head}.matrixIn[1]", list(om.MMatrix(self.head_guide_matrix).inverse()), type="matrix")
        cmds.connectAttr(f"{mult_matrix_negate_head}.matrixSum", f"{self.eye_direct_nodes[0]}.offsetParentMatrix")
        cmds.xform(self.eye_direct_nodes[0], m=om.MMatrix.kIdentity)
        self.lock_attributes(self.eye_direct_ctl, ["sx", "sy", "sz", "v"])

        cmds.addAttr(self.eye_direct_ctl, ln="EYE_ATTRIBUTES", at="enum", en="____", k=True)
        cmds.setAttr(f"{self.eye_direct_ctl}.EYE_ATTRIBUTES", lock=True, keyable=False, channelBox=True)
        cmds.addAttr(self.eye_direct_ctl, ln="Upper_Blink", at="float", min=-1, max=1, dv=0, k=True)
        cmds.addAttr(self.eye_direct_ctl, ln="Lower_Blink", at="float", min=-1, max=1, dv=0, k=True)
        cmds.addAttr(self.eye_direct_ctl, ln="Blink_Height", at="float", min=0, max=1, dv=0.2, k=True)
        cmds.addAttr(self.eye_direct_ctl, ln="Fleshy", at="float", min=0, max=1, dv=0.3, k=True)
        cmds.addAttr(self.eye_direct_ctl, ln="Fleshy_Corners", at="float", min=0, max=1, dv=0.5, k=True)

        # ---- Connect blink curve to blend shape ----
        # cmds.connectAttr(f"{self.eye_direct_ctl}.Blink_Height", f"{self.blink_ref_blend_shape}.w[0]", force=True)

        condition_primary = cmds.createNode("condition", name="C_eyesPrimaryControllers_COND", ss=True)
        cmds.setAttr(f"{condition_primary}.operation", 3)  # Greater Than or Equal
        cmds.setAttr(f"{condition_primary}.secondTerm", 1)
        cmds.setAttr(f"{condition_primary}.colorIfTrueR", 1)
        cmds.setAttr(f"{condition_primary}.colorIfFalseR", 0)
        cmds.connectAttr(f"{self.face_ctl}.Eyes", f"{condition_primary}.firstTerm")
        for grp in self.primary_controller:
            cmds.connectAttr(f"{condition_primary}.outColorR", f"{grp}.visibility", f=True)
        condition_secondary = cmds.createNode("condition", name="C_eyesSecondaryControllers_COND", ss=True)
        cmds.setAttr(f"{condition_secondary}.operation", 3)  # Greater Than or Equal
        cmds.setAttr(f"{condition_secondary}.secondTerm", 2)
        cmds.setAttr(f"{condition_secondary}.colorIfTrueR", 1)
        cmds.setAttr(f"{condition_secondary}.colorIfFalseR", 0)
        cmds.connectAttr(f"{self.face_ctl}.Eyes", f"{condition_secondary}.firstTerm")
        for grp in self.secondary_controller:
            cmds.connectAttr(f"{condition_secondary}.outColorR", f"{grp}.visibility", f=True)
        condition_all = cmds.createNode("condition", name="C_eyesAllControllers_COND", ss=True)
        cmds.setAttr(f"{condition_all}.operation", 0)  # Equal
        cmds.setAttr(f"{condition_all}.secondTerm", 3)
        cmds.setAttr(f"{condition_all}.colorIfTrueR", 1)
        cmds.setAttr(f"{condition_all}.colorIfFalseR", 0)
        cmds.connectAttr(f"{self.face_ctl}.Eyes", f"{condition_all}.firstTerm")
        cmds.connectAttr(f"{condition_all}.outColorR", f"{self.extra_controllers_grp}.visibility", f=True)

        # Connect the aim matrix to the eye direct controller and orient constrain the eye joint to it
        aim_eye_matrix = cmds.createNode("aimMatrix", name=f"{self.side}_eyeDirectEye_AIM", ss=True)
        cmds.connectAttr(f"{self.eye_direct_nodes[0]}.worldMatrix[0]", f"{aim_eye_matrix}.inputMatrix")
        cmds.connectAttr(f"{self.side_aim_ctl}.worldMatrix[0]", f"{aim_eye_matrix}.primaryTargetMatrix")
        cmds.setAttr(f"{aim_eye_matrix}.primaryInputAxis", 0, 0, 1)
        cmds.setAttr(f"{aim_eye_matrix}.secondaryMode", 2)
        cmds.setAttr(f"{aim_eye_matrix}.secondaryInputAxis", 0, 1, 0)
        cmds.setAttr(f"{aim_eye_matrix}.secondaryTargetVector", 0, 1, 0)
        cmds.connectAttr(f"{self.head_ctl}.worldMatrix[0]", f"{aim_eye_matrix}.secondaryTargetMatrix")


        mult_matrix = cmds.createNode("multMatrix", name=f"{self.side}_eyeDirectEye_MMX", ss=True)
        cmds.connectAttr(f"{aim_eye_matrix}.outputMatrix", f"{mult_matrix}.matrixIn[0]")
        cmds.connectAttr(f"{self.eye_direct_nodes[0]}.worldInverseMatrix[0]", f"{mult_matrix}.matrixIn[1]")
        cmds.connectAttr(f"{mult_matrix}.matrixSum", f"{self.eye_direct_nodes[1]}.offsetParentMatrix", force=True)
        cmds.connectAttr(f"{self.eye_direct_ctl}.worldMatrix[0]", f"{self.eye_skinning_jnt}.offsetParentMatrix", force=True)

    def create_blink_setup(self):

        """
        Create the blink setup for the eyelid module.
        """

        # Upper Blink
        # blink_ref_curve weight = Upper_Blink directly (-1..1):
        #   positive → eyelid closes toward blink height
        #   negative → extrapolates away (opens wider), no guide curve needed
        upper_blink = cmds.blendShape(self.blink_ref_curve, self.eyelid_up_curve, self.eyelid_up_curve_rebuild, name=f"{self.side}_upperEyelidBlink_BLS")[0]
        cmds.connectAttr(f"{self.eye_direct_ctl}.Upper_Blink", f"{upper_blink}.{self.blink_ref_curve}")
        upper_blink_abs = cmds.createNode("condition", name=f"{self.side}_upperBlinkAbs_COND", ss=True)
        cmds.setAttr(f"{upper_blink_abs}.operation", 4)  # Greater or Equal
        cmds.setAttr(f"{upper_blink_abs}.secondTerm", 0)
        cmds.connectAttr(f"{self.eye_direct_ctl}.Upper_Blink", f"{upper_blink_abs}.firstTerm")
        cmds.connectAttr(f"{self.eye_direct_ctl}.Upper_Blink", f"{upper_blink_abs}.colorIfTrueR")
        upper_blink_neg = cmds.createNode("negate", name=f"{self.side}_upperBlinkAbs_NEG", ss=True)
        cmds.connectAttr(f"{self.eye_direct_ctl}.Upper_Blink", f"{upper_blink_neg}.input")
        cmds.connectAttr(f"{upper_blink_neg}.output", f"{upper_blink_abs}.colorIfFalseR")
        upper_blink_rev = cmds.createNode("reverse", name=f"{self.side}_upperBlink_REV", ss=True)
        cmds.connectAttr(f"{upper_blink_abs}.outColorR", f"{upper_blink_rev}.inputX")
        cmds.connectAttr(f"{upper_blink_rev}.outputX", f"{upper_blink}.{self.eyelid_up_curve}")

        # Lower Blink
        lower_blink = cmds.blendShape(self.blink_ref_curve, self.eyelid_down_curve, self.eyelid_down_curve_rebuild, name=f"{self.side}_lowerEyelidBlink_BLS")[0]
        cmds.connectAttr(f"{self.eye_direct_ctl}.Lower_Blink", f"{lower_blink}.{self.blink_ref_curve}")
        lower_blink_abs = cmds.createNode("condition", name=f"{self.side}_lowerBlinkAbs_COND", ss=True)
        cmds.setAttr(f"{lower_blink_abs}.operation", 4)  # Greater or Equal
        cmds.setAttr(f"{lower_blink_abs}.secondTerm", 0)
        cmds.connectAttr(f"{self.eye_direct_ctl}.Lower_Blink", f"{lower_blink_abs}.firstTerm")
        cmds.connectAttr(f"{self.eye_direct_ctl}.Lower_Blink", f"{lower_blink_abs}.colorIfTrueR")
        lower_blink_neg = cmds.createNode("negate", name=f"{self.side}_lowerBlinkAbs_NEG", ss=True)
        cmds.connectAttr(f"{self.eye_direct_ctl}.Lower_Blink", f"{lower_blink_neg}.input")
        cmds.connectAttr(f"{lower_blink_neg}.output", f"{lower_blink_abs}.colorIfFalseR")
        lower_blink_rev = cmds.createNode("reverse", name=f"{self.side}_lowerBlink_REV", ss=True)
        cmds.connectAttr(f"{lower_blink_abs}.outColorR", f"{lower_blink_rev}.inputX")
        cmds.connectAttr(f"{lower_blink_rev}.outputX", f"{lower_blink}.{self.eyelid_down_curve}")

        # Blink Height
        blink_blend = cmds.blendShape(self.eyelid_up_curve, self.eyelid_down_curve, self.blink_ref_curve, name=f"{self.side}_eyelidBlink_BLS")[0] # Blend between blink curve and upper eyelid curve
        cmds.connectAttr(f"{self.eye_direct_ctl}.Blink_Height", f"{blink_blend}.{self.eyelid_up_curve}") # Connect upper blink attribute to blend shape weight
        reverse_node = cmds.createNode("reverse", name=f"{self.side}_blinkHeight_REV", ss=True)
        cmds.connectAttr(f"{self.eye_direct_ctl}.Blink_Height", f"{reverse_node}.inputX") # Connect blink height attribute to reverse
        cmds.connectAttr(f"{reverse_node}.outputX", f"{blink_blend}.{self.eyelid_down_curve}") # Connect reverse output to blend shape weight

        upper_eyelid_curve_skin = cmds.skinCluster(*self.upper_local_jnt, self.eyelid_up_curve_rebuild, toSelectedBones=True, bindMethod=0, skinMethod=0, normalizeWeights=1, n=f"{self.side}_upperEyelid_SKIN")[0]
        lower_eyelid_curve_skin = cmds.skinCluster(*self.lower_local_jnt, self.eyelid_down_curve_rebuild, toSelectedBones=True, bindMethod=0, skinMethod=0, normalizeWeights=1, n=f"{self.side}_lowerEyelid_SKIN")[0]

        cmds.skinPercent(upper_eyelid_curve_skin, f"{self.eyelid_up_curve_rebuild}.cv[0]", tv=[(self.upper_local_jnt[0], 1.0)])
        cmds.skinPercent(upper_eyelid_curve_skin, f"{self.eyelid_up_curve_rebuild}.cv[1]", tv=[(self.upper_local_jnt[0], 0.5), (self.upper_local_jnt[1], 0.5)])
        cmds.skinPercent(upper_eyelid_curve_skin, f"{self.eyelid_up_curve_rebuild}.cv[2]", tv=[(self.upper_local_jnt[1], 1.0)])
        cmds.skinPercent(upper_eyelid_curve_skin, f"{self.eyelid_up_curve_rebuild}.cv[3]", tv=[(self.upper_local_jnt[2], 1)])
        cmds.skinPercent(upper_eyelid_curve_skin, f"{self.eyelid_up_curve_rebuild}.cv[4]", tv=[(self.upper_local_jnt[3], 1.0)])
        cmds.skinPercent(upper_eyelid_curve_skin, f"{self.eyelid_up_curve_rebuild}.cv[5]", tv=[(self.upper_local_jnt[3], 0.5), (self.upper_local_jnt[4], 0.5)])
        cmds.skinPercent(upper_eyelid_curve_skin, f"{self.eyelid_up_curve_rebuild}.cv[6]", tv=[(self.upper_local_jnt[4], 1.0)])



        cmds.skinPercent(lower_eyelid_curve_skin, f"{self.eyelid_down_curve_rebuild}.cv[0]", tv=[(self.lower_local_jnt[0], 1.0)])
        cmds.skinPercent(lower_eyelid_curve_skin, f"{self.eyelid_down_curve_rebuild}.cv[1]", tv=[(self.lower_local_jnt[0], 0.5), (self.lower_local_jnt[1], 0.5)])
        cmds.skinPercent(lower_eyelid_curve_skin, f"{self.eyelid_down_curve_rebuild}.cv[2]", tv=[(self.lower_local_jnt[1], 1.0)])
        cmds.skinPercent(lower_eyelid_curve_skin, f"{self.eyelid_down_curve_rebuild}.cv[3]", tv=[(self.lower_local_jnt[2], 1.0)])
        cmds.skinPercent(lower_eyelid_curve_skin, f"{self.eyelid_down_curve_rebuild}.cv[4]", tv=[(self.lower_local_jnt[3], 1.0)])
        cmds.skinPercent(lower_eyelid_curve_skin, f"{self.eyelid_down_curve_rebuild}.cv[5]", tv=[(self.lower_local_jnt[3], 0.5), (self.lower_local_jnt[4], 0.5)])
        cmds.skinPercent(lower_eyelid_curve_skin, f"{self.eyelid_down_curve_rebuild}.cv[6]", tv=[(self.lower_local_jnt[4], 1.0)])

    def fleshy_setup(self):

        """
        Create the fleshy setup for the eyelid module.
        """
        rotation_from_matrix = cmds.createNode("rotationFromMatrix", name=f"{self.side}_fleshy_RFM", ss=True)
        multiply_fleshy = cmds.createNode("multiply", name=f"{self.side}_fleshy_MLT", ss=True)
        blend_colors_fleshy = cmds.createNode("blendColors", name=f"{self.side}_fleshy_BLC", ss=True)
        blend_colors_corners = cmds.createNode("blendColors", name=f"{self.side}_fleshyCorners_BLC", ss=True)

        mult_matrix_eye_direct_local = cmds.createNode("multMatrix", name=f"{self.side}_eyeDirectLocal_MMX", ss=True)
        cmds.connectAttr(f"{self.eye_direct_ctl}.worldMatrix[0]", f"{mult_matrix_eye_direct_local}.matrixIn[0]")
        cmds.connectAttr(f"{self.eye_direct_nodes[0]}.worldInverseMatrix[0]", f"{mult_matrix_eye_direct_local}.matrixIn[1]")

        cmds.connectAttr(f"{mult_matrix_eye_direct_local}.matrixSum", f"{rotation_from_matrix}.input")
        cmds.connectAttr(f"{self.eye_direct_ctl}.Fleshy", f"{multiply_fleshy}.input[0]")
        cmds.connectAttr(f"{self.eye_direct_ctl}.Fleshy_Corners", f"{multiply_fleshy}.input[1]")
        cmds.connectAttr(f"{rotation_from_matrix}.outputX", f"{blend_colors_fleshy}.color1R")
        cmds.connectAttr(f"{rotation_from_matrix}.outputY", f"{blend_colors_fleshy}.color1G")
        cmds.connectAttr(f"{rotation_from_matrix}.outputZ", f"{blend_colors_fleshy}.color1B")
        cmds.connectAttr(f"{rotation_from_matrix}.outputX", f"{blend_colors_corners}.color1R")
        cmds.connectAttr(f"{rotation_from_matrix}.outputY", f"{blend_colors_corners}.color1G")
        cmds.connectAttr(f"{rotation_from_matrix}.outputZ", f"{blend_colors_corners}.color1B")
        cmds.connectAttr(f"{self.eye_direct_ctl}.Fleshy", f"{blend_colors_fleshy}.blender")
        cmds.setAttr(f"{blend_colors_fleshy}.color2R", 0)
        cmds.setAttr(f"{blend_colors_fleshy}.color2G", 0)
        cmds.setAttr(f"{blend_colors_fleshy}.color2B", 0)
        cmds.setAttr(f"{blend_colors_corners}.color2R", 0)
        cmds.setAttr(f"{blend_colors_corners}.color2G", 0)
        cmds.setAttr(f"{blend_colors_corners}.color2B", 0)
        cmds.connectAttr(f"{multiply_fleshy}.output", f"{blend_colors_corners}.blender")

        compose_matrix = cmds.createNode("composeMatrix", name=f"{self.side}_fleshy_CM", ss=True)
        cmds.connectAttr(f"{blend_colors_fleshy}.output", f"{compose_matrix}.inputRotate")

        compose_matrix_corners = cmds.createNode("composeMatrix", name=f"{self.side}_fleshyCorners_CM", ss=True)
        cmds.connectAttr(f"{blend_colors_corners}.output", f"{compose_matrix_corners}.inputRotate")


        # primary_controller = [upper[0], upper[2], upper[-1], lower[2]]: los
        # índices 0 y 2 son las ESQUINAS de la boca (extremos del labio
        # superior) y usan el blend de esquinas; el resto, el fleshy normal.
        for i, ctl in enumerate(self.primary_controller):

            is_corner = i == 0 or i == 2

            mult_matrix_position = cmds.createNode("multMatrix", name=f"{self.side}_fleshyPosition_MMX", ss=True)
            cmds.connectAttr(f"{self.eye_aim_matrix}.outputMatrix", f"{mult_matrix_position}.matrixIn[0]")
            if is_corner:
                cmds.connectAttr(f"{compose_matrix_corners}.outputMatrix", f"{mult_matrix_position}.matrixIn[1]")
            else:
                cmds.connectAttr(f"{compose_matrix}.outputMatrix", f"{mult_matrix_position}.matrixIn[1]")

            ctl_connection = cmds.listConnections(f"{ctl}.offsetParentMatrix", plugs=True, source=True)[0]
            parent_matrix = cmds.createNode("parentMatrix", name=f"{self.side}_fleshyPosition_PMT", ss=True)
            cmds.connectAttr(ctl_connection, f"{parent_matrix}.inputMatrix")
            cmds.connectAttr(f"{mult_matrix_position}.matrixSum", f"{parent_matrix}.target[0].targetMatrix")
            cmds.setAttr(f"{parent_matrix}.target[0].offsetMatrix", matrix_manager.get_offset_matrix(ctl, f"{mult_matrix_position}.matrixSum"), type="matrix")

            mult_matrix_position_final = cmds.createNode("multMatrix", name=f"{self.side}_fleshyPositionFinal_MMX", ss=True)
            
            inverse_matrix_node = cmds.createNode("inverseMatrix", name=f"{self.side}_fleshyPositionFinal_INV", ss=True)
            cmds.connectAttr(ctl_connection, f"{inverse_matrix_node}.inputMatrix")
            cmds.connectAttr(f"{parent_matrix}.outputMatrix", f"{mult_matrix_position_final}.matrixIn[0]")
            cmds.connectAttr(f"{inverse_matrix_node}.outputMatrix", f"{mult_matrix_position_final}.matrixIn[1]")
            
            rotation_from_matrix_final = cmds.createNode("rotationFromMatrix", name=f"{self.side}_fleshyPositionFinal_RFM", ss=True)
            cmds.connectAttr(f"{mult_matrix_position_final}.matrixSum", f"{rotation_from_matrix_final}.input")
            cmds.connectAttr(f"{rotation_from_matrix_final}.output", f"{ctl.replace('GRP', 'OFF')}.rotate")
            cmds.connectAttr(f"{rotation_from_matrix_final}.output", f"{ctl.replace('_GRP', 'Local_JNT')}.rotate")
     
                

    def create_eye_surface(self):

        """
        NURBS surface esférica del tamaño del ojo, centrada en el ojo, sobre la que
        se proyectan las joints del párpado (flag `surface`). El radio = distancia
        media del centro del ojo a los CVs de las guías lineales del párpado (el
        borde del párpado descansa sobre el globo). Estática en el mismo espacio
        que las joints del párpado (mundo, bajo el module_trn), reference+oculta.
        """
        m = self.eye_guide_matrix
        center = om.MVector(m[12], m[13], m[14])
        cvs = cmds.ls(f"{self.linear_upper_curve}.cv[*]", fl=True) + cmds.ls(f"{self.linear_lower_curve}.cv[*]", fl=True)
        dists = [(om.MVector(*cmds.pointPosition(cv, w=True)) - center).length() for cv in cvs]
        radius = (sum(dists) / len(dists)) if dists else 1.0
        self.eye_radius = radius

        surf = cmds.sphere(radius=radius, ch=False, name=f"{self.side}_eyeSurface_NRB")[0]
        cmds.xform(surf, ws=True, t=(center.x, center.y, center.z))
        cmds.parent(surf, self.module_trn)
        cmds.setAttr(f"{surf}.overrideEnabled", 1)
        cmds.setAttr(f"{surf}.overrideDisplayType", 2)  # reference (visible para ajustar, no seleccionable)
        cmds.setAttr(f"{surf}.visibility", 0)
        self.lock_attributes(surf, ["tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz", "v"])
        self.eye_surface = surf
        self.eye_surface_shape = cmds.listRelatives(surf, shapes=True)[0]

        # --- Blink HORIZONTAL (aplanado al proyectar) ---
        # Al cerrar, la ALTURA (eje up del ojo, Y local) de las joints converge a un
        # nivel COMÚN -> la línea de cierre queda horizontal en el frame del ojo. El
        # nivel sigue a Blink_Height (entre el borde inferior y el superior). Se usan
        # los atributos del blink directamente (no se toca la cadena de blendShapes).
        self.eye_inv_matrix = list(om.MMatrix(self.eye_guide_matrix).inverse())
        inv = om.MMatrix(self.eye_guide_matrix).inverse()

        def _local_y_avg(curve):
            ys = [(om.MPoint(*cmds.pointPosition(c, w=True)) * inv).y for c in cmds.ls(f"{curve}.cv[*]", fl=True)]
            return sum(ys) / len(ys) if ys else 0.0

        up_y = _local_y_avg(self.linear_upper_curve)
        dn_y = _local_y_avg(self.linear_lower_curve)

        # flat_Y = dn_y + Blink_Height * (up_y - dn_y)
        fy_mul = cmds.createNode("multiply", name=f"{self.side}_blinkFlatY_MUL", ss=True)
        cmds.connectAttr(f"{self.eye_direct_ctl}.Blink_Height", f"{fy_mul}.input[0]")
        cmds.setAttr(f"{fy_mul}.input[1]", up_y - dn_y)
        fy_sum = cmds.createNode("sum", name=f"{self.side}_blinkFlatY_SUM", ss=True)
        cmds.connectAttr(f"{fy_mul}.output", f"{fy_sum}.input[0]")
        cmds.setAttr(f"{fy_sum}.input[1]", dn_y)
        self.blink_flat_y = f"{fy_sum}.output"

        # cantidad de cierre (0..1) por párpado: solo cerrar (Blink>0) aplana
        def _amount(attr, suffix):
            clamp_node = cmds.createNode("clamp", name=f"{self.side}_{suffix}BlinkAmount_CLP", ss=True)
            cmds.setAttr(f"{clamp_node}.minR", 0)
            cmds.setAttr(f"{clamp_node}.maxR", 1)
            cmds.connectAttr(f"{self.eye_direct_ctl}.{attr}", f"{clamp_node}.inputR")
            return f"{clamp_node}.outputR"

        self.upper_blink_amount = _amount("Upper_Blink", "upper")
        self.lower_blink_amount = _amount("Lower_Blink", "lower")

    def skinning_joints(self):

        """
        Output the skinning joints for the eyelid module, creating one for each vertex on the upper and lower eyelid curves.
        """

        self.upper_skin_joints = []
        self.lower_skin_joints = []

        upper_cvs = cmds.ls(f"{self.linear_upper_curve}.cv[*]", fl=True)
        lower_cvs = cmds.ls(f"{self.linear_lower_curve}.cv[*]", fl=True)

        skinning_jnts = []
        skinning_aims = []

        for i, cv in enumerate(upper_cvs + lower_cvs):

            cv_pos = cmds.xform(cv, q=True, t=True, ws=True)

            if cv in upper_cvs:
                name = "upper"
                parameter = self.getClosestParamToPosition(self.eyelid_up_curve_rebuild, cv_pos) # Get the closest parameter on the curve to the CV position
            else:
                name = "down"
                parameter = self.getClosestParamToPosition(self.eyelid_down_curve_rebuild, cv_pos) # Get the closest parameter on the curve to the CV position

            mtp = cmds.createNode("motionPath", name=f"{self.side}_{name}Eyelid0{i}_MTP", ss=True)
            four_by_four_matrix = cmds.createNode("fourByFourMatrix", name=f"{self.side}_{name}Eyelid0{i}_F4X4", ss=True)

            cmds.setAttr(f"{mtp}.uValue", parameter) # Set the parameter value
            # cmds.setAttr(f"{mtp}.fractionMode", 1) # Disable fraction mode
            

            if cv in upper_cvs:
                cmds.connectAttr(f"{self.eyelid_up_curve_rebuild}.worldSpace[0]", f"{mtp}.geometryPath")
            else:
                cmds.connectAttr(f"{self.eyelid_down_curve_rebuild}.worldSpace[0]", f"{mtp}.geometryPath")

            cmds.connectAttr(f"{mtp}.allCoordinates.xCoordinate", f"{four_by_four_matrix}.in30", f=True)
            cmds.connectAttr(f"{mtp}.allCoordinates.yCoordinate", f"{four_by_four_matrix}.in31", f=True)
            cmds.connectAttr(f"{mtp}.allCoordinates.zCoordinate", f"{four_by_four_matrix}.in32", f=True)

            if self.side == "R":
                float_constant = cmds.createNode("floatConstant", name=f"{self.side}_{name}Eyelid0{i}_FLC", ss=True)
                cmds.setAttr(f"{float_constant}.inFloat", -1) 
                cmds.connectAttr(f"{float_constant}.outFloat", f"{four_by_four_matrix}.in00") # -1 Scale X for mirroring

            parent_matrix = cmds.createNode("parentMatrix", name=f"{self.side}_{name}Eyelid0{i}_PMT", ss=True)
            four_by_four_matrix_origin = cmds.createNode("fourByFourMatrix", name=f"{self.side}_{name}Eyelid0{i}Origin_F4X4", ss=True)
            if cv in upper_cvs:
                cmds.connectAttr(f"{self.linear_upper_curve}.editPoints[{i}].xValueEp", f"{four_by_four_matrix_origin}.in30", f=True)
                cmds.connectAttr(f"{self.linear_upper_curve}.editPoints[{i}].yValueEp", f"{four_by_four_matrix_origin}.in31", f=True)
                cmds.connectAttr(f"{self.linear_upper_curve}.editPoints[{i}].zValueEp", f"{four_by_four_matrix_origin}.in32", f=True)
            else:
                cmds.connectAttr(f"{self.linear_lower_curve}.editPoints[{i - len(upper_cvs)}].xValueEp", f"{four_by_four_matrix_origin}.in30", f=True)
                cmds.connectAttr(f"{self.linear_lower_curve}.editPoints[{i - len(upper_cvs)}].yValueEp", f"{four_by_four_matrix_origin}.in31", f=True)
                cmds.connectAttr(f"{self.linear_lower_curve}.editPoints[{i - len(upper_cvs)}].zValueEp", f"{four_by_four_matrix_origin}.in32", f=True)

            if self.side == "R":
                cmds.connectAttr(f"{float_constant}.outFloat", f"{four_by_four_matrix_origin}.in00") # -1 Scale X for mirroring

            cmds.connectAttr(f"{four_by_four_matrix_origin}.output", f"{parent_matrix}.inputMatrix") # Connect the four by four matrix to the parent matrix input
            cmds.connectAttr(f"{four_by_four_matrix}.output", f"{parent_matrix}.target[0].targetMatrix") # Connect the origin four by four matrix to the parent matrix target

            temp_trn = cmds.createNode("transform", name=f"{self.side}_{name}Eyelid0{i}_TEMP", ss=True)
            cmds.connectAttr(f"{parent_matrix}.outputMatrix", f"{temp_trn}.offsetParentMatrix")
            if "upper" in name:
                skinning_jnt = cmds.createNode("joint", name=f"{self.side}_{name}Eyelid0{i}Skinning_JNT", ss=True, p=self.skeleton_grp)
            if "down" in name:
                skinning_jnt = cmds.createNode("joint", name=f"{self.side}_{name}Eyelid0{i-len(upper_cvs)}Skinning_JNT", ss=True, p=self.skeleton_grp)
            # cmds.connectAttr(f"{jnt}.worldMatrix[0]", f"{skinning_jnt}.offsetParentMatrix")
            if "upper" in name:
                node, ctl = curve_tool.create_controller(name=f"{self.side}_{name}Eyelid0{i}", offset=["GRP", "OFF"])
            if "down" in name:
                node, ctl = curve_tool.create_controller(name=f"{self.side}_{name}Eyelid0{i - len(upper_cvs)}", offset=["GRP", "OFF"])
            self.lock_attributes(ctl, ["sx", "sy", "sz", "v"])
            cmds.connectAttr(f"{parent_matrix}.outputMatrix", f"{node[0]}.offsetParentMatrix")

            mult_matrix_skin = cmds.createNode("multMatrix", name=f"{self.side}_{name}Eyelid0{i}Skinning_MMT", ss=True)
            cmds.connectAttr(f"{ctl}.matrix", f"{mult_matrix_skin}.matrixIn[0]")
            cmds.connectAttr(f"{parent_matrix}.outputMatrix", f"{mult_matrix_skin}.matrixIn[1]")
            cmds.connectAttr(f"{mult_matrix_skin}.matrixSum", f"{skinning_jnt}.offsetParentMatrix")
            four_by_four_matrix_temp = cmds.createNode("transform", name=f"{self.side}_{name}Eyelid0{i}_F4X4_TEMP", ss=True)
            cmds.connectAttr(f"{four_by_four_matrix_origin}.output", f"{four_by_four_matrix_temp}.offsetParentMatrix") # Connect the four by four matrix to the transform offset parent matrix
            cmds.parent(node[0], self.extra_controllers_grp)
            cmds.setAttr(f"{parent_matrix}.target[0].offsetMatrix", matrix_manager.get_offset_matrix(four_by_four_matrix_temp, temp_trn), type="matrix") # Calculate offset matrix between driven and driver
            cmds.delete(temp_trn)
            cmds.delete(four_by_four_matrix_temp)

            aim_matrix_final = cmds.createNode("aimMatrix", name=f"{self.side}_{name}Eyelid0{i}Skinning_AIM", ss=True)
            cmds.connectAttr(f"{mult_matrix_skin}.matrixSum", f"{aim_matrix_final}.inputMatrix")
            cmds.setAttr(f"{aim_matrix_final}.primaryTargetMatrix", self.eye_guide_matrix, type="matrix")
            
            cmds.setAttr(f"{aim_matrix_final}.primaryInputAxis", 0, 0, -1)

            if self.surface:
                # BLINK HORIZONTAL + sobre la esfera, todo en espacio LOCAL del ojo:
                # (a) aplana la ALTURA (Y local) hacia el nivel de cierre según el blink
                #     del párpado -> la línea de cierre queda horizontal en el frame.
                # (b) proyecta PRESERVANDO esa Y: lleva (X,Z) al círculo de la esfera a
                #     esa latitud (radio sqrt(r^2 - Y^2)), así queda sobre el globo Y
                #     horizontal (el closestPointOnSurface radial deshacía el aplanado).
                amount = self.upper_blink_amount if "upper" in name else self.lower_blink_amount
                to_local = cmds.createNode("multMatrix", name=f"{self.side}_{name}Eyelid0{i}Local_MMX", ss=True)
                cmds.connectAttr(f"{aim_matrix_final}.outputMatrix", f"{to_local}.matrixIn[0]")
                cmds.setAttr(f"{to_local}.matrixIn[1]", self.eye_inv_matrix, type="matrix")  # mundo -> local ojo
                loc_rfm = cmds.createNode("rowFromMatrix", name=f"{self.side}_{name}Eyelid0{i}Local_RFM", ss=True)
                cmds.setAttr(f"{loc_rfm}.input", 3)
                cmds.connectAttr(f"{to_local}.matrixSum", f"{loc_rfm}.matrix")
                flat_y = cmds.createNode("blendTwoAttr", name=f"{self.side}_{name}Eyelid0{i}FlatY_BTA", ss=True)
                cmds.connectAttr(f"{loc_rfm}.outputY", f"{flat_y}.input[0]")
                cmds.connectAttr(self.blink_flat_y, f"{flat_y}.input[1]")
                cmds.connectAttr(amount, f"{flat_y}.attributesBlender")
                # escala (X,Z) al círculo de radio sqrt(r^2 - Y^2) a esa latitud
                xsq = cmds.createNode("multiply", name=f"{self.side}_{name}Eyelid0{i}Xsq_MUL", ss=True)
                cmds.connectAttr(f"{loc_rfm}.outputX", f"{xsq}.input[0]"); cmds.connectAttr(f"{loc_rfm}.outputX", f"{xsq}.input[1]")
                zsq = cmds.createNode("multiply", name=f"{self.side}_{name}Eyelid0{i}Zsq_MUL", ss=True)
                cmds.connectAttr(f"{loc_rfm}.outputZ", f"{zsq}.input[0]"); cmds.connectAttr(f"{loc_rfm}.outputZ", f"{zsq}.input[1]")
                xzsq = cmds.createNode("sum", name=f"{self.side}_{name}Eyelid0{i}XZsq_SUM", ss=True)
                cmds.connectAttr(f"{xsq}.output", f"{xzsq}.input[0]"); cmds.connectAttr(f"{zsq}.output", f"{xzsq}.input[1]")
                xzlen = cmds.createNode("power", name=f"{self.side}_{name}Eyelid0{i}XZlen_POW", ss=True)
                cmds.connectAttr(f"{xzsq}.output", f"{xzlen}.input"); cmds.setAttr(f"{xzlen}.exponent", 0.5)
                ysq = cmds.createNode("multiply", name=f"{self.side}_{name}Eyelid0{i}Ysq_MUL", ss=True)
                cmds.connectAttr(f"{flat_y}.output", f"{ysq}.input[0]"); cmds.connectAttr(f"{flat_y}.output", f"{ysq}.input[1]")
                horizsq = cmds.createNode("subtract", name=f"{self.side}_{name}Eyelid0{i}Horizsq_SUB", ss=True)
                cmds.setAttr(f"{horizsq}.input1", self.eye_radius * self.eye_radius)
                cmds.connectAttr(f"{ysq}.output", f"{horizsq}.input2")
                horizmax = cmds.createNode("max", name=f"{self.side}_{name}Eyelid0{i}Horizmax_MAX", ss=True)
                cmds.connectAttr(f"{horizsq}.output", f"{horizmax}.input[0]"); cmds.setAttr(f"{horizmax}.input[1]", 0.0001)
                horiz = cmds.createNode("power", name=f"{self.side}_{name}Eyelid0{i}Horiz_POW", ss=True)
                cmds.connectAttr(f"{horizmax}.output", f"{horiz}.input"); cmds.setAttr(f"{horiz}.exponent", 0.5)
                scale_xz = cmds.createNode("divide", name=f"{self.side}_{name}Eyelid0{i}ScaleXZ_DIV", ss=True)
                cmds.connectAttr(f"{horiz}.output", f"{scale_xz}.input1"); cmds.connectAttr(f"{xzlen}.output", f"{scale_xz}.input2")
                xp = cmds.createNode("multiply", name=f"{self.side}_{name}Eyelid0{i}Xp_MUL", ss=True)
                cmds.connectAttr(f"{loc_rfm}.outputX", f"{xp}.input[0]"); cmds.connectAttr(f"{scale_xz}.output", f"{xp}.input[1]")
                zp = cmds.createNode("multiply", name=f"{self.side}_{name}Eyelid0{i}Zp_MUL", ss=True)
                cmds.connectAttr(f"{loc_rfm}.outputZ", f"{zp}.input[0]"); cmds.connectAttr(f"{scale_xz}.output", f"{zp}.input[1]")
                loc_fbf = cmds.createNode("fourByFourMatrix", name=f"{self.side}_{name}Eyelid0{i}LocalProj_F4X4", ss=True)
                cmds.connectAttr(f"{xp}.output", f"{loc_fbf}.in30")
                cmds.connectAttr(f"{flat_y}.output", f"{loc_fbf}.in31")
                cmds.connectAttr(f"{zp}.output", f"{loc_fbf}.in32")
                to_world = cmds.createNode("multMatrix", name=f"{self.side}_{name}Eyelid0{i}World_MMX", ss=True)
                cmds.connectAttr(f"{loc_fbf}.output", f"{to_world}.matrixIn[0]")
                cmds.setAttr(f"{to_world}.matrixIn[1]", self.eye_guide_matrix, type="matrix")  # local ojo -> mundo
                # posición proyectada + ORIENTACIÓN del aim (-Z al centro = normal)
                wpos_rfm = cmds.createNode("rowFromMatrix", name=f"{self.side}_{name}Eyelid0{i}Wpos_RFM", ss=True)
                cmds.setAttr(f"{wpos_rfm}.input", 3)
                cmds.connectAttr(f"{to_world}.matrixSum", f"{wpos_rfm}.matrix")
                proj_pos = cmds.createNode("fourByFourMatrix", name=f"{self.side}_{name}Eyelid0{i}ProjPos_F4X4", ss=True)
                for col, axis in enumerate("XYZ"):
                    cmds.connectAttr(f"{wpos_rfm}.output{axis}", f"{proj_pos}.in3{col}")
                proj_rot = cmds.createNode("pickMatrix", name=f"{self.side}_{name}Eyelid0{i}ProjRot_PMX", ss=True)
                cmds.connectAttr(f"{aim_matrix_final}.outputMatrix", f"{proj_rot}.inputMatrix")
                cmds.setAttr(f"{proj_rot}.useTranslate", 0)
                proj_mmx = cmds.createNode("multMatrix", name=f"{self.side}_{name}Eyelid0{i}Proj_MMX", ss=True)
                cmds.connectAttr(f"{proj_rot}.outputMatrix", f"{proj_mmx}.matrixIn[0]")
                cmds.connectAttr(f"{proj_pos}.output", f"{proj_mmx}.matrixIn[1]")
                cmds.connectAttr(f"{proj_mmx}.matrixSum", f"{skinning_jnt}.offsetParentMatrix", f=True)
            else:
                cmds.connectAttr(f"{aim_matrix_final}.outputMatrix", f"{skinning_jnt}.offsetParentMatrix", f=True)

            skinning_jnts.append(skinning_jnt)
            skinning_aims.append(aim_matrix_final)

        # for i, (jnt, aim) in enumerate(zip(skinning_jnts, skinning_aims)):

        #     if i == len(skinning_jnts) - 1 or i == (len(skinning_jnts) // 2) -1:
        #         if "upper" in jnt:
        #             name = "upper"
        #         else:
        #             name = "lower"
                    
        #         mpt_helper = cmds.createNode("motionPath", name=f"{self.side}_{name}EyelidEnd_AimHelper_MTP", ss=True)
        #         cmds.setAttr(f"{mpt_helper}.uValue", 0.95)
        #         cmds.connectAttr(f"{mpt_helper}.allCoordinates", f"{aim}.secondaryTargetVector")
        #         compose_matrix_helper = cmds.createNode("composeMatrix", name=f"{self.side}_{name}EyelidEndAimHelper_CM", ss=True)
        #         cmds.connectAttr(f"{mpt_helper}.allCoordinates", f"{compose_matrix_helper}.inputTranslate")
        #         cmds.connectAttr(f"{mpt_helper}.rotate", f"{compose_matrix_helper}.inputRotate")
        #         cmds.connectAttr(f"{compose_matrix_helper}.outputMatrix", f"{aim}.secondaryTargetMatrix")

        #         cmds.setAttr(f"{aim}.secondaryInputAxis", -1, 0, 0)
                
        #         if "upper" in jnt:
        #             cmds.connectAttr(f"{self.eyelid_down_curve_rebuild}.worldSpace[0]", f"{mpt_helper}.geometryPath")
        #         else:
        #             cmds.connectAttr(f"{self.eyelid_up_curve_rebuild}.worldSpace[0]", f"{mpt_helper}.geometryPath")
                
        #     else:
        #         cmds.connectAttr(f"{skinning_jnts[i+1]}.worldMatrix[0]", f"{aim}.secondaryTargetMatrix")

        #     cmds.connectAttr(f"{aim}.outputMatrix", f"{jnt}.offsetParentMatrix", f=True)
        

    def sockets(self):

        """
        Sockets for the eyelid module.
        """
        eyebrow_controller = data_manager.DataExportBiped().get_data("eyebrow_module", f"{self.side}_main_eyebrow_ctl")
        cmds.addAttr(eyebrow_controller, ln="Auto_Socket", at="float", min=0, max=1, dv=0, k=True)
        pair_blend = cmds.createNode("pairBlend", name=f"{self.side}_autoSocket_PBA", ss=True)
        cmds.connectAttr(f"{eyebrow_controller}.Auto_Socket", f"{pair_blend}.weight")
        cmds.connectAttr(f"{eyebrow_controller}.translate", f"{pair_blend}.inTranslate2")

        socket_names = [
            "upperSocket", "lowerSocket", "inSocket", "outSocket",
            "upInSocket", "upOutSocket", "downInSocket", "downOutSocket"
        ]

        # Fuente de las posiciones de los sockets: una CURVA-ANILLO {side}_socket_CRV
        # dibujada alrededor del ojo (como la guía de la ceja: cualquier número de
        # CVs, cualquier punto de inicio — cada socket se deriva por su ángulo
        # alrededor del centro), o las guías {side}_{name}_JNT una a una. Si no hay
        # ninguna de las dos, se omiten los sockets con un warning: el build sigue.
        from_curve = False
        socket_positions = {}
        crv = None
        try:
            res = guides_manager.get_guides(f"{self.side}_socket_CRVShape", parent=self.module_trn)
            if res and isinstance(res, str) and cmds.objExists(res):
                crv = res
        except Exception:
            crv = None

        if crv:
            from_curve = True
            socket_positions = socket_positions_from_ring(crv, self.side, socket_names)
            crv_tf = cmds.listRelatives(crv, parent=True, fullPath=True)
            cmds.delete(crv_tf[0] if crv_tf else crv)
        else:
            missing = []
            for name in socket_names:
                cmds.select(cl=True)
                guides_manager.get_guides(guide_export=f"{self.side}_{name}_JNT")
                if cmds.objExists(f"{self.side}_{name}_JNT"):
                    socket_positions[name] = cmds.xform(f"{self.side}_{name}_JNT", q=True, ws=True, t=True)
                else:
                    missing.append(f"{self.side}_{name}_JNT")

            if missing:
                for name in socket_names:  # limpiar las guías que sí se importaron
                    if cmds.objExists(f"{self.side}_{name}_JNT"):
                        cmds.delete(f"{self.side}_{name}_JNT")
                om.MGlobal.displayWarning(
                    f"{self.side} eyelid: sin guía {self.side}_socket_CRV y faltan {missing}: se omiten los sockets.")
                return None
        cmds.select(cl=True)

        def socket_matrix(name):
            # Matriz de guía del socket: desde la curva (posición + escala X en R) o
            # desde la guía JNT (matriz de mundo completa).
            if from_curve:
                p = socket_positions[name]
                sx = -1.0 if self.side == "R" else 1.0
                return om.MMatrix([sx, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, p[0], p[1], p[2], 1])
            return om.MMatrix(cmds.getAttr(f"{self.side}_{name}_JNT.worldMatrix[0]"))

        main_sockets = cmds.createNode("transform", name=f"{self.side}_mainEyelidSockets_GRP", ss=True, p=self.controllers_grp)
        cmds.setAttr(f"{main_sockets}.offsetParentMatrix", list(om.MMatrix(self.head_guide_matrix).inverse()), type="matrix")
        main_condition = cmds.createNode("condition", name=f"{self.side}_mainEyelidSockets_COND", ss=True)
        cmds.setAttr(f"{main_condition}.operation", 3)  # Equal
        cmds.setAttr(f"{main_condition}.secondTerm", 1)
        cmds.setAttr(f"{main_condition}.colorIfTrueR", 1)
        cmds.setAttr(f"{main_condition}.colorIfFalseR", 0)
        cmds.connectAttr(f"{self.face_ctl}.Sockets", f"{main_condition}.firstTerm")
        cmds.connectAttr(f"{main_condition}.outColorR", f"{main_sockets}.visibility", f=True)
        secondary_sockets = cmds.createNode("transform", name=f"{self.side}_secondaryEyelidSockets_GRP", ss=True, p=self.controllers_grp)
        secondary_condition = cmds.createNode("condition", name=f"{self.side}_secondaryEyelidSockets_COND", ss=True)
        cmds.setAttr(f"{secondary_condition}.operation", 3)  # Equal
        cmds.setAttr(f"{secondary_condition}.secondTerm", 2)
        cmds.setAttr(f"{secondary_condition}.colorIfTrueR", 1)
        cmds.setAttr(f"{secondary_condition}.colorIfFalseR", 0)
        cmds.connectAttr(f"{self.face_ctl}.Sockets", f"{secondary_condition}.firstTerm")
        cmds.connectAttr(f"{secondary_condition}.outColorR", f"{secondary_sockets}.visibility", f=True)
        cmds.setAttr(f"{secondary_sockets}.offsetParentMatrix", list(om.MMatrix(self.head_guide_matrix).inverse()), type="matrix")

        socket_logic = {
            "upperSocket": ("upInSocket", "upOutSocket"),
            "lowerSocket": ("downInSocket", "downOutSocket"),
            "inSocket": ("upInSocket", "downInSocket"),
            "outSocket": ("upOutSocket", "downOutSocket")
        }

        socket_main_controllers = []
        driver_ctls_cache = {}
        driver_guide_matrices = {}

        for socket, (driver1, driver2) in socket_logic.items():

            parent_name = f"{self.side}_{socket}"
            # Posición del socket (de la curva o de la guía JNT), matriz posición + escala X en R
            socket_pos = socket_positions[socket]
            scale_x = -1.0 if self.side == "R" else 1.0
            parent_guide_matrix = [scale_x, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, socket_pos[0], socket_pos[1], socket_pos[2], 1]

            parent_nodes, parent_ctl = curve_tool.create_controller(
                name=parent_name, offset=["GRP", "OFF"], parent=main_sockets
            )
            cmds.setAttr(f"{parent_nodes[0]}.offsetParentMatrix", parent_guide_matrix, type="matrix")
            socket_main_controllers.append(parent_ctl)

            if "upperSocket" in socket:
                cmds.connectAttr(f"{pair_blend}.outTranslate", f"{parent_nodes[1]}.translate")
            

            parent_skinning_jnt = cmds.createNode(
                "joint", name=f"{parent_name}Skinning_JNT", ss=True, p=self.skeleton_grp
            )
            parent_mult_matrix = cmds.createNode(
                "multMatrix", name=f"{parent_name}_MMX", ss=True
            )
            parent_wm = cmds.getAttr(f"{parent_ctl}.worldMatrix[0]")
            cmds.connectAttr(f"{parent_ctl}.worldMatrix[0]", f"{parent_mult_matrix}.matrixIn[0]")
            cmds.connectAttr(f"{parent_nodes[0]}.worldInverseMatrix[0]", f"{parent_mult_matrix}.matrixIn[1]")
            cmds.setAttr(f"{parent_mult_matrix}.matrixIn[2]", parent_wm, type="matrix")
            cmds.connectAttr(f"{parent_mult_matrix}.matrixSum", f"{parent_skinning_jnt}.offsetParentMatrix")

            cmds.xform(parent_nodes[0], m=om.MMatrix.kIdentity)
            cmds.xform(parent_skinning_jnt, m=om.MMatrix.kIdentity)

            for driver in (driver1, driver2):

                driver_name = f"{self.side}_{driver}"

                if driver_name not in driver_ctls_cache:

                    # Matriz de guía del driver (curva o JNT)
                    driver_guide_matrices[driver_name] = socket_matrix(driver)

                    driver_nodes, driver_ctl = curve_tool.create_controller(
                        name=driver_name, offset=["GRP", "OFF"], parent=secondary_sockets
                    )

                    wam = cmds.createNode("wtAddMatrix", name=f"{driver_name}_WAM", ss=True)
                    cmds.connectAttr(f"{wam}.matrixSum", f"{driver_nodes[0]}.offsetParentMatrix")

                    driver_skinning_jnt = cmds.createNode(
                        "joint", name=f"{driver_name}Skinning_JNT", ss=True, p=self.skeleton_grp
                    )
                    wam_jnt = cmds.createNode("wtAddMatrix", name=f"{driver_name}_jnt_WAM", ss=True)
                    cmds.connectAttr(f"{wam_jnt}.matrixSum", f"{driver_skinning_jnt}.offsetParentMatrix")

                    driver_ctls_cache[driver_name] = (driver_ctl, driver_nodes, wam, wam_jnt, driver_skinning_jnt)

                driver_ctl, driver_nodes, wam, wam_jnt, driver_skinning_jnt = driver_ctls_cache[driver_name]

                offset_matrix = list(
                    driver_guide_matrices[driver_name]
                    * om.MMatrix(cmds.getAttr(f"{parent_mult_matrix}.matrixSum")).inverse()
                )

                if not cmds.listConnections(f"{wam}.wtMatrix[0].matrixIn", source=True, destination=False):
                    idx = 0
                else:
                    idx = 1

                parent_offset_mmx = cmds.createNode("multMatrix", name=f"{driver_name}_p{idx}_OFX", ss=True)
                cmds.setAttr(f"{parent_offset_mmx}.matrixIn[0]", offset_matrix, type="matrix")
                cmds.connectAttr(f"{parent_mult_matrix}.matrixSum", f"{parent_offset_mmx}.matrixIn[1]")
                cmds.connectAttr(f"{parent_offset_mmx}.matrixSum", f"{wam}.wtMatrix[{idx}].matrixIn")
                cmds.setAttr(f"{wam}.wtMatrix[{idx}].weightIn", 0.5)
                cmds.connectAttr(f"{parent_offset_mmx}.matrixSum", f"{wam_jnt}.wtMatrix[{idx}].matrixIn")
                cmds.setAttr(f"{wam_jnt}.wtMatrix[{idx}].weightIn", 0.5)

                cmds.xform(driver_nodes[0], m=om.MMatrix.kIdentity)
                cmds.xform(driver_skinning_jnt, m=om.MMatrix.kIdentity)

        if not from_curve:
            for name in socket_names:
                if cmds.objExists(f"{self.side}_{name}_JNT"):
                    cmds.delete(f"{self.side}_{name}_JNT")

        return socket_main_controllers

    def getClosestParamToPosition(self, curve, position):
        """
        Returns the closest parameter (u) on the given NURBS curve to a world-space position.
        
        Args:
            curve (str or MObject or MDagPath): The curve to evaluate.
            position (list or tuple): A 3D world-space position [x, y, z].

        Returns:
            float: The parameter (u) value on the curve closest to the given position.
        """
        if isinstance(curve, str):
            sel = om.MSelectionList()
            sel.add(curve)
            curve_dag_path = sel.getDagPath(0)
        elif isinstance(curve, om.MObject):
            curve_dag_path = om.MDagPath.getAPathTo(curve)
        elif isinstance(curve, om.MDagPath):
            curve_dag_path = curve
        else:
            raise TypeError("Curve must be a string name, MObject, or MDagPath.")

        curve_fn = om.MFnNurbsCurve(curve_dag_path)

        point = om.MPoint(*position)

        closest_point, paramU = curve_fn.closestPoint(point, space=om.MSpace.kWorld)

        return paramU


    def constraints_callback(self, guide, driven, drivers=[], local_jnt=None):

        """
        Create a parent constraint between a driven object and multiple driver objects with equal weights.
        Args:
            driven (str): The name of the driven object.
            drivers (list): A list of driver objects.
        """
        driven_ctl = driven.replace("GRP", "CTL")
        suffix = driven.split("_")[-1]
        parent_matrix = cmds.createNode("parentMatrix", name=driven.replace(suffix, "PMT"), ss=True)
        cmds.connectAttr(guide, f"{parent_matrix}.inputMatrix")
        cmds.connectAttr(f"{drivers[0]}.worldMatrix[0]", f"{parent_matrix}.target[0].targetMatrix")
        cmds.connectAttr(f"{drivers[1]}.worldMatrix[0]", f"{parent_matrix}.target[1].targetMatrix")
        cmds.connectAttr(f"{parent_matrix}.outputMatrix", f"{driven}.offsetParentMatrix", force=True)
        cmds.setAttr(f"{parent_matrix}.target[0].weight", 0.7) # Up or Down controllers have more influence
        cmds.setAttr(f"{parent_matrix}.target[1].weight", 0.3) # In or Out controllers have less influence

        cmds.setAttr(f"{driven}.inheritsTransform", 0)
        guide_trn_temp = cmds.createNode("transform", name="temp_TRN", ss=True)
        cmds.connectAttr(guide, f"{guide_trn_temp}.offsetParentMatrix")
        cmds.setAttr(f"{parent_matrix}.target[0].offsetMatrix", matrix_manager.get_offset_matrix(guide_trn_temp, drivers[0]), type="matrix") # Calculate offset matrix between driven and driver
        cmds.setAttr(f"{parent_matrix}.target[1].offsetMatrix", matrix_manager.get_offset_matrix(guide_trn_temp, drivers[1]), type="matrix") # Calculate offset matrix between driven and driver
        
        cmds.xform(driven, m=om.MMatrix.kIdentity)
        cmds.delete(guide_trn_temp)

        return parent_matrix
    
    def local_constraints_callback(self, driven_jnt, drivers=[]):

        """
        Create a parent constraint between a driven object and multiple driver objects with equal weights.
        Args:
            driven_jnt (str): The name of the driven object.
            drivers (list): A list of driver objects. Driver[0] == 0.7 weight, Driver[1] == 0.3 weight
        """
        driven_ctl = driven_jnt.replace("Local_MMX", "_CTL")

        mult_matrix = cmds.createNode("multMatrix", name=driven_jnt.replace("MMX", "MMT"), ss=True)

        compose_matrix_00 = cmds.createNode("composeMatrix", name=driven_jnt.replace("00_MMX", "00_CMT"), ss=True)
        compose_matrix_01 = cmds.createNode("composeMatrix", name=driven_jnt.replace("01_MMX", "01_CMT"), ss=True)

        # One scalar multiply per axis: driver rotate/translate channel * weight -> compose matrix
        compose_matrices = [compose_matrix_00, compose_matrix_01]
        weights = [0.7, 0.3]
        for driver, compose_matrix, weight in zip(drivers, compose_matrices, weights):
            for channel, label, compose_attr in (("rotate", "Rotation", "inputRotate"), ("translate", "Translation", "inputTranslate")):
                for axis in "XYZ":
                    mult = cmds.createNode("multiply", name=driver.replace("_CTL", f"{label}00{axis}_MUL"), ss=True)
                    cmds.connectAttr(f"{driver}.{channel}{axis}", f"{mult}.input[0]")
                    cmds.setAttr(f"{mult}.input[1]", weight)
                    cmds.connectAttr(f"{mult}.output", f"{compose_matrix}.{compose_attr}{axis}")
        cmds.connectAttr(f"{driven_ctl}.matrix", f"{mult_matrix}.matrixIn[0]") # Connect driven controller matrix to mult matrix
        cmds.connectAttr(f"{compose_matrix_00}.outputMatrix", f"{mult_matrix}.matrixIn[1]") # Connect compose matrix 0.7 to mult matrix
        cmds.connectAttr(f"{compose_matrix_01}.outputMatrix", f"{mult_matrix}.matrixIn[2]") # Connect compose matrix 0.3 to mult matrix
        cmds.connectAttr(f"{mult_matrix}.matrixSum", f"{driven_jnt}.matrixIn[0]", force=True)

            

