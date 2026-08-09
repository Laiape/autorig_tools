from maya import cmds
from maya.api import OpenMaya as om
from maya.api import OpenMayaAnim as oma
from maya_tools.scripts.utils import de_boor_core as core


OPEN = 'open'
PERIODIC = 'periodic'
INDEX_TO_KNOT_TYPE = {0: OPEN, 2: PERIODIC}


def split_with_curve(verts, jnts, crv, d=None, tol=0.000001):
    """
    Redistribute skinCluster weights for a list of joints using De Boor weights
    derived from each vertex's closest point on a curve.

    Args:
        verts (str | list): mesh or vertex selection to operate on
        jnts (list): joints whose weights will be redistributed (in curve order)
        crv (str): NURBS curve used for closest-point parameter lookup
        d (int): basis function degree; defaults to len(jnts)-1
        tol (float): weight prune threshold

    Returns:
        None
    """
    original_sel = om.MGlobal.getActiveSelectionList()

    verts = cmds.ls(cmds.polyListComponentConversion(verts, toVertex=True), fl=True)
    d = len(jnts) - 1 if d is None else d
    crv_spans = cmds.getAttr(f'{crv}.spans')

    kv_type = INDEX_TO_KNOT_TYPE[cmds.getAttr(f'{crv}.form')]
    kv, modified_jnts = core.knot_vector(kv_type, jnts, d)

    vert_pa = om.MPointArray([cmds.xform(v, q=True, ws=True, t=True) for v in verts])

    cmds.select(verts)
    vert_sl = om.MGlobal.getActiveSelectionList()
    dag, components = vert_sl.getComponent(0)

    skin_cluster = cmds.ls(cmds.listHistory(dag.fullPathName()), typ='skinCluster')[0]
    cmds.skinPercent(skin_cluster, pruneWeights=tol)

    sc_sl  = om.MGlobal.getSelectionListByName(skin_cluster)
    sc_obj = sc_sl.getDependNode(0)
    sc_fn  = oma.MFnSkinCluster(sc_obj)

    influence_dpa   = sc_fn.influenceObjects()
    influence_names = [i.partialPathName() for i in influence_dpa]
    influence_ia    = om.MIntArray(range(len(influence_dpa)))
    jnt_indices     = [influence_names.index(jnt) for jnt in jnts]

    skin_wts     = sc_fn.getWeights(dag, components, influence_ia)
    n_influences = len(influence_dpa)

    jnts_total_wts = [
        sum(skin_wts[jnt_idx + i * n_influences] for jnt_idx in jnt_indices)
        for i in range(len(verts))
    ]

    crv_sl = om.MGlobal.getSelectionListByName(crv)
    crv_dp = crv_sl.getDagPath(0)
    crv_fn = om.MFnNurbsCurve(crv_dp)

    for vert_p, total_wt, i in zip(vert_pa, jnts_total_wts, range(len(verts))):

        if total_wt < tol:
            continue

        _, t = crv_fn.closestPoint(vert_p)
        t_n  = t / crv_spans

        if kv_type == PERIODIC:
            t_n = (kv[d + 1] * (d * 0.5 + 0.5)) * (1 - t_n) + t_n * (1 - kv[d + 1] * (d * 0.5 - 0.5))

        wts = core.de_boor(len(modified_jnts), d, t_n, kv, tol=tol)

        if kv_type == PERIODIC:
            consolidated = {jnt: 0 for jnt in jnts}
            for j, wt in enumerate(wts):
                consolidated[modified_jnts[j]] += wt
            wts = consolidated.values()

        jnts_wts = [wt * total_wt for wt in wts]
        for j, jnt_idx in enumerate(jnt_indices):
            skin_wts[jnt_idx + i * n_influences] = jnts_wts[j]

    sc_fn.setWeights(dag, components, influence_ia, skin_wts)
    om.MGlobal.setActiveSelectionList(original_sel)
