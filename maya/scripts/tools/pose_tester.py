"""
pose_tester.py
==============
Rig Pose Tester — genera la animación ROM (Range of Motion) estándar de la
industria sobre los controladores del rig bípedo.

Flujo de trabajo (el recomendado por riggers de producción para validar
skinning y deformaciones — Kiel Figgins "Painting Weights", Maya Rigging
Wiki, herramientas ROM de estudios):
  - cada zona del cuerpo se anima AISLADA, un eje cada vez,
  - keys espaciadas N frames (10 por defecto),
  - se vuelve SIEMPRE a la pose neutral entre extremos (neutral -> max ->
    neutral -> min -> neutral), de modo que las keys nunca se solapan y cada
    deformación se puede evaluar por separado en el timeline.

Los ángulos vienen de las tablas de goniometría clínica (AAOS / NASM /
Physiopedia) usadas como referencia del rango articular humano, redondeados
para stress-test. En las bisagras (codo / rodilla) se aplica el rango de
flexión en AMBOS sentidos para estresar el skinning con independencia del
signo del eje, y en cadera se incluyen los extremos de kick/splits que se
usan en los ROM de producción.

Convención de ejes de este autorig (ver arm_module / fingers_module):
    rotateZ = bend en el plano vertical (elevación de hombro, flexión de
              muñeca, curl de dedos)
    rotateY = bend en el plano horizontal (flexión del CODO en T-pose) /
              lateral / spread
    rotateX = twist

Uso sin UI (Script Editor):
    from tools import pose_tester
    pose_tester.animate_pose("Shoulder", 0, sides=("L", "R"))
    pose_tester.animate_full_body()
    pose_tester.clear_test()
"""

import maya.cmds as cmds

DEFAULT_SPACING = 10  # frames entre key y key (estándar ROM)
DEFAULT_START = 1


def _ch(ctl, attr, v_max, v_min, distribute=False):
    """Canal de test: un bloque de keys aislado sobre `ctl.attr`.

    `distribute=True` reparte el valor total entre todos los controles que
    matcheen el patrón (p. ej. la cadena de spine).
    """
    return {"ctl": ctl, "attr": attr, "max": v_max, "min": v_min,
            "distribute": distribute}


# ─────────────────────────────────────────────────────────────────────────────
#  POSE LIBRARY  (zona -> poses ROM)
# ─────────────────────────────────────────────────────────────────────────────
# Orden top-down: es el orden del Full Body ROM y el de la UI.
ZONES = [
    "Spine",
    "Neck / Head",
    "Clavicle",
    "Shoulder",
    "Elbow",
    "Wrist",
    "Fingers",
    "Hip",
    "Knee",
    "Ankle / Foot",
]

POSE_LIBRARY = {
    "Spine": {
        "settings": None,
        "poses": [
            ("Flexion / Extension  (rotateZ +75/-30 total)",
             [_ch("C_spine0?_CTL", "rotateZ", 75, -30, distribute=True)]),
            ("Lateral Bend  (rotateY +/-35 total)",
             [_ch("C_spine0?_CTL", "rotateY", 35, -35, distribute=True)]),
            ("Twist  (rotateX +/-45 total)",
             [_ch("C_spine0?_CTL", "rotateX", 45, -45, distribute=True)]),
            ("Full ROM (all axes)",
             [_ch("C_spine0?_CTL", "rotateZ", 75, -30, distribute=True),
              _ch("C_spine0?_CTL", "rotateY", 35, -35, distribute=True),
              _ch("C_spine0?_CTL", "rotateX", 45, -45, distribute=True)]),
        ],
    },
    "Neck / Head": {
        "settings": None,
        "poses": [
            ("Flexion / Extension  (rotateZ +25/-30 each)",
             [_ch("C_neck_CTL", "rotateZ", 25, -30),
              _ch("C_head_CTL", "rotateZ", 25, -30)]),
            ("Lateral Bend  (rotateY +/-20 each)",
             [_ch("C_neck_CTL", "rotateY", 20, -20),
              _ch("C_head_CTL", "rotateY", 20, -20)]),
            ("Turn / Twist  (rotateX +/-40 each)",
             [_ch("C_neck_CTL", "rotateX", 40, -40),
              _ch("C_head_CTL", "rotateX", 40, -40)]),
            ("Full ROM (all axes)",
             [_ch("C_neck_CTL", "rotateZ", 25, -30),
              _ch("C_head_CTL", "rotateZ", 25, -30),
              _ch("C_neck_CTL", "rotateY", 20, -20),
              _ch("C_head_CTL", "rotateY", 20, -20),
              _ch("C_neck_CTL", "rotateX", 40, -40),
              _ch("C_head_CTL", "rotateX", 40, -40)]),
        ],
    },
    "Clavicle": {
        "settings": None,
        "poses": [
            ("Shrug Up / Down  (rotateZ +40/-15)",
             [_ch("{side}_clavicle_CTL", "rotateZ", 40, -15)]),
            ("Forward / Back  (rotateY +/-30)",
             [_ch("{side}_clavicle_CTL", "rotateY", 30, -30)]),
            ("Full ROM (all axes)",
             [_ch("{side}_clavicle_CTL", "rotateZ", 40, -15),
              _ch("{side}_clavicle_CTL", "rotateY", 30, -30)]),
        ],
    },
    "Shoulder": {
        "settings": "{side}_armSettings_CTL",
        "poses": [
            ("Flexion / Extension — raise & lower  (rotateZ +170/-50)",
             [_ch("{side}_shoulderFk_CTL", "rotateZ", 170, -50)]),
            ("Abduction / Adduction  (rotateY +110/-40)",
             [_ch("{side}_shoulderFk_CTL", "rotateY", 110, -40)]),
            ("Twist In / Out  (rotateX +90/-70)",
             [_ch("{side}_shoulderFk_CTL", "rotateX", 90, -70)]),
            ("Full ROM (all axes)",
             [_ch("{side}_shoulderFk_CTL", "rotateZ", 170, -50),
              _ch("{side}_shoulderFk_CTL", "rotateY", 110, -40),
              _ch("{side}_shoulderFk_CTL", "rotateX", 90, -70)]),
        ],
    },
    "Elbow": {
        "settings": "{side}_armSettings_CTL",
        "poses": [
            ("Bend  (rotateY +/-145)",
             [_ch("{side}_elbowFk_CTL", "rotateY", 145, -145)]),
            ("Forearm Twist — pron / sup  (rotateX +/-85)",
             [_ch("{side}_elbowFk_CTL", "rotateX", 85, -85)]),
            ("Full ROM (all axes)",
             [_ch("{side}_elbowFk_CTL", "rotateY", 145, -145),
              _ch("{side}_elbowFk_CTL", "rotateX", 85, -85)]),
        ],
    },
    "Wrist": {
        "settings": "{side}_armSettings_CTL",
        "poses": [
            ("Flexion / Extension  (rotateZ +80/-70)",
             [_ch("{side}_wristFk_CTL", "rotateZ", 80, -70)]),
            ("Radial / Ulnar  (rotateY +30/-25)",
             [_ch("{side}_wristFk_CTL", "rotateY", 30, -25)]),
            ("Twist  (rotateX +/-85)",
             [_ch("{side}_wristFk_CTL", "rotateX", 85, -85)]),
            ("Full ROM (all axes)",
             [_ch("{side}_wristFk_CTL", "rotateZ", 80, -70),
              _ch("{side}_wristFk_CTL", "rotateY", 30, -25),
              _ch("{side}_wristFk_CTL", "rotateX", 85, -85)]),
        ],
    },
    "Fingers": {
        "settings": None,
        "poses": [
            ("Curl  (Curl +/-10)",
             [_ch("{side}_fingersAttributes_CTL", "Curl", 10, -10)]),
            ("Spread  (Spread +/-10)",
             [_ch("{side}_fingersAttributes_CTL", "Spread", 10, -10)]),
            ("Cup  (Cup +/-10)",
             [_ch("{side}_fingersAttributes_CTL", "Cup", 10, -10)]),
            ("Fan  (Fan +/-10)",
             [_ch("{side}_fingersAttributes_CTL", "Fan", 10, -10)]),
            ("Thumb Curl  (Thumb_Curl +/-10)",
             [_ch("{side}_fingersAttributes_CTL", "Thumb_Curl", 10, -10)]),
            ("Thumb Spread  (Thumb_Spread +/-10)",
             [_ch("{side}_fingersAttributes_CTL", "Thumb_Spread", 10, -10)]),
            ("Full ROM (all attributes)",
             [_ch("{side}_fingersAttributes_CTL", "Curl", 10, -10),
              _ch("{side}_fingersAttributes_CTL", "Spread", 10, -10),
              _ch("{side}_fingersAttributes_CTL", "Cup", 10, -10),
              _ch("{side}_fingersAttributes_CTL", "Fan", 10, -10),
              _ch("{side}_fingersAttributes_CTL", "Thumb_Curl", 10, -10),
              _ch("{side}_fingersAttributes_CTL", "Thumb_Spread", 10, -10)]),
        ],
    },
    "Hip": {
        "settings": "{side}_legSettings_CTL",
        "poses": [
            ("Flexion / Extension — kick & splits  (rotateZ +120/-70)",
             [_ch("{side}_hipFk_CTL", "rotateZ", 120, -70)]),
            ("Abduction / Adduction — side split  (rotateY +90/-30)",
             [_ch("{side}_hipFk_CTL", "rotateY", 90, -30)]),
            ("Twist In / Out  (rotateX +/-45)",
             [_ch("{side}_hipFk_CTL", "rotateX", 45, -45)]),
            ("Full ROM (all axes)",
             [_ch("{side}_hipFk_CTL", "rotateZ", 120, -70),
              _ch("{side}_hipFk_CTL", "rotateY", 90, -30),
              _ch("{side}_hipFk_CTL", "rotateX", 45, -45)]),
        ],
    },
    "Knee": {
        "settings": "{side}_legSettings_CTL",
        "poses": [
            ("Bend  (rotateZ +/-140)",
             [_ch("{side}_kneeFk_CTL", "rotateZ", 140, -140)]),
            ("Tibial Twist  (rotateX +/-15)",
             [_ch("{side}_kneeFk_CTL", "rotateX", 15, -15)]),
            ("Full ROM (all axes)",
             [_ch("{side}_kneeFk_CTL", "rotateZ", 140, -140),
              _ch("{side}_kneeFk_CTL", "rotateX", 15, -15)]),
        ],
    },
    "Ankle / Foot": {
        "settings": "{side}_legSettings_CTL",
        "poses": [
            ("Dorsi / Plantar Flexion  (rotateZ +25/-50)",
             [_ch("{side}_ankleFk_CTL", "rotateZ", 25, -50)]),
            ("Inversion / Eversion  (rotateY +35/-25)",
             [_ch("{side}_ankleFk_CTL", "rotateY", 35, -25)]),
            ("Ball Roll  (rotateZ +40/-25)",
             [_ch("{side}_ballFk_CTL", "rotateZ", 40, -25)]),
            ("Full ROM (all axes)",
             [_ch("{side}_ankleFk_CTL", "rotateZ", 25, -50),
              _ch("{side}_ankleFk_CTL", "rotateY", 35, -25),
              _ch("{side}_ballFk_CTL", "rotateZ", 40, -25)]),
        ],
    },
}


# ─────────────────────────────────────────────────────────────────────────────
#  STATE  (para restaurar la escena con clear_test)
# ─────────────────────────────────────────────────────────────────────────────

_prev_settings = {}   # plug Ik_Fk -> valor previo al test
_prev_range = None    # (min, max, ast, aet) del playback antes del test


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _resolve(template, side):
    """Resuelve un template de control a nodos existentes en escena."""
    name = template.format(side=side)
    if "*" in name or "?" in name:
        return sorted(cmds.ls(name, type="transform") or [])
    return [name] if cmds.objExists(name) else []


def _settable(plug):
    try:
        return cmds.getAttr(plug, settable=True)
    except Exception:
        return False


def _default_value(ctl, attr):
    try:
        default = cmds.attributeQuery(attr, node=ctl, listDefault=True)
        return default[0] if default else 0.0
    except Exception:
        return 0.0


def _gather(channels, sides):
    """Convierte los canales de una pose en bloques de keys.

    Devuelve (blocks, missing): cada block es la lista de plugs que se
    keyean juntos (L y R a la vez = calistenia simétrica); los bloques se
    animan en secuencia para que las keys nunca se solapen entre ejes.
    """
    blocks, missing = [], []
    for ch in channels:
        entries = []
        ch_sides = sides if "{side}" in ch["ctl"] else ("",)
        for side in ch_sides:
            ctls = _resolve(ch["ctl"], side)
            if not ctls:
                missing.append(ch["ctl"].format(side=side))
                continue
            div = float(len(ctls)) if ch["distribute"] else 1.0
            for ctl in ctls:
                plug = f"{ctl}.{ch['attr']}"
                if not _settable(plug):
                    missing.append(plug)
                    continue
                entries.append((plug, ch["max"] / div, ch["min"] / div,
                                _default_value(ctl, ch["attr"])))
        if entries:
            blocks.append(entries)
    return blocks, missing


def _key_axis_block(entries, frame, spacing):
    """Keyea un eje aislado: neutral -> max -> neutral -> min -> neutral."""
    for plug, v_max, v_min, default in entries:
        cmds.setKeyframe(plug, time=frame, value=default)
        cmds.setKeyframe(plug, time=frame + spacing, value=v_max)
        cmds.setKeyframe(plug, time=frame + spacing * 2, value=default)
        cmds.setKeyframe(plug, time=frame + spacing * 3, value=v_min)
        cmds.setKeyframe(plug, time=frame + spacing * 4, value=default)
    return frame + spacing * 4


def _animate_blocks(blocks, start_frame, spacing):
    frame = start_frame
    for entries in blocks:
        frame = _key_axis_block(entries, frame, spacing)
    return frame


def _ensure_fk(zone_data, sides):
    """Pone el switch Ik_Fk en FK (1) guardando el valor previo."""
    template = zone_data.get("settings")
    if not template:
        return
    for side in sides:
        ctl = template.format(side=side)
        if not cmds.objExists(ctl):
            continue
        if not cmds.attributeQuery("Ik_Fk", node=ctl, exists=True):
            continue
        plug = f"{ctl}.Ik_Fk"
        if plug not in _prev_settings:
            _prev_settings[plug] = cmds.getAttr(plug)
        try:
            cmds.setAttr(plug, 1)
        except Exception:
            pass


def _frame_playback(start, end, play):
    """Encuadra el timeline al test (guardando el rango previo) y reproduce."""
    global _prev_range
    if _prev_range is None:
        _prev_range = (cmds.playbackOptions(q=True, min=True),
                       cmds.playbackOptions(q=True, max=True),
                       cmds.playbackOptions(q=True, ast=True),
                       cmds.playbackOptions(q=True, aet=True))
    cmds.playbackOptions(min=start, max=end, ast=start, aet=end)
    cmds.currentTime(start)
    if play:
        cmds.play(forward=True)


# ─────────────────────────────────────────────────────────────────────────────
#  API
# ─────────────────────────────────────────────────────────────────────────────

def pose_labels(zone):
    """Etiquetas de las poses disponibles para una zona (para la UI)."""
    return [label for label, _ in POSE_LIBRARY[zone]["poses"]]


def animate_pose(zone, pose_index, sides=("L", "R"), spacing=DEFAULT_SPACING,
                 start_frame=DEFAULT_START, set_fk=True, play=True):
    """Anima la pose ROM `pose_index` de `zone` sobre los controladores.

    Returns:
        int | None: último frame keyeado, o None si no hay controles.
    """
    zone_data = POSE_LIBRARY[zone]
    label, channels = zone_data["poses"][pose_index]
    blocks, missing = _gather(channels, sides)
    if not blocks:
        cmds.warning(f"[Pose Tester] No controls found for '{zone} - {label}'."
                     " Build the rig first.")
        return None

    cmds.undoInfo(openChunk=True, chunkName="rigPoseTester")
    try:
        if set_fk:
            _ensure_fk(zone_data, sides)
        end = _animate_blocks(blocks, start_frame, spacing)
    finally:
        cmds.undoInfo(closeChunk=True)

    _frame_playback(start_frame, end, play)
    if missing:
        cmds.warning("[Pose Tester] Skipped missing/locked: "
                     + ", ".join(sorted(set(missing))))
    return end


def animate_full_body(sides=("L", "R"), spacing=DEFAULT_SPACING,
                      start_frame=DEFAULT_START, set_fk=True, play=True):
    """ROM de cuerpo completo: encadena el 'Full ROM' de todas las zonas
    (top-down, sin solapar keys), la calistenia completa estándar.

    Returns:
        int | None: último frame keyeado, o None si no hay controles.
    """
    frame = start_frame
    animated, all_missing = [], []

    cmds.undoInfo(openChunk=True, chunkName="rigPoseTesterFullBody")
    try:
        for zone in ZONES:
            zone_data = POSE_LIBRARY[zone]
            _, channels = zone_data["poses"][-1]  # la última pose es Full ROM
            blocks, missing = _gather(channels, sides)
            all_missing.extend(missing)
            if not blocks:
                continue
            if set_fk:
                _ensure_fk(zone_data, sides)
            frame = _animate_blocks(blocks, frame, spacing)
            animated.append(zone)
    finally:
        cmds.undoInfo(closeChunk=True)

    if not animated:
        cmds.warning("[Pose Tester] No controls found. Build the rig first.")
        return None

    _frame_playback(start_frame, frame, play)
    if all_missing:
        cmds.warning("[Pose Tester] Skipped missing/locked: "
                     + ", ".join(sorted(set(all_missing))))
    return frame


def clear_test(reset_range=True):
    """Borra TODA la animación de test y devuelve el rig a la pose neutral.

    Recorre la librería completa (no depende de qué se haya lanzado en esta
    sesión), corta las keys de cada canal de test, restaura los valores por
    defecto, los switches Ik_Fk previos y el rango de playback original.

    Returns:
        int: número de canales limpiados.
    """
    global _prev_range
    cmds.play(state=False)

    visited, cleared = set(), 0
    cmds.undoInfo(openChunk=True, chunkName="rigPoseTesterClear")
    try:
        for zone_data in POSE_LIBRARY.values():
            for _, channels in zone_data["poses"]:
                for ch in channels:
                    ch_sides = ("L", "R") if "{side}" in ch["ctl"] else ("",)
                    for side in ch_sides:
                        for ctl in _resolve(ch["ctl"], side):
                            plug = f"{ctl}.{ch['attr']}"
                            if plug in visited:
                                continue
                            visited.add(plug)
                            if cmds.keyframe(plug, q=True, keyframeCount=True):
                                cmds.cutKey(plug)
                                cleared += 1
                            if _settable(plug):
                                try:
                                    cmds.setAttr(
                                        plug, _default_value(ctl, ch["attr"]))
                                except Exception:
                                    pass
        for plug, value in _prev_settings.items():
            if cmds.objExists(plug.split(".")[0]) and _settable(plug):
                try:
                    cmds.setAttr(plug, value)
                except Exception:
                    pass
        _prev_settings.clear()
    finally:
        cmds.undoInfo(closeChunk=True)

    if reset_range and _prev_range is not None:
        r_min, r_max, r_ast, r_aet = _prev_range
        cmds.playbackOptions(min=r_min, max=r_max, ast=r_ast, aet=r_aet)
        cmds.currentTime(r_min)
        _prev_range = None

    return cleared
