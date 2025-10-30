import maya.cmds as cmds

def triangle_solver(name, guides=[], controllers=[], trn_guides=[], use_stretch=False, use_soft=False, ik_handle_manager=False, primary_mode=(1,0,0), secondary_mode=(0,1,0)):
        
        """Custom IK solver for biped characters. Cosinus theorem based.
        Args:
            guides (list): List of guide objects.
            controllers (list): List of controller objects.
        Returns:
                None
                """
        master_walk_ctl = "C_masterwalk_CTL"
        side = guides[0].split('_')[0]
        if side == 'R':
                primary_mode = (-1,0,0)
                secondary_mode = (0,1,0)
        grp_upper = controllers[0].replace('CTL', 'GRP')
        grp_lower = controllers[1].replace('CTL', 'GRP')
        grp_eff = controllers[2].replace('CTL', 'GRP')

        guides_00_name = side + "_" + guides[0].split('_')[1] + '_GUIDE'
        guides_01_name = side + "_" + guides[1].split('_')[1] + '_GUIDE'
        guides_02_name = side + "_" + guides[2].split('_')[1] + '_GUIDE'

        if ik_handle_manager == True:

                ik_handle_manager_mmx = cmds.createNode('multMatrix', name=f"{name}IkHandleManager_MMX", ss=True)
                cmds.connectAttr(f"{guides[2]}", ik_handle_manager_mmx+'.matrixIn[0]') # connect ankle guide world matrix to ik handle manager
                cmds.connectAttr(f"{trn_guides[-2]}.worldInverseMatrix[0]", ik_handle_manager_mmx+'.matrixIn[1]') # connect ball guide inverse world matrix to ik handle manager
                cmds.connectAttr(f"{controllers[-1]}.worldMatrix[0]", ik_handle_manager_mmx+'.matrixIn[2]') # connect ball controller world matrix to ik handle manager

        if use_stretch == True:
                distance_between_eff, distance_between_up, distance_between_low, current_length = stretch(name=name, master_walk_ctl=master_walk_ctl, guides=guides, controllers=controllers, trn_guides=trn_guides)
                if ik_handle_manager == True:
                        cmds.connectAttr(ik_handle_manager_mmx+'.matrixSum', current_length+'.inMatrix2', f=True) # connect ik handle manager output to current length
                if use_soft == True:
                        upper_length_scaler, lower_length_scaler = soft_ik(side=side, limb=name.split('_')[1], ik_controller=controllers[2], upper_length_node=distance_between_up, lower_length_node=distance_between_low, effector_length_node=distance_between_eff)
                        
                        upper_length_scaled = cmds.createNode('multiply', name=f"{side}_{name.split('_')[1]}UpperLengthScaled_MULT", ss=True) # scaled upper length
                        cmds.connectAttr(upper_length_scaler, upper_length_scaled+'.input[0]')
                        cmds.connectAttr(distance_between_up+'.output', upper_length_scaled+'.input[1]')
                        lower_length_scaled = cmds.createNode('multiply', name=f"{side}_{name.split('_')[1]}LowerLengthScaled_MULT", ss=True) # scaled lower length
                        cmds.connectAttr(lower_length_scaler, lower_length_scaled+'.input[0]')
                        cmds.connectAttr(distance_between_low+'.output', lower_length_scaled+'.input[1]')

        # Create nodes for the IK solver
        multiply_upper = cmds.createNode('multiply', name=guides_00_name.replace('_GUIDE', 'ASquared_MULT'), ss=True) # a squared
        multiply_lower = cmds.createNode('multiply', name=guides_01_name.replace('_GUIDE', 'BSquared_MULT'), ss=True) # b squared
        multiply_eff = cmds.createNode('multiply', name=guides_02_name.replace('_GUIDE', 'CSquared_MULT'), ss=True) # c squared

        
        if use_stretch == False:
                distance_between_eff = cmds.createNode('distanceBetween', name=guides_02_name.replace('_GUIDE', 'InitialLength_DBT'), ss=True)
                distance_between_up = cmds.createNode('distanceBetween', name=guides_00_name.replace('_GUIDE', 'InitialLength_DBT'), ss=True)
                distance_between_low = cmds.createNode('distanceBetween', name=guides_01_name.replace('_GUIDE', 'InitialLength_DBT'), ss=True)
                cmds.connectAttr(guides[0], distance_between_up+'.inMatrix1') # a
                cmds.connectAttr(guides[1], distance_between_up+'.inMatrix2')
                cmds.connectAttr(guides[1], distance_between_low+'.inMatrix1') # b
                cmds.connectAttr(guides[2], distance_between_low+'.inMatrix2')
                cmds.connectAttr(guides[0], distance_between_eff+'.inMatrix1') # c
                cmds.connectAttr(guides[2], distance_between_eff+'.inMatrix2')
                cmds.connectAttr(distance_between_up+'.distance', multiply_upper+'.input[0]') # a2
                cmds.connectAttr(distance_between_up+'.distance', multiply_upper+'.input[1]')
                cmds.connectAttr(distance_between_low+'.distance', multiply_lower+'.input[0]') # b2
                cmds.connectAttr(distance_between_low+'.distance', multiply_lower+'.input[1]')
                cmds.connectAttr(distance_between_eff+'.distance', multiply_eff+'.input[0]') # c2
                cmds.connectAttr(distance_between_eff+'.distance', multiply_eff+'.input[1]')
                if use_soft == True:
                        upper_length_scaler, lower_length_scaler = soft_ik(side=side, limb=name.split('_')[1], ik_controller=controllers[2], upper_length_node=distance_between_up, lower_length_node=distance_between_low, effector_length_node=distance_between_eff)
        else:
                if use_soft == True:
                        cmds.connectAttr(upper_length_scaled+'.output', multiply_upper+'.input[0]') # a2
                        cmds.connectAttr(upper_length_scaled+'.output', multiply_upper+'.input[1]')
                        cmds.connectAttr(lower_length_scaled+'.output', multiply_lower+'.input[0]') #b2
                        cmds.connectAttr(lower_length_scaled+'.output', multiply_lower+'.input[1]')
                        cmds.connectAttr(distance_between_eff+'.output', multiply_eff+'.input[0]') # c2
                        cmds.connectAttr(distance_between_eff+'.output', multiply_eff+'.input[1]')
                else:
                        cmds.connectAttr(distance_between_up+'.output', multiply_upper+'.input[0]') # a2
                        cmds.connectAttr(distance_between_up+'.output', multiply_upper+'.input[1]')
                        cmds.connectAttr(distance_between_low+'.output', multiply_lower+'.input[0]') # b2
                        cmds.connectAttr(distance_between_low+'.output', multiply_lower+'.input[1]')
                        cmds.connectAttr(distance_between_eff+'.output', multiply_eff+'.input[0]') # c2
                        cmds.connectAttr(distance_between_eff+'.output', multiply_eff+'.input[1]')

        sum_node = cmds.createNode('sum', name=guides_00_name.replace('_GUIDE', 'ASquaredPlusCSquared_UpperFull_SUM'), ss=True)
        cmds.connectAttr(multiply_upper+'.output', sum_node+'.input[0]') # a2+c2
        cmds.connectAttr(multiply_eff+'.output', sum_node+'.input[1]')

        subtract_node = cmds.createNode('subtract', name=guides_02_name.replace('_GUIDE', 'UpperFullMinusBSquared_Lower_SUB'), ss=True)
        cmds.connectAttr(sum_node+'.output', subtract_node+'.input1') # a2+c2
        cmds.connectAttr(multiply_lower+'.output', subtract_node+'.input2') # - b2

        multiply_node = cmds.createNode('multiply', name=guides_00_name.replace('_GUIDE', '2ac_MULT'), ss=True)
        float_constant = cmds.createNode('floatConstant', name=guides_00_name.replace('_GUIDE', '2_FCN'), ss=True)
        cmds.setAttr(float_constant+'.inFloat', 2)
        if use_stretch == False:
                cmds.connectAttr(distance_between_up+'.distance', multiply_node+'.input[0]') # a
                cmds.connectAttr(distance_between_eff+'.distance', multiply_node+'.input[1]') # c
        else:
                if use_soft == True:
                        cmds.connectAttr(upper_length_scaled+'.output', multiply_node+'.input[0]') # a
                        cmds.connectAttr(distance_between_eff+'.output', multiply_node+'.input[1]') # c
                else:
                        cmds.connectAttr(distance_between_up+'.output', multiply_node+'.input[0]') # a
                        cmds.connectAttr(distance_between_eff+'.output', multiply_node+'.input[1]') # c
        cmds.connectAttr(float_constant+'.outFloat', multiply_node+'.input[2]') # *2ac

        divide_node = cmds.createNode('divide', name=guides_00_name.replace('_GUIDE', 'CosineValue_DIV'), ss=True)
        cmds.connectAttr(subtract_node+'.output', divide_node+'.input1') # a2+c2-b2
        cmds.connectAttr(multiply_node+'.output', divide_node+'.input2') # 2ac

        acos_node = cmds.createNode('acos', name=guides_00_name.replace('_GUIDE', 'Angle_ACOS'), ss=True)
        cmds.connectAttr(divide_node+'.output', acos_node+'.input') # (a2+c2-b2)/2ac
        
        # Lower controller rotation
        add_lower = cmds.createNode('sum', name=guides_01_name.replace('_GUIDE', 'ASquaredPlusBSquared_SUM'), ss=True)
        cmds.connectAttr(multiply_upper+'.output', add_lower+'.input[0]') # a2+b2
        cmds.connectAttr(multiply_lower+'.output', add_lower+'.input[1]')

        subtract_lower = cmds.createNode('subtract', name=guides_01_name.replace('_GUIDE', 'SUB'), ss=True)
        cmds.connectAttr(add_lower+'.output', subtract_lower+'.input1') # a2+b2
        cmds.connectAttr(multiply_eff+'.output', subtract_lower+'.input2') # - c2

        multiply_lower_2 = cmds.createNode('multiply', name=guides_01_name.replace('GUIDE', '2ab_MULT'), ss=True)
        if use_stretch == False:
                cmds.connectAttr(distance_between_up+'.distance', multiply_lower_2+'.input[0]') # a
                cmds.connectAttr(distance_between_low+'.distance', multiply_lower_2+'.input[1]') # b
        else:
                if use_soft == True:
                        cmds.connectAttr(upper_length_scaled+'.output', multiply_lower_2+'.input[0]') # a
                        cmds.connectAttr(lower_length_scaled+'.output', multiply_lower_2+'.input[1]') # b
                else:
                        cmds.connectAttr(distance_between_up+'.output', multiply_lower_2+'.input[0]') # a
                        cmds.connectAttr(distance_between_low+'.output', multiply_lower_2+'.input[1]') # b
        cmds.connectAttr(float_constant+'.outFloat', multiply_lower_2+'.input[2]') # *2

        divide_lower = cmds.createNode('divide', name=guides_01_name.replace('GUIDE', 'CosValue_DIV'), ss=True)
        cmds.connectAttr(subtract_lower+'.output', divide_lower+'.input1') # a2+b2-c2
        cmds.connectAttr(multiply_lower_2+'.output', divide_lower+'.input2') # 2ab

        # Upper WM
        aim_matrix = cmds.createNode('aimMatrix', name=guides_02_name.replace('_GUIDE', 'Eff_AMX'), ss=True) # aim matrix for end controller,
        cmds.setAttr(aim_matrix+'.primaryInputAxis', *primary_mode, type="double3") # X axis
        cmds.setAttr(aim_matrix+'.secondaryInputAxis', *secondary_mode, type="double3") # Y axis
        cmds.setAttr(aim_matrix+'.secondaryTargetVector', *secondary_mode, type="double3") # Y axis
        cmds.setAttr(aim_matrix+'.secondaryMode', 1) # Aim to secondary axis
        cmds.connectAttr(f"{controllers[0]}.worldMatrix[0]", aim_matrix+'.inputMatrix') # input
        if ik_handle_manager == True:
                cmds.connectAttr(ik_handle_manager_mmx+'.matrixSum', aim_matrix+'.inputMatrix', f=True) # connect ik handle manager output to aim matrix
        cmds.connectAttr(f"{controllers[2]}.worldMatrix[0]", aim_matrix+'.primaryTargetMatrix') # target
        cmds.connectAttr(f"{controllers[1]}.worldMatrix[0]", aim_matrix+'.secondaryTargetMatrix') # secondary target


        sin_upper = cmds.createNode('sin', name=guides_00_name.replace('GUIDE', 'SIN'), ss=True)
        four_by_four_up_local_rotation = cmds.createNode('fourByFourMatrix', name=guides_00_name.replace('_GUIDE', 'LocalRotation_F4FX'), ss=True) # local rotation matrix for upper arm
        negate_sin = cmds.createNode('negate', name=guides_00_name.replace('_GUIDE', 'Sin_NEG'), ss=True)
        cmds.connectAttr(acos_node+'.output', sin_upper+'.input') # upper angle
        cmds.connectAttr(sin_upper+'.output', negate_sin+'.input') # negate sin
        cmds.connectAttr(divide_node+'.output', four_by_four_up_local_rotation+'.in00') # cos
        cmds.connectAttr(sin_upper+'.output', four_by_four_up_local_rotation+'.in01') # sin
        cmds.connectAttr(negate_sin+'.output', four_by_four_up_local_rotation+'.in10') # -sin
        cmds.connectAttr(divide_node+'.output', four_by_four_up_local_rotation+'.in11') # cos

        mult_matrix_upper_wm = cmds.createNode('multMatrix', name=guides_00_name.replace('_GUIDE', 'UpWM_MMT'), ss=True) # world matrix mult for upper arm
        cmds.connectAttr(aim_matrix+'.outputMatrix', mult_matrix_upper_wm+'.matrixIn[1]') # connect aim matrix to world matrix
        cmds.connectAttr(four_by_four_up_local_rotation+'.output', mult_matrix_upper_wm+'.matrixIn[0]') # connect local rotation to world matrix
        upper_wm = mult_matrix_upper_wm+'.matrixSum' # upper world matrix
        locator_upper = cmds.spaceLocator(name=f"{side}_armUpper_LOC")[0]
        cmds.connectAttr(upper_wm, locator_upper+'.offsetParentMatrix') # connect upper
        #  ----- This will be used to connect it to the blend matrix later -----

        # Lower WM
        four_by_four_low_local_rotation = cmds.createNode('fourByFourMatrix', name=guides_01_name.replace('_GUIDE', 'Local_F4FX'), ss=True) # local matrix for lower arm

        negate_sin_lower = cmds.createNode('negate', name=guides_01_name.replace('_GUIDE', 'SinNegate_NEG'), ss=True)
        negate_cos_lower = cmds.createNode('negate', name=guides_01_name.replace('_GUIDE', 'CosNegate_NEG'), ss=True)
        cmds.connectAttr(divide_lower+'.output', negate_cos_lower+'.input') # negate cos
        square_cos_lower = cmds.createNode('multiply', name=guides_01_name.replace('_GUIDE', 'CosSquared_MULT'), ss=True)
        cmds.connectAttr(divide_lower+'.output', square_cos_lower+'.input[0]') # cos
        cmds.connectAttr(divide_lower+'.output', square_cos_lower+'.input[1]') # cos
        subtract_to_sin = cmds.createNode('subtract', name=guides_01_name.replace('_GUIDE', 'ToSin_SUB'), ss=True)
        max_value = cmds.createNode('max', name=guides_01_name.replace('_GUIDE', 'MaxValue_MAX'), ss=True)
        float_constant_zero = cmds.createNode('floatConstant', name=guides_01_name.replace('_GUIDE', 'Zero_FCN'), ss=True)
        cmds.setAttr(float_constant_zero+'.inFloat', 0) # constant 0
        cmds.connectAttr(float_constant_zero+'.outFloat', max_value+'.input[0]')
        cmds.connectAttr(subtract_to_sin+'.output', max_value+'.input[1]') # max sin

        float_constant_one = cmds.createNode('floatConstant', name=guides_01_name.replace('_GUIDE', 'One_FCN'), ss=True)
        cmds.setAttr(float_constant_one+'.inFloat', 1) # constant 1
        cmds.connectAttr(float_constant_one+'.outFloat', subtract_to_sin+'.input1') # 1
        cmds.connectAttr(square_cos_lower+'.output', subtract_to_sin+'.input2') # cos2
        power_to_sin = cmds.createNode('power', name=guides_01_name.replace('_GUIDE', 'SinValue_POWER'), ss=True)
        cmds.setAttr(power_to_sin+'.exponent', 0.5) # square
        cmds.connectAttr(max_value+'.output', power_to_sin+'.input') # sin
        cmds.connectAttr(power_to_sin+'.output', negate_sin_lower+'.input') # negate sin

        cmds.connectAttr(negate_cos_lower+'.output', four_by_four_low_local_rotation+'.in00') # cos
        cmds.connectAttr(negate_sin_lower+'.output', four_by_four_low_local_rotation+'.in01') # -sin
        cmds.connectAttr(power_to_sin+'.output', four_by_four_low_local_rotation+'.in10') # sin
        cmds.connectAttr(negate_cos_lower+'.output', four_by_four_low_local_rotation+'.in11') # cos
        if side == 'L':
                if use_stretch == False:
                        cmds.connectAttr(distance_between_up+'.distance', four_by_four_low_local_rotation+'.in30') # position x, add the position
                else:
                        if use_soft == True:
                                cmds.connectAttr(upper_length_scaled+'.output', four_by_four_low_local_rotation+'.in30') # position x, add the position
                        else:
                                cmds.connectAttr(distance_between_up+'.output', four_by_four_low_local_rotation+'.in30') # position x, add the position
        else:
                negate_position_x = cmds.createNode('negate', name=guides_01_name.replace('_GUIDE', 'PosX_NEG'), ss=True)
                if use_stretch == False:
                        cmds.connectAttr(distance_between_up+'.distance', negate_position_x+'.input') # negate position
                else:
                        if use_soft == True:
                                cmds.connectAttr(upper_length_scaled+'.output', negate_position_x+'.input') # negate position
                        else:
                                cmds.connectAttr(distance_between_up+'.output', negate_position_x+'.input') # negate position
                cmds.connectAttr(negate_position_x+'.output', four_by_four_low_local_rotation+'.in30') # position x, add the position


        mult_matrix_lower_rwm = cmds.createNode('multMatrix', name=guides_01_name.replace('_GUIDE', 'LowWM_MMT'), ss=True) # world matrix rotation mult for lower arm
        cmds.connectAttr(upper_wm, mult_matrix_lower_rwm+'.matrixIn[1]') # connect upper world matrix to lower world matrix
        cmds.connectAttr(four_by_four_low_local_rotation+'.output', mult_matrix_lower_rwm+'.matrixIn[0]') # connect local rotation to world matrix
        lower_wm = mult_matrix_lower_rwm+'.matrixSum' # lower world matrix
        lower_lm = four_by_four_low_local_rotation+'.output' # lower local matrix
        locator_lower = cmds.spaceLocator(name=f"{side}_armLower_LOC")[0]
        cmds.connectAttr(lower_wm, locator_lower+'.offsetParentMatrix') # connect lower
        # ----- This will be used to connect it to the blend matrix later -----

        # Effector WM
        mult_matrix_eff = cmds.createNode('multMatrix', name=f"{name}EffectorLocalMatrix_MMT", ss=True) # world matrix mult for end effector
        inverse_matrix_lower = cmds.createNode('inverseMatrix', name=guides_02_name.replace('_GUIDE', 'Lower_INV'), ss=True)
        cmds.connectAttr(lower_lm, inverse_matrix_lower+'.inputMatrix') # connect lower local matrix to inverse
        cmds.connectAttr(f"{controllers[2]}.worldMatrix[0]", mult_matrix_eff+'.matrixIn[0]')
        if ik_handle_manager == True:
                cmds.connectAttr(ik_handle_manager_mmx+'.matrixSum', mult_matrix_eff+'.matrixIn[0]', f=True) # connect ik handle manager output to effector world matrix
        cmds.connectAttr(inverse_matrix_lower+'.outputMatrix', mult_matrix_eff+'.matrixIn[1]')

        four_by_four_effector_position = cmds.createNode('fourByFourMatrix', name=f"{name}EffectorPosition_F4FX", ss=True) # local position matrix for end effector
        if side == 'L':
                if use_stretch == False:
                        cmds.connectAttr(distance_between_low+'.distance', four_by_four_effector_position+'.in30') # position x
                else:
                        if use_soft == True:
                                cmds.connectAttr(lower_length_scaled+'.output', four_by_four_effector_position+'.in30') # position x
                        else:
                                cmds.connectAttr(distance_between_low+'.output', four_by_four_effector_position+'.in30') # position x
        else:
                negate_eff_pos_x = cmds.createNode('negate', name=guides_02_name.replace('_GUIDE', 'EffPosX_NEG'), ss=True)
                if use_stretch == False:
                        cmds.connectAttr(distance_between_low+'.distance', negate_eff_pos_x+'.input') # negate position
                else:
                        if use_soft == True:
                                cmds.connectAttr(lower_length_scaled+'.output', negate_eff_pos_x+'.input') # negate position
                        else:
                                cmds.connectAttr(distance_between_low+'.output', negate_eff_pos_x+'.input') # negate position

                cmds.connectAttr(negate_eff_pos_x+'.output', four_by_four_effector_position+'.in30') # position x
        pick_matrix_effector = cmds.createNode('pickMatrix', name=f"{name}EffectorPick_MMT", ss=True) # pick matrix for end effector
        cmds.setAttr(f"{pick_matrix_effector}.useTranslate", 0)
        cmds.connectAttr(mult_matrix_eff+'.matrixSum', pick_matrix_effector+'.inputMatrix') # connect world matrix mult to pick matrix
        mult_matrix_add_effector_pos = cmds.createNode('multMatrix', name=f"{name}EffectorPos_MMT", ss=True) # final mult matrix for end effector
        cmds.connectAttr(pick_matrix_effector+'.outputMatrix', mult_matrix_add_effector_pos+'.matrixIn[0]')
        cmds.connectAttr(four_by_four_effector_position+'.output', mult_matrix_add_effector_pos+'.matrixIn[1]')
        effector_mult_matrix_wm = cmds.createNode('multMatrix', name=f"{name}EffectorWM_MMT", ss=True) # world matrix mult for end effector
        cmds.connectAttr(lower_wm, effector_mult_matrix_wm+'.matrixIn[1]') # connect lower world matrix to effector world matrix
        cmds.connectAttr(mult_matrix_add_effector_pos+'.matrixSum', effector_mult_matrix_wm+'.matrixIn[0]')
        effector_wm = effector_mult_matrix_wm+'.matrixSum' # effector world matrix
        locator_effector = cmds.spaceLocator(name=f"{side}_armEffector_LOC")[0]
        cmds.connectAttr(effector_wm, locator_effector+'.offsetParentMatrix') # connect effector
        # ----- This will be used to connect it to the blend matrix

        ik_matrices = [upper_wm, lower_wm, effector_wm]

        return ik_matrices


def single_chain_solver(blend_matrix, controller, guides=[], primary_mode=(1,0,0), secondary_mode=(0,1,0)):

        """Custom IK solver for single bone chains.
        Args:
                blend_matrix (list): Blend matrix of the controller. (ik-fk blend matrix)
                controller (str): Name of the controller object that will constraint the single chain solver.
                guides (list): List of the affected guide objects (start-end).
        Returns:
                matrix
                """
        side = blend_matrix[0].split('_')[0]
        if side == 'R':
                primary_mode = (-1,0,0)
                secondary_mode = (0,1,0)

        name_ctl = controller.split('_')[1]
        name_guide = guides[1].split('_')[1]

        distance = cmds.createNode('distanceBetween', name=f"{side}_{name_ctl}To{name_guide}_DBT", ss=True) # distance between controller and guide
        cmds.connectAttr(f"{guides[0]}.worldMatrix[0]", f"{distance}.inMatrix1") # start
        cmds.connectAttr(f"{guides[1]}.worldMatrix[0]", f"{distance}.inMatrix2") # end

        controller_position = cmds.createNode('fourByFourMatrix', name=controller.replace('_CTL', 'CtlPosition_F4FX'), ss=True) # local position matrix for controller
        if primary_mode == (1,0,0) or primary_mode == (-1,0,0):
                cmds.connectAttr(distance+'.distance', controller_position+'.in30') # position x
                if side == 'R':
                        negate_pos_x = cmds.createNode('negate', name=controller.replace('_CTL', 'PosX_NEG'), ss=True)
                        cmds.connectAttr(distance+'.distance', negate_pos_x+'.input') # negate position
                        cmds.connectAttr(negate_pos_x+'.output', controller_position+'.in30') # position x
        elif primary_mode == (0,1,0) or primary_mode == (0,-1,0):
                cmds.connectAttr(distance+'.distance', controller_position+'.in31') # position y
        elif primary_mode == (0,0,1) or primary_mode == (0,0,-1):
                cmds.connectAttr(distance+'.distance', controller_position+'.in32') # position z

        aim_matrix_rotation = cmds.createNode('aimMatrix', name=controller.replace('_CTL', '_AMX'), ss=True) # aim matrix for end controller,
        cmds.setAttr(aim_matrix_rotation+'.primaryInputAxis', *primary_mode, type="double3") # X axis
        cmds.setAttr(aim_matrix_rotation+'.secondaryInputAxis', *secondary_mode, type="double3") # Y axis
        cmds.setAttr(aim_matrix_rotation+'.secondaryTargetVector', *secondary_mode, type="double3") # Y axis
        cmds.setAttr(aim_matrix_rotation+'.secondaryMode', 2) # Align to secondary axis
        cmds.connectAttr(blend_matrix, aim_matrix_rotation+'.inputMatrix') # input
        cmds.connectAttr(f"{controller}.worldMatrix[0]", aim_matrix_rotation+'.primaryTargetMatrix') # target
        cmds.connectAttr(f"{controller}.worldMatrix[0]", aim_matrix_rotation+'.secondaryTargetMatrix') # secondary target

        parent_matrix = cmds.createNode('parentMatrix', name=guides[0].replace('_GUIDE', 'SC_MMT'), ss=True) # final mult matrix for controller
        cmds.connectAttr(aim_matrix_rotation+'.outputMatrix', parent_matrix+'.inputMatrix') # connect aim matrix to parent matrix
        cmds.connectAttr(controller_position+'.output', parent_matrix+'.target[0].targetMatrix') # connect position matrix to parent matrix

        effector_wm = parent_matrix+'.outputMatrix' # effector world matrix

        return effector_wm

def stretch(name, master_walk_ctl, guides=[], controllers=[], trn_guides=[]):

        """
        Stretch system for limbs.
        Args:
                name (str): Name of the limb (e.g., "L_arm").
                master_walk_ctl (str): Name of the master walk controller for global scale reference.
                guides (list): List of guide objects.
                controllers (list): List of controller objects.
                trn_guides (list): List of transform guide objects.
        Returns:
                distance_between_eff (str): Node representing the distance between start and effector.
                distance_between_up (str): Node representing the distance between start and mid.
                distance_between_low (str): Node representing the distance between mid and effector.
        """

        side = name.split('_')[0]
        limb = name.split('_')[1]
        limb_length = cmds.createNode('distanceBetween', name=f"{side}_{limb}Length_DBT", ss=True) # arm length distance between start and effector
        cmds.connectAttr(f"{trn_guides[0]}.worldMatrix[0]", f"{limb_length}.inMatrix1") # start
        cmds.connectAttr(f"{trn_guides[2]}.worldMatrix[0]", f"{limb_length}.inMatrix2") # effector

        current_length = cmds.createNode('distanceBetween', name=f"{side}_{limb}CurrentLength_DBT", ss=True) # arm length distance between start and effector
        cmds.connectAttr(f"{controllers[0]}.worldMatrix[0]", f"{current_length}.inMatrix1") # start
        cmds.connectAttr(f"{controllers[2]}.worldMatrix[0]", f"{current_length}.inMatrix2") # effector

        global_scale_factor = cmds.createNode('divide', name=f"{side}_{limb}GlobalScale_DIV", ss=True)
        cmds.connectAttr(f"{current_length}.distance", f"{global_scale_factor}.input1")
        cmds.connectAttr(f"{master_walk_ctl}.globalScale", f"{global_scale_factor}.input2")

        limb_upper_length = cmds.createNode('distanceBetween', name=f"{side}_{limb}UpperInitialLength_DBT", ss=True)
        cmds.connectAttr(f"{trn_guides[0]}.worldMatrix[0]", f"{limb_upper_length}.inMatrix1") # start
        cmds.connectAttr(f"{trn_guides[1]}.worldMatrix[0]", f"{limb_upper_length}.inMatrix2") # mid

        limb_lower_length = cmds.createNode('distanceBetween', name=f"{side}_{limb}LowerInitialLength_DBT", ss=True)
        cmds.connectAttr(f"{trn_guides[1]}.worldMatrix[0]", f"{limb_lower_length}.inMatrix1") # mid
        cmds.connectAttr(f"{trn_guides[2]}.worldMatrix[0]", f"{limb_lower_length}.inMatrix2") # effector

        sum_upper_lower = cmds.createNode('sum', name=f"{side}_{limb}InitialLength_SUM", ss=True)
        cmds.connectAttr(f"{limb_upper_length}.distance", f"{sum_upper_lower}.input[0]") # upper length
        cmds.connectAttr(f"{limb_lower_length}.distance", f"{sum_upper_lower}.input[1]") # lower length

        divide_length = cmds.createNode('divide', name=f"{side}_{limb}LengthRatio_DIV", ss=True)
        cmds.connectAttr(f"{global_scale_factor}.output", f"{divide_length}.input1") # current length
        cmds.connectAttr(f"{sum_upper_lower}.output", f"{divide_length}.input2") # upper + lower length

        max_length = cmds.createNode('max', name=f"{side}_{limb}Scaler_MAX", ss=True) # max node to avoid scaling down
        float_constant_one = cmds.createNode('floatConstant', name=f"{side}_{limb}One_FCN", ss=True)
        cmds.setAttr(f"{float_constant_one}.inFloat", 1) # constant 1
        cmds.connectAttr(f"{float_constant_one}.outFloat", f"{max_length}.input[0]") # connect 1
        cmds.connectAttr(f"{divide_length}.output", f"{max_length}.input[1]") # connect division result

        remap_stretch = cmds.createNode('remapValue', name=f"{side}_{limb}Stretch_RMV", ss=True) # remap node to control stretch influence
        cmds.connectAttr(f"{controllers[2]}.Stretch", f"{remap_stretch}.inputValue") # connect stretch attribute
        cmds.setAttr(f"{remap_stretch}.inputMin", 0)
        cmds.setAttr(f"{remap_stretch}.inputMax", 1)
        cmds.setAttr(f"{remap_stretch}.outputMin", 1)
        cmds.connectAttr(f"{max_length}.output", f"{remap_stretch}.outputMax") # connect max node to remap output max

        multiply_upper_length = cmds.createNode('multiply', name=f"{side}_{limb}UpperLength_MULT", ss=True) # multiply upper length by scaler
        cmds.connectAttr(f"{limb_upper_length}.distance", f"{multiply_upper_length}.input[0]") # upper length
        cmds.connectAttr(f"{remap_stretch}.outValue", f"{multiply_upper_length}.input[1]") # max length
        cmds.connectAttr(f"{controllers[2]}.upperLengthMult", f"{multiply_upper_length}.input[2]") # connect stretch attribute

        multiply_lower_length = cmds.createNode('multiply', name=f"{side}_{limb}LowerLength_MULT", ss=True) # multiply lower length by scaler
        cmds.connectAttr(f"{limb_lower_length}.distance", f"{multiply_lower_length}.input[0]") # lower length
        cmds.connectAttr(f"{remap_stretch}.outValue", f"{multiply_lower_length}.input[1]") # max length
        cmds.connectAttr(f"{controllers[2]}.lowerLengthMult", f"{multiply_lower_length}.input[2]") # connect stretch attribute

        length_final = cmds.createNode("sum", name=f"{side}_{limb}FinalLength_SUM", ss=True)
        cmds.connectAttr(f"{multiply_upper_length}.output", f"{length_final}.input[0]")
        cmds.connectAttr(f"{multiply_lower_length}.output", f"{length_final}.input[1]")


        clamped_final_length = cmds.createNode('min', name=f"{side}_{limb}ClampedFinalLength_MIN", ss=True) 
        cmds.connectAttr(f"{length_final}.output", f"{clamped_final_length}.input[0]")
        cmds.connectAttr(f"{global_scale_factor}.output", f"{clamped_final_length}.input[1]")

        return clamped_final_length, multiply_upper_length, multiply_lower_length, current_length

def soft_ik(side, limb, ik_controller, upper_length_node, lower_length_node, effector_length_node):

        # Cosine law for the upper angle = ((a^2 + c^2 - b^2) / (2ac))
        upper_soft_multiply = cmds.createNode('multiply', name=f"{side}_{limb}UpperLengthSquaredSoft_MUL", ss=True)
        lower_soft_multiply = cmds.createNode('multiply', name=f"{side}_{limb}LowerLengthSquaredSoft_MUL", ss=True)
        effector_soft_multiply = cmds.createNode('multiply', name=f"{side}_{limb}EffectorLengthSquaredSoft_MUL", ss=True)
        float_constant = cmds.createNode('floatConstant', name=f"{side}_{limb}Soft2_FCN", ss=True)
        cmds.setAttr(float_constant+'.inFloat', 2)

        cmds.connectAttr(upper_length_node+'.output', upper_soft_multiply+'.input[0]') # a
        cmds.connectAttr(upper_length_node+'.output', upper_soft_multiply+'.input[1]') # a
        cmds.connectAttr(lower_length_node+'.output', lower_soft_multiply+'.input[0]') # b
        cmds.connectAttr(lower_length_node+'.output', lower_soft_multiply+'.input[1]') # b
        cmds.connectAttr(effector_length_node+'.output', effector_soft_multiply+'.input[0]') # c
        cmds.connectAttr(effector_length_node+'.output', effector_soft_multiply+'.input[1]') # c

        # Sum a^2 + c^2
        sum_upper = cmds.createNode('sum', name=f"{side}_{limb}SoftUpperSum_SUM", ss=True)
        cmds.connectAttr(upper_soft_multiply+'.output', sum_upper+'.input[0]') # a2
        cmds.connectAttr(effector_soft_multiply+'.output', sum_upper+'.input[1]') # c2
        # Subtract b^2
        subtract_lower = cmds.createNode('subtract', name=f"{side}_{limb}SoftLowerSubtract_SUB", ss=True)
        cmds.connectAttr(lower_soft_multiply+'.output', subtract_lower+'.input2') # b2
        cmds.connectAttr(sum_upper+'.output', subtract_lower+'.input1') # a2 + c2
        # Multiply 2ac
        multiply_ac = cmds.createNode('multiply', name=f"{side}_{limb}Soft2ac_MUL", ss=True)
        cmds.connectAttr(upper_length_node+'.output', multiply_ac+'.input[0]') # a
        cmds.connectAttr(effector_length_node+'.output', multiply_ac+'.input[1]') # c
        cmds.connectAttr(float_constant+'.outFloat', multiply_ac+'.input[2]') # *2
        # Divide (a2 + c2 - b2) / 2ac
        divide_cosine = cmds.createNode('divide', name=f"{side}_{limb}SoftCosineValue_DIV", ss=True)
        cmds.connectAttr(subtract_lower+'.output', divide_cosine+'.input1') # a2 + c2 - b2
        cmds.connectAttr(multiply_ac+'.output', divide_cosine+'.input2') # 2ac

        # Square the sin height
        cosine_upper_squared = cmds.createNode('multiply', name=f"{side}_{limb}SoftUpperHeightSquared_MUL", ss=True)
        cmds.connectAttr(divide_cosine+'.output', cosine_upper_squared+'.input[0]') # sin height
        cmds.connectAttr(divide_cosine+'.output', cosine_upper_squared+'.input[1]') # sin height
        
        float_constant_one = cmds.createNode('floatConstant', name=f"{side}_{limb}SoftOne_FCN", ss=True)
        cmds.setAttr(float_constant_one+'.inFloat', 1)
        subtract_to_cos = cmds.createNode('subtract', name=f"{side}_{limb}SoftToCos_SUB", ss=True)
        float_constant_zero = cmds.createNode('floatConstant', name=f"{side}_{limb}SoftZero_FCN", ss=True)
        cmds.setAttr(float_constant_zero+'.inFloat', 0)

        max_cosine = cmds.createNode('max', name=f"{side}_{limb}SoftMaxCosine_MAX", ss=True)
        cmds.connectAttr(float_constant_zero+'.outFloat', max_cosine+'.input[0]')
        cmds.connectAttr(subtract_to_cos+'.output', max_cosine+'.input[1]')
        cmds.connectAttr(float_constant_one+'.outFloat', subtract_to_cos+'.input1') # 1
        cmds.connectAttr(cosine_upper_squared+'.output', subtract_to_cos+'.input2') # sin^2

        power_to_cos = cmds.createNode('power', name=f"{side}_{limb}SoftCosValue_POWER", ss=True)
        cmds.setAttr(power_to_cos+'.exponent', 0.5) # square root
        cmds.connectAttr(max_cosine+'.output', power_to_cos+'.input') # cos

        # Target length node
        one_subtract_cosine = cmds.createNode('subtract', name=f"{side}_{limb}SoftLinearTargetLength_SUB", ss=True)
        cmds.connectAttr(float_constant_one+'.outFloat', one_subtract_cosine+'.input1') # 1
        cmds.connectAttr(divide_cosine+'.output', one_subtract_cosine+'.input2') # cos
        
        
        quadratic_target_length = cmds.createNode('multiply', name=f"{side}_{limb}SoftQuadraticTargetLength_MUL", ss=True) # QUADRATIC CURVE
        cmds.connectAttr(one_subtract_cosine+'.output', quadratic_target_length+'.input[0]') # 1 - cos
        cmds.connectAttr(one_subtract_cosine+'.output', quadratic_target_length+'.input[1]') # 1 - cos
        
        cubic_target_length = cmds.createNode('multiply', name=f"{side}_{limb}SoftCubicTargetLength_MUL", ss=True) # CUBIC CURVE
        cmds.connectAttr(quadratic_target_length+'.output', cubic_target_length+'.input[0]') # 1 - cos
        cmds.connectAttr(quadratic_target_length+'.output', cubic_target_length+'.input[1]') # 1 - cos
        cmds.connectAttr(quadratic_target_length+'.output', cubic_target_length+'.input[2]') # 1 -

        remap_quadratic = cmds.createNode('remapValue', name=f"{side}_{limb}SoftCosineValueRemaped_RMV", ss=True) # LINEAR CURVE
        cmds.setAttr(remap_quadratic+'.inputMin', 0)
        cmds.setAttr(remap_quadratic+'.inputMax', 1)
        cmds.setAttr(remap_quadratic+'.outputMin', 0)
        cmds.setAttr(remap_quadratic+'.outputMax', 1)
        cmds.connectAttr(divide_cosine+'.output', remap_quadratic+'.inputValue') # connect cosine value as input
        cmds.connectAttr(f"{ik_controller}.Soft_Start", remap_quadratic+'.inputMin') # connect soft ik attribute

        # Create blender between quadratic and linear
        smooth_step = cmds.createNode('smoothStep', name=f"{side}_{limb}SoftSmoothStep_SST", ss=True)
        cmds.setAttr(smooth_step+'.leftEdge', 0)
        cmds.setAttr(smooth_step+'.rightEdge', 1)
        cmds.connectAttr(remap_quadratic+'.outValue', smooth_step+'.input') # connect remap to smoothstep

        cubic_curve_cosine = cmds.createNode('multiply', name=f"{side}_{limb}SoftCubicCurveCosine_MUL", ss=True) # CUBIC CURVE
        cmds.connectAttr(remap_quadratic+'.outValue', cubic_curve_cosine+'.input[0]')
        cmds.connectAttr(remap_quadratic+'.outValue', cubic_curve_cosine+'.input[1]')
        cmds.connectAttr(remap_quadratic+'.outValue', cubic_curve_cosine+'.input[2]')


        blend_two_curves = cmds.createNode('blendTwoAttr', name=f"{side}_{limb}SoftBlendTwoCurves_BLN", ss=True)
        cmds.connectAttr(ik_controller+'.Soft', blend_two_curves+'.attributesBlender')
        cmds.connectAttr(quadratic_target_length+'.output', blend_two_curves+'.input[0]') # cubic length
        cmds.connectAttr(smooth_step+'.output', blend_two_curves+'.input[1]') # smooth length
        
        blend_two_height = cmds.createNode('blendTwoAttr', name=f"{side}_{limb}SoftBlendedHeight_BLN", ss=True)
        cmds.connectAttr(blend_two_curves+'.output', blend_two_height+'.attributesBlender') # blended curve
        cmds.connectAttr(power_to_cos+'.output', blend_two_height+'.input[0]') # linear height
        cmds.connectAttr(one_subtract_cosine+'.output', blend_two_height+'.input[1]') # quadratic

        blend_height_squared = cmds.createNode('multiply', name=f"{side}_{limb}SoftBlendedHeightSquared_MUL", ss=True)
        cmds.connectAttr(blend_two_height+'.output', blend_height_squared+'.input[0]')
        cmds.connectAttr(blend_two_height+'.output', blend_height_squared+'.input[1]')

        add_blendedH_to_cosine = cmds.createNode('sum', name=f"{side}_{limb}SoftAddBlendedHeightToCosine_SUM", ss=True)
        cmds.connectAttr(cosine_upper_squared+'.output', add_blendedH_to_cosine+'.input[0]') # original cosine squared
        cmds.connectAttr(blend_height_squared+'.output', add_blendedH_to_cosine+'.input[1]') # blended height squared
        upper_length_final_cosine = cmds.createNode('power', name=f"{side}_{limb}SoftFinalUpperScaler_POWER", ss=True)
        cmds.setAttr(upper_length_final_cosine+'.exponent', 0.5) # square root
        cmds.connectAttr(add_blendedH_to_cosine+'.output', upper_length_final_cosine+'.input')

        # Lower length calculation with pythagoras
        upper_ratio = cmds.createNode('divide', name=f"{side}_{limb}SoftUpperSegmentArmRatio_DIV", ss=True)
        cmds.connectAttr(upper_length_node+'.output', upper_ratio+'.input1')
        cmds.connectAttr(lower_length_node+'.output', upper_ratio+'.input2')

        lower_soft_height = cmds.createNode('multiply', name=f"{side}_{limb}SoftLowerCosValue_MUL", ss=True)
        cmds.connectAttr(power_to_cos+'.output', lower_soft_height+'.input[0]') # original height (cos)
        cmds.connectAttr(upper_ratio+'.output', lower_soft_height+'.input[1]') # ratio

        lower_soft_blended_height = cmds.createNode('multiply', name=f"{side}_{limb}SoftLowerBlendedHeight_MUL", ss=True)
        cmds.connectAttr(blend_two_height+'.output', lower_soft_blended_height+'.input[0]') # blended height
        cmds.connectAttr(upper_ratio+'.output', lower_soft_blended_height+'.input[1]') # ratio

        lower_soft_height_squared = cmds.createNode('multiply', name=f"{side}_{limb}SoftLowerHeightSquared_MUL", ss=True)
        cmds.connectAttr(lower_soft_height+'.output', lower_soft_height_squared+'.input[0]')
        cmds.connectAttr(lower_soft_height+'.output', lower_soft_height_squared+'.input[1]')

        one_minus_lower_height_squared = cmds.createNode('subtract', name=f"{side}_{limb}SoftOneMinusLowerCosValueSquared_SUB", ss=True) # 1 - lower height squared
        cmds.connectAttr(float_constant_one+'.outFloat', one_minus_lower_height_squared+'.input1')
        cmds.connectAttr(lower_soft_height_squared+'.output', one_minus_lower_height_squared+'.input2')

        lower_soft_blended_height_squared = cmds.createNode('multiply', name=f"{side}_{limb}SoftLowerBlendedHeightSquared_MUL", ss=True)
        cmds.connectAttr(lower_soft_blended_height+'.output', lower_soft_blended_height_squared+'.input[0]')
        cmds.connectAttr(lower_soft_blended_height+'.output', lower_soft_blended_height_squared+'.input[1]')

        add_lower_blendedH_to_cosine = cmds.createNode('sum', name=f"{side}_{limb}SoftAddLowerBlendedHeightToCosine_SUM", ss=True)
        cmds.connectAttr(one_minus_lower_height_squared+'.output', add_lower_blendedH_to_cosine+'.input[0]') # original cosine squared
        cmds.connectAttr(lower_soft_blended_height_squared+'.output', add_lower_blendedH_to_cosine+'.input[1]') # blended height squared

        scaler_lower_length_final = cmds.createNode('power', name=f"{side}_{limb}SoftFinalLowerScaler_POWER", ss=True)
        cmds.setAttr(scaler_lower_length_final+'.exponent', 0.5) # square root
        cmds.connectAttr(add_lower_blendedH_to_cosine+'.output', scaler_lower_length_final+'.input')

        return f"{upper_length_final_cosine}.output", f"{scaler_lower_length_final}.output"