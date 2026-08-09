import maya.cmds as cmds
import maya.api.OpenMaya as om
from importlib import reload
import os
import math

from maya.scripts.utils import data_manager
from maya.scripts.utils import guides_manager
from maya.scripts.utils import curve_tool
from maya.scripts.utils import matrix_manager
from maya.scripts.utils import ribbon

reload(data_manager)
reload(guides_manager)
reload(curve_tool)
reload(matrix_manager)
reload(ribbon)

class SpineModule(object):

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

    def make(self, side, spine_joints, spine_controllers):

        """ 
        Create the spine module structure and controllers. Call this method with the side ('L' or 'R') to create the respective spine module.
        Args:
            side (str): The side of the spine ('L' or 'R').
            spine_joints (int): The number of spine joints.
            spine_controllers (int): The number of spine controllers.

        """

        self.spine_joints = spine_joints
        self.spine_controllers = spine_controllers
        self.side = side
        self.module_trn = cmds.createNode("transform", name=f"{self.side}_spineModule_GRP", ss=True, p=self.modules)
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.side}_spineSkinning_GRP", ss=True, p=self.skel_grp)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.side}_spineControllers_GRP", ss=True, p=self.masterwalk_ctl)

        self.load_guides()
        self.create_guides_logic()
        self.controller_creation()
        self.local_hip_chest_setup()
        self.ribbon_setup()

        data_manager.DataExportBiped().append_data("spine_module",
                            {
                                "local_hip_ctl": self.local_hip_ctl,
                                "body_ctl": self.body_ctl,
                                "local_chest_ctl": self.local_chest_ctl,
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
        # Nuevo método de guías: matrices horneadas en Python entre la guía root
        # y la end. Todas comparten la misma orientación (X apunta a la guía
        # siguiente, Y mira al up del mundo) con las posiciones repartidas en
        # línea recta entre ambas — tantas como controladores se pidan. El
        # espaciado lo pondera SAGITTAL_BIAS (ver arriba): no cambia por dónde
        # pasa la recta, solo dónde caen los controles sobre ella.
        root_pos = om.MVector(cmds.xform(self.spine_chain[0], q=True, ws=True, t=True))
        end_pos = om.MVector(cmds.xform(self.spine_chain[-1], q=True, ws=True, t=True))
        cmds.delete(self.spine_chain[0])

        base_matrix = guides_manager._aim_matrix(
            root_pos, end_pos, root_pos + om.MVector(0.0, 1.0, 0.0),
            self.primary_input_axis, self.secondary_input_axis
        )

        self.spine_guides_matrices = []
        for i in range(self.spine_controllers):
            weight = (i / (self.spine_controllers - 1)) ** self.SAGITTAL_BIAS
            pos = root_pos * (1.0 - weight) + end_pos * weight
            self.spine_guides_matrices.append(list(guides_manager._with_translation(base_matrix, pos)))


    def controller_creation(self):

        """
        Create controllers for the spine module.
        """

        self.body_nodes, self.body_ctl = curve_tool.create_controller(name=f"{self.side}_body", offset=["GRP", "SPC", "ANM"], parent=self.controllers_grp, locked_attrs=["sx", "sy", "sz", "v"])
        self.local_hip_nodes, self.local_hip_ctl = curve_tool.create_controller(name=f"{self.side}_pelvis", offset=["GRP", "SPC", "ANM"], parent=self.controllers_grp, locked_attrs=["sx", "sy", "sz", "v"])
        self.local_chest_nodes, self.local_chest_ctl = curve_tool.create_controller(name=f"{self.side}_localChest", offset=["GRP", "SPC", "ANM"], parent=self.controllers_grp, locked_attrs=["sx", "sy", "sz", "v"])
        
        cmds.setAttr(f"{self.body_nodes[0]}.offsetParentMatrix", self.spine_guides_matrices[0], type="matrix")
        cmds.setAttr(f"{self.local_hip_nodes[0]}.offsetParentMatrix", self.spine_guides_matrices[0], type="matrix")

        # Create the spine controllers
        self.spine_nodes = []
        self.spine_ctls = []

        body_rest_inverse = om.MMatrix(self.spine_guides_matrices[0]).inverse()

        for i, matrix in enumerate(self.spine_guides_matrices):

            spine_node, spine_ctl = curve_tool.create_controller(name=f"{self.side}_spine0{i}", offset=["GRP", "SPC", "ANM"], parent=self.controllers_grp, locked_attrs=["v"])
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

        # ----- Stretch setup (UNIFORME) -----
        # El stretch multiplica por IGUAL la distancia entre joints: factor único =
        # longitud real total de la cadena de controles / longitud de reposo. Cada
        # segmento = rest_length * factor (todos crecen lo mismo), siguiendo la
        # dirección de los controles. Stretch_Activate enciende/apaga el efecto.
        cmds.addAttr(self.body_ctl, longName="Stretch", niceName="STRETCH ------", attributeType="enum", enumName="------", keyable=True)
        cmds.setAttr(f"{self.body_ctl}.Stretch", lock=True, keyable=False, channelBox=True)
        cmds.addAttr(self.body_ctl, longName="Stretch_Activate", niceName="Stretch", attributeType="float", minValue=0, maxValue=1, defaultValue=0, keyable=True)

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
            cmds.connectAttr(f"{self.spine_ctls[i - 1]}.worldMatrix[0]", f"{dbt}.inMatrix1")
            cmds.connectAttr(f"{self.spine_ctls[i]}.worldMatrix[0]", f"{dbt}.inMatrix2")
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

        self.stretch_drivers = [self.spine_ctls[0]]
        prev_plug = f"{self.spine_ctls[0]}.worldMatrix[0]"

        for i in range(1, len(self.spine_ctls)):

            target_plug = f"{self.spine_ctls[i]}.worldMatrix[0]"

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
        cmds.connectAttr(f"{self.spine_ctls[0]}.worldMatrix[0]", f"{row_translation}.matrix")
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

        # ----- Local chest setup ------
        cmds.connectAttr(f"{self.spine_ctls[-1]}.worldMatrix[0]", f"{self.local_chest_nodes[0]}.offsetParentMatrix")
        cmds.setAttr(f"{self.local_chest_nodes[0]}.inheritsTransform", 0)
        cmds.select(clear=True)
        local_chest_skinning_jnt = cmds.joint(name=f"{self.side}_localChestSkinning_JNT")
        cmds.setAttr(f"{local_chest_skinning_jnt}.inheritsTransform", 0)
        cmds.connectAttr(f"{self.local_chest_ctl}.worldMatrix[0]", f"{local_chest_skinning_jnt}.offsetParentMatrix")
        cmds.select(clear=True)
        
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
