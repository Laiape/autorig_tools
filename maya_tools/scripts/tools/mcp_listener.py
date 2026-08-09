"""Listener TCP para el MCP de Maya (~/maya-mcp/server.py).

Protocolo: una conexion por comando, una linea JSON de peticion
{"type": ..., "params": {...}} y una linea JSON de respuesta.
Solo escucha en localhost.
"""
import json
import socket
import threading
import traceback

import maya.utils as mu
import maya.cmds as cmds
import maya.mel as mel
import maya.OpenMaya as om

PORT = 9877


def _handle(payload):
    kind = payload.get("type")
    params = payload.get("params", {})
    if kind == "execute_python":
        ns = {}
        exec(params.get("code", ""), ns)
        return ns.get("result")
    if kind == "execute_mel":
        return mel.eval(params.get("code", ""))
    if kind == "scene_info":
        return {
            "file": om.MFileIO.currentFile(),
            "selection": cmds.ls(selection=True),
            "frame_range": [
                cmds.playbackOptions(q=True, min=True),
                cmds.playbackOptions(q=True, max=True),
            ],
        }
    if kind == "list_nodes":
        node_type = params.get("type") or ""
        return cmds.ls(type=node_type) if node_type else cmds.ls()
    raise ValueError(f"Tipo de comando desconocido: {kind}")


def _serve(sock):
    while True:
        conn, _ = sock.accept()
        try:
            buf = b""
            while b"\n" not in buf:
                chunk = conn.recv(8192)
                if not chunk:
                    break
                buf += chunk
            if not buf.strip():
                continue
            payload = json.loads(buf.decode("utf-8"))
            try:
                if cmds.about(batch=True):
                    # ponytail: en batch no hay cola de idle, se ejecuta en este
                    # hilo; algunos flags booleanos de cmds fallan fuera del hilo
                    # principal (p.ej. ls -sl). El caso real es GUI.
                    result = _handle(payload)
                else:
                    result = mu.executeInMainThreadWithResult(_handle, payload)
                reply = {"result": result}
            except Exception:
                reply = {"error": traceback.format_exc()}
            conn.sendall((json.dumps(reply, default=str) + "\n").encode("utf-8"))
        except Exception:
            pass
        finally:
            conn.close()


def start():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("localhost", PORT))
    except OSError:
        sock.close()
        return  # ya hay un listener en este puerto
    sock.listen(1)
    threading.Thread(target=_serve, args=(sock,), daemon=True).start()
