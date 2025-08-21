import maya.cmds as cmds
from maya.api import OpenMaya as om
import de_boor_core as core
from importlib import reload

reload(core)

OPEN = 'open'
PERIODIC = 'periodic'
KNOT_TO_FORM_INDEX = {OPEN : om.MFnNurbsCurve.kOpen, PERIODIC : om.MFnNurbsCurve.kPeriodic}


def de_boor_ribbon(cvs, controllers_grps, aim_axis='x', up_axis='y', num_joints=5, parameter_length=True, tangent_offset=0.001, d=None, kv_type=OPEN, tol=0.000001, name='ribbon'):

    """
    In this function we will create a ribbon setup using the de Boor algorithm.
    args:
        None
    """

    # Match the controller groups to the cvs
    ctls = []
    for i, grp in enumerate(controllers_grps):

        if not cmds.objExists(grp):
            raise om.MGlobal.displayError(
                f'Controller group {grp} does not exist. Please check the input.')

        cmds.matchTransform(grp, cvs[i], pos=True, rot=True, scl=False, pivot=True)

        children = cmds.listRelatives(grp, c=True, type='transform') or [] # Get children of the group
        ctl = next((child for child in children if child.endswith('CTL')), None) # Find the controller in the group

        if ctl:
            ctls.append(ctl) # If found, add to the list

    num_cvds = len(cvs)
    original_cvs = cvs[:]

    d = num_cvds - 1 if d is None else d

    if kv_type == OPEN:
        
        kv, _ = core.knot_vector(OPEN, cvs, d)

    else:  # kv_type is PERIODIC
        m_cvs = [i % len(cvs) for i in range(len(cvs))]
        for i in range(d):
            m_cvs.append(m_cvs[i])

        m_kv_len = len(m_cvs) + d + 1
        m_kv_interval = 1 / (m_kv_len - 2 * (d - 1))
        m_kv = [
            t / (m_kv_len - 1)
            for t in range(m_kv_len)
        ]

        kv, cvs = core.knot_vector(PERIODIC, cvs, d)

        m_cv_pos = om.MPointArray(
            [cmds.xform(obj, q=True, ws=True, t=True) for obj in m_cvs]
        )

        form = KNOT_TO_FORM_INDEX[kv_type]
        is_2d = False
        rational = True
        data_creator = om.MFnNurbsCurveData()
        parent = data_creator.create()

        crv_fn = om.MFnNurbsCurve()
        crv_fn.create(m_cv_pos, m_kv, d, form, is_2d, rational)#, parent)


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

        for i, ctl in enumerate(ctls):

            par_off = cmds.createNode('multMatrix', n=f'{name}_parentOffset_{i}_MM')
            cmds.connectAttr(f'{ctl}.worldMatrix', f'{par_off}.matrixIn[0]')
            cmds.connectAttr(f'{controllers_grps[0]}.worldInverseMatrix', f'{par_off}.matrixIn[1]')

            


