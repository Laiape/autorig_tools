import maya.cmds as cmds
import maya.api.OpenMaya as om
from importlib import reload
import os
import math

from maya_tools.scripts.utils import data_manager
from maya_tools.scripts.utils import guides_manager
from maya_tools.scripts.utils import curve_tool
from maya_tools.scripts.utils import matrix_manager
from maya_tools.scripts.utils import ribbon

reload(data_manager)
reload(guides_manager)
reload(curve_tool)
reload(matrix_manager)
reload(ribbon)

class NeckModule(object):

    def __init__(self):

        """
        Initialize the neckModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExportBiped().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExportBiped().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExportBiped().get_data("basic_structure", "masterwalk_ctl")
        self.preferences_ctl = data_manager.DataExportBiped().get_data("basic_structure", "preferences_ctl")

    def make(self, side, skinning_joints_number, controllers_number, mGear_integration=False):

        """ 
        Create the neck module structure and controllers. Call this method with the side ('L' or 'R') to create the respective neck module.
        Args:
            side (str): The side of the neck ('L' or 'R').

        """
        self.side = side
        
        self.module_trn = cmds.createNode("transform", name=f"{self.side}_neckModule_GRP", ss=True, p=self.modules)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.side}_neckControllers_GRP", ss=True, p=self.masterwalk_ctl)
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.side}_neckSkinning_GRP", ss=True, p=self.skel_grp)
        self.mGear_integration_ = mGear_integration
        
        self.load_guides()

        if mGear_integration:
            self.mGear_integration()
            self.mGear = True
            # Store data for later use
            data_manager.DataExportBiped().append_data("neck_module",
                            {
                                "head_ctl": self.head_ctl,
                                "head_skinning_jnt": None,
                                "face_ctl": self.face_ctl,
                                "head_guide_matrix": self.head_guide_matrix,
                                "mGear": self.mGear,
                            })
            
        else:
            self.controller_creation()
            self.neck_stretch_setup()
            self.ribbon_setup(skinning_joints_number)
            self.local_head()
            self.head_squash_setup()

            # Store data for later use
            data_manager.DataExportBiped().append_data("neck_module",
                            {
                                "head_ctl": self.neck_ctls[-1],
                                "head_skinning_jnt": self.head_skinning_jnt,
                                "neck_ctl": self.neck_ctls[0],
                                "head_guide_matrix": self.head_guide_matrix,
                                "face_ctl": self.face_ctl,
                                "head_squash_ctl": self.head_squash_ctl,
                                "face_controls_parent": self.face_controls_parent,
                            })
            # Clean up and store data
            # if cmds.objExists(self.throat_guide[0]):
            #     cmds.delete(self.throat_guide)
   

    def load_guides(self):

        """
        Load the neck guides for the specified side and parent them to the module transform.
        """

        self.neck_chain = guides_manager.get_guides(f"{self.side}_neck00_JNT", parent=self.module_trn)
        cmds.select(clear=True)

        cmds.select(clear=True)
        # Matrices horneadas de las guías (estáticas) en lugar de transforms _GUIDE vivos
        self.neck_guide_matrix = cmds.getAttr(f"{self.neck_chain[0]}.worldMatrix[0]")
        self.head_guide_matrix = cmds.getAttr(f"{self.neck_chain[-1]}.worldMatrix[0]")
       

    def controller_creation(self):

        """
        Create controllers for the neck module.
        """

        self.neck_nodes = []
        self.neck_ctls = []

        face_nodes, self.face_ctl = curve_tool.create_controller(name=f"{self.side}_face", offset=["GRP", "ANM"])
        # Facial modules follow this stationary offset, not the squash driver's TY.
        self.face_controls_parent = face_nodes[-1]
        curve_tool.lock_attributes(self.face_ctl, ["tx", "tz", "rx", "ry", "rz", "sx", "sy", "sz", "v"])
        cmds.addAttr(self.face_ctl, longName="FACE_VIS", niceName="FACE VISIBILITY ------", attributeType="enum", enumName="------")
        cmds.setAttr(f"{self.face_ctl}.FACE_VIS", lock=True, keyable=False, channelBox=True)
        
        for i, jnt in enumerate(self.neck_chain):

            if i == 0:

                corner_nodes, corner_ctl = curve_tool.create_controller(name=f"{self.side}_neck", offset=["GRP"])
                cmds.connectAttr(f"{corner_ctl}.worldMatrix[0]", f"{jnt}.offsetParentMatrix")
                
            if i == len(self.neck_chain) - 1:

                corner_nodes, corner_ctl = curve_tool.create_controller(name=f"{self.side}_head", offset=["GRP"])
                cmds.parent(face_nodes[0], corner_ctl)
                cmds.matchTransform(face_nodes[0], corner_ctl, pos=True, rot=True)

            if i == 0 or i == len(self.neck_chain) - 1:

                
                if i == len(self.neck_chain) - 1:
                    cmds.setAttr(f"{corner_nodes[0]}.offsetParentMatrix", self.head_guide_matrix, type="matrix")
                    cmds.xform(corner_nodes[0], m=om.MMatrix.kIdentity)
                else:
                    cmds.setAttr(f"{corner_nodes[0]}.offsetParentMatrix", self.neck_guide_matrix, type="matrix")
                    cmds.xform(corner_nodes[0], m=om.MMatrix.kIdentity)
                cmds.parent(corner_nodes[0], self.controllers_grp)
                
                self.neck_nodes.append(corner_nodes[0])
                self.neck_ctls.append(corner_ctl)


        cmds.xform(self.neck_chain[0], m=om.MMatrix.kIdentity)
        for i , ctl in enumerate(self.neck_ctls):
            curve_tool.lock_attributes(ctl, ["sx", "sy", "sz", "v"])

        # throat_nodes, throat_ctl = curve_tool.create_controller(name=f"{self.side}_throat", offset=["GRP"], parent=self.neck_ctls[0])
        # curve_tool.lock_attributes(throat_ctl, ["sx", "sy", "sz", "v"])
        # cmds.matchTransform(throat_nodes[0], self.throat_guide[0], pos=True, rot=True, scl=False)
        # skin_throat_jnt = cmds.createNode("joint", name=f"{self.side}_throatSkinning_JNT", ss=True, p=self.skeleton_grp)
        # cmds.connectAttr(f"{throat_ctl}.matrix", f"{skin_throat_jnt}.offsetParentMatrix")
        # cmds.matchTransform(skin_throat_jnt, self.throat_guide[0], pos=True, rot=True, scl=False)
    


    def ribbon_setup(self, skinning_joints_number):

        """
        Set up the ribbon for the neck module.
        """
        sel = (self.neck_ctls[0], self.neck_stretch_driver)
        self.output_joints, temp = ribbon.de_boor_ribbon(sel, name=f"{self.side}_neckSkinning", aim_axis="y", up_axis="z", skeleton_grp=self.skeleton_grp, num_joints=skinning_joints_number) # Do the ribbon setup, with the created controllers

        for t in temp:
            cmds.delete(t)

        for jnt in self.output_joints:
            cmds.setAttr(f"{jnt}.inheritsTransform", 1)
        self.neck_squash_setup()

    def neck_stretch_setup(self):
        """Bound ribbon length in neck-base space, independent of global scale."""
        ctl = self.neck_ctls[0]
        cmds.addAttr(ctl, ln="neckStretchSep", nn="STRETCH ------", at="enum", en="------")
        cmds.setAttr(f"{ctl}.neckStretchSep", lock=True, channelBox=True)
        for name, label, default, minimum, maximum in (
                ("neckStretch", "Auto Stretch", 1, 0, 1),
                ("neckStretchMin", "Stretch Min", 0.8, 0.01, 1),
                ("neckStretchMax", "Stretch Max", 1.2, 1, None)):
            options = {"ln": name, "nn": label, "at": "double", "dv": default, "min": minimum, "k": True}
            if maximum is not None:
                options["max"] = maximum
            cmds.addAttr(ctl, **options)
        rest = om.MMatrix(self.head_guide_matrix) * om.MMatrix(self.neck_guide_matrix).inverse()
        rest_length = max(0.001, om.MVector(rest[12], rest[13], rest[14]).length())
        local = cmds.createNode("multMatrix", name=f"{self.side}_neckHeadLocal_MMX", ss=True)
        cmds.connectAttr(f"{self.neck_ctls[-1]}.worldMatrix[0]", f"{local}.matrixIn[0]")
        cmds.connectAttr(f"{ctl}.worldInverseMatrix[0]", f"{local}.matrixIn[1]")
        row = cmds.createNode("rowFromMatrix", name=f"{self.side}_neckHeadLocal_RFM", ss=True)
        cmds.setAttr(f"{row}.input", 3)
        cmds.connectAttr(f"{local}.matrixSum", f"{row}.matrix")
        length = cmds.createNode("length", name=f"{self.side}_neckLength_LEN", ss=True)
        for axis in "XYZ":
            cmds.connectAttr(f"{row}.output{axis}", f"{length}.input{axis}")
        safe_length = cmds.createNode("max", name=f"{self.side}_neckLength_MAX", ss=True)
        cmds.connectAttr(f"{length}.output", f"{safe_length}.input[0]")
        cmds.setAttr(f"{safe_length}.input[1]", 0.0001)
        ratio = cmds.createNode("divide", name=f"{self.side}_neckStretchFactor_DIV", ss=True)
        cmds.connectAttr(f"{safe_length}.output", f"{ratio}.input1")
        cmds.setAttr(f"{ratio}.input2", rest_length)
        limit = cmds.createNode("clamp", name=f"{self.side}_neckStretch_CLAMP", ss=True)
        cmds.connectAttr(f"{ratio}.output", f"{limit}.inputR")
        cmds.connectAttr(f"{ctl}.neckStretchMin", f"{limit}.minR")
        cmds.connectAttr(f"{ctl}.neckStretchMax", f"{limit}.maxR")
        blend = cmds.createNode("blendTwoAttr", name=f"{self.side}_neckStretch_BTA", ss=True)
        cmds.setAttr(f"{blend}.input[0]", 1)
        cmds.connectAttr(f"{limit}.outputR", f"{blend}.input[1]")
        cmds.connectAttr(f"{ctl}.neckStretch", f"{blend}.attributesBlender")
        self.neck_stretch_factor = f"{blend}.output"
        point_scale = cmds.createNode("divide", name=f"{self.side}_neckEndpointScale_DIV", ss=True)
        cmds.connectAttr(self.neck_stretch_factor, f"{point_scale}.input1")
        cmds.connectAttr(f"{ratio}.output", f"{point_scale}.input2")
        endpoint = cmds.createNode("fourByFourMatrix", name=f"{self.side}_neckEndpoint_FBF", ss=True)
        for col, axis in enumerate("XYZ"):
            scaled = cmds.createNode("multiply", name=f"{self.side}_neckEndpoint{axis}_MUL", ss=True)
            cmds.connectAttr(f"{row}.output{axis}", f"{scaled}.input[0]")
            cmds.connectAttr(f"{point_scale}.output", f"{scaled}.input[1]")
            cmds.connectAttr(f"{scaled}.output", f"{endpoint}.in3{col}")
        world = cmds.createNode("multMatrix", name=f"{self.side}_neckEndpointWorld_MMX", ss=True)
        cmds.connectAttr(f"{endpoint}.output", f"{world}.matrixIn[0]")
        cmds.connectAttr(f"{ctl}.worldMatrix[0]", f"{world}.matrixIn[1]")
        position = cmds.createNode("pickMatrix", name=f"{self.side}_neckEndpointPosition_PMX", ss=True)
        cmds.connectAttr(f"{world}.matrixSum", f"{position}.inputMatrix")
        for attr in ("useRotate", "useScale", "useShear"):
            cmds.setAttr(f"{position}.{attr}", 0)
        orientation = cmds.createNode("pickMatrix", name=f"{self.side}_neckHeadOrientation_PMX", ss=True)
        cmds.connectAttr(f"{self.neck_ctls[-1]}.worldMatrix[0]", f"{orientation}.inputMatrix")
        cmds.setAttr(f"{orientation}.useTranslate", 0)
        driver_matrix = cmds.createNode("multMatrix", name=f"{self.side}_neckStretchDriver_MMX", ss=True)
        cmds.connectAttr(f"{orientation}.outputMatrix", f"{driver_matrix}.matrixIn[0]")
        cmds.connectAttr(f"{position}.outputMatrix", f"{driver_matrix}.matrixIn[1]")
        self.neck_stretch_driver = cmds.createNode("transform", name=f"{self.side}_neckStretchDriver_TRN", ss=True, p=self.module_trn)
        cmds.setAttr(f"{self.neck_stretch_driver}.inheritsTransform", 0)
        cmds.connectAttr(f"{driver_matrix}.matrixSum", f"{self.neck_stretch_driver}.offsetParentMatrix")
        cmds.setAttr(f"{self.neck_stretch_driver}.hiddenInOutliner", 1)
        # Facial controls follow the same bounded endpoint as head skinning,
        # including when the animated head target exceeds the stretch limits.
        face_root = cmds.listRelatives(self.face_controls_parent, parent=True)[0]
        face_follow = cmds.createNode("multMatrix", name=f"{self.side}_neckFaceFollow_MMX", ss=True)
        cmds.connectAttr(f"{self.neck_stretch_driver}.worldMatrix[0]", f"{face_follow}.matrixIn[0]")
        cmds.connectAttr(f"{self.neck_ctls[-1]}.worldInverseMatrix[0]", f"{face_follow}.matrixIn[1]")
        cmds.connectAttr(f"{face_follow}.matrixSum", f"{face_root}.offsetParentMatrix")

    def neck_squash_setup(self):
        """Compensate X/Z volume without scaling the independent head joint."""
        ctl = self.neck_ctls[0]
        cmds.addAttr(ctl, ln="neckSquashSep", nn="SQUASH ------", at="enum", en="------")
        cmds.setAttr(f"{ctl}.neckSquashSep", lock=True, channelBox=True)
        for name, label, default in (("volumePreservation", "Auto Squash", 1),
                                     ("neckFalloff", "Falloff", 0),
                                     ("neckSquashMaxPos", "Max Pos", 0.5)):
            cmds.addAttr(ctl, ln=name, nn=label, at="double", min=0, max=1, dv=default, k=True)
        for index, joint in enumerate(self.output_joints):
            name = f"{self.side}_neckVolume{index:02d}"
            profile = cmds.createNode("remapValue", name=f"{name}Profile_RMV", ss=True)
            cmds.setAttr(f"{profile}.inputValue", index / max(1, len(self.output_joints) - 1))
            for point, value in enumerate((0, 1, 0)):
                cmds.setAttr(f"{profile}.value[{point}].value_FloatValue", value)
                cmds.setAttr(f"{profile}.value[{point}].value_Interp", 2)
            cmds.connectAttr(f"{ctl}.neckSquashMaxPos", f"{profile}.value[1].value_Position")
            cmds.setAttr(f"{profile}.value[2].value_Position", 1)
            falloff = cmds.createNode("blendTwoAttr", name=f"{name}Falloff_BTA", ss=True)
            cmds.setAttr(f"{falloff}.input[0]", 1)
            cmds.connectAttr(f"{profile}.outValue", f"{falloff}.input[1]")
            cmds.connectAttr(f"{ctl}.neckFalloff", f"{falloff}.attributesBlender")
            exponent = cmds.createNode("multiplyDivide", name=f"{name}Exponent_MD", ss=True)
            cmds.connectAttr(f"{falloff}.output", f"{exponent}.input1X")
            cmds.connectAttr(f"{ctl}.volumePreservation", f"{exponent}.input2X")
            negative = cmds.createNode("multiply", name=f"{name}Exponent_MUL", ss=True)
            cmds.connectAttr(f"{exponent}.outputX", f"{negative}.input[0]")
            cmds.setAttr(f"{negative}.input[1]", -0.5)
            volume = cmds.createNode("power", name=f"{name}_POW", ss=True)
            cmds.connectAttr(self.neck_stretch_factor, f"{volume}.input")
            cmds.connectAttr(f"{negative}.output", f"{volume}.exponent")
            cmds.connectAttr(self.neck_stretch_factor, f"{joint}.scaleY")
            for axis in "XZ":
                cmds.connectAttr(f"{volume}.output", f"{joint}.scale{axis}")

    
    def local_head(self):

        """
        Create the local head setup to have the head follow the neck's movement.
        """


        head_skinning_jnt = cmds.createNode("joint", name=f"{self.side}_headSkinning_JNT", ss=True, p=self.skeleton_grp)
        cmds.setAttr(f"{head_skinning_jnt}.inheritsTransform", 0)
        self.head_skinning_jnt = head_skinning_jnt

        # rowFromMatrix + fourByFourMatrix, behaviour-preserving: rows 0-2 are the
        # head ctl rotation rows NORMALIZED (drop the ctl scale, like the rotation
        # decompose did) and rescaled with the output joint row lengths (= its
        # outputScale); row 3 is the output joint translation.
        four_by_four = cmds.createNode("fourByFourMatrix", name=f"{self.side}_head_FBF")
        row_translation = cmds.createNode("rowFromMatrix", name=f"{self.side}_headTranslation_RFM")
        cmds.setAttr(f"{row_translation}.input", 3)
        cmds.connectAttr(f"{self.output_joints[-1]}.worldMatrix[0]", f"{row_translation}.matrix")
        for col_index, axis in enumerate("XYZ"):
            cmds.connectAttr(f"{row_translation}.output{axis}", f"{four_by_four}.in3{col_index}")

        for row_index in range(3):
            row_rotation = cmds.createNode("rowFromMatrix", name=f"{self.side}_headRotation0{row_index}_RFM")
            cmds.setAttr(f"{row_rotation}.input", row_index)
            cmds.connectAttr(f"{self.neck_ctls[-1]}.worldMatrix[0]", f"{row_rotation}.matrix")
            normalize_row = cmds.createNode("normalize", name=f"{self.side}_headRotation0{row_index}_NRM")

            row_scale = cmds.createNode("rowFromMatrix", name=f"{self.side}_headScale0{row_index}_RFM")
            cmds.setAttr(f"{row_scale}.input", row_index)
            # Keep the head's original driver/global scale; neck volume and
            # longitudinal compensation belong only to the neck influences.
            cmds.connectAttr(f"{self.neck_ctls[-1]}.worldMatrix[0]", f"{row_scale}.matrix")
            scale_length = cmds.createNode("length", name=f"{self.side}_headScale0{row_index}_LEN")

            for axis in "XYZ":
                cmds.connectAttr(f"{row_rotation}.output{axis}", f"{normalize_row}.input{axis}")
                cmds.connectAttr(f"{row_scale}.output{axis}", f"{scale_length}.input{axis}")

            for col_index, axis in enumerate("XYZ"):
                mult = cmds.createNode("multiply", name=f"{self.side}_headRow{row_index}{axis}_MUL")
                cmds.connectAttr(f"{normalize_row}.output{axis}", f"{mult}.input[0]")
                cmds.connectAttr(f"{scale_length}.output", f"{mult}.input[1]")
                cmds.connectAttr(f"{mult}.output", f"{four_by_four}.in{row_index}{col_index}")

        cmds.connectAttr(f"{four_by_four}.output", f"{head_skinning_jnt}.offsetParentMatrix")

        cmds.matchTransform(f"{self.neck_nodes[-1]}", self.neck_chain[-1], pos=True, rot=True, scl=False)
        cmds.delete(self.neck_chain[0])
        
        matrix_manager.space_switches(self.neck_ctls[-1], [self.neck_ctls[0], self.masterwalk_ctl], default_rotate=1, default_translate=1) # Neck base and masterwalk

    def head_squash_setup(self):

        """
        Stretch & squash de la cabeza (inspirado en el head_squash_ctl de Vittorio,
        pero por ESCALA del joint en vez de un deformer no-lineal, para que viva en
        el módulo de joints sin depender de la geometría).

        El control face: su translateY ESTIRA (arriba) o APLASTA (abajo) el
        headSkinning_JNT a lo largo de su eje vertical (Y local), y los ejes
        perpendiculares (X,Z) compensan con preservación de volumen modulada por el
        atributo Volume (1 = volumen exacto, 0 = sin compensación, >1 = exagerado).
        El factor se normaliza por la longitud del cuello, así es independiente de la
        escala del rig. Identidad en reposo (ty=0 -> escala 1).
        """

        squash_ctl = self.face_ctl
        self.head_squash_ctl = squash_ctl
        cmds.addAttr(squash_ctl, longName="Volume", attributeType="double", min=0, max=10, defaultValue=1, keyable=True)

        # Longitud de referencia (cuello) -> factor independiente de la escala del rig.
        neck_m = om.MMatrix(self.neck_guide_matrix)
        head_m = om.MMatrix(self.head_guide_matrix)
        neck_len = max(0.001, ((neck_m[12] - head_m[12]) ** 2 +
                               (neck_m[13] - head_m[13]) ** 2 +
                               (neck_m[14] - head_m[14]) ** 2) ** 0.5)

        # factor = translateY / neck_len
        factor = cmds.createNode("multiply", name=f"{self.side}_headSquashFactor_MUL", ss=True)
        cmds.connectAttr(f"{squash_ctl}.translateY", f"{factor}.input[0]")
        cmds.setAttr(f"{factor}.input[1]", 1.0 / neck_len)

        # scaleY = 1 + factor (clamp > 0.05 para no invertir)
        scale_y = cmds.createNode("sum", name=f"{self.side}_headSquashScaleY_SUM", ss=True)
        cmds.setAttr(f"{scale_y}.input[0]", 1.0)
        cmds.connectAttr(f"{factor}.output", f"{scale_y}.input[1]")
        scale_y_clamp = cmds.createNode("clamp", name=f"{self.side}_headSquashScaleY_CLP", ss=True)
        cmds.setAttr(f"{scale_y_clamp}.minR", 0.05)
        cmds.setAttr(f"{scale_y_clamp}.maxR", 1000)
        cmds.connectAttr(f"{scale_y}.output", f"{scale_y_clamp}.inputR")

        # exponente = -0.5 * Volume ; scaleXZ = scaleY ^ exponente (preserva volumen)
        exponent = cmds.createNode("multiply", name=f"{self.side}_headSquashExp_MUL", ss=True)
        cmds.connectAttr(f"{squash_ctl}.Volume", f"{exponent}.input[0]")
        cmds.setAttr(f"{exponent}.input[1]", -0.5)
        scale_xz = cmds.createNode("power", name=f"{self.side}_headSquashScaleXZ_POW", ss=True)
        cmds.connectAttr(f"{scale_y_clamp}.outputR", f"{scale_xz}.input")
        cmds.connectAttr(f"{exponent}.output", f"{scale_xz}.exponent")

        # Aplicar al joint de la cabeza (Y = eje de stretch, X/Z = compensación).
        cmds.connectAttr(f"{scale_y_clamp}.outputR", f"{self.head_skinning_jnt}.scaleY")
        cmds.connectAttr(f"{scale_xz}.output", f"{self.head_skinning_jnt}.scaleX")
        cmds.connectAttr(f"{scale_xz}.output", f"{self.head_skinning_jnt}.scaleZ")

    def mGear_integration(self):

        """
        Integrate the neck module with mGear by adding the necessary attributes to the preferences controller.
        """

        self.head_ctl = cmds.ls(f"{self.side}_head_CTL")[0]
        face_nodes, self.face_ctl = curve_tool.create_controller(name=f"{self.side}_face", offset=["GRP", "ANM"], parent=self.head_ctl)
        curve_tool.lock_attributes(self.face_ctl, ["tx", "tz", "rx", "ry", "rz", "sx", "sy", "sz", "v"])
        cmds.addAttr(self.face_ctl, longName="FACE_VIS", niceName="FACE VISIBILITY ------", attributeType="enum", enumName="------")
        cmds.setAttr(f"{self.face_ctl}.FACE_VIS", lock=True, keyable=False, channelBox=True)
        self.head_guide_matrix = cmds.getAttr(f"{self.head_ctl}.worldMatrix[0]")
        cmds.matchTransform(face_nodes[0], self.head_ctl, pos=True, rot=True)
