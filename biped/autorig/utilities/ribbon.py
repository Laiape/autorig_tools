import maya.cmds as cmds
from maya.api import OpenMaya as om
from biped.autorig.utilities import de_boor_core as core
import importlib
importlib.reload(core)


OPEN = 'open'
PERIODIC = 'periodic'
AXIS_VECTOR = {'x': (1, 0, 0), 'y': (0, 1, 0), 'z': (0, 0, 1), "-x": (-1, 0, 0), "-y": (0, -1, 0), "-z": (0, 0, -1)}
KNOT_TO_FORM_INDEX = {OPEN: om.MFnNurbsCurve.kOpen, PERIODIC: om.MFnNurbsCurve.kPeriodic}


def de_boor_ribbon(cvs, ctls_grp=None, aim_axis='x', up_axis='y', num_joints=5, tangent_offset=0.001, d=None, kv_type=OPEN,
                   param_from_length=False, tol=0.000001, name='ribbon', use_position=True, use_tangent=True,
                   use_up=True, use_scale=True, custom_parameter=[], skeleton_grp=None):
    """
    Use controls and de_boor function to get position, tangent and up values for joints.  The param_from_length can
    be used to get the parameter values using a fraction of the curve length, otherwise the parameter values will be
    equally spaced

    To optimize the setup we change the nodes and connections if different combinations of position, tangent and up are
    used:
        use_position=True, use_tangent=True, use_up=True
            create 3 wtAddMatrix nodes and connect to aimMatrix

        use_position=False, use_tangent=True, use_up=True
            wtAddMatrix for tangent only created if use_position=True
            use wts and tangent_wts to set matrix values for aimMatrix
            create wtAddMatrix for up and connect to aimMatrix

        use_position=True, use_tangent=False, use_up=True
            create offset matrices in the aim direction for each joint
            use offset matrices to set the primaryTargetMatrix of aimMatrix
            create wtAddMatrix nodes for position and up and connect to aimMatrix

        use_position=True, use_tangent=True, use_up=False
            use module group matrix as the secondaryTargetMatrix of aimMatrix
            create wtAddMatrix nodes for position and tangent and connect to aimMatrix

        use_position=False, use_tangent=False, use_up=True
            same as use_position=False, use_tangent=True, use_up=True

        use_position=False, use_tangent=True, use_up=False
            translation and rotation of joints set

        use_position=True, use_tangent=False, use_up=False
            no aimMatrix needed, connect the wtAddMatrix for translation to the joints

        use_position=False, use_tangent=False, use_up=False
            translation and rotation of joints set

        aimMatrix not created when use_tangent=False and use_up=False, otherwise it is

        Examples:
        from maya import cmds
        import ribbon
        from importlib import reload
        reload(ribbon)


        # ----- example 1, open knot vector type with linear degree
        cmds.file(new=True, f=True)

        cvs = []
        for i in range(4):
            loc = cmds.spaceLocator()[0]
            cvs.append(loc)
            cmds.setAttr(f'{loc}.t', i, 0, 0)

        jnts = ribbon.de_boor_ribbon(cvs)
        for jnt in jnts:
            cmds.setAttr(f'{jnt}.displayLocalAxis', True)

        # ----- example 2, periodic knot vector type with quadratic degree
        cmds.file(new=True, f=True)

        cvs = []
        ts = ((1, 0, 1), (-1, 0, 1), (-1, 0, -1), (1, 0, -1))
        rys = (-135, 135, 45, -45)
        for t, ry in zip(ts, rys):
            loc = cmds.spaceLocator()[0]
            cvs.append(loc)
            cmds.setAttr(f'{loc}.t', *t)
            cmds.setAttr(f'{loc}.ry', ry)

        jnts = ribbon.de_boor_ribbon(cvs, kv_type='periodic', d=2, num_joints=13)
        for jnt in jnts:
            cmds.setAttr(f'{jnt}.displayLocalAxis', True)

        Args:
            cvs (list): transforms that will act as the curve cvs
            aim_axis (str): aim axis of the output joints
            up_axis (str): up axis of the output joints
            num_joints (int): number of output joints to be created
            tangent_offset (float): tolerance used to optimization
            d (int): degree of the basis functions
            kv_type (str): 'open' or 'periodic', 'periodic' will create a closed curve
            param_from_length (bool): evenly distributes joints along the curve if cvs are not evenly spaced
            tol (float): tolerance used to optimization
            name (str): prefix given to all node created
            use_position (bool): if True then create position setup else set position
            use_tangent (bool): if True (and use_position is True) then create tangent setup else set tangent
            use_up (bool): if True then create up setup else set up
            use_scale (bool): if True then create scale setup

    Returns:
        list: joints
    """

    ctls = []
    grps = []

    if ctls_grp is not None: # If the first cv is not a control

        for i, cv in enumerate(cvs):
                
                grp = cmds.createNode("transform", n=f"{name}0{i}_GRP")
                ctl = cmds.circle(n=f"{name}0{i}_CTL", nr=(1,0,0), ch=False)[0] # Create a controller circle
                cmds.parent(grp, ctls_grp)
                if cmds.listRelatives(ctl, parent=True) != grp:
                    cmds.parent(ctl, grp)
                    cmds.matchTransform(grp, cv, pos=True, rot=True, scl=False)
                grps.append(grp)
                ctls.append(ctl)

    else:

        ctls = cvs

    num_cvs = len(cvs)
    original_cvs = cvs[:]

    d = num_cvs - 1 if d is None else d

    if kv_type == OPEN:

        kv, _ = core.knot_vector(OPEN, cvs, d)

        m_kv = kv[1:-1]
        m_cvs = cvs[:]

    else:  # kv_type is PERIODIC

        m_cvs = [cvs[i - 1 % len(cvs)] for i in range(len(cvs))]
        for i in range(d):
            m_cvs.append(m_cvs[i])

        m_kv_len = len(m_cvs) + d - 1
        m_kv_interval = 1 / (m_kv_len - 2 * (d - 1) - 1)
        m_kv = [-m_kv_interval * (d - 1) * (1 - t / (m_kv_len - 1)) +
                (1 + m_kv_interval * (d - 1)) * t / (m_kv_len - 1) for t in range(m_kv_len)]

        kv, cvs = core.knot_vector(PERIODIC, cvs, d)

    temp_nodes = []

    for i, cv in enumerate(m_cvs): # Create temporary nodes for each CV and get the position of each one

        temp_node = cmds.createNode('transform', n=f'temp_{i}') 
        if cmds.objExists(f"{cv}.worldMatrix[0]"):
            cmds.connectAttr(f'{cv}.worldMatrix[0]', f'{temp_node}.offsetParentMatrix')
        elif cmds.objExists(f"{cv}.outputMatrix"):
            cmds.connectAttr(f'{cv}.outputMatrix', f'{temp_node}.offsetParentMatrix')
        elif cmds.objExists(f"{cv}.output"):
            cmds.connectAttr(f'{cv}.output', f'{temp_node}.offsetParentMatrix')
        temp_nodes.append(temp_node)

    if skeleton_grp is None:
        skeleton_grp = cmds.createNode('transform', n=f'{name}Skinning_GRP')
        cmds.matchTransform(skeleton_grp, temp_nodes[0])
    else:
        skeleton_grp = skeleton_grp

    m_cv_poss = om.MPointArray([cmds.xform(obj, q=True, ws=True, t=True) for obj in temp_nodes])
    form = KNOT_TO_FORM_INDEX[kv_type]
    is_2d = False
    rational = True
    data_creator = om.MFnNurbsCurveData()
    parent = data_creator.create()

    crv_fn = om.MFnNurbsCurve()
    crv_fn.create(m_cv_poss, m_kv, d, form, is_2d, rational, parent)

    if param_from_length:

        crv_len = crv_fn.length()
        params = []

        for i in range(num_joints):

            sample_len = crv_len * i / (num_joints - 1)

            if kv_type == PERIODIC:
                t = crv_fn.findParamFromLength((sample_len + crv_len * m_kv[2] * 0.5) % crv_len)
                params.append(t - m_kv[2] * 0.5)
            else:
                t = crv_fn.findParamFromLength(sample_len)
                params.append(t)

    else:
        params = [i / (num_joints - 1) for i in range(num_joints)]

        params = custom_parameter if custom_parameter else params

    if kv_type == PERIODIC:

        params = [(kv[d + 1] * (d * 0.5 + 0.5)) * (1 - t) + t * (1 - kv[d + 1] * (d * 0.5 - 0.5))
                  for i, t in enumerate(params)]

    par_off_plugs = []
    trans_off_plugs = []
    sca_off_plugs = []

    for i, ctl in enumerate(cvs):

        if skeleton_grp is None:

            par_off = cmds.createNode('multMatrix', n=f'{name}_parentOffset_{i}_MM')

            if cmds.objExists(f"{ctl}.worldMatrix[0]"):
                cmds.connectAttr(f'{ctl}.worldMatrix[0]', f'{par_off}.matrixIn[0]')
            elif cmds.objExists(f"{ctl}.outputMatrix"):
                cmds.connectAttr(f'{ctl}.outputMatrix', f'{par_off}.matrixIn[0]')
            elif cmds.objExists(f"{ctl}.output"):
                cmds.connectAttr(f'{ctl}.output', f'{par_off}.matrixIn[0]')
                
            cmds.connectAttr(f'{skeleton_grp}.worldInverseMatrix', f'{par_off}.matrixIn[1]') # First guide

            par_off_plugs.append(f'{par_off}.matrixSum')

        else:
            if cmds.objExists(f"{ctl}.worldMatrix[0]"):
                par_off_plugs.append(f'{ctl}.worldMatrix[0]')
            elif cmds.objExists(f"{ctl}.outputMatrix"):
                par_off_plugs.append(f'{ctl}.outputMatrix')
            elif cmds.objExists(f"{ctl}.output"):
                par_off_plugs.append(f'{ctl}.output')
            

        trans_off = cmds.createNode('pickMatrix', n=f'{name}_translation_{i}_PM')

        if skeleton_grp is None:
            cmds.connectAttr(f'{par_off}.matrixSum', f'{trans_off}.inputMatrix')
        else:
            if cmds.objExists(f"{ctl}.worldMatrix[0]"):
                cmds.connectAttr(f'{ctl}.worldMatrix[0]', f'{trans_off}.inputMatrix')
            elif cmds.objExists(f"{ctl}.outputMatrix"):
                cmds.connectAttr(f'{ctl}.outputMatrix', f'{trans_off}.inputMatrix')
            elif cmds.objExists(f"{ctl}.output"):
                cmds.connectAttr(f'{ctl}.output', f'{trans_off}.inputMatrix')
            

        for attr in 'useRotate', 'useScale', 'useShear':
            cmds.setAttr(f'{trans_off}.{attr}', False)

        trans_off_plugs.append(f'{trans_off}.outputMatrix')

        if use_scale and use_tangent or use_up:

            sca_off = cmds.createNode('pickMatrix', n=f'{name}_scaleOffset_{i}_PM')
            if skeleton_grp is None:
                cmds.connectAttr(f'{par_off}.matrixSum', f'{sca_off}.inputMatrix')
            else:
                if cmds.objExists(f"{ctl}.worldMatrix[0]"):
                    cmds.connectAttr(f'{ctl}.worldMatrix[0]', f'{sca_off}.inputMatrix')
                elif cmds.objExists(f"{ctl}.outputMatrix"):
                    cmds.connectAttr(f'{ctl}.outputMatrix', f'{sca_off}.inputMatrix')
                elif cmds.objExists(f"{ctl}.output"):
                    cmds.connectAttr(f'{ctl}.output', f'{sca_off}.inputMatrix')

            for attr in 'useRotate', 'useShear', 'useTranslate':
                cmds.setAttr(f'{sca_off}.{attr}', False)

            sca_off_plugs.append(f'{sca_off}.outputMatrix')

    jnts = []

    for i, param in enumerate(params):

        # print(param)
        cmds.select(cl=True)
        jnt = cmds.joint(n=f'{name}0{i}_JNT')
        # cube = cmds.polyCube(n=f'{name}0{i}_JNT_Cube', ch=False)[0]
        # cmds.parent(cube, jnt)
        cmds.parent(jnt, skeleton_grp)
        cmds.setAttr(f'{jnt}.jo', 0, 0, 0)
        cmds.xform(jnt, m=om.MMatrix.kIdentity)

        jnts.append(jnt)

        wts = core.de_boor(len(cvs), d, param, kv, tol=tol)
        if kv_type == PERIODIC:
            wts = get_consolidated_wts(wts, original_cvs, cvs)

        tangent_param = param + tangent_offset
        aim_vector = om.MVector(AXIS_VECTOR[aim_axis])
        if tangent_param > 1:
            tangent_param = param - 2 * tangent_offset
            aim_vector *= -1

        tangent_wts = core.de_boor(len(cvs), d, tangent_param, kv, tol=tol)
        if kv_type == PERIODIC:
            tangent_wts = get_consolidated_wts(tangent_wts, original_cvs, cvs)

        position_plug = None
        tangent_plug = None

        # ----- position setup
        if use_position:

            position = create_wt_add_matrix(trans_off_plugs, wts, f'{name}_position_{i}_WAM', tol=tol)
            position_plug = f'{position}.matrixSum'

            if not use_tangent and not use_up:  # no aimMatrix necessary, connect wtAddMatrix to joint

                cmds.connectAttr(position_plug, f'{jnt}.offsetParentMatrix')

                if use_scale:

                    for trans_off_plug in trans_off_plugs:

                        trans_off = trans_off_plug.split('.')[0]
                        cmds.setAttr(f'{trans_off}.useScale', True)

                continue

            # ----- tangent setup
            if use_tangent:

                tangent = create_wt_add_matrix(trans_off_plugs, tangent_wts, f'{name}_tangent_{i}_WAM', tol=tol)
                tangent_plug = f'{tangent}.matrixSum'

        up_plug = f'{skeleton_grp}.worldMatrix'

        # ----- up setup
        if use_up:

            temp = cmds.createNode('transform')
            cmds.parent(temp, skeleton_grp)
            ori_con = cmds.orientConstraint(temp_nodes, temp)[0]
            cmds.setAttr(f'{ori_con}.interpType', 2)
            for j, wt in enumerate(wts):
                cmds.setAttr(f'{ori_con}.{temp_nodes[j]}W{j}', wt)

            up = create_wt_add_matrix(par_off_plugs, wts, f'{name}_up_{i}_WAM', tol=tol)

            temp_mat = om.MMatrix(cmds.getAttr(f'{temp}.matrix'))
            up_inverse = om.MMatrix(cmds.getAttr(f'{up}.matrixSum')).inverse()
            up_off_val = temp_mat * up_inverse

            up_off = cmds.createNode('multMatrix', n=f'{name}_upOffset_{i}_MM')
            # cmds.setAttr(f'{up_off}.matrixIn[0]', list(up_off_val), type='matrix')
            fourByfour = cmds.createNode('fourByFourMatrix', n=f'{name}_upOffset_{i}_F4X4')
            if up_axis == 'x':
                cmds.setAttr(f'{fourByfour}.in30', 10)
            elif up_axis == 'y':
                cmds.setAttr(f'{fourByfour}.in31', 10)
            elif up_axis == 'z':
                cmds.setAttr(f'{fourByfour}.in32', 10)
            cmds.connectAttr(f'{fourByfour}.output', f'{up_off}.matrixIn[0]')
            cmds.connectAttr(f'{up}.matrixSum', f'{up_off}.matrixIn[2]')

            if skeleton_grp is not None:
                up_plug = f'{up_off}.matrixSum'
            else:
                if cmds.objExists(f"{ctl}.worldMatrix[0]"):
                    up_plug = f'{ctl}.worldMatrix[0]'
                elif cmds.objExists(f"{ctl}.outputMatrix"):
                    up_plug = f'{ctl}.outputMatrix'
                elif cmds.objExists(f"{ctl}.output"):
                    up_plug = f'{ctl}.output'
                elif cmds.objExists(f"{skeleton_grp}.matrix"):
                    up_plug = f'{skeleton_grp}.matrix'

            cmds.delete(temp)

        aim = cmds.createNode('aimMatrix', n=f'{name}_pointOnCurve_{i}_AM')

        if position_plug:
            cmds.connectAttr(position_plug, f'{aim}.inputMatrix')
        else:
            matrices = [om.MMatrix(cmds.getAttr(top)) for top in trans_off_plugs]
            trans_wt_mat = get_weighted_translation_matrix(matrices, wts)
            cmds.setAttr(f'{aim}.inputMatrix', trans_wt_mat, type='matrix')

        if tangent_plug:
            cmds.connectAttr(f'{tangent}.matrixSum', f'{aim}.primaryTargetMatrix')
        else:
            matrices = [om.MMatrix(cmds.getAttr(top)) for top in trans_off_plugs]
            trans_wt_mat = get_weighted_translation_matrix(matrices, tangent_wts)

            if position_plug:

                position_m = om.MMatrix(cmds.getAttr(position_plug))
                tangent_offset_val = trans_wt_mat * position_m.inverse()

                tangent_off = cmds.createNode('multMatrix', n=f'{name}_tangentOffset_{i}_MM')
                cmds.setAttr(f'{tangent_off}.matrixIn[0]', tangent_offset_val, type='matrix')
                cmds.connectAttr(position_plug, f'{tangent_off}.matrixIn[1]')

                cmds.connectAttr(f'{tangent_off}.matrixSum', f'{aim}.primaryTargetMatrix')

            else:

                cmds.setAttr(f'{aim}.primaryTargetMatrix', trans_wt_mat, type='matrix')

        if up_plug == f'{skeleton_grp}.worldMatrix':
            mod_mat = cmds.getAttr(up_plug)
            cmds.setAttr(f'{aim}.secondaryTargetMatrix', mod_mat, type='matrix')
        else:
            cmds.connectAttr(up_plug, f'{aim}.secondaryTargetMatrix')

        output_plug = f'{aim}.outputMatrix'

        cmds.setAttr(f'{aim}.primaryInputAxis', *aim_vector)
        cmds.setAttr(f'{aim}.secondaryInputAxis', *AXIS_VECTOR[up_axis])
        cmds.setAttr(f'{aim}.secondaryMode', 1) # Aim
        # cmds.setAttr(f'{aim}.secondaryTargetVector', *AXIS_VECTOR[up_axis])

        if use_scale:
            scale_wam = create_wt_add_matrix(sca_off_plugs, wts, f'{name}_scale_{i}_WAM', tol=tol)

            scale_mm = cmds.createNode('multMatrix', n=f'{name}_scale_{i}_MM')
            cmds.connectAttr(f'{scale_wam}.matrixSum', f'{scale_mm}.matrixIn[0]')
            cmds.connectAttr(output_plug, f'{scale_mm}.matrixIn[1]')

            output_plug = f'{scale_mm}.matrixSum'

        cmds.connectAttr(output_plug, f'{jnt}.offsetParentMatrix')

    

    return jnts, temp_nodes


def get_consolidated_wts(wts, original_cvs, cvs):

    consolidated_wts = {cv: 0 for cv in original_cvs}
    for j, wt in enumerate(wts):
        consolidated_wts[cvs[j]] += wt

    return [consolidated_wts[cv] for cv in original_cvs]


def create_wt_add_matrix(matrix_attrs, wts, name, tol=0.000001):

    wam = cmds.createNode('wtAddMatrix', n=name)

    for matrix_attr, wt, i in zip(matrix_attrs, wts, range(len(matrix_attrs))):

        if wt < tol:
            continue

        cmds.connectAttr(matrix_attr, f'{wam}.wtMatrix[{i}].matrixIn')
        cmds.setAttr(f'{wam}.wtMatrix[{i}].weightIn', wt)

    return wam

def get_weighted_translation_matrix(matrices, wts):

    translation_m = om.MMatrix(((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)))

    for m, wt in zip(matrices, wts):
        for i in 12, 13, 14:
            translation_m[i] += m[i] * wt

    return translation_m
