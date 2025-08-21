import maya.cmds as cmds
from maya.api import OpenMaya as om
from autorig.utilities import de_boor_core as core
from importlib import reload

reload(core)

OPEN = "open"
PERIODIC = "periodic"
AXIS_VECTOR = {"x": (1,0,0), "y": (0,1,0), "z": (0,0,1)}
KNOT_TO_FORM_INDEX = {OPEN : om.MFnNurbsCurve.kOpen, PERIODIC : om.MFnNurbsCurve.kPeriodic}


def de_boor_ribbon(cvs, controllers_grp = [], aim_axis="x", up_axis="y", num_joints=5, parameter_length=True, tangent_offset=0.001, d=None, kv_type=OPEN, tol=0.000001, name = "ribbon", use_position = True, use_tangent=True, use_up=True, use_scale=True):

    """
    In this function we will create a ribbon setup using the de Boor algorithm.
    args:
        None
    """
    
    # Match the controller groups to the cvs
    
    ctls = []
    controllers_groups = []
    
    if controllers_grp is not None and len(controllers_grp) != 0:

        controllers_grps = cmds.listRelatives(controllers_grp, c=True, type="transform")

        for i, grp in enumerate(controllers_grps):
            
            jnts_grp = cmds.createNode("transform", n=grp.replace("_GRP", "Joints_GRP")) # Create a group for joints
            cmds.matchTransform(jnts_grp, controllers_grps[0], pos=True, rot=True, scl=False) # Match the joints group to the first controller group
            cmds.matchTransform(grp, cvs[i], pos=True, rot=True, scl=False)

            children = cmds.listRelatives(grp, c=True, type="transform") or [] # Get children of the group
            ctl = next((child for child in children if child.endswith("CTL")), None) # Find the controller in the group

            if ctl:
                ctls.append(ctl) # If found, add to the list

            controllers_groups.append(grp) # Add the group to the list of controller groups


    else:
        
        jnts_grp = cmds.createNode("transform", n=f"{name}_Joints_GRP") # Create a group for joints
        controllers_grp = cmds.createNode("transform", n=f"{name}_Controllers_GRP") 
        cmds.matchTransform(jnts_grp, cvs[0], pos=True, rot=True, scl=False)
        cmds.matchTransform(controllers_grp, cvs[0], pos=True, rot=True, scl=False)
        
        
        for i, cv in enumerate(cvs):
            
            grp = cmds.createNode("transform", n=f"{name}0{i}_GRP")
            ctl = cmds.circle(n=f"{name}0{i}_CTL", nr=(1,0,0), ch=False)[0] # Create a controller circle
            cmds.parent(grp, controllers_grp)
            if cmds.listRelatives(ctl, parent=True) != grp:
                cmds.parent(ctl, grp)
                cmds.matchTransform(grp, cv, pos=True, rot=True, scl=False)
            controllers_groups.append(grp)
            ctls.append(ctl)          

    num_cvds = len(cvs)
    original_cvs = cvs[:]

    d = num_cvds - 1 if d is None else d

    if kv_type == OPEN:

        print("Open")
        
        kv, _ = core.knot_vector(OPEN, cvs, d)

        m_kv = kv[1:-1]  # Remove the first and last knots for open curves
        m_cvs = cvs[:]

    else:  # kv_type is PERIODIC
        print("Periodic")
        m_cvs = [i % len(cvs) for i in range(len(cvs))]
        for i in range(d):
            m_cvs.append(m_cvs[i])

        m_kv_len = len(m_cvs) + d + 1
        m_kv_interval = 1 / (m_kv_len - 2 * (d - 1))
        m_kv = [-m_kv_interval * (d - 1) * (1 - t / (m_kv_len - 1)) +
        (1 + m_kv_interval * (d - 1)) * t / (m_kv_len - 1) for t in range(m_kv_len)]

        kv, cvs = core.knot_vector(PERIODIC, cvs, d)

    m_cv_pos = om.MPointArray(
        [cmds.xform(obj, q=True, ws=True, t=True) for obj in m_cvs]
    )

    form = KNOT_TO_FORM_INDEX[kv_type]
    is_2d = False
    rational = True
    data_creator = om.MFnNurbsCurveData()
    parent = data_creator.create()

    crv_fn = om.MFnNurbsCurve() # Create a NURBS curve function set
    crv_fn.create(m_cv_pos, m_kv, d, form, is_2d, rational, parent)


    if parameter_length: # Calculate the parameters for the controllers based on the curve length or evenly spaced

        crv_length = crv_fn.length()
        params = []

        for i in range(num_joints):

            # Calculate the parameter based on the length of the curve

            sample_len = crv_length * (i / (num_joints - 1))
            t = crv_fn.findParamFromLength(sample_len)
            params.append(t)
    else:

        params = [i/(num_joints - 1) for i in range(num_joints)]

    if kv_type == PERIODIC:

        params = [(kv[d + 1] * (d * 0.5 + 0.5)) * (1 - t) + t * (1 - kv[d + 1] * (d * 0.5 - 0.5))
                for i, t in enumerate(params)]

    parent_offsets = []
    translation_offsets = []
    scale_offsets = []

    for i, ctl in enumerate(ctls):

        par_off = cmds.createNode("multMatrix", n=f"{name}_parentOffset_{i}_MM")
        cmds.connectAttr(f"{ctl}.worldMatrix", f"{par_off}.matrixIn[0]")
        cmds.connectAttr(f"{controllers_groups[0]}.worldInverseMatrix", f"{par_off}.matrixIn[1]")

        parent_offsets.append(f"{par_off}.matrixSum")
        
        trans_off = cmds.createNode("decomposeMatrix", n=f"{name}_transOffset0{i}_DM")
        compose_matrix = cmds.createNode("composeMatrix", n=f"{name}_0{i}_CM")
        cmds.connectAttr(f"{par_off}.matrixSum", f"{trans_off}.inputMatrix")
        cmds.connectAttr(f"{trans_off}.outputTranslate", f"{compose_matrix}.inputTranslate")

        translation_offsets.append(f"{compose_matrix}.outputMatrix")

        if use_scale and use_tangent or use_up:

            scale_off = cmds.createNode("pickMatrix", n=f"{name}_scaleOffset0{i}_PM")
            cmds.connectAttr(f"{par_off}.matrixSum", f"{scale_off}.inputMatrix")
            for attr in "useRotate", "useShear", "useTranslate":
                cmds.setAttr(f"{scale_off}.{attr}", 0)

            scale_offsets.append(f"{scale_off}.outputMatrix")

    jnts = []

    for i, param in enumerate(params):
        
        cmds.select(clear=True)
        jnt = cmds.joint(n = f"{name}0{i}_JNT")
        cmds.parent(jnt, jnts_grp)
        cmds.setAttr(f"{jnt}.jo", 0, 0, 0)
        cmds.xform(jnt, m=om.MMatrix.kIdentity)

        jnts.append(jnt)

        wts = core.de_boor(len(cvs), d, param, kv)

        if kv_type == PERIODIC:

            wts = get_consolidated_wts(wts, original_cvs, cvs)
        
          
        tangent_param = tangent_offset + param
        aim_vector = om.MVector(AXIS_VECTOR[aim_axis])

        if tangent_param > 1:
            tangent_param = param - 2 * tangent_offset
            aim_vector *= -1

        tangent_wts = core.de_boor(len(cvs), d, tangent_param, kv, tol)

        if kv_type == PERIODIC:

            tangent_wts = get_consolidated_wts(tangent_wts, original_cvs, cvs)

        position_plug = None
        tangent_plug = None

        # ---- Position setup ----
        if use_position:
            
            position = create_weight_add_matrix(translation_offsets, wts, f"{name}0{i}Trans_WAM", tol)
            position_plug = f"{position}.matrixSum"

            if not use_tangent and not use_up: # No aim matrix necesary, connect wtAddMatrix ToJ oints

                cmds.connectAttr(position_plug, f"{jnt}.offsetParentMatrix")

                if use_scale:

                    for transform_offset in translation_offsets:

                        trans_off = transform_offset.split(".")[0]
                        cmds.setAttr(f"{trans_off}.useScale", 1)

                continue

            # ---- Tangent setup ----
            if use_tangent:

                tangent = create_weight_add_matrix(translation_offsets, tangent_wts, f"{name}0{i}Tan_WAM", tol)
                tangent_plug = f"{tangent}.matrixSum"

        # ---- Up setup ----
        up_plug = f"{controllers_groups[0]}.worldMatrix"

        if use_up:

            temp = cmds.createNode("transform")
            cmds.parent(temp, controllers_groups[0])
            ori_con = cmds.orientConstraint(original_cvs, temp)[0]
            cmds.setAttr(f"{ori_con}.interpType", 2)
            for j, wt in enumerate(wts):
                cmds.setAttr(f"{ori_con}.{original_cvs[j]}W{j}", wt)

            up = create_weight_add_matrix(parent_offsets, wts, f"{name}_up0{i}_WAM", tol=tol)

            temp_mat = om.MMatrix(cmds.getAttr(f"{temp}.matrix"))
            up_inverse = om.MMatrix(cmds.getAttr(f"{up}.matrixSum")).inverse()
            up_off_val = temp_mat * up_inverse

            up_off = cmds.createNode("multMatrix", n=f"{name}_upOffset0{i}_MM", ss=True)
            cmds.setAttr(f"{up_off}.matrixIn[0]", list(up_off_val), type="matrix")
            cmds.connectAttr(f"{up}.matrixSum", f"{up_off}.matrixIn[1]")

            up_plug = f"{up_off}.matrixSum"

            cmds.delete(temp)


        aim = cmds.createNode("aimMatrix", n=f"{name}_pointOnCurve0{i}_AMX", ss=True)

        if position_plug:

            cmds.connectAttr(position_plug, f"{aim}.inputMatrix")

        else:

            matrices = [om.MMatrix(cmds.getAttr(f"{top}")) for top in translation_offsets]
            translation_matrix_weight = get_weighted_translation_matrix(matrices, wts)
            cmds.setAttr(f"{aim}.inputMatrix", translation_matrix_weight, type="matrix")

        if tangent_plug:

            cmds.connectAttr(f"{tangent}.matrixSum", f"{aim}.primaryTargetMatrix")

        else:

            matrices = [om.MMatrix(cmds.getAttr(f"{top}")) for top in translation_offsets]
            translation_matrix_weight = get_weighted_translation_matrix(matrices, tangent_wts)

            if position_plug:

                position_matrix = om.MMatrix(cmds.getAttr(position_plug))
                tangent_offset_value = translation_matrix_weight * position_matrix.inverse()

                tangent_offset_matrix = cmds.createNode("multMatrix", n=f"{name}_tangentOffset0{i}_MM", ss=True)
                cmds.setAttr(f"{tangent_offset_matrix}.matrixIn[0]", tangent_offset_value, type="matrix")
                cmds.connectAttr(f"{position_plug}.matrixSum", f"{tangent_offset_matrix}.matrixIn[1]")
            else:

                cmds.setAttr(f"{aim}.primaryTargetMatrix", translation_matrix_weight, type="matrix")

        
        if up_plug == f"{controllers_groups[0]}.worldMatrix":

            world_mat = cmds.getAttr(f"{up_plug}.worldMatrix")
            cmds.setAttr(f"{aim}.secondaryTargetMatrix", world_mat, type="matrix")

        else:

            cmds.connectAttr(up_plug, f"{aim}.secondaryTargetMatrix")
 
        cmds.setAttr(f"{aim}.primaryInputAxis", *aim_vector)
        cmds.setAttr(f"{aim}.secondaryInputAxis", *AXIS_VECTOR[up_axis])
        cmds.setAttr(f"{aim}.secondaryMode", 2)
        cmds.setAttr(f"{aim}.secondaryTargetVector", *AXIS_VECTOR[up_axis])

        output_plug = f"{aim}.outputMatrix"

        if use_scale:

            scale_weight = create_weight_add_matrix(scale_offsets, wts, f"{name}0{i}_scale_WAM", tol=tol)
            scale_mm = cmds.createNode("multMatrix", n=f"{name}_scale0{i}_MM", ss=True)
            cmds.connectAttr(f"{scale_weight}.matrixSum", f"{scale_mm}.matrixIn[0]")
            cmds.connectAttr(output_plug, f"{scale_mm}.matrixIn[1]")
            
            output_plug = f"{scale_mm}.matrixSum"

        cmds.connectAttr(output_plug, f"{jnt}.offsetParentMatrix")



    return jnts

    """
    import ribbon
    from importlib import reload
    reload(ribbon)
    ribbon.de_boor_ribbon(cmds.ls(sl=True))
    """

def get_consolidated_wts(wts, original_cvs, cvs):
     
    consolidated_weights = {cv : 0 for cv in original_cvs}

    for j, wt in enumerate(wts):
        consolidated_weights[cvs[j]] += wt

    return [consolidated_weights[cv] for cv in original_cvs]

def create_weight_add_matrix(matrix_attrs, wts, name, tol=0.000001):

    wam = cmds.createNode("wtAddMatrix", n=name)

    for matrix_attr, wt, i in zip(matrix_attrs, wts, range(len(matrix_attrs))):

        if wt < tol:

            continue

        cmds.connectAttr(matrix_attr, f"{wam}.wtMatrix[{i}].matrixIn")
        cmds.setAttr(f"{wam}.wtMatrix[{i}].weightIn", wt)

    return wam

def get_weighted_translation_matrix(matrices, weights):

    translation_matrix = om.MMatrix(((1,0,0,0), (0,1,0,0), (0,0,1,0), (0,0,0,1)))

    for m, wt in zip(matrices, weights):
        for i in 12, 13, 14:
            translation_matrix[i] += m[i] * wt

    return translation_matrix
