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
from maya_tools.scripts.utils import guide_frames
from maya_tools.scripts.utils.module_nurbs import organize_module_nurbs

reload(data_manager)
reload(guides_manager)
reload(curve_tool)
reload(matrix_manager)
reload(ribbon)

class SpineModule(object):

    # Historical two-guide calibration below; now applied inside each segment.
    # Reparto de la flexión sagital: sesga hacia el extremo CAUDAL las posiciones
    # de REPOSO de los controles -> weight = (i/(n-1))**SAGITTAL_BIAS. Esas
    # posiciones son los CVs del ribbon, así que juntarlos en la grupa deja que la
    # curva gire fuerte ahí y siga recta hacia el tórax. 1.0 = uniforme = curvatura
    # constante = el lomo se arquea parejo de punta a punta, que es la firma FELINA
    # (el guepardo flexiona mucho y repartido; el caballo, poco y concentrado en la
    # unión lumbosacra). Ex vivo: lumbosacra 26.3° frente a 5.4° de un nivel
    # toracolumbar (T17-T18/T18-L1) -> ratio 4.87.
    #
    # 1.3 está MEDIDO contra ese ratio, no estimado. Medición: respuesta unitaria
    # (ctl caudal +5u dorsal) y ángulo por segmento entre joints de skinning. Se usa
    # la respuesta unitaria y no un "arco" repartido a mano porque el gesto libre no
    # impone la forma: imponerla mediría el gesto, no el rig.
    # Barrido con la guía ya en la lumbosacra (span 85.8u):
    #   1.10 -> 3.89 · 1.20 -> 4.35 · 1.25 -> 4.59 · 1.30 -> 4.84 · 1.35 -> 5.09
    #   1.50 -> 5.87 · 2.00 -> 8.18 · 2.40 -> 8.78 (máximo) · 3.20 -> 6.84 · 4.50 -> 4.92
    # Reparto por joint con 1.3: [10.52, 6.16, 3.57, 1.95, 0.95, 0.36, 0.07].
    # Este es EL parámetro équido/felino: mismo módulo, distinta ponderación.
    #
    # OJO, LA CURVA NO ES MONÓTONA: la concentración sube hasta un máximo en ~2.4 y
    # luego BAJA, porque con los CVs muy apiñados mover el caudal arrastra a sus
    # vecinos y el doblez se vuelve a repartir. Hay por tanto DOS valores que dan el
    # ratio objetivo (~1.3 y ~4.6); se elige el bajo porque deja los controles mejor
    # separados para el animador.
    #
    # El 2.4 anterior NO es comparable: se calibró con la guía en z=-55.84 (span
    # 66.6u) y con un gesto de arco repartido entre los 4 controles.
    #
    # La guía C_spine00 se movió de z=-55.844 a z=-75.0 (y de 108.177 a 108.410 por
    # extrapolación lineal del eje de la columna, pendiente -0.01221) para que el
    # extremo caudal del ribbon caiga en la UNIÓN LUMBOSACRA real, deducida de las
    # guías: cadera en z=-74.93, primera caudal en z=-91.54. Antes la lumbosacra
    # quedaba ~19u FUERA del tramo y la flexión se concentraba en lumbar medio.
    # Eso SÍ mueve los joints de skinning (espaciado 9.52 -> 12.26): hay que
    # REIMPORTAR PESOS.
    #
    # ponytail: flag de clase (idioma del repo, como PV_SIGN del leg) -> es por
    # MÓDULO, no por personaje, y los únicos Rig_Type=1 son horse y giraffe (la
    # jirafa lo recibe a 1.0 desde rig_manager). Si divergen más, esto sube al
    # .build; ojo: hay que añadirlo también a create_rig_settings (hoy solo hace
    # int/enum), porque get_rig_data reescribe el .build desde los atributos de
    # C_guides_GRP y se comería una clave suelta.
    SAGITTAL_BIAS = 1.3

    def __init__(self):

        """
        Initialize the spineModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExportBiped().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExportBiped().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExportBiped().get_data("basic_structure", "masterwalk_ctl")

        self.primary_input_axis = (1, 0, 0)
        self.secondary_input_axis = (0, 1, 0)

    @organize_module_nurbs
    def make(self, side, spine_joints, spine_controllers, spine_tangents=False):

        """ 
        Create the spine module structure and controllers. Call this method with the side ('L' or 'R') to create the respective spine module.
        Args:
            side (str): The side of the spine ('L' or 'R').
            spine_joints (int): The number of spine joints.
            spine_controllers (int): The number of spine controllers.
            spine_tangents (bool): Add two endpoint tangent controls, hidden by default.

        """

        self.spine_joints = spine_joints
        self.spine_controllers = spine_controllers
        self.spine_tangents = bool(spine_tangents)
        self.authored_orientation = guide_frames.enabled()
        if self.spine_tangents and spine_controllers < 3:
            raise ValueError("A tangent spine requires at least three primary controls.")
        self.side = side
        self.module_trn = cmds.createNode("transform", name=f"{self.side}_spineModule_GRP", ss=True, p=self.modules)
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.side}_spineSkinning_GRP", ss=True, p=self.skel_grp)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.side}_spineControllers_GRP", ss=True, p=self.masterwalk_ctl)

        self.load_guides()
        self.create_guides_logic()
        self.controller_creation()
        self.ribbon_setup()
        self.local_hip_chest_setup()

        data_manager.DataExportBiped().append_data("spine_module",
                            {
                                "local_hip_ctl": self.local_hip_ctl,
                                "body_ctl": self.body_ctl,
                                "local_chest_ctl": self.local_chest_ctl,
                                "spine_ctl": self.spine_ctls[0],
                                "body_pivot_ctl": self.body_pivot_ctl,
                            })
        

    def load_guides(self):

        """
        Load the spine guides for the specified side and parent them to the module transform.
        """

        self.spine_chain = guides_manager.get_guides(f"{self.side}_spine00_JNT")
        cmds.parent(self.spine_chain[0], self.module_trn)
        print(f"Spine guides loaded for side {self.side}: {self.spine_chain}")

    def create_guides_logic(self):

        """
        Create the logic for spine guides.
        """
        self.spine_guides_matrices = guides_manager.sample_chain_matrices(
            self.spine_chain, self.spine_controllers + (2 if self.spine_tangents else 0),
            self.primary_input_axis, self.secondary_input_axis,
            spacing_bias=self.SAGITTAL_BIAS)
        self.solver_guides_matrices = self.spine_guides_matrices
        if self.authored_orientation:
            self.spine_guides_matrices = guides_manager.sample_chain_matrices(
                self.spine_chain, len(self.solver_guides_matrices),
                self.primary_input_axis, self.secondary_input_axis,
                spacing_bias=self.SAGITTAL_BIAS, preserve_orientation=True)
        self.spine_controllers = len(self.spine_guides_matrices)
        base_matrix = om.MMatrix(self.spine_guides_matrices[0])
        cmds.delete(self.spine_chain[0])

        # guia OPCIONAL del localHip: da la POSICION del ctl del pelvis (la
        # orientacion sigue siendo la del spine); sin guia cae al root
        self.local_hip_matrix = self.spine_guides_matrices[0]
        hip_guide = guides_manager.get_guides(f"{self.side}_localHip_JNT")
        if hip_guide:
            hip_matrix = cmds.xform(hip_guide[0], q=True, ws=True, m=True)
            hip_pos = om.MVector(cmds.xform(hip_guide[0], q=True, ws=True, t=True))
            cmds.delete(hip_guide[0])
            self.local_hip_matrix = list(guides_manager._with_translation(base_matrix, hip_pos))
            if self.authored_orientation:
                self.local_hip_matrix = hip_matrix


    def controller_creation(self):

        """
        Create controllers for the spine module.
        """

        self.body_nodes, self.body_ctl = curve_tool.create_controller(name=f"{self.side}_body", offset=["GRP", "SPC", "ANM"], parent=self.controllers_grp, locked_attrs=["sx", "sy", "sz", "v"])
        self.local_hip_nodes, self.local_hip_ctl = curve_tool.create_controller(name=f"{self.side}_pelvis", offset=["GRP", "SPC", "ANM"], parent=self.controllers_grp, locked_attrs=["sx", "sy", "sz", "v"])
        self.local_chest_nodes, self.local_chest_ctl = curve_tool.create_controller(name=f"{self.side}_localChest", offset=["GRP", "SPC", "ANM"], parent=self.controllers_grp, locked_attrs=["v"])
        
        cmds.setAttr(f"{self.body_nodes[0]}.offsetParentMatrix", self.spine_guides_matrices[0], type="matrix")
        cmds.setAttr(f"{self.local_hip_nodes[0]}.offsetParentMatrix", self.local_hip_matrix, type="matrix")
        self.movable_body_pivot()

        # Create the spine controllers
        self.spine_nodes = []
        self.spine_ctls = []
        self.tangent_indices = {1, self.spine_controllers - 2} if self.spine_tangents else set()

        body_rest_inverse = om.MMatrix(self.spine_guides_matrices[0]).inverse()

        for i, matrix in enumerate(self.spine_guides_matrices):

            name = f"{self.side}_spine0{i}" + ("Tan" if i in self.tangent_indices else "")
            spine_node, spine_ctl = curve_tool.create_controller(name=name, offset=["GRP", "SPC", "ANM"], parent=self.controllers_grp, locked_attrs=["v"])
            local_matrix = om.MMatrix(matrix) * body_rest_inverse
            cmds.setAttr(f"{spine_node[0]}.offsetParentMatrix", list(local_matrix), type="matrix")
            cmds.xform(spine_node[0], m=om.MMatrix.kIdentity)
            self.spine_nodes.append(spine_node)
            self.spine_ctls.append(spine_ctl)

        # Connect the spine controllers to the body controller
        cmds.connectAttr(f"{self.body_ctl}.worldMatrix[0]", f"{self.spine_nodes[0][0]}.offsetParentMatrix")
        cmds.setAttr(f"{self.spine_nodes[0][0]}.inheritsTransform", 0)
        for i in range(1, len(self.spine_nodes)):
            cmds.setAttr(f"{self.spine_nodes[i][0]}.offsetParentMatrix", self.spine_guides_matrices[i], type="matrix")

        self.primary_spine_ctls = [ctl for i, ctl in enumerate(self.spine_ctls)
                                   if i not in self.tangent_indices]
        self.tangent_ctls = [self.spine_ctls[i] for i in sorted(self.tangent_indices)]
        self.parent_spine_controls()
        if self.tangent_indices:
            cmds.addAttr(self.spine_ctls[0], longName="tanVisibility",
                         niceName="Tangent Controllers Visibility", attributeType="bool",
                         defaultValue=False, keyable=False)
            cmds.setAttr(f"{self.spine_ctls[0]}.tanVisibility", channelBox=True)
            for i in sorted(self.tangent_indices):
                endpoint = 0 if i == 1 else len(self.spine_ctls) - 1
                parent = self.spine_ctls[endpoint]
                root = self.spine_nodes[i][0]
                local_rest = (om.MMatrix(self.spine_guides_matrices[i]) *
                              om.MMatrix(self.spine_guides_matrices[endpoint]).inverse())
                cmds.parent(root, parent, relative=True)
                cmds.setAttr(f"{root}.offsetParentMatrix", list(local_rest), type="matrix")
                cmds.connectAttr(f"{self.spine_ctls[0]}.tanVisibility", f"{root}.visibility")

        self.control_follow_setup()

        # ----- Stretch setup (UNIFORME) -----
        # El stretch multiplica por IGUAL la distancia entre joints: factor único =
        # longitud real total de la cadena de controles / longitud de reposo. Cada
        # segmento = rest_length * factor (todos crecen lo mismo), siguiendo la
        # dirección de los controles. Stretch_Activate enciende/apaga el efecto.
        cmds.addAttr(self.body_ctl, longName="Stretch", niceName="STRETCH ------", attributeType="enum", enumName="------", keyable=True)
        cmds.setAttr(f"{self.body_ctl}.Stretch", lock=True, keyable=False, channelBox=True)
        cmds.addAttr(self.body_ctl, longName="Stretch_Activate", niceName="Stretch", attributeType="float", minValue=0, maxValue=1, defaultValue=0, keyable=True)

        self.chest_drivers = self.chest_spine_curve_drivers()

        if self.primary_input_axis == (1, 0, 0):
            translate_attr = "inputTranslateX"
        elif self.primary_input_axis == (0, 0, 1):
            translate_attr = "inputTranslateZ"
        else:
            translate_attr = "inputTranslateY"

        guide_positions = [om.MVector(m[12], m[13], m[14]) for m in self.spine_guides_matrices]
        rest_lengths = [(guide_positions[i] - guide_positions[i - 1]).length() for i in range(1, len(self.spine_ctls))]
        total_rest = sum(rest_lengths)

        # Longitud real total = suma de las distancias entre controles consecutivos
        total_dist = cmds.createNode("plusMinusAverage", name=f"{self.side}_spineStretchTotal_PMA", ss=True)
        cmds.setAttr(f"{total_dist}.operation", 1)  # sum
        for i in range(1, len(self.spine_ctls)):
            dbt = cmds.createNode("distanceBetween", name=f"{self.side}_spine0{i}StretchDist_DBT", ss=True)
            cmds.connectAttr(guide_frames.matrix_plug(self.chest_drivers[i - 1]), f"{dbt}.inMatrix1")
            cmds.connectAttr(guide_frames.matrix_plug(self.chest_drivers[i]), f"{dbt}.inMatrix2")
            cmds.connectAttr(f"{dbt}.distance", f"{total_dist}.input1D[{i - 1}]")

        # Factor uniforme = (longitud real / globalScale) / longitud de reposo
        global_div = cmds.createNode("divide", name=f"{self.side}_spineStretchGlobal_DIV", ss=True)
        cmds.connectAttr(f"{total_dist}.output1D", f"{global_div}.input1")
        cmds.connectAttr(f"{self.masterwalk_ctl}.globalScale", f"{global_div}.input2")

        factor_div = cmds.createNode("divide", name=f"{self.side}_spineStretchFactor_DIV", ss=True)
        cmds.connectAttr(f"{global_div}.output", f"{factor_div}.input1")
        cmds.setAttr(f"{factor_div}.input2", total_rest)

        # Blend 1 (sin stretch) <-> factor (con stretch), por Stretch_Activate
        factor_blend = cmds.createNode("blendTwoAttr", name=f"{self.side}_spineStretchFactor_B2A", ss=True)
        cmds.setAttr(f"{factor_blend}.input[0]", 1.0)
        cmds.connectAttr(f"{factor_div}.output", f"{factor_blend}.input[1]")
        cmds.connectAttr(f"{self.body_ctl}.Stretch_Activate", f"{factor_blend}.attributesBlender")

        solve_controls = (guide_frames.control_drivers(self.chest_drivers, self.spine_guides_matrices,
                           self.solver_guides_matrices, f"{self.side}_spine")
                          if self.authored_orientation else self.chest_drivers)
        self.stretch_drivers = [solve_controls[0]]
        prev_plug = guide_frames.matrix_plug(solve_controls[0])

        for i in range(1, len(self.spine_ctls)):

            target_plug = guide_frames.matrix_plug(solve_controls[i])

            # Longitud uniforme de este segmento = rest_length * factor
            seg_len = cmds.createNode("multiply", name=f"{self.side}_spine0{i}StretchLen_MUL", ss=True)
            cmds.setAttr(f"{seg_len}.input[0]", rest_lengths[i - 1])
            cmds.connectAttr(f"{factor_blend}.output", f"{seg_len}.input[1]")

            aim = cmds.createNode("aimMatrix", name=f"{self.side}_spine0{i}Stretch_AIM", ss=True)
            cmds.setAttr(f"{aim}.primaryInputAxis", *self.primary_input_axis, type="double3")
            cmds.setAttr(f"{aim}.secondaryInputAxis", *self.secondary_input_axis, type="double3")
            cmds.setAttr(f"{aim}.secondaryTargetVector", *self.secondary_input_axis, type="double3")
            cmds.setAttr(f"{aim}.secondaryMode", 2)  # Align: el twist sigue al control
            cmds.connectAttr(prev_plug, f"{aim}.inputMatrix")
            cmds.connectAttr(target_plug, f"{aim}.primary.primaryTargetMatrix")
            cmds.connectAttr(target_plug, f"{aim}.secondary.secondaryTargetMatrix")

            cmx = cmds.createNode("composeMatrix", name=f"{self.side}_spine0{i}Stretch_CMX", ss=True)
            cmds.connectAttr(f"{seg_len}.output", f"{cmx}.{translate_attr}")

            mmx = cmds.createNode("multMatrix", name=f"{self.side}_spine0{i}Stretch_MMX", ss=True)
            cmds.connectAttr(f"{cmx}.outputMatrix", f"{mmx}.matrixIn[0]")
            cmds.connectAttr(f"{aim}.outputMatrix", f"{mmx}.matrixIn[1]")

            self.stretch_drivers.append(mmx)
            prev_plug = f"{mmx}.matrixSum"


    def local_hip_chest_setup(self):

        # ------ Local hip setup ------
        cmds.select(clear=True)
        local_hip_skinning_jnt = cmds.joint(name=f"{self.side}_localHipSkinning_JNT")
        four_by_four = cmds.createNode("fourByFourMatrix", name=f"{self.side}_localHip_FBF")
        row_translation = cmds.createNode("rowFromMatrix", name=f"{self.side}_localHipTranslation_RFM")
        cmds.setAttr(f"{row_translation}.input", 3)
        # offset horneado guia->spine delante: el joint reposa en la guia del
        # localHip y sigue viviendo la traslacion del spine (identidad sin guia)
        hip_offset = om.MMatrix(self.local_hip_matrix) * om.MMatrix(self.spine_guides_matrices[0]).inverse()
        hip_pos_mmx = cmds.createNode("multMatrix", name=f"{self.side}_localHipPos_MMX")
        cmds.setAttr(f"{hip_pos_mmx}.matrixIn[0]", list(hip_offset), type="matrix")
        cmds.connectAttr(f"{self.spine_ctls[0]}.worldMatrix[0]", f"{hip_pos_mmx}.matrixIn[1]")
        cmds.connectAttr(f"{hip_pos_mmx}.matrixSum", f"{row_translation}.matrix")
        for col_index, axis in enumerate("XYZ"):
            cmds.connectAttr(f"{row_translation}.output{axis}", f"{four_by_four}.in3{col_index}")

        for row_index in range(3):
            row_rotation = cmds.createNode("rowFromMatrix", name=f"{self.side}_localHipRotation0{row_index}_RFM")
            cmds.setAttr(f"{row_rotation}.input", row_index)
            cmds.connectAttr(f"{self.local_hip_ctl}.worldMatrix[0]", f"{row_rotation}.matrix")
            normalize_row = cmds.createNode("normalize", name=f"{self.side}_localHipRotation0{row_index}_NRM")

            row_scale = cmds.createNode("rowFromMatrix", name=f"{self.side}_localHipScale0{row_index}_RFM")
            cmds.setAttr(f"{row_scale}.input", row_index)
            cmds.connectAttr(f"{self.spine_ctls[0]}.worldMatrix[0]", f"{row_scale}.matrix")
            scale_length = cmds.createNode("length", name=f"{self.side}_localHipScale0{row_index}_LEN")

            for axis in "XYZ":
                cmds.connectAttr(f"{row_rotation}.output{axis}", f"{normalize_row}.input{axis}")
                cmds.connectAttr(f"{row_scale}.output{axis}", f"{scale_length}.input{axis}")

            for col_index, axis in enumerate("XYZ"):
                mult = cmds.createNode("multiply", name=f"{self.side}_localHipRow{row_index}{axis}_MUL")
                cmds.connectAttr(f"{normalize_row}.output{axis}", f"{mult}.input[0]")
                cmds.connectAttr(f"{scale_length}.output", f"{mult}.input[1]")
                cmds.connectAttr(f"{mult}.output", f"{four_by_four}.in{row_index}{col_index}")

        cmds.connectAttr(f"{four_by_four}.output", f"{local_hip_skinning_jnt}.offsetParentMatrix")
        
        cmds.setAttr(f"{self.local_hip_nodes[0]}.inheritsTransform", 0)
        cmds.parent(local_hip_skinning_jnt, self.skeleton_grp)

        self.local_chest_setup()

    def local_chest_setup(self):
        """Follow the solved tip without feeding solved motion into the ribbon."""
        chest_frame = cmds.createNode("blendMatrix", name=f"{self.side}_localChest_BLM", ss=True)
        cmds.connectAttr(self.ribbon_tip_plug, f"{chest_frame}.inputMatrix")
        cmds.connectAttr(f"{self.spine_ctls[-1]}.worldMatrix[0]", f"{chest_frame}.target[0].targetMatrix")
        cmds.setAttr(f"{chest_frame}.target[0].translateWeight", 0)
        cmds.setAttr(f"{chest_frame}.target[0].shearWeight", 0)
        untranslate = cmds.createNode("composeMatrix", name=f"{self.side}_localChestUntranslate_CMX", ss=True)
        negate = cmds.createNode("multiplyDivide", name=f"{self.side}_localChestUntranslate_MDV", ss=True)
        cmds.connectAttr(f"{self.local_chest_ctl}.translate", f"{negate}.input1")
        cmds.setAttr(f"{negate}.input2", -1, -1, -1)
        cmds.connectAttr(f"{negate}.output", f"{untranslate}.inputTranslate")
        chest_parent = cmds.createNode("multMatrix", name=f"{self.side}_localChestParent_MMX", ss=True)
        cmds.connectAttr(f"{untranslate}.outputMatrix", f"{chest_parent}.matrixIn[0]")
        cmds.connectAttr(f"{chest_frame}.outputMatrix", f"{chest_parent}.matrixIn[1]")
        cmds.connectAttr(f"{chest_parent}.matrixSum", f"{self.local_chest_nodes[0]}.offsetParentMatrix", force=True)
        cmds.setAttr(f"{self.local_chest_nodes[0]}.inheritsTransform", 0)
        cmds.select(clear=True)
        local_chest_skinning_jnt = f"{self.side}_localChestSkinning_JNT"
        if not cmds.objExists(local_chest_skinning_jnt):
            local_chest_skinning_jnt = cmds.joint(name=local_chest_skinning_jnt)
        cmds.setAttr(f"{local_chest_skinning_jnt}.inheritsTransform", 0)
        cmds.connectAttr(f"{self.local_chest_ctl}.worldMatrix[0]", f"{local_chest_skinning_jnt}.offsetParentMatrix", force=True)
        cmds.select(clear=True)
        
        if cmds.listRelatives(local_chest_skinning_jnt, parent=True) != [self.skeleton_grp]:
            cmds.parent(local_chest_skinning_jnt, self.skeleton_grp)

    def ribbon_setup(self):

        """
        Set up the ribbon for the spine module.
        """
        # Create the attribute for FK in the body controller
        cmds.addAttr(self.body_ctl, longName="FK", niceName="ATTACHED FK ------", attributeType="enum", enumName="------", keyable=True)
        cmds.setAttr(f"{self.body_ctl}.FK", lock=True, keyable=False, channelBox=True)
        cmds.addAttr(self.body_ctl, longName="FK_Vis", niceName="FK Controllers Visibility", attributeType="bool", defaultValue=0, keyable=True)
        cmds.setAttr(f"{self.body_ctl}.FK_Vis", lock=False, keyable=False, channelBox=True)

        # Create the FK controllers
        self.fk_nodes = []
        self.fk_controllers = []
        
        for i in range(self.spine_joints):
            
            fk_node, fk_ctl = curve_tool.create_controller(name=f"{self.side}_spine0{i}AttatchedFk", offset=["GRP"])
            if i == 0:
                cmds.setAttr(f"{fk_node[0]}.inheritsTransform", 0)
                cmds.parent(fk_node[0], self.controllers_grp)
                cmds.connectAttr(f"{self.body_ctl}.FK_Vis", f"{fk_node[0]}.visibility")

            curve_tool.lock_attributes(fk_ctl, ["sx", "sy", "sz", "v"])
            if self.fk_controllers:
                cmds.parent(fk_node[0], self.fk_controllers[-1])
            self.fk_nodes.append(fk_node)
            self.fk_controllers.append(fk_ctl)

        guide_positions = [om.MVector(m[12], m[13], m[14]) for m in self.spine_guides_matrices]
        segment_length = (guide_positions[-1] - guide_positions[0]).length() / (len(guide_positions) - 1)

        sel = tuple(self.stretch_drivers)
        output_joints, temp = ribbon.de_boor_ribbon(sel, name=f"{self.side}_spine", aim_axis="x", up_axis="y", num_joints=self.spine_joints, skeleton_grp=self.skeleton_grp, d=3, tangent_cvs=0, tangent_axis="x", param_from_length=True)
        self.ribbon_tip_plug = cmds.connectionInfo(output_joints[-1] + '.offsetParentMatrix', sourceFromDestination=True)
        self.volume_setup(output_joints)
        if self.authored_orientation:
            guide_frames.orient_outputs(output_joints, self.spine_guides_matrices, f"{self.side}_spine")
        for t in temp:
            cmds.delete(t)
    
        jnt_connections = []
        for i, jnt in enumerate(output_joints): # Use the output joints from the ribbon setup to connect to the FK controllers

            jnt_connection = cmds.listConnections(jnt, source=True, destination=True, plugs=True)[0]

            if jnt_connection:
                
                mult_matrix_node = cmds.createNode("multMatrix", name=jnt.replace("_JNT", "_MMX"))
                cmds.connectAttr(jnt_connection, f"{mult_matrix_node}.matrixIn[0]")
                if i != 0:
                    inverse_matrix_node = cmds.createNode("inverseMatrix", name=jnt.replace("_JNT", "_INV"))
                    cmds.connectAttr(jnt_connections[-1], f"{inverse_matrix_node}.inputMatrix")
                    cmds.connectAttr(f"{inverse_matrix_node}.outputMatrix", f"{mult_matrix_node}.matrixIn[1]")
                    cmds.connectAttr(f"{mult_matrix_node}.matrixSum", f"{self.fk_nodes[i][0]}.offsetParentMatrix")
                elif i == 0:
                    cmds.connectAttr(jnt_connection, f"{self.fk_nodes[i][0]}.offsetParentMatrix")
                
                cmds.connectAttr(f"{self.fk_controllers[i]}.worldMatrix[0]", f"{jnt}.offsetParentMatrix", force=True)
                jnt_connections.append(jnt_connection)

    def movable_body_pivot(self):
        """Move the body rotation center without moving the neutral body."""
        nodes, self.body_pivot_ctl = curve_tool.create_controller(
            name=f"{self.side}_bodyPivot", offset=["GRP"], parent=self.controllers_grp,
            locked_attrs=["rx", "ry", "rz", "sx", "sy", "sz", "v"])
        cmds.setAttr(nodes[0] + '.offsetParentMatrix', self.spine_guides_matrices[0], type='matrix')
        cmds.setAttr(self.body_nodes[0] + '.inheritsTransform', 0)
        cmds.connectAttr(self.body_pivot_ctl + '.worldMatrix[0]', self.body_nodes[0] + '.offsetParentMatrix', force=True)
        negate = cmds.createNode('multiplyDivide', name=f'{self.side}_bodyPivotCompensate_MDV', ss=True)
        cmds.setAttr(negate + '.input2', -1, -1, -1)
        cmds.connectAttr(self.body_pivot_ctl + '.translate', negate + '.input1')
        cmds.connectAttr(self.body_pivot_ctl + '.translate', self.body_ctl + '.rotatePivot')
        cmds.connectAttr(self.body_pivot_ctl + '.translate', self.body_ctl + '.scalePivot')
        cmds.connectAttr(negate + '.output', self.body_ctl + '.rotatePivotTranslate')
        cmds.addAttr(self.body_ctl, longName='pivotVisibility', attributeType='bool', defaultValue=True)
        cmds.setAttr(self.body_ctl + '.pivotVisibility', channelBox=True)
        cmds.connectAttr(self.body_ctl + '.pivotVisibility', nodes[0] + '.visibility')
        # Use the asset's actual leg-PV drawing, including its authored CVs.
        pv = 'L_backLegPv_CTL'
        temporary = []
        if not cmds.objExists(pv) and hasattr(curve_tool, 'build_curves_from_template'):
            temporary = curve_tool.build_curves_from_template(pv) or []
            pv = temporary[0] if temporary else pv
        if cmds.objExists(pv):
            old = cmds.listRelatives(self.body_pivot_ctl, shapes=True, fullPath=True) or []
            for index, shape in enumerate(cmds.listRelatives(pv, shapes=True, fullPath=True, type='nurbsCurve') or []):
                copied = cmds.createNode('nurbsCurve', name=f'{self.body_pivot_ctl}Shape{index}', parent=self.body_pivot_ctl)
                cmds.connectAttr(shape + '.local', copied + '.create')
                cmds.dgeval(copied + '.local')
                cmds.disconnectAttr(shape + '.local', copied + '.create')
            if old:
                cmds.delete(old)
        if temporary:
            cmds.delete(temporary)
        cmds.setAttr(self.body_pivot_ctl + '.overrideEnabled', True)
        cmds.setAttr(self.body_pivot_ctl + '.overrideColor', 17)

    def parent_spine_controls(self):
        """Keep primary controls below the root and the tip below the middle."""
        primary = [i for i in range(len(self.spine_ctls)) if i not in self.tangent_indices]
        middle = primary[len(primary) // 2]
        for i in primary[1:]:
            parent_index = middle if i == primary[-1] and middle != i else 0
            root = self.spine_nodes[i][0]
            cmds.parent(root, self.spine_ctls[parent_index], relative=True)
            local = om.MMatrix(self.spine_guides_matrices[i]) * om.MMatrix(self.spine_guides_matrices[parent_index]).inverse()
            cmds.setAttr(root + '.offsetParentMatrix', list(local), type='matrix')
            cmds.xform(root, matrix=list(om.MMatrix.kIdentity))

    def chest_spine_curve_drivers(self):
        """Apply chest translation/scale upstream; keep chest rotation local."""
        orientation = cmds.createNode('pickMatrix', name=f'{self.side}_spineChestFrame_PMX', ss=True)
        cmds.connectAttr(self.spine_ctls[-1] + '.worldMatrix[0]', orientation + '.inputMatrix')
        cmds.setAttr(orientation + '.useTranslate', False)
        pivot = cmds.createNode('pickMatrix', name=f'{self.side}_spineChestPivot_PMX', ss=True)
        cmds.connectAttr(self.spine_ctls[len(self.spine_ctls) // 2] + '.worldMatrix[0]', pivot + '.inputMatrix')
        for attr in ('useRotate', 'useScale', 'useShear'):
            cmds.setAttr(pivot + '.' + attr, False)
        frame = cmds.createNode('multMatrix', name=f'{self.side}_spineChestFrame_MMX', ss=True)
        cmds.connectAttr(orientation + '.outputMatrix', frame + '.matrixIn[0]')
        cmds.connectAttr(pivot + '.outputMatrix', frame + '.matrixIn[1]')
        inverse = cmds.createNode('inverseMatrix', name=f'{self.side}_spineChestFrame_IMX', ss=True)
        cmds.connectAttr(frame + '.matrixSum', inverse + '.inputMatrix')
        delta = cmds.createNode('pickMatrix', name=f'{self.side}_spineChestDelta_PMX', ss=True)
        cmds.connectAttr(self.local_chest_ctl + '.matrix', delta + '.inputMatrix')
        cmds.setAttr(delta + '.useRotate', False)
        cmds.setAttr(delta + '.useShear', False)
        drivers = list(self.spine_ctls)
        for i in range(max(1, len(drivers) - 2), len(drivers)):
            node = cmds.createNode('multMatrix', name=f'{self.side}_spineChestPoint{i:02d}_MMX', ss=True)
            for slot, plug in enumerate((drivers[i] + '.worldMatrix[0]', inverse + '.outputMatrix',
                                         delta + '.outputMatrix', frame + '.matrixSum')):
                cmds.connectAttr(plug, node + f'.matrixIn[{slot}]')
            drivers[i] = node
        return drivers

    def control_follow_setup(self):
        """Give every secondary primary/tangent its own local/global choice."""
        from maya_tools.scripts.utils.matrix_manager import control_follow_switch
        for ctl in self.spine_ctls[1:]:
            root = ctl.replace('_CTL', '_GRP')
            parent = cmds.listRelatives(root, parent=True)[0]
            control_follow_switch(ctl, parent, self.masterwalk_ctl)

    def volume_setup(self, joints, drivers=None, connect=True):
        """Preserve cross-sectional volume in solver axes, before authored axes."""
        from maya_tools.scripts.utils.ribbon_volume import create_volume_matrix
        drivers = drivers or [cmds.connectionInfo(j + '.offsetParentMatrix', sourceFromDestination=True) for j in joints]
        volume = create_volume_matrix(drivers, self.body_ctl, self.masterwalk_ctl, f'{self.side}_spineVolume')
        chest_rotation = om.MTransformationMatrix(om.MMatrix(self.spine_guides_matrices[-1])).rotation(asQuaternion=True).asMatrix()
        direction = om.MVector(self.spine_guides_matrices[-1][12:15]) - om.MVector(self.spine_guides_matrices[0][12:15])
        direction = direction * chest_rotation.inverse()
        length_axis = max(range(3), key=lambda axis: abs(direction[axis]))
        result = []
        for i, (joint, plug) in enumerate(zip(joints, drivers)):
            prefix = f'{self.side}_spineVolume{i:02d}'
            manual = cmds.createNode('composeMatrix', name=prefix + 'Chest_CMX', ss=True)
            weight = max(0.0, 2.0 * i / max(1, len(joints) - 1) - 1.0)
            for axis_index, axis in enumerate('XYZ'):
                if axis_index == length_axis:
                    continue
                scale = cmds.createNode('blendTwoAttr', name=prefix + 'Chest' + axis + '_BTA', ss=True)
                cmds.setAttr(scale + '.input[0]', 1)
                cmds.connectAttr(self.local_chest_ctl + '.scale' + axis, scale + '.input[1]')
                cmds.setAttr(scale + '.attributesBlender', weight)
                cmds.connectAttr(scale + '.output', manual + '.inputScale' + axis)
            rotation = om.MTransformationMatrix(om.MMatrix(cmds.getAttr(plug))).rotation(asQuaternion=True).asMatrix()
            offset = rotation * chest_rotation.inverse()
            matrix = cmds.createNode('multMatrix', name=prefix + '_MMX', ss=True)
            cmds.setAttr(matrix + '.matrixIn[0]', list(offset), type='matrix')
            cmds.connectAttr(manual + '.outputMatrix', matrix + '.matrixIn[1]')
            cmds.setAttr(matrix + '.matrixIn[2]', list(offset.inverse()), type='matrix')
            cmds.connectAttr(volume, matrix + '.matrixIn[3]')
            cmds.connectAttr(plug, matrix + '.matrixIn[4]')
            result.append(matrix + '.matrixSum')
            if connect:
                cmds.connectAttr(result[-1], joint + '.offsetParentMatrix', force=True)
        return result
