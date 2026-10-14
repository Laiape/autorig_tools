"""Self-contained scene bootstrap: persistent scriptNode restores session jobs.

This complete source is embedded in the scene. No AutoRig imports are permitted.
"""
import base64
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import zipfile

import maya.cmds as cmds
import maya.utils


def _ar_picker_state():
    if not hasattr(cmds, "_autorig_scene_pickers"):
        cmds._autorig_scene_pickers = {"instances": {}, "jobs": {}, "active": None, "window": None}
    return cmds._autorig_scene_pickers


def _ar_picker_close():
    state = _ar_picker_state()
    window = state.get("window")
    if window is not None:
        try:
            window.close()
        except RuntimeError:
            pass
    state["window"] = None
    state["active"] = None


def _ar_picker_clear():
    state = _ar_picker_state()
    _ar_picker_close()
    jobs = list(state["jobs"].values()) + [i["delete_job"] for i in state["instances"].values()]
    # Clear ownership before killing jobs: Maya can stop a currently running job.
    state["instances"].clear()
    state["jobs"].clear()
    owned = {int(line.split(":", 1)[0]) for line in cmds.scriptJob(listJobs=True) or []
             if "_ar_picker_" in line}
    for job in jobs:
        if job in owned and cmds.scriptJob(exists=job):
            try:
                cmds.scriptJob(kill=job, force=True)
            except RuntimeError:
                pass  # A runOnce callback may already be completing.


def _ar_picker_deleted(key):
    state = _ar_picker_state()
    state["instances"].pop(key, None)
    if state["active"] == key:
        _ar_picker_close()
    if not state["instances"]:
        _ar_picker_clear()


def _ar_picker_directory(payload):
    digest = hashlib.sha256(payload.encode("ascii")).hexdigest()
    directory = Path(cmds.internalVar(userAppDir=True))/"scripts/character_picker_cache"/digest
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(payload))) as archive:
        for info in archive.infolist():
            path = (directory/info.filename).resolve()
            if not path.is_relative_to(directory.resolve()):
                raise ValueError("Invalid embedded picker path")
            data = archive.read(info)
            if not path.is_file() or path.read_bytes() != data:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
    return directory


def _ar_picker_activate(key, force=False):
    state = _ar_picker_state()
    if key not in state["instances"]:
        return None
    if state["active"] == key and not force:
        # Respect an intentional close until another character or scene is chosen.
        return state["window"]
    instance = state["instances"][key]
    nodes = cmds.ls(key, long=True) or []
    roots = cmds.ls(instance["root_uuid"], long=True) or []
    if not nodes or not roots:
        _ar_picker_deleted(key)
        return None
    try:
        payload = cmds.getAttr(nodes[0]+".autorigPickerPayload")
        directory = _ar_picker_directory(payload)
        name = "autorig_embedded_picker_"+directory.name
        module = sys.modules.get(name)
        if module is None:
            spec = importlib.util.spec_from_file_location(name, str(directory/"character_picker_runtime.py"))
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
        _ar_picker_close()
        window = module.show(root_uuid=instance["root_uuid"])
        state["active"], state["window"] = key, window
        return window
    except Exception:
        import traceback
        cmds.warning("Embedded character picker could not open:\n"+traceback.format_exc())
        return None


def _ar_picker_selection():
    state = _ar_picker_state()
    for node in cmds.ls(selection=True, long=True) or []:
        for key, instance in list(state["instances"].items()):
            roots = cmds.ls(instance["root_uuid"], long=True) or []
            if roots and (node == roots[0] or node.startswith(roots[0]+"|")):
                _ar_picker_activate(key)
                return


def _ar_picker_identity(node):
    # References to the same file share source UUIDs. Their full names are unique.
    if cmds.referenceQuery(node, isNodeReferenced=True):
        return cmds.ls(node, long=True)[0]
    return cmds.ls(node, uuid=True)[0]


def _ar_picker_register_all(auto_open=True):
    if cmds.about(batch=True) or int(cmds.about(apiVersion=True)) < 20240000:
        return
    from functools import partial
    state = _ar_picker_state()
    for key, instance in list(state["instances"].items()):
        if not cmds.ls(key) or not cmds.ls(instance["root_uuid"]):
            _ar_picker_deleted(key)
    for node in cmds.ls(type="script") or []:
        if not cmds.attributeQuery("autorigPickerPayload", node=node, exists=True):
            continue
        roots = cmds.listConnections(node+".autorigPickerRoot", source=True, destination=False) or []
        if len(roots) != 1:
            continue
        key = _ar_picker_identity(node)
        root_uuid = _ar_picker_identity(roots[0])
        previous = state["instances"].get(key)
        if previous and cmds.scriptJob(exists=previous["delete_job"]):
            continue
        state["instances"][key] = {"root_uuid": root_uuid,
                                  "delete_job": cmds.scriptJob(nodeDeleted=[roots[0], partial(_ar_picker_deleted, key)], killWithScene=True)}
    if not state["instances"]:
        _ar_picker_clear()
        return
    for event, callback, options in [
            ("SelectionChanged", _ar_picker_selection, {"killWithScene": True}),
            ("deleteAll", _ar_picker_clear, {"runOnce": True})]:
        old = state["jobs"].get(event)
        if not old or not cmds.scriptJob(exists=old):
            state["jobs"][event] = cmds.scriptJob(event=[event, callback], **options)
    if auto_open:
        _ar_picker_selection()
        if state["active"] is None:
            _ar_picker_activate(next(iter(state["instances"])))


def attach(directory, root, open_picker=True):
    """Store only picker code/data on one live rig root; reuse its existing node."""
    directory = Path(directory)
    root = (cmds.ls(root, long=True) or [None])[0]
    if root is None:
        raise ValueError("Missing character root")
    config = json.loads((directory/"picker_config.json").read_text(encoding="utf-8"))
    files = ["character_picker_runtime.py", "picker.json", "picker_config.json"] + [p["background"] for p in config["panels"]]
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in files:
            archive.write(directory/name, name)
    payload = base64.b64encode(stream.getvalue()).decode("ascii")
    nodes = [n for n in cmds.listConnections(root+".message", destination=True, source=False, type="script") or []
             if cmds.attributeQuery("autorigPickerPayload", node=n, exists=True)]
    if len(nodes) > 1:
        raise ValueError("Multiple embedded picker nodes on " + root)
    if nodes:
        node = nodes[0]
    else:
        node = cmds.scriptNode(name=root.rsplit("|", 1)[-1]+"_Picker_SCRIPT", scriptType=2, sourceType="python")
        cmds.addAttr(node, longName="autorigPickerPayload", dataType="string")
        cmds.addAttr(node, longName="autorigPickerRoot", attributeType="message")
        cmds.connectAttr(root+".message", node+".autorigPickerRoot")
    bootstrap = Path(__file__).read_text(encoding="utf-8") + "\nmaya.utils.executeDeferred(_ar_picker_register_all)\n"
    cmds.scriptNode(node, edit=True, beforeScript=bootstrap, afterScript="", scriptType=2, sourceType="python")
    cmds.setAttr(node+".autorigPickerPayload", payload, type="string")
    if open_picker and not cmds.about(batch=True):
        _ar_picker_register_all(auto_open=False)
        _ar_picker_activate(_ar_picker_identity(node), force=True)
    return node


def matching_roots(character):
    """Only actual character rigs, excluding a character group containing meshes."""
    roots = cmds.ls(character, "*:"+character, type="transform", long=True) or []
    controls = cmds.ls("C_character_CTL", "*:C_character_CTL", type="transform", long=True) or []
    return [root for root in roots if any(n.startswith(root+"|") for n in controls)]
