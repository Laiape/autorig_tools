import maya.cmds as cmds

def solver(guides=[], controllers=[], stretch=False, primary_mode=(1,0,0), secondary_mode=(0,1,0)):
        
        """Custom IK solver for biped characters. Cosinus theorem based.
        Args:
            guides (list): List of guide objects.
            controllers (list): List of controller objects.
        Returns:
                None
                """
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

        #Connect guides to controllers
        cmds.connectAttr(guides[0], grp_upper+'.offsetParentMatrix')
        cmds.connectAttr(guides[1], grp_lower+'.offsetParentMatrix')
        cmds.connectAttr(guides[2], grp_eff+'.offsetParentMatrix')

        # Create distanceBetween nodes to measure initial lengths
        distance_between_up = cmds.createNode('distanceBetween', name=guides_00_name.replace('_GUIDE', 'InitialLength_DBT'), ss=True)
        distance_between_low = cmds.createNode('distanceBetween', name=guides_01_name.replace('_GUIDE', 'InitialLength_DBT'), ss=True)
        distance_between_eff = cmds.createNode('distanceBetween', name=guides_02_name.replace('_GUIDE', 'InitialLength_DBT'), ss=True)

        cmds.connectAttr(guides[0], distance_between_up+'.inMatrix1') # a
        cmds.connectAttr(guides[1], distance_between_up+'.inMatrix2')
        cmds.connectAttr(guides[1], distance_between_low+'.inMatrix1') # b
        cmds.connectAttr(guides[2], distance_between_low+'.inMatrix2')
        cmds.connectAttr(guides[0], distance_between_eff+'.inMatrix1') # c
        cmds.connectAttr(guides[2], distance_between_eff+'.inMatrix2')
        
        # Create nodes for the IK solver
        multiply_upper = cmds.createNode('multiply', name=guides_00_name.replace('_GUIDE', 'Squared_MULT'), ss=True)
        multiply_lower = cmds.createNode('multiply', name=guides_01_name.replace('_GUIDE', 'Squared_MULT'), ss=True)
        multiply_eff = cmds.createNode('multiply', name=guides_02_name.replace('_GUIDE', 'Squared_MULT'), ss=True)

        cmds.connectAttr(distance_between_up+'.distance', multiply_upper+'.input[0]') # a2
        cmds.connectAttr(distance_between_up+'.distance', multiply_upper+'.input[1]')
        cmds.connectAttr(distance_between_low+'.distance', multiply_lower+'.input[0]') # b2
        cmds.connectAttr(distance_between_low+'.distance', multiply_lower+'.input[1]')
        cmds.connectAttr(distance_between_eff+'.distance', multiply_eff+'.input[0]') # c2
        cmds.connectAttr(distance_between_eff+'.distance', multiply_eff+'.input[1]')

        sum_node = cmds.createNode('sum', name=guides_00_name.replace('_GUIDE', 'UpperFull_SUM'), ss=True)
        cmds.connectAttr(multiply_upper+'.output', sum_node+'.input[0]') # a2+c2
        cmds.connectAttr(multiply_eff+'.output', sum_node+'.input[1]')

        subtract_node = cmds.createNode('subtract', name=guides_02_name.replace('_GUIDE', 'Lower_SUB'), ss=True)
        cmds.connectAttr(sum_node+'.output', subtract_node+'.input1') # a2+c2
        cmds.connectAttr(multiply_lower+'.output', subtract_node+'.input2') # - b2

        multiply_node = cmds.createNode('multiply', name=guides_00_name.replace('_GUIDE', 'MULT'), ss=True)
        float_constant = cmds.createNode('floatConstant', name=guides_00_name.replace('_GUIDE', 'FCN'), ss=True)
        cmds.setAttr(float_constant+'.inFloat', 2)
        cmds.connectAttr(distance_between_up+'.distance', multiply_node+'.input[0]') # a
        cmds.connectAttr(distance_between_eff+'.distance', multiply_node+'.input[1]') # c
        cmds.connectAttr(float_constant+'.outFloat', multiply_node+'.input[2]') # *2

        divide_node = cmds.createNode('divide', name=guides_00_name.replace('GUIDE', 'DIV'), ss=True)
        cmds.connectAttr(subtract_node+'.output', divide_node+'.input1') # a2+b2-c2
        cmds.connectAttr(multiply_node+'.output', divide_node+'.input2') # 2ac

        acos_node = cmds.createNode('acos', name=guides_00_name.replace('GUIDE', 'ACOS'), ss=True)
        cmds.connectAttr(divide_node+'.output', acos_node+'.input') # (a2+c2-b2)/2ac
        
        # Lower controller rotation
        add_lower = cmds.createNode('sum', name=guides_01_name.replace('GUIDE', 'SUM'), ss=True)
        cmds.connectAttr(multiply_upper+'.output', add_lower+'.input[0]') # a2+b2
        cmds.connectAttr(multiply_lower+'.output', add_lower+'.input[1]')

        subtract_lower = cmds.createNode('subtract', name=guides_01_name.replace('GUIDE', 'SUB'), ss=True)
        cmds.connectAttr(add_lower+'.output', subtract_lower+'.input1') # a2+b2
        cmds.connectAttr(multiply_eff+'.output', subtract_lower+'.input2') # - c2

        multiply_lower_2 = cmds.createNode('multiply', name=guides_01_name.replace('GUIDE', 'MULT'), ss=True)
        cmds.connectAttr(distance_between_up+'.distance', multiply_lower_2+'.input[0]') # a
        cmds.connectAttr(distance_between_low+'.distance', multiply_lower_2+'.input[1]') # b
        cmds.connectAttr(float_constant+'.outFloat', multiply_lower_2+'.input[2]') # *2

        divide_lower = cmds.createNode('divide', name=guides_01_name.replace('GUIDE', 'DIV'), ss=True)
        cmds.connectAttr(subtract_lower+'.output', divide_lower+'.input1') # a2+b2-c2
        cmds.connectAttr(multiply_lower_2+'.output', divide_lower+'.input2') # 2ab

        acos_lower = cmds.createNode('acos', name=guides_01_name.replace('GUIDE', 'ACOS'), ss=True)
        cmds.connectAttr(divide_lower+'.output', acos_lower+'.input') # (a2+b2-c2)/2ab

        subtract_angle = cmds.createNode('subtract', name=guides_02_name.replace('_GUIDE', 'Angle_SUB'), ss=True)
        float_constant_180 = cmds.createNode('floatConstant', name=guides_02_name.replace('GUIDE', 'FCN'), ss=True)
        cmds.setAttr(float_constant_180+'.inFloat', 180) # 180 degrees in radians
        cmds.connectAttr(float_constant_180+'.outFloat', subtract_angle+'.input1') # 180 degrees
        cmds.connectAttr(acos_lower+'.output', subtract_angle+'.input2') # upper angle

        negate_node = cmds.createNode('negate', name=guides_02_name.replace('_GUIDE', 'AngleNegate_NEG'), ss=True)
        cmds.connectAttr(subtract_angle+'.output', negate_node+'.input') # lower angle

        # Upper WM
        aim_matrix = cmds.createNode('aimMatrix', name=guides_02_name.replace('_GUIDE', 'Eff_AMX'), ss=True) # aim matrix for end controller,
        cmds.setAttr(aim_matrix+'.primaryInputAxis', *primary_mode, type="double3") # X axis
        cmds.setAttr(aim_matrix+'.secondaryInputAxis', *secondary_mode, type="double3") # Y axis
        cmds.setAttr(aim_matrix+'.secondaryTargetVector', *secondary_mode, type="double3") # Y axis
        cmds.setAttr(aim_matrix+'.secondaryMode', 2) # Alingn to secondary axis
        cmds.connectAttr(f"{controllers[0]}.worldMatrix[0]", aim_matrix+'.inputMatrix') # input
        cmds.connectAttr(f"{controllers[1]}.worldMatrix[0]", aim_matrix+'.primaryTargetMatrix') # target
        cmds.connectAttr(f"{controllers[2]}.worldMatrix[0]", aim_matrix+'.secondaryTargetMatrix') # secondary target


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
        #  ----- This will be used to connect it to the blend matrix later -----

        # Lower WM
        four_by_four_low_local_rotation = cmds.createNode('fourByFourMatrix', name=guides_01_name.replace('_GUIDE', 'Local_F4FX'), ss=True) # local matrix for lower arm
        sin_lower = cmds.createNode('sin', name=guides_01_name.replace('GUIDE', 'SIN'), ss=True)
        negate_sin_lower = cmds.createNode('negate', name=guides_01_name.replace('_GUIDE', 'Sin_NEG'), ss=True)
        negate_cos_lower = cmds.createNode('negate', name=guides_01_name.replace('_GUIDE', 'Cos_NEG'), ss=True)
        cmds.connectAttr(divide_lower+'.output', negate_cos_lower+'.input') # negate cos
        cmds.connectAttr(negate_node+'.output', sin_lower+'.input') # lower angle
        cmds.connectAttr(sin_lower+'.output', negate_sin_lower+'.input') # negate sin
        cmds.connectAttr(negate_cos_lower+'.output', four_by_four_low_local_rotation+'.in00') # -cos
        cmds.connectAttr(negate_sin_lower+'.output', four_by_four_low_local_rotation+'.in01') # sin
        cmds.connectAttr(sin_lower+'.output', four_by_four_low_local_rotation+'.in10') # -sin
        cmds.connectAttr(negate_cos_lower+'.output', four_by_four_low_local_rotation+'.in11') # -cos
        if side == 'L':
                cmds.connectAttr(distance_between_up+'.distance', four_by_four_low_local_rotation+'.in30') # position x, add the position
        else:
                negate_position_x = cmds.createNode('negate', name=guides_01_name.replace('_GUIDE', 'PosX_NEG'), ss=True)
                cmds.connectAttr(distance_between_up+'.distance', negate_position_x+'.input') # negate position
                cmds.connectAttr(negate_position_x+'.output', four_by_four_low_local_rotation+'.in30') # position x, add the position


        mult_matrix_lower_rwm = cmds.createNode('multMatrix', name=guides_01_name.replace('_GUIDE', 'LowWM_MMT'), ss=True) # world matrix rotation mult for lower arm
        cmds.connectAttr(upper_wm, mult_matrix_lower_rwm+'.matrixIn[1]') # connect upper world matrix to lower world matrix
        cmds.connectAttr(four_by_four_low_local_rotation+'.output', mult_matrix_lower_rwm+'.matrixIn[0]') # connect local rotation to world matrix
        lower_wm = mult_matrix_lower_rwm+'.matrixSum' # lower world matrix
        lower_lm = four_by_four_low_local_rotation+'.output' # lower local matrix
        # ----- This will be used to connect it to the blend matrix later -----

        # Effector WM
        

        # Add stretch functionality
        if stretch != False:
                add_upper_lower_length = cmds.createNode('sum', name=guides_00_name.replace('_GUIDE', 'SummedLength_SUM'), ss=True) # sum of upper and lower lengths
                cmds.connectAttr(distance_between_up+'.distance', add_upper_lower_length+'.input[0]') # upper length
                cmds.connectAttr(distance_between_low+'.distance', add_upper_lower_length+'.input[1]') # lower length

                full_length = cmds.createNode('distanceBetween', name=guides_00_name.replace('_GUIDE', 'CurrentLength_DBT'), ss=True) # full length distance between start and effector
                cmds.connectAttr(controllers[0]+'.worldMatrix[0]', full_length+'.inMatrix1') # start
                cmds.connectAttr(controllers[2]+'.worldMatrix[0]', full_length+'.inMatrix2') # effector

                divide_length = cmds.createNode('divide', name=guides_00_name.replace('_GUIDE', 'Length_DIV'), ss=True) # divide full length by upper+lower length
                cmds.connectAttr(full_length+'.distance', divide_length+'.input1') # current length
                cmds.connectAttr(add_upper_lower_length+'.output', divide_length+'.input2') # upper + lower length

                max_node = cmds.createNode('max', name=guides_00_name.replace('_GUIDE', 'scaler_MAX'), ss=True) # max node to avoid scaling down
                float_constant_one = cmds.createNode('floatConstant', name=guides_00_name.replace('_GUIDE', 'One_FCN'), ss=True)
                cmds.setAttr(float_constant_one+'.inFloat', 1) # constant 1
                cmds.connectAttr(float_constant_one+'.outFloat', max_node+'.input[0]') # connect 1
                cmds.connectAttr(divide_length+'.output', max_node+'.input[1]') # connect division result

                remap_node = cmds.createNode('remapValue', name=guides_00_name.replace('_GUIDE', 'EnableIKStretch_RMV'), ss=True) # remap node to control stretch influence
                cmds.connectAttr(controllers[-1]+'.Stretch', remap_node+'.inputValue') # connect stretch attribute
                cmds.setAttr(remap_node+'.inputMin', 0)
                cmds.setAttr(remap_node+'.inputMax', 1)
                cmds.setAttr(remap_node+'.outputMin', 1)
                cmds.connectAttr(max_node+'.output', remap_node+'.outputMax') # connect max node to remap output max

                multiply_upper_length = cmds.createNode('multiply', name=guides_00_name.replace('_GUIDE', 'UpperLength_MULT'), ss=True) # multiply upper length by scaler
                cmds.connectAttr(distance_between_up+'.distance', multiply_upper_length+'.input[0]') # upper length
                cmds.connectAttr(remap_node+'.outValue', multiply_upper_length+'.input[1]') # remap output

                multiply_lower_length = cmds.createNode('multiply', name=guides_01_name.replace('_GUIDE', 'LowerLength_MULT'), ss=True) # multiply lower length by scaler
                cmds.connectAttr(distance_between_low+'.distance', multiply_lower_length+'.input[0]') # lower length
                cmds.connectAttr(remap_node+'.outValue', multiply_lower_length+'.input[1]') # remap output