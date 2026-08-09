from maya import cmds
from maya.api import OpenMaya as om
from utils import de_boor_core as core


OPEN = 'open'
PERIODIC = 'periodic'
INDEX_TO_KNOT_TYPE = {0: OPEN, 2: PERIODIC}


def split_with_curve(mesh, base_mesh, crv, output_names, d=None):
    """
    Create blendShape targets by splitting offset vectors with De Boor weights along a curve.

    Args:
        mesh (str): deformed mesh
        base_mesh (str): base/neutral mesh
        crv (str): NURBS curve for closest-point parameter lookup
        output_names (list): names (and count) of output blendshape targets
        d (int): basis function degree; defaults to len(output_names)-1

    Returns:
        list: created mesh names
    """
    num_outputs = len(output_names)
    crv_form  = cmds.getAttr(f'{crv}.form')
    crv_spans = cmds.getAttr(f'{crv}.spans')

    d = num_outputs - 1 if d is None else d
    kv_type = INDEX_TO_KNOT_TYPE[crv_form]
    kv, modified_output_names = core.knot_vector(kv_type, output_names, d)

    mesh_sel      = om.MGlobal.getSelectionListByName(mesh)
    base_mesh_sel = om.MGlobal.getSelectionListByName(base_mesh)
    crv_sel       = om.MGlobal.getSelectionListByName(crv)

    mesh_dp      = mesh_sel.getDagPath(0)
    base_mesh_dp = base_mesh_sel.getDagPath(0)

    mesh_fn      = om.MFnMesh(mesh_dp)
    base_mesh_fn = om.MFnMesh(base_mesh_dp)

    mesh_pa      = mesh_fn.getPoints()
    base_mesh_pa = base_mesh_fn.getPoints()

    base_mesh_va = om.MVectorArray(base_mesh_pa)
    offset_va    = om.MVectorArray([mp - bp for mp, bp in zip(mesh_pa, base_mesh_pa)])

    crv_dp = crv_sel.getDagPath(0)
    crv_fn = om.MFnNurbsCurve(crv_dp)

    output_pas = [base_mesh_pa[:] for _ in range(num_outputs)]

    for base_p, offset_v, base_v, i in zip(base_mesh_pa, offset_va, base_mesh_va, range(len(mesh_pa))):

        if not offset_v.isEquivalent(om.MVector.kZeroVector):

            _, t = crv_fn.closestPoint(base_p)
            t_n  = t / crv_spans

            if kv_type == PERIODIC:
                t_n = kv[d + 1] * (1 - t_n) * (d * 0.5 + 0.5) + t_n * (1 - kv[d + 1] * (d * 0.5 - 0.5))

            wts = core.de_boor(len(modified_output_names), d, t_n, kv)

            if kv_type == PERIODIC:
                consolidated = {name: 0 for name in output_names}
                for j, wt in enumerate(wts):
                    consolidated[modified_output_names[j]] += wt
                wts = consolidated.values()

            for output_pa, wt in zip(output_pas, wts):
                output_pa[i] = om.MPoint(base_v + offset_v * wt)

    output_meshes = []
    for output_pa, output in zip(output_pas, output_names):
        out_mesh = cmds.duplicate(base_mesh, n=output)[0]
        out_sel  = om.MGlobal.getSelectionListByName(out_mesh)
        out_dp   = out_sel.getDagPath(0)
        out_fn   = om.MFnMesh(out_dp)
        out_fn.setPoints(output_pa)
        output_meshes.append(out_mesh)

    return output_meshes
