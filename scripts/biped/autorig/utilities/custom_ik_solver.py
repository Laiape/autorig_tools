import maya.cmds as cmds

def custom_ik_solver(side, chain=[]):

        """
        Custom IK solver for the arm module.

        # cos(b) = (a^2 + c^2 - b^2) / (2ac)
        # cos(c) = (a^2 + b^2 - c^2) / (2ab)
        # a = distance between shoulder and elbow
        # b = distance between elbow and wrist
        # c = distance between shoulder and wrist
        # The angles are calculated using the law of cosines.

        """
        

        a = cmds.getAttr(f"{chain[0]}.translateX")  # Shoulder to Elbow distance
        b = cmds.getAttr(f"{chain[1]}.translateX")  # Elbow to Wrist distance
        c = cmds.getAttr(f"{chain[2]}.translateX")  # Shoulder to Wrist distance

        print((a**2 + c**2 - b**2) / (2 * a * c))
        print((a**2 + b**2 - c**2) / (2 * a * b))

        # Calculate angle B in radians
        distance_between_distance_a = cmds.createNode("distanceBetween", name=f"{side}_upperDistance_DBT", ss=True)
        cmds.connectAttr(f"{chain[0]}.translate.translateX", f"{distance_between_distance_a}.point1.point1X")
        cmds.connectAttr(f"{chain[1]}.translate.translateX", f"{distance_between_distance_a}.point2.point2X")

        distance_between_distance_b = cmds.createNode("distanceBetween", name=f"{side}_lowerDistance_DBT", ss=True)
        cmds.connectAttr(f"{chain[1]}.translate.translateX", f"{distance_between_distance_b}.point1.point1X")
        cmds.connectAttr(f"{chain[2]}.translate.translateX", f"{distance_between_distance_b}.point2.point2X")

        distance_between_distance_c = cmds.createNode("distanceBetween", name=f"{side}_shoulderWristDistance_DBT", ss=True)
        cmds.connectAttr(f"{chain[0]}.translate.translateX", f"{distance_between_distance_c}.point1.point1X")
        cmds.connectAttr(f"{chain[2]}.translate.translateX", f"{distance_between_distance_c}.point2.point2X")

        multiply_node_a_square = cmds.createNode("multiply", name=f"{side}_aSquare_MUL", ss=True)
        cmds.connectAttr(f"{distance_between_distance_a}.distance", f"{multiply_node_a_square}.input[0]")
        cmds.connectAttr(f"{distance_between_distance_a}.distance", f"{multiply_node_a_square}.input[1]")
        multiply_node_b_square = cmds.createNode("multiply", name=f"{side}_bSquare_MUL", ss=True)
        cmds.connectAttr(f"{distance_between_distance_b}.distance", f"{multiply_node_b_square}.input[0]")
        cmds.connectAttr(f"{distance_between_distance_b}.distance", f"{multiply_node_b_square}.input[1]")
        multiply_node_c_square = cmds.createNode("multiply", name=f"{side}_cSquare_MUL", ss=True)
        cmds.connectAttr(f"{distance_between_distance_c}.distance", f"{multiply_node_c_square}.input[0]")
        cmds.connectAttr(f"{distance_between_distance_c}.distance", f"{multiply_node_c_square}.input[1]")
        add_node_ac = cmds.createNode("sum", name=f"{side}_aPlusb_SUM", ss=True)
        cmds.connectAttr(f"{multiply_node_a_square}.output", f"{add_node_ac}.input[0]")
        cmds.connectAttr(f"{multiply_node_c_square}.output", f"{add_node_ac}.input[1]")
        subtract_node_b = cmds.createNode("subtract", name=f"{side}_aPlusbMinusc_SUB", ss=True)
        cmds.connectAttr(f"{add_node_ac}.output", f"{subtract_node_b}.input1")
        cmds.connectAttr(f"{multiply_node_b_square}.output", f"{subtract_node_b}.input2")
        float_constant_2 = cmds.createNode("floatConstant", name=f"{side}_2multiply_FC", ss=True)
        cmds.setAttr(f"{float_constant_2}.inFloat", 2)
        multiply_2ac = cmds.createNode("multiply", name=f"{side}_2ac_MUL", ss=True)
        cmds.connectAttr(f"{distance_between_distance_a}.distance", f"{multiply_2ac}.input[0]")
        cmds.connectAttr(f"{distance_between_distance_c}.distance", f"{multiply_2ac}.input[1]")
        cmds.connectAttr(f"{float_constant_2}.outFloat", f"{multiply_2ac}.input[2]")
        divide_node_cos_b = cmds.createNode("divide", name=f"{side}_cosB_DV", ss=True)
        cmds.connectAttr(f"{subtract_node_b}.output", f"{divide_node_cos_b}.input1")
        cmds.connectAttr(f"{multiply_2ac}.output", f"{divide_node_cos_b}.input2")
        arc_b = cmds.createNode("acos", name=f"{side}_armIkSolverB_ACOS", ss=True)
        cmds.connectAttr(f"{divide_node_cos_b}.output", f"{arc_b}.input")
        cmds.connectAttr(f"{arc_b}.output", f"{ik_chain[0]}.rotateZ") # Shoulder rotation


        # Calculate angle C in radians
        add_node_ab = cmds.createNode("sum", name=f"{side}_aPlusb_SUM", ss=True)
        cmds.connectAttr(f"{multiply_node_a_square}.output", f"{add_node_ab}.input[0]")
        cmds.connectAttr(f"{multiply_node_b_square}.output", f"{add_node_ab}.input[1]")
        subtract_node_c = cmds.createNode("subtract", name=f"{side}_aPlusbMinusc_SUB", ss=True)
        cmds.connectAttr(f"{add_node_ab}.output", f"{subtract_node_c}.input1")
        cmds.connectAttr(f"{multiply_node_c_square}.output", f"{subtract_node_c}.input2")
        multiply_2ab = cmds.createNode("multiply", name=f"{side}_2ab_MUL", ss=True)
        cmds.connectAttr(f"{distance_between_distance_a}.distance", f"{multiply_2ab}.input[0]")
        cmds.connectAttr(f"{distance_between_distance_b}.distance", f"{multiply_2ab}.input[1]")
        cmds.connectAttr(f"{float_constant_2}.outFloat", f"{multiply_2ab}.input[2]")
        divide_node_cos_c = cmds.createNode("divide", name=f"{side}_cosC_DV", ss=True)
        cmds.connectAttr(f"{subtract_node_c}.output", f"{divide_node_cos_c}.input1")
        cmds.connectAttr(f"{multiply_2ab}.output", f"{divide_node_cos_c}.input2")
        arc_c = cmds.createNode("acos", name=f"{side}_armIkSolverC_ACOS", ss=True) 
        cmds.connectAttr(f"{divide_node_cos_c}.output", f"{arc_c}.input")
        subtract_180 = cmds.createNode("subtract", name=f"{side}_180_SUB", ss=True)
        cmds.setAttr(f"{subtract_180}.input1", 180)
        cmds.connectAttr(f"{arc_c}.output", f"{subtract_180}.input2")
        cmds.connectAttr(f"{subtract_180}.output", f"{ik_chain[1]}.rotateZ") # Elbow rotation