"""One-shot IK/FK pose matching, including matrix-only limb solvers."""
import inspect
from functools import partial

import maya.cmds as cmds
import maya.api.OpenMaya as om


def _connected(node, attribute, index=None):
    plug = "{}.{}".format(node, attribute)
    if index is not None:
        plug += "[{}]".format(index)
    return (cmds.listConnections(plug, source=True, destination=False) or [None])[0]


def match_ik_to_fk(settings):
    """Snapshot IK matrices before editing FK; keep locked CTL translations intact."""
    indices = cmds.getAttr(settings + ".matchFkControls", multiIndices=True) or []
    controls = [_connected(settings, "matchFkControls", i) for i in indices]
    blends = [_connected(settings, "matchIkMatrices", i) for i in indices]
    if not controls or not all(controls + blends):
        raise RuntimeError("Incomplete IK/FK match connections on " + settings)
    matrices = [om.MMatrix(cmds.getAttr(node + ".inputMatrix")) for node in blends]
    positions = [om.MVector(m[12], m[13], m[14]) for m in matrices]
    offsets = [cmds.listRelatives(ctl, parent=True, fullPath=True)[0] for ctl in controls]
    # Save editable channels so a failed match cannot leave half of the limb changed.
    plugs = [settings + ".Ik_Fk"]
    for ctl, offset in zip(controls, offsets):
        plugs.extend(ctl + ".rotate" + axis for axis in "XYZ")
        plugs.extend(offset + ".translate" + axis for axis in "XYZ")
        if cmds.objExists(ctl + ".Stretch"):
            plugs.append(ctl + ".Stretch")
    values = [cmds.getAttr(plug) for plug in plugs]
    if not all(cmds.getAttr(plug, settable=True) for plug in plugs):
        raise RuntimeError("IK/FK match channels are locked or connected on " + settings)

    cmds.undoInfo(openChunk=True, chunkName="Match IK to FK")
    try:
        for offset in offsets:
            cmds.setAttr(offset + ".translate", 0, 0, 0)
        for i, (ctl, offset, matrix) in enumerate(zip(controls, offsets, matrices)):
            # Stretch moves the next FK GRP along its rest primary axis. Measure
            # in world space to account for global scale and either mirrored side.
            if i and cmds.objExists(controls[i - 1] + ".Stretch"):
                stretch = controls[i - 1] + ".Stretch"
                cmds.setAttr(stretch, 1)
                a = om.MVector(cmds.xform(controls[i - 1], q=True, ws=True, t=True))
                b = om.MVector(cmds.xform(ctl, q=True, ws=True, t=True))
                rest_length = (b - a).length()
                if rest_length > 1e-8:
                    cmds.setAttr(stretch, (positions[i] - positions[i - 1]).length() / rest_length)

            # ANM is an editable offset below the driven GRP. Move it only by the
            # residual needed for root offsets, pinning, or foot pivot poses.
            current = om.MVector(cmds.xform(ctl, q=True, ws=True, t=True))
            origin = om.MVector(cmds.xform(offset, q=True, ws=True, t=True))
            cmds.xform(offset, ws=True, t=list(origin + positions[i] - current))
            parent_world = om.MMatrix(cmds.getAttr(offset + ".worldMatrix[0]"))
            opm = om.MMatrix(cmds.getAttr(ctl + ".offsetParentMatrix"))
            local = om.MTransformationMatrix(matrix * (opm * parent_world).inverse())
            rotation = local.rotation()
            rotation.reorderIt(cmds.getAttr(ctl + ".rotateOrder"))
            angle = lambda value: om.MAngle(value).asUnits(om.MAngle.uiUnit())
            cmds.setAttr(ctl + ".rotate", *[angle(v) for v in (rotation.x, rotation.y, rotation.z)])
        cmds.setAttr(settings + ".Ik_Fk", 1)
    except Exception:
        for plug, value in zip(plugs, values):
            cmds.setAttr(plug, value)
        raise
    finally:
        cmds.undoInfo(closeChunk=True)


def _set_world(node, matrix, rotate=True):
    """Set editable TR channels through the existing parent/space and OPM."""
    parent = cmds.listRelatives(node, parent=True, fullPath=True) or []
    world = om.MMatrix(cmds.getAttr(parent[0] + ".worldMatrix[0]")) if parent else om.MMatrix()
    opm = om.MMatrix(cmds.getAttr(node + ".offsetParentMatrix"))
    local = om.MTransformationMatrix(matrix * (opm * world).inverse())
    cmds.setAttr(node + ".translate", *list(local.translation(om.MSpace.kTransform)))
    if rotate:
        rotation = local.rotation()
        rotation.reorderIt(cmds.getAttr(node + ".rotateOrder"))
        cmds.setAttr(node + ".rotate", *[om.MAngle(v).asUnits(om.MAngle.uiUnit())
                                         for v in (rotation.x, rotation.y, rotation.z)])


def match_fk_to_ik(settings):
    """Match root, end effector, bend plane and reverse-foot targets to FK."""
    indices = cmds.getAttr(settings + ".matchFkControls", multiIndices=True) or []
    controls = [_connected(settings, "matchFkControls", i) for i in indices]
    root, end, pv = [_connected(settings, attr) for attr in ("matchIkRoot", "matchIkEnd", "matchIkPv")]
    if len(controls) < 3 or not all(controls + [root, end, pv]):
        raise RuntimeError("Incomplete FK/IK match connections on " + settings)
    matrices = [om.MMatrix(cmds.getAttr(ctl + ".worldMatrix[0]")) for ctl in controls]
    positions = [om.MVector(m[12], m[13], m[14]) for m in matrices]
    foot_indices = cmds.getAttr(settings + ".matchFootControls", multiIndices=True) or []
    foot = [_connected(settings, "matchFootControls", i) for i in foot_indices]
    if foot and (len(foot) != 6 or not all(foot)):
        raise RuntimeError("Incomplete reverse-foot connections on " + settings)
    master = _connected(settings, "matchScaleControl")
    scale = abs(cmds.getAttr(master + ".globalScale")) if master else 1.0
    if scale < 1e-8:
        raise RuntimeError("Cannot match an IK limb with zero global scale")
    targets = [(root, False), (end, True), (pv, False)]
    targets.extend((ctl, True) for ctl in foot[1:])
    plugs = [settings + ".Ik_Fk"]
    for ctl, rotate in targets:
        plugs.extend(ctl + ".translate" + axis for axis in "XYZ")
        if rotate:
            plugs.extend(ctl + ".rotate" + axis for axis in "XYZ")
    neutral = {"Soft": 0, "Stretch": 0, "Ankle_Twist": 0, "Ball_Twist": 0,
               "Toe_Twist": 0, "Heel_Twist": 0, "Bank": 0, "Roll": 0}
    adjustments = {end + "." + attr: value for attr, value in neutral.items()
                   if cmds.objExists(end + "." + attr)}
    for i, attr in enumerate(("upperLengthMult", "lowerLengthMult")):
        if cmds.objExists(end + "." + attr):
            rest = cmds.getAttr(settings + ".matchRestLength{}".format(i)) * scale
            adjustments[end + "." + attr] = max(0.001, (positions[i + 1] - positions[i]).length() / rest)
    if cmds.objExists(pv + ".Pin"):
        adjustments[pv + ".Pin"] = 0
    plugs.extend(adjustments)
    plugs = list(dict.fromkeys(plugs))
    if not all(cmds.getAttr(plug, settable=True) for plug in plugs):
        raise RuntimeError("FK/IK match channels are locked or connected on " + settings)
    values = [cmds.getAttr(plug) for plug in plugs]

    # Project the middle joint onto the root/end line. A straight chain uses
    # the previous PV direction, then the stored rest direction as a fallback.
    axis = positions[2] - positions[0]
    projection = om.MVector(positions[0])
    if axis.length() > 1e-8:
        projection += axis * ((positions[1] - positions[0]) * axis / (axis * axis))
    bend = positions[1] - projection
    if bend.length() < 1e-8:
        bend = om.MVector(cmds.xform(pv, q=True, ws=True, t=True)) - projection
        if axis.length() > 1e-8:
            bend -= axis * (bend * axis / (axis * axis))
    if bend.length() < 1e-8:
        rest_direction = cmds.getAttr(settings + ".matchRestPvDirection")[0]
        bend = om.MVector(rest_direction) * matrices[0]
        if axis.length() > 1e-8:
            bend -= axis * (bend * axis / (axis * axis))
    if bend.length() < 1e-8:
        bend = axis ^ om.MVector(0, 1, 0)
        if bend.length() < 1e-8:
            bend = om.MVector(0, 0, 1)
    distance = max((positions[1] - positions[0]).length() + (positions[2] - positions[1]).length(), 1.0)
    pv_matrix = om.MMatrix()
    pv_position = positions[1] + bend.normal() * distance
    pv_matrix[12], pv_matrix[13], pv_matrix[14] = pv_position.x, pv_position.y, pv_position.z

    cmds.undoInfo(openChunk=True, chunkName="Match FK to IK")
    try:
        for plug, value in adjustments.items():
            cmds.setAttr(plug, value)
        _set_world(root, matrices[0], rotate=False)
        offset = om.MMatrix(cmds.getAttr(settings + ".matchEndOffset"))
        _set_world(end, offset * matrices[2])
        if foot:
            # Clear the intermediate reverse-foot pivots before matching their
            # descendants in hierarchy order (toe, then ball).
            for ctl in foot[1:4]:
                cmds.setAttr(ctl + ".translate", 0, 0, 0)
                cmds.setAttr(ctl + ".rotate", 0, 0, 0)
            if cmds.getAttr(settings + ".matchCustomFoot"):
                base_offset = om.MMatrix(cmds.getAttr(settings + ".matchFootBaseOffset"))
                bone_offset = om.MMatrix(cmds.getAttr(settings + ".matchFootBoneOffset"))
                _set_world(foot[4], base_offset.inverse() * bone_offset * matrices[3])
                ball_offset = om.MMatrix(cmds.getAttr(settings + ".matchFootBallOffset"))
                _set_world(foot[5], ball_offset * matrices[2])
            else:
                toe_offset = om.MMatrix(cmds.getAttr(settings + ".matchFootToeOffset"))
                _set_world(foot[4], toe_offset * matrices[3])
                _set_world(foot[5], matrices[3])
        _set_world(pv, pv_matrix, rotate=False)
        # Custom solvers can add a rest-axis correction or PV frame offset.
        # Refine the geometric target against the actual evaluated middle joint.
        middle_blend = _connected(settings, "matchIkMatrices", indices[1])
        solver_middle = om.MVector(positions[1])
        for _ in range(12 if cmds.getAttr(settings + ".matchRefineMiddle") else 0):
            actual = cmds.getAttr(middle_blend + ".inputMatrix")
            error = positions[1] - om.MVector(actual[12], actual[13], actual[14])
            if error.length() < 1e-5:
                break
            solver_middle += error
            for i, attr in enumerate(("upperLengthMult", "lowerLengthMult")):
                if cmds.objExists(end + "." + attr):
                    point = positions[0] if i == 0 else positions[2]
                    rest = cmds.getAttr(settings + ".matchRestLength{}".format(i)) * scale
                    cmds.setAttr(end + "." + attr, max(0.001, (solver_middle - point).length() / rest))
            refined_bend = solver_middle - projection
            if axis.length() > 1e-8:
                refined_bend -= axis * (refined_bend * axis / (axis * axis))
            if refined_bend.length() > 1e-8:
                refined_position = solver_middle + refined_bend.normal() * distance
                pv_matrix[12], pv_matrix[13], pv_matrix[14] = refined_position.x, refined_position.y, refined_position.z
                _set_world(pv, pv_matrix, rotate=False)
        cmds.setAttr(settings + ".Ik_Fk", 0)
    except Exception:
        for plug, value in zip(plugs, values):
            cmds.setAttr(plug, value)
        raise
    finally:
        cmds.undoInfo(closeChunk=True)


def _trigger(uuid, attribute="Match_Ik_To_Fk"):
    nodes = cmds.ls(uuid, long=True) or []
    if not nodes or om.MGlobal.isUndoing() or om.MGlobal.isRedoing():
        return
    settings = nodes[0]
    if not cmds.getAttr(settings + "." + attribute):
        return
    try:
        if attribute == "Match_Fk_To_Ik":
            match_fk_to_ik(settings)
        else:
            match_ik_to_fk(settings)
    except Exception as error:
        cmds.warning("{} failed: {}".format(attribute, error))
    finally:
        cmds.setAttr(settings + "." + attribute, 0)


def install_all():
    """Restore callbacks on scene load; message links survive namespaces/renames."""
    jobs = getattr(cmds, "_autorig_ik_to_fk_jobs", {})
    cmds._autorig_ik_to_fk_jobs = jobs
    for script in cmds.ls(type="script") or []:
        if not cmds.attributeQuery("ikFkMatchSettings", node=script, exists=True):
            continue
        settings = _connected(script, "ikFkMatchSettings")
        if not settings:
            continue
        uuid = cmds.ls(settings, uuid=True)[0]
        for attribute in ("Match_Ik_To_Fk", "Match_Fk_To_Ik"):
            if not cmds.attributeQuery(attribute, node=settings, exists=True):
                continue
            key = (uuid, attribute)
            old_job = jobs.get(key)
            if old_job and cmds.scriptJob(exists=old_job):
                continue
            jobs[key] = cmds.scriptJob(
                attributeChange=[settings + "." + attribute, partial(_trigger, uuid, attribute)],
                killWithScene=True, compressUndo=True)


def setup(settings, fk_controls, blend_matrices, ik_root=None, ik_end=None,
          pv=None, foot_controls=None, guides=None, master=None, custom_foot=False,
          refine_middle=False):
    """Add the Channel Box action and a self-contained scene-load installer."""
    if len(fk_controls) != len(blend_matrices):
        raise ValueError("Each FK control needs its IK blend matrix")
    cmds.addAttr(settings, longName="Match_Ik_To_Fk", niceName="Match IK To FK",
                 attributeType="enum", enumName="Ready:Match", keyable=False)
    cmds.setAttr(settings + ".Match_Ik_To_Fk", channelBox=True)
    for attribute in ("matchFkControls", "matchIkMatrices"):
        cmds.addAttr(settings, longName=attribute, attributeType="message", multi=True)
    for i, (ctl, blend) in enumerate(zip(fk_controls, blend_matrices)):
        cmds.connectAttr(ctl + ".message", "{}.matchFkControls[{}]".format(settings, i))
        cmds.connectAttr(blend[0] + ".message", "{}.matchIkMatrices[{}]".format(settings, i))
    if ik_root and ik_end and pv:
        cmds.addAttr(settings, longName="Match_Fk_To_Ik", niceName="Match FK To IK",
                     attributeType="enum", enumName="Ready:Match", keyable=False)
        cmds.setAttr(settings + ".Match_Fk_To_Ik", channelBox=True)
        for attribute, node in (("matchIkRoot", ik_root), ("matchIkEnd", ik_end),
                                ("matchIkPv", pv), ("matchScaleControl", master)):
            cmds.addAttr(settings, longName=attribute, attributeType="message")
            if node:
                cmds.connectAttr(node + ".message", settings + "." + attribute)
        rest = [om.MMatrix(cmds.getAttr(plug)) for plug in guides] if guides else [
            om.MMatrix(cmds.getAttr(ctl + ".worldMatrix[0]")) for ctl in fk_controls]
        scale = abs(cmds.getAttr(master + ".globalScale")) if master else 1.0
        for i in range(2):
            a, b = rest[i], rest[i + 1]
            length = (om.MVector(b[12], b[13], b[14]) - om.MVector(a[12], a[13], a[14])).length() / scale
            if length < 1e-8:
                raise ValueError("Cannot register an IK limb with zero rest length")
            cmds.addAttr(settings, longName="matchRestLength{}".format(i), at="double", dv=length)
        cmds.addAttr(settings, longName="matchRestPvDirection", at="double3")
        for axis in "XYZ":
            cmds.addAttr(settings, longName="matchRestPvDirection" + axis, at="double", p="matchRestPvDirection")
        direction = om.MVector(cmds.xform(pv, q=True, ws=True, t=True)) - om.MVector(rest[1][12], rest[1][13], rest[1][14])
        direction = direction * rest[0].inverse()
        cmds.setAttr(settings + ".matchRestPvDirection", *list(direction))
        matrix_values = {"matchEndOffset": om.MMatrix(cmds.getAttr(ik_end + ".worldMatrix[0]")) * rest[2].inverse()}
        cmds.addAttr(settings, longName="matchFootControls", at="message", multi=True)
        cmds.addAttr(settings, longName="matchCustomFoot", at="bool", dv=custom_foot)
        cmds.addAttr(settings, longName="matchRefineMiddle", at="bool", dv=refine_middle)
        if foot_controls:
            for i, ctl in enumerate(foot_controls):
                cmds.connectAttr(ctl + ".message", "{}.matchFootControls[{}]".format(settings, i))
            ankle, toe, ball = [om.MMatrix(cmds.getAttr(ctl + ".worldMatrix[0]"))
                                for ctl in (foot_controls[0], foot_controls[4], foot_controls[5])]
            matrix_values.update(matchFootBallOffset=ball * rest[2].inverse(),
                                 matchFootToeOffset=toe * rest[3].inverse(),
                                 matchFootBaseOffset=ankle * toe.inverse())
            length = (om.MVector(rest[3][12], rest[3][13], rest[3][14]) -
                      om.MVector(rest[2][12], rest[2][13], rest[2][14])).length()
            sign = -1 if (rest[3] * rest[2].inverse())[12] < 0 else 1
            bone = om.MMatrix()
            bone[12] = -sign * length
            matrix_values["matchFootBoneOffset"] = bone
        for attribute, value in matrix_values.items():
            cmds.addAttr(settings, longName=attribute, dataType="matrix")
            cmds.setAttr(settings + "." + attribute, list(value), type="matrix")
    runtime = "import maya.cmds as cmds\nimport maya.api.OpenMaya as om\nfrom functools import partial\n\n"
    runtime += "\n\n".join(inspect.getsource(fn) for fn in
                            (_connected, match_ik_to_fk, _set_world, match_fk_to_ik, _trigger, install_all))
    runtime += "\ninstall_all()\n"
    script = cmds.scriptNode(name=settings.replace("_CTL", "_IkFkMatch_SCRIPT"),
                             scriptType=1, sourceType="python",
                             beforeScript="exec({!r}, {{}})".format(runtime))
    cmds.addAttr(script, longName="ikFkMatchSettings", attributeType="message")
    cmds.connectAttr(settings + ".message", script + ".ikFkMatchSettings")
    install_all()
