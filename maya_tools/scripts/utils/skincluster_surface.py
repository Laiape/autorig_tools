from maya import cmds
from maya.api import OpenMaya as om
from maya.api import OpenMayaAnim as oma
from maya_tools.scripts.utils import de_boor_core as core


OPEN = 'open'
PERIODIC = 'periodic'
INDEX_TO_KNOT_TYPE = {0: OPEN, 2: PERIODIC}


def split_with_surface(verts, jnts, srf, d=None, tol=0.000001):
    """
    Redistribute skinCluster weights using 2-D De Boor weights derived from
    each vertex's closest UV point on a NURBS surface.

    Args:
        verts (str | list): mesh or vertex selection to operate on
        jnts (list[list[str]]): 2-D grid of joints — outer list = U rows,
            inner list = V joints within each row.  E.g. [[j00,j01],[j10,j11]]
        srf (str): NURBS surface used for closest UV lookup
        d (list[int] | None): [d_u, d_v] degrees; defaults to [n_rows-1, n_cols-1]
        tol (float): weight prune threshold

    Returns:
        None
    """
    original_sel = om.MGlobal.getActiveSelectionList()

    verts     = cmds.ls(cmds.polyListComponentConversion(verts, toVertex=True), fl=True)
    jnts_copy = jnts[:]

    if d is None:
        d_u = len(jnts_copy) - 1
        d_v = min(len(row) for row in jnts_copy) - 1
        d   = [d_u, d_v]

    max_val_u = cmds.getAttr(f'{srf}.maxValueU')
    max_val_v = cmds.getAttr(f'{srf}.maxValueV')
    form_u    = cmds.getAttr(f'{srf}.formU')
    form_v    = cmds.getAttr(f'{srf}.formV')
    kv_type   = [INDEX_TO_KNOT_TYPE[form_u], INDEX_TO_KNOT_TYPE[form_v]]

    vert_pa = om.MPointArray([cmds.xform(v, q=True, ws=True, t=True) for v in verts])

    cmds.select(verts)
    vert_sl = om.MGlobal.getActiveSelectionList()
    dag, components = vert_sl.getComponent(0)

    skin_cluster = cmds.ls(cmds.listHistory(dag.fullPathName()), typ='skinCluster')[0]
    cmds.skinPercent(skin_cluster, pruneWeights=tol)

    sc_sl  = om.MGlobal.getSelectionListByName(skin_cluster)
    sc_obj = sc_sl.getDependNode(0)
    sc_fn  = oma.MFnSkinCluster(sc_obj)

    influences_dpa   = sc_fn.influenceObjects()
    influences_names = [i.partialPathName() for i in influences_dpa]
    influence_ia     = om.MIntArray(range(len(influences_dpa)))
    n_influences     = len(influences_dpa)

    skin_wts = sc_fn.getWeights(dag, components, influence_ia)

    # Collapse V joints into jnts[i][0] before applying De Boor
    for v_jnts in jnts_copy:
        v0_idx = influences_names.index(v_jnts[0])
        for v_jnt in v_jnts[1:]:
            vj_idx = influences_names.index(v_jnt)
            for j in range(len(verts)):
                skin_wts[n_influences * j + v0_idx] += skin_wts[n_influences * j + vj_idx]
                skin_wts[n_influences * j + vj_idx]  = 0

    srf_sl = om.MGlobal.getSelectionListByName(srf)
    srf_dp = srf_sl.getDagPath(0)
    srf_fn = om.MFnNurbsSurface(srf_dp)

    u_jnts = [row[0] for row in jnts_copy]
    jnts_copy.insert(0, u_jnts)

    for i, _jnts in enumerate(jnts_copy):

        if len(_jnts) < 2:
            continue

        _d       = d[0] if i == 0 else d[1]
        _kv_type = kv_type[0] if i == 0 else kv_type[1]
        kv, modified_jnts = core.knot_vector(_kv_type, _jnts, _d)

        max_val     = max_val_u if i == 0 else max_val_v
        jnt_indices = [influences_names.index(jnt) for jnt in _jnts]

        jnts_total_wts = [
            sum(skin_wts[jnt_idx + j * n_influences] for jnt_idx in jnt_indices)
            for j in range(len(verts))
        ]

        for vert_p, total_wt, j in zip(vert_pa, jnts_total_wts, range(len(verts))):

            if total_wt < tol:
                continue

            cp  = srf_fn.closestPoint(vert_p)
            t   = cp[1] if i == 0 else cp[2]
            t_n = t / max_val

            if _kv_type == PERIODIC:
                t_n = (kv[_d + 1] * (_d * 0.5 + 0.5)) * (1 - t_n) + t_n * (1 - kv[_d + 1] * (_d * 0.5 - 0.5))

            wts = core.de_boor(len(modified_jnts), _d, t_n, kv, tol=tol)

            if _kv_type == PERIODIC:
                consolidated = {jnt: 0 for jnt in _jnts}
                for k, wt in enumerate(wts):
                    consolidated[modified_jnts[k]] += wt
                wts = consolidated.values()

            jnts_wts = [wt * total_wt for wt in wts]
            for k, jnt_idx in enumerate(jnt_indices):
                skin_wts[jnt_idx + j * n_influences] = jnts_wts[k]

    sc_fn.setWeights(dag, components, influence_ia, skin_wts)
    om.MGlobal.setActiveSelectionList(original_sel)
