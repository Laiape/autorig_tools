"""
Proxy Locator — Maya Python Plugin
Draws a mesh patch on each controller showing the nearest skin region.
Color is inherited from the controller's override color.

LOAD:
    import maya.cmds as cmds
    cmds.loadPlugin(r"C:/GIT/autorig_tools/maya_tools/scripts/tools/proxy_locator.py")

ASSIGN after rig build (Auto-detectando el body):
    from tools.proxy_locator import assign_all_proxy_locators
    assign_all_proxy_locators(radius=10.0)
    
ASSIGN after rig build (Especificando el mesh manualmente):
    from tools.proxy_locator import assign_all_proxy_locators
    assign_all_proxy_locators(mesh_transform="personaje_geo", radius=10.0)
"""

import maya.api.OpenMaya as om
import maya.api.OpenMayaUI as omui
import maya.api.OpenMayaRender as omr
import maya.cmds as cmds


def maya_useNewAPI():
    pass


# ── Constants ─────────────────────────────────────────────────────────────────

NODE_NAME           = "proxyLocator"
NODE_ID             = om.MTypeId(0x00127891)
DRAW_CLASSIFICATION = "drawdb/geometry/proxyLocator"
DRAW_REGISTRANT_ID  = "proxyLocatorOverride"


# ── Draw data container ───────────────────────────────────────────────────────

class _ProxyData(om.MUserData):
    def __init__(self):
        super().__init__(False)        # deleteAfterUse = False → reuse across frames
        self.positions  = om.MPointArray()
        self.normals    = om.MVectorArray()
        self.indices    = []               # flat triangle index buffer
        self.color      = om.MColor((1.0, 1.0, 0.0, 0.4))
        self.draw_mode  = 0            # 0=solid  1=wireframe  2=points


# ── Node definition ───────────────────────────────────────────────────────────

class ProxyLocatorNode(omui.MPxLocatorNode):

    aInputMesh      = om.MObject()
    aVertexIndices  = om.MObject()
    aLocatorColor   = om.MObject()
    aOpacity        = om.MObject()
    aDrawMode       = om.MObject()

    @classmethod
    def creator(cls):
        return cls()

    @classmethod
    def initialize(cls):
        tAttr = om.MFnTypedAttribute()
        nAttr = om.MFnNumericAttribute()
        eAttr = om.MFnEnumAttribute()

        try:
            cls.aInputMesh = tAttr.create("inputMesh", "im", om.MFnData.kMesh)
            tAttr.storable = False
            tAttr.keyable  = False
            tAttr.hidden   = True
            cls.addAttribute(cls.aInputMesh)
        except Exception:
            pass

        try:
            cls.aVertexIndices = tAttr.create("vertexIndices", "vi", om.MFnData.kIntArray)
            tAttr.storable = True
            tAttr.keyable  = False
            cls.addAttribute(cls.aVertexIndices)
        except Exception:
            pass

        try:
            cls.aLocatorColor = nAttr.createColor("locatorColor", "lc")
            nAttr.storable = True
            nAttr.keyable  = True
            cls.addAttribute(cls.aLocatorColor)
        except Exception:
            pass

        try:
            cls.aOpacity = nAttr.create("opacity", "op", om.MFnNumericData.kFloat, 0.4)
            nAttr.setMin(0.0)
            nAttr.setMax(1.0)
            nAttr.storable = True
            nAttr.keyable  = True
            cls.addAttribute(cls.aOpacity)
        except Exception:
            pass

        try:
            cls.aDrawMode = eAttr.create("drawMode", "dm", 0)
            eAttr.addField("Solid",      0)
            eAttr.addField("Wireframe",  1)
            eAttr.addField("Points",     2)
            eAttr.storable = True
            eAttr.keyable  = True
            cls.addAttribute(cls.aDrawMode)
        except Exception:
            pass

    def isBounded(self):
        return True

    def boundingBox(self):
        return om.MBoundingBox(om.MPoint(-500, -500, -500), om.MPoint(500, 500, 500))


# ── Draw override ─────────────────────────────────────────────────────────────

class ProxyLocatorDrawOverride(omr.MPxDrawOverride):

    @classmethod
    def creator(cls, obj):
        return cls(obj)

    def __init__(self, obj):
        # isAlwaysDirty=False: prepareForDraw only fires when the node is dirty.
        # The worldMesh connection ensures dirtying whenever the mesh deforms.
        super().__init__(obj, None, False)

    def supportedDrawAPIs(self):
        return (omr.MRenderer.kOpenGL |
                omr.MRenderer.kOpenGLCoreProfile |
                omr.MRenderer.kDirectX11)

    def isBounded(self, obj_path, camera_path):
        return True

    def boundingBox(self, obj_path, camera_path):
        return om.MBoundingBox(om.MPoint(-500, -500, -500), om.MPoint(500, 500, 500))

    def hasUIDrawables(self):
        return True

    # ── Prepare ───────────────────────────────────────────────────────────────

    def prepareForDraw(self, obj_path, camera_path, frame_context, old_data):
        data = old_data if isinstance(old_data, _ProxyData) else _ProxyData()
        node = obj_path.node()
        if node.isNull():
            return data

        # Draw mode
        data.draw_mode = om.MPlug(node, ProxyLocatorNode.aDrawMode).asInt()

        # Color + opacity
        cp = om.MPlug(node, ProxyLocatorNode.aLocatorColor)
        r  = cp.child(0).asFloat()
        g  = cp.child(1).asFloat()
        b  = cp.child(2).asFloat()
        a  = om.MPlug(node, ProxyLocatorNode.aOpacity).asFloat()
        data.color = om.MColor((r, g, b, a))

        # Early-out if no mesh connected
        mesh_plug = om.MPlug(node, ProxyLocatorNode.aInputMesh)
        if not mesh_plug.isConnected:
            data.positions = om.MPointArray()
            return data

        mesh_obj = mesh_plug.asMObject()
        if mesh_obj.isNull():
            data.positions = om.MPointArray()
            return data

        # Vertex index array
        idx_plug = om.MPlug(node, ProxyLocatorNode.aVertexIndices)
        idx_obj  = idx_plug.asMObject()
        if idx_obj.isNull():
            data.positions = om.MPointArray()
            return data

        fn_int   = om.MFnIntArrayData(idx_obj)
        raw      = list(fn_int.array())
        if not raw:
            data.positions = om.MPointArray()
            return data

        idx_set   = set(raw)
        local_map = {orig: local for local, orig in enumerate(raw)}

        # Mesh data
        fn_mesh    = om.MFnMesh(mesh_obj)
        all_pts    = fn_mesh.getPoints(om.MSpace.kWorld)
        all_nrm    = fn_mesh.getVertexNormals(True, om.MSpace.kWorld)

        data.positions = om.MPointArray([all_pts[i]  for i in raw])
        data.normals   = om.MVectorArray([all_nrm[i] for i in raw])

        # Build triangle index buffer from faces whose ALL verts are in idx_set
        face_counts, face_verts = fn_mesh.getVertices()
        tri_counts,  tri_verts  = fn_mesh.getTriangles()

        face_counts_l = list(face_counts)
        face_verts_l  = list(face_verts)
        tri_counts_l  = list(tri_counts)
        tri_verts_l   = list(tri_verts)

        flat_indices    = []
        face_v_offset   = 0
        tri_v_offset    = 0

        for fi in range(fn_mesh.numPolygons):
            fvc    = face_counts_l[fi]
            face_v = face_verts_l[face_v_offset : face_v_offset + fvc]
            face_v_offset += fvc
            ntri   = tri_counts_l[fi]

            if all(v in idx_set for v in face_v):
                for t in range(ntri):
                    base = tri_v_offset + t * 3
                    flat_indices.append(local_map[tri_verts_l[base]])
                    flat_indices.append(local_map[tri_verts_l[base + 1]])
                    flat_indices.append(local_map[tri_verts_l[base + 2]])

            tri_v_offset += ntri * 3

        data.indices = flat_indices

        return data

    # ── Draw ──────────────────────────────────────────────────────────────────

    def addUIDrawables(self, obj_path, draw_manager, frame_context, data):
        if not isinstance(data, _ProxyData) or len(data.positions) == 0:
            return

        draw_manager.beginDrawable()
        draw_manager.setColor(data.color)
        draw_manager.setDepthPriority(omr.MRenderItem.sDormantWireDepthPriority)

        mode = data.draw_mode

        if mode == 2:                                   # ── Points
            draw_manager.points(data.positions, False)

        elif mode == 1:                                 # ── Wireframe
            n_tris = len(data.indices) // 3
            if n_tris > 0:
                edge_pts = om.MPointArray()
                for t in range(n_tris):
                    i0 = data.indices[t * 3]
                    i1 = data.indices[t * 3 + 1]
                    i2 = data.indices[t * 3 + 2]
                    edge_pts.append(data.positions[i0])
                    edge_pts.append(data.positions[i1])
                    edge_pts.append(data.positions[i1])
                    edge_pts.append(data.positions[i2])
                    edge_pts.append(data.positions[i2])
                    edge_pts.append(data.positions[i0])
                draw_manager.mesh(omr.MUIDrawManager.kLines, edge_pts)

        else:                                           # ── Solid
            if len(data.indices) >= 3:
                draw_manager.mesh(
                    omr.MUIDrawManager.kTriangles,
                    data.positions,
                    data.normals,
                    None, None,
                    data.indices
                )

        draw_manager.endDrawable()


# ── Plugin registration ───────────────────────────────────────────────────────

def initializePlugin(obj):
    plugin = om.MFnPlugin(obj, "autorig_tools", "1.0")

    try:
        plugin.registerNode(
            NODE_NAME, NODE_ID,
            ProxyLocatorNode.creator,
            ProxyLocatorNode.initialize,
            omui.MPxLocatorNode.kLocatorNode,
            DRAW_CLASSIFICATION
        )
    except Exception as e:
        if "already exists" not in str(e).lower() and "kInvalidParameter" not in str(e):
            om.MGlobal.displayError(f"Failed to register {NODE_NAME}: {e}")
            raise

    try:
        omr.MDrawRegistry.registerDrawOverrideCreator(
            DRAW_CLASSIFICATION,
            DRAW_REGISTRANT_ID,
            ProxyLocatorDrawOverride.creator
        )
    except Exception as e:
        if "already exists" not in str(e).lower() and "kInvalidParameter" not in str(e):
            om.MGlobal.displayError(f"Failed to register draw override: {e}")
            raise


def uninitializePlugin(obj):
    plugin = om.MFnPlugin(obj)
    try:
        omr.MDrawRegistry.deregisterDrawOverrideCreator(DRAW_CLASSIFICATION, DRAW_REGISTRANT_ID)
    except Exception:
        pass
    try:
        plugin.deregisterNode(NODE_ID)
    except Exception:
        pass


# ═════════════════════════════════════════════════════════════════════════════
# Proximity assignment  ── call AFTER rig build, plugin must be loaded
# ═════════════════════════════════════════════════════════════════════════════

# Maya index-color → approximate RGB
_INDEX_COLORS = {
    0:  (0.60, 0.60, 0.60),  1:  (0.00, 0.00, 0.00),  2:  (0.25, 0.25, 0.25),
    3:  (0.60, 0.60, 0.60),  4:  (0.61, 0.00, 0.15),  5:  (0.00, 0.02, 0.37),
    6:  (0.00, 0.00, 1.00),  7:  (0.00, 0.28, 0.10),  8:  (0.15, 0.00, 0.26),
    9:  (0.78, 0.00, 0.78),  10: (0.54, 0.28, 0.20),  11: (0.25, 0.13, 0.13),
    12: (0.70, 0.20, 0.00),  13: (1.00, 0.00, 0.00),  14: (0.00, 1.00, 0.00),
    15: (0.00, 0.30, 0.60),  16: (1.00, 1.00, 1.00),  17: (1.00, 1.00, 0.00),
    18: (0.39, 0.86, 1.00),  19: (0.26, 1.00, 0.64),  20: (1.00, 0.69, 0.69),
    21: (0.89, 0.68, 0.48),  22: (1.00, 1.00, 0.39),  23: (0.00, 0.60, 0.33),
    24: (0.63, 0.41, 0.19),  25: (0.62, 0.63, 0.19),  26: (0.41, 0.63, 0.19),
    27: (0.19, 0.63, 0.36),  28: (0.19, 0.63, 0.63),  29: (0.19, 0.40, 0.63),
    30: (0.43, 0.19, 0.63),  31: (0.63, 0.19, 0.40),
}


def _ctl_color(ctl):
    """Read override color from a controller transform. Returns (r, g, b)."""
    try:
        if cmds.getAttr(f"{ctl}.overrideEnabled"):
            if cmds.getAttr(f"{ctl}.overrideRGBColors"):
                r, g, b = cmds.getAttr(f"{ctl}.overrideColorRGB")[0]
                return (r, g, b)
            idx = cmds.getAttr(f"{ctl}.overrideColor")
            return _INDEX_COLORS.get(idx, (1.0, 1.0, 0.0))
    except Exception:
        pass
    return (1.0, 1.0, 0.0)

def find_body_node(parent_group="geo_GRP"):
    """Find the body mesh transform under parent_group by looking for 'body' in the name."""
    if not cmds.objExists(parent_group):
        return None

    descendants = cmds.listRelatives(parent_group, allDescendents=True, type='transform', fullPath=True)
    
    if not descendants:
        return None

    for node in descendants:
        node_name = node.split('|')[-1]
        if "body" in node_name.lower():
            return node 
            
    return None


def get_vertices_in_radius(mesh_transform, world_pos, radius):
    """Return vertex indices of mesh_transform within radius of world_pos."""
    sel = om.MSelectionList()
    sel.add(mesh_transform)
    dag = sel.getDagPath(0)
    dag.extendToShape()
    fn_mesh = om.MFnMesh(dag)
    pts     = fn_mesh.getPoints(om.MSpace.kWorld)
    cx, cy, cz = world_pos
    indices = []
    for i in range(len(pts)):
        dx = pts[i].x - cx
        dy = pts[i].y - cy
        dz = pts[i].z - cz
        if (dx*dx + dy*dy + dz*dz) <= radius * radius:
            indices.append(i)
    return indices


def _set_vertex_indices(shape_node, indices):
    """Write a Python int list into the proxyLocator.vertexIndices attribute."""
    sel      = om.MSelectionList()
    sel.add(shape_node)
    node_obj = sel.getDependNode(0)
    m_arr    = om.MIntArray(len(indices), 0)
    for i, v in enumerate(indices):
        m_arr[i] = v
    fn_data  = om.MFnIntArrayData()
    data_obj = fn_data.create(m_arr)
    plug     = om.MPlug(node_obj, ProxyLocatorNode.aVertexIndices)
    plug.setMObject(data_obj)


def create_proxy_locator(ctl_transform, mesh_transform, radius=10.0, draw_mode=0):
    """
    Create a proxyLocator shape under ctl_transform.
    Connects to mesh_transform.worldMesh, assigns nearby vertices, copies CTL color.
    Returns the shape node name, or None if no vertices found.
    """
    world_pos = cmds.xform(ctl_transform, q=True, ws=True, t=True)
    indices   = get_vertices_in_radius(mesh_transform, world_pos, radius)

    if not indices:
        om.MGlobal.displayWarning(
            f"proxyLocator: no verts within radius {radius} of '{ctl_transform}' — skipped"
        )
        return None

    short_name = ctl_transform.split("|")[-1]
    cmds.createNode("proxyLocator", parent=ctl_transform, name=f"{short_name}_proxyShape")
    shapes = cmds.listRelatives(ctl_transform, shapes=True, type="proxyLocator") or []
    if not shapes:
        return None
    shape = shapes[-1]

    # Connect mesh deformation output → locator input
    mesh_shape = cmds.listRelatives(mesh_transform, shapes=True, type="mesh")[0]
    cmds.connectAttr(f"{mesh_shape}.worldMesh[0]", f"{shape}.inputMesh")

    # Store vertex indices
    _set_vertex_indices(shape, indices)

    # Inherit controller color
    r, g, b = _ctl_color(ctl_transform)
    cmds.setAttr(f"{shape}.locatorColor", r, g, b, type="double3")
    cmds.setAttr(f"{shape}.drawMode", draw_mode)

    return shape


def assign_all_proxy_locators(mesh_transform=None, ctl_suffix="_CTL", radius=10.0, draw_mode=0, parent_group="geo_GRP"):
    """
    Create proxy locators for every controller in the scene.

    Parameters
    ----------
    mesh_transform : str   Name of the body mesh transform. If None, it auto-detects it.
    ctl_suffix     : str   Suffix that identifies controllers (default "_CTL")
    radius         : float World-space capture radius in scene units
    draw_mode      : int   0=Solid  1=Wireframe  2=Points
    parent_group   : str   Group to search under if mesh_transform is None
    """
    if not cmds.pluginInfo("proxy_locator", q=True, loaded=True):
        try:
            cmds.loadPlugin(__file__)
        except Exception as e:
            om.MGlobal.displayError(f"proxyLocator: Could not load plugin automatically. {e}")
            return []

    # ─── AUTO-DETECCIÓN DEL MESH ──────────────────────────────────────────────
    if not mesh_transform:
        mesh_transform = find_body_node(parent_group)
        if not mesh_transform:
            om.MGlobal.displayError(f"proxyLocator: Auto-detect failed. No body mesh found under '{parent_group}'.")
            return []
        om.MGlobal.displayInfo(f"proxyLocator: Auto-detected mesh -> '{mesh_transform}'")
    # ──────────────────────────────────────────────────────────────────────────

    ctls = [n for n in (cmds.ls(type="transform") or []) if n.endswith(ctl_suffix)]
    if not ctls:
        om.MGlobal.displayWarning(f"proxyLocator: no transforms ending in '{ctl_suffix}' found.")
        return []

    created = []
    for ctl in ctls:
        shape = create_proxy_locator(ctl, mesh_transform, radius=radius, draw_mode=draw_mode)
        if shape:
            created.append(shape)

    om.MGlobal.displayInfo(
        f"proxyLocator: {len(created)}/{len(ctls)} locators created on '{mesh_transform}'."
    )
    return created
