"""
DWPicker biped body picker generator.

Generates a standard body picker for all biped characters built with autorig_tools.
Facial controls are excluded. The layout is fixed — only controller names change.

Usage (in Maya, after rig build):
    from utils import picker
    picker.generate_and_load()

    # Or save to file only:
    picker.generate_and_load(load=False)
"""
import json
import uuid
import os
import maya.cmds as cmds
import maya.api.OpenMaya as om


# ─────────────────────────────────────────────────────────────────
#  Layout constants
# ─────────────────────────────────────────────────────────────────

CANVAS_W = 480
CANVAS_H = 680

# Column left-edge x positions
XL = 10    # L_ controls  (character's left = viewer's right)
XC = 165   # C_ controls  (center)
XR = 325   # R_ controls  (character's right = viewer's left)

CW  = 150  # Column width
CWC = 150  # Center column width
CH  = 22   # Standard cell height
GAP = 4    # Gap between rows in a section
SGAP = 10  # Gap between sections

# Button colors — side / type
COL_GLOBAL     = "#1A5C1A"   # green  — character / masterwalk
COL_CENTER     = "#1B3D70"   # blue   — spine, head, neck, body
COL_CTR_SOFT   = "#2A5494"   # lighter blue — localHip, localChest, throat
COL_TAN        = "#133050"   # dark blue — tangent (secondary) spine ctls
COL_L_IK       = "#0E3D55"   # dark teal — L IK
COL_L_FK       = "#1A5E80"   # medium teal — L FK
COL_L_CLAV     = "#163D55"   # dark teal variant — L clavicle
COL_R_IK       = "#550E0E"   # dark red — R IK
COL_R_FK       = "#803020"   # medium red — R FK
COL_R_CLAV     = "#551616"   # dark red variant — R clavicle
COL_SETTINGS   = "#5C4400"   # gold — IK/FK settings / switches


# ─────────────────────────────────────────────────────────────────
#  Shape builders
# ─────────────────────────────────────────────────────────────────

def _short_label(name):
    """Derive a short display label from a controller name."""
    label = name.replace("_CTL", "")
    for prefix in ("C_", "L_", "R_"):
        if label.startswith(prefix):
            label = label[len(prefix):]
            break
    return label


def _btn(name, x, y, w, h, label=None, color=None, size=9, panel=0):
    """Return a DWPicker interactive button shape dict."""
    if label is None:
        label = _short_label(name)
    if color is None:
        color = "#444444"
    return {
        "id": str(uuid.uuid4()),
        "panel": panel,
        "background": False,
        "visibility_layer": None,
        "children": [],
        "shape.ignored_by_focus": False,
        "shape": "rounded_rect",
        "shape.space": "world",
        "shape.anchor": "top_left",
        "shape.path": [],
        "shape.left": float(x),
        "shape.top": float(y),
        "shape.width": float(w),
        "shape.height": float(h),
        "shape.cornersx": 4,
        "shape.cornersy": 4,
        "border": True,
        "borderwidth.normal": 1.0,
        "borderwidth.hovered": 1.5,
        "borderwidth.clicked": 2,
        "bordercolor.normal": "#111111",
        "bordercolor.hovered": "#888888",
        "bordercolor.clicked": "#FFFFFF",
        "bordercolor.transparency": 0,
        "bgcolor.normal": color,
        "bgcolor.hovered": color,
        "bgcolor.clicked": "#DDDDDD",
        "bgcolor.transparency": 0,
        "text.content": label,
        "text.size": size,
        "text.bold": False,
        "text.italic": False,
        "text.color": "#FFFFFF",
        "text.valign": "center",
        "text.halign": "center",
        "action.targets": [name],
        "action.commands": [],
        "action.menu_commands": [],
        "image.path": "",
        "image.fit": True,
        "image.ratio": True,
        "image.height": 32,
        "image.width": 32,
    }


def _label_bg(text, x, y, w, h, color="#1A1A1A", text_color="#777777", panel=0):
    """Return a non-interactive background/section-label shape dict."""
    return {
        "id": str(uuid.uuid4()),
        "panel": panel,
        "background": True,
        "visibility_layer": None,
        "children": [],
        "shape.ignored_by_focus": True,
        "shape": "square",
        "shape.space": "world",
        "shape.anchor": "top_left",
        "shape.path": [],
        "shape.left": float(x),
        "shape.top": float(y),
        "shape.width": float(w),
        "shape.height": float(h),
        "shape.cornersx": 0,
        "shape.cornersy": 0,
        "border": False,
        "borderwidth.normal": 0,
        "borderwidth.hovered": 0,
        "borderwidth.clicked": 0,
        "bordercolor.normal": "#000000",
        "bordercolor.hovered": "#000000",
        "bordercolor.clicked": "#000000",
        "bordercolor.transparency": 0,
        "bgcolor.normal": color,
        "bgcolor.hovered": color,
        "bgcolor.clicked": color,
        "bgcolor.transparency": 0,
        "text.content": text,
        "text.size": 8,
        "text.bold": True,
        "text.italic": False,
        "text.color": text_color,
        "text.valign": "center",
        "text.halign": "center",
        "action.targets": [],
        "action.commands": [],
        "action.menu_commands": [],
        "image.path": "",
        "image.fit": True,
        "image.ratio": True,
        "image.height": 32,
        "image.width": 32,
    }


# ─────────────────────────────────────────────────────────────────
#  Body picker layout
# ─────────────────────────────────────────────────────────────────

def _build_body_shapes():
    """
    Returns all shapes for the BODY panel (panel index 0).
    Layout: 3 columns (L_ | C_ | R_), top-to-bottom.
    L_ = character's left side = viewer's RIGHT column.
    R_ = character's right side = viewer's LEFT column.
    """
    P = 0  # panel index
    shapes = []

    def btn(name, x, y, w=CW, h=CH, **kw):
        kw.setdefault("panel", P)
        shapes.append(_btn(name, x, y, w, h, **kw))

    def bg(text, x, y, w, h, **kw):
        kw.setdefault("panel", P)
        shapes.append(_label_bg(text, x, y, w, h, **kw))

    # ── GLOBAL ──────────────────────────────── y=5
    bg("", 0, 0, CANVAS_W, 62, color="#111111")
    btn("C_character_CTL",  130, 5,  220, 26, color=COL_GLOBAL, size=10)
    btn("C_settings_CTL",   365, 5,  105, 26, color="#333355",  label="settings")
    btn("C_masterwalk_CTL", 145, 36, 190, 22, color=COL_GLOBAL, label="masterwalk")

    # ── HEAD / NECK ─────────────────────────── y=72
    y = 72
    btn("C_head_CTL",   180, y,      CWC, 26, color=COL_CENTER, label="head")
    y += 26 + GAP
    btn("C_neck_CTL",   190, y, 130, CH,  color=COL_CENTER,   label="neck")
    y += CH + GAP
    btn("C_throat_CTL", 205, y, 100, 18,  color=COL_CTR_SOFT, label="throat", size=8)

    # ── CLAVICLE ────────────────────────────── y=158
    y = 158
    bg("", 0, y - 2, CANVAS_W, CH + 4, color="#161616")
    btn("L_clavicle_CTL", XL, y, CW, CH, color=COL_L_CLAV, label="clavicle")
    btn("C_localChest_CTL", XC, y, CWC, CH, color=COL_CTR_SOFT, label="localChest")
    btn("R_clavicle_CTL", XR, y, CW, CH, color=COL_R_CLAV, label="clavicle")

    # ── ARM FK / SPINE ──────────────────────── y=185
    y = 185
    # Arm FK (L and R) run alongside the spine
    btn("L_shoulderFk_CTL", XL, y,      CW, CH, color=COL_L_FK, label="shoulderFk")
    btn("C_spine07_CTL",    XC, y,      CWC,CH, color=COL_CENTER, label="spine top")
    btn("R_shoulderFk_CTL", XR, y,      CW, CH, color=COL_R_FK, label="shoulderFk")

    y += CH + GAP
    btn("L_elbowFk_CTL",    XL, y,      CW, CH, color=COL_L_FK, label="elbowFk")
    btn("C_spine06Tan_CTL", XC, y,      CWC,18, color=COL_TAN,  label="spine06Tan", size=8)
    btn("R_elbowFk_CTL",    XR, y,      CW, CH, color=COL_R_FK, label="elbowFk")

    y += CH + GAP
    btn("L_wristFk_CTL",    XL, y,      CW, CH, color=COL_L_FK, label="wristFk")
    btn("C_spine03_CTL",    XC, y,      CWC,CH, color=COL_CENTER,label="spine mid")
    btn("R_wristFk_CTL",    XR, y,      CW, CH, color=COL_R_FK, label="wristFk")

    y += CH + GAP
    btn("L_armSettings_CTL",XL, y,      CW, CH, color=COL_SETTINGS, label="IK / FK")
    btn("C_spine01Tan_CTL", XC, y,      CWC,18, color=COL_TAN,  label="spine01Tan", size=8)
    btn("R_armSettings_CTL",XR, y,      CW, CH, color=COL_SETTINGS, label="IK / FK")

    y += CH + GAP
    btn("L_armIkWrist_CTL", XL, y,      CW, CH, color=COL_L_IK, label="armIk wrist")
    btn("C_spine00_CTL",    XC, y,      CWC,CH, color=COL_CENTER,label="spine bot")
    btn("R_armIkWrist_CTL", XR, y,      CW, CH, color=COL_R_IK, label="armIk wrist")

    y += CH + GAP
    btn("L_armIkRoot_CTL",  XL, y,      CW, CH, color=COL_L_IK, label="armIk root")
    btn("C_body_CTL",       XC, y,      CWC,CH, color=COL_CENTER,label="body")
    btn("R_armIkRoot_CTL",  XR, y,      CW, CH, color=COL_R_IK, label="armIk root")

    y += CH + GAP
    btn("L_armPv_CTL",      XL, y,      CW, CH, color=COL_L_IK, label="armPv")
    btn("C_localHip_CTL",   XC, y,      CWC,CH, color=COL_CTR_SOFT, label="localHip")
    btn("R_armPv_CTL",      XR, y,      CW, CH, color=COL_R_IK, label="armPv")

    # ── FINGER ATTRIBUTES (inline, small) ───
    y += CH + GAP
    btn("L_fingersAttributes_CTL", XL, y, CW, 18, color=COL_SETTINGS, label="fingers attr", size=8)
    btn("R_fingersAttributes_CTL", XR, y, CW, 18, color=COL_SETTINGS, label="fingers attr", size=8)

    # ── LEGS SEPARATOR ──────────────────────────
    y += 18 + SGAP
    bg("  LEGS", 0, y, CANVAS_W, 16, color="#111111", text_color="#555555")
    y += 16 + GAP

    # ── LEG SETTINGS ────────────────────────
    btn("L_legSettings_CTL", XL, y, CW, CH, color=COL_SETTINGS, label="IK / FK")
    btn("R_legSettings_CTL", XR, y, CW, CH, color=COL_SETTINGS, label="IK / FK")

    # ── LEG FK ──────────────────────────────
    y += CH + GAP
    btn("L_hipFk_CTL",   XL, y, CW, CH, color=COL_L_FK, label="hipFk")
    btn("R_hipFk_CTL",   XR, y, CW, CH, color=COL_R_FK, label="hipFk")

    y += CH + GAP
    btn("L_kneeFk_CTL",  XL, y, CW, CH, color=COL_L_FK, label="kneeFk")
    btn("R_kneeFk_CTL",  XR, y, CW, CH, color=COL_R_FK, label="kneeFk")

    y += CH + GAP
    btn("L_ankleFk_CTL", XL, y, CW, CH, color=COL_L_FK, label="ankleFk")
    btn("R_ankleFk_CTL", XR, y, CW, CH, color=COL_R_FK, label="ankleFk")

    y += CH + GAP
    btn("L_ballFk_CTL",  XL, y, CW, CH, color=COL_L_FK, label="ballFk")
    btn("R_ballFk_CTL",  XR, y, CW, CH, color=COL_R_FK, label="ballFk")

    # ── LEG IK ──────────────────────────────
    y += CH + SGAP
    btn("L_legRootIk_CTL", XL, y, CW, CH, color=COL_L_IK, label="legRootIk")
    btn("R_legRootIk_CTL", XR, y, CW, CH, color=COL_R_IK, label="legRootIk")

    y += CH + GAP
    btn("L_legPv_CTL",     XL, y, CW, CH, color=COL_L_IK, label="legPv")
    btn("R_legPv_CTL",     XR, y, CW, CH, color=COL_R_IK, label="legPv")

    y += CH + GAP
    btn("L_ankleIk_CTL",   XL, y, CW, CH, color=COL_L_IK, label="ankleIk")
    btn("R_ankleIk_CTL",   XR, y, CW, CH, color=COL_R_IK, label="ankleIk")

    # toe + ball on same row (split)
    y += CH + GAP
    btn("L_toeIk_CTL",  XL,         y, 96, CH, color=COL_L_IK, label="toeIk")
    btn("L_ballIk_CTL", XL + 100,   y, 50, CH, color=COL_L_IK, label="ball", size=8)
    btn("R_toeIk_CTL",  XR,         y, 96, CH, color=COL_R_IK, label="toeIk")
    btn("R_ballIk_CTL", XR + 100,   y, 50, CH, color=COL_R_IK, label="ball", size=8)

    y += CH + GAP
    btn("L_heel_CTL", XL, y, CW, CH, color=COL_L_IK, label="heel")
    btn("R_heel_CTL", XR, y, CW, CH, color=COL_R_IK, label="heel")

    return shapes


# ─────────────────────────────────────────────────────────────────
#  Face picker layout  (panel 1)
# ─────────────────────────────────────────────────────────────────
#
#  Layout mirrors the face viewed front-on:
#    R_ controls (char's right) → viewer's LEFT  (x ~ 5-200)
#    Center (C_)                → x ~ 160-300
#    L_ controls (char's left)  → viewer's RIGHT (x ~ 260-455)
#
#  Eyebrow secondary (In / InTan / Mid / OutTan / Out):
#    L side: In → Out  left-to-right  (inner near nose, outer far)
#    R side: Out → In  left-to-right  (mirrored)

_BROW_SEC_NAMES = ["Out", "OutTan", "Mid", "InTan", "In"]   # R order (left→right)
_BROW_SEC_L     = ["In", "InTan", "Mid", "OutTan", "Out"]   # L order

_BTN_BROW_W = 36   # secondary eyebrow button width
_BTN_BROW_G = 2    # gap between them


def _build_face_shapes():
    P = 1  # panel index
    shapes = []

    def btn(name, x, y, w, h, **kw):
        kw["panel"] = P
        shapes.append(_btn(name, x, y, w, h, **kw))

    def bg(text, x, y, w, h, **kw):
        kw["panel"] = P
        shapes.append(_label_bg(text, x, y, w, h, **kw))

    # column positions
    XFL  = 260   # L_ column start (viewer's right)
    XFR  = 5     # R_ column start (viewer's left)
    XFCL = 205   # narrow center left edge
    WFMAIN = 195 # main (eyebrow/eye) side width
    WFCTR  = 50  # center narrow button width

    # ── HEADER ──────────────────────────────── y=5
    bg("", 0, 0, 460, 30, color="#111111")
    btn("C_face_CTL", 120, 5, 220, 22, color=COL_CTR_SOFT, label="face")

    # ── EYEBROW MAIN ────────────────────────── y=40
    y = 40
    btn("R_eyebrowMain_CTL", XFR,  y, WFMAIN, CH, color=COL_R_FK,   label="eyebrowMain")
    btn("C_eyebrowMid_CTL",  XFCL, y, WFCTR,  CH, color=COL_CENTER, label="~")
    btn("L_eyebrowMain_CTL", XFL,  y, WFMAIN, CH, color=COL_L_FK,   label="eyebrowMain")

    # ── EYEBROW SECONDARY ───────────────────── y=68
    y = 68
    for i, name in enumerate(_BROW_SEC_NAMES):
        x = XFR + i * (_BTN_BROW_W + _BTN_BROW_G)
        btn(f"R_eyebrow{name}_CTL", x, y, _BTN_BROW_W, 18,
            color=COL_R_FK, label=name[:3], size=7)
    for i, name in enumerate(_BROW_SEC_L):
        x = XFL + i * (_BTN_BROW_W + _BTN_BROW_G)
        btn(f"L_eyebrow{name}_CTL", x, y, _BTN_BROW_W, 18,
            color=COL_L_FK, label=name[:3], size=7)

    # ── EYES ────────────────────────────────── y=96
    y = 96
    EW = 95  # eye button width
    btn("R_eye_CTL",      XFR,       y, EW, CH, color=COL_R_IK, label="eye")
    btn("R_eyeDirect_CTL",XFR+EW+4,  y, EW, CH, color=COL_R_FK, label="eyeDirect", size=8)
    btn("C_eyeMain_CTL",  XFCL,      y, WFCTR+10, CH, color=COL_CENTER, label="eyeMain", size=8)
    btn("L_eye_CTL",      XFL,       y, EW, CH, color=COL_L_IK, label="eye")
    btn("L_eyeDirect_CTL",XFL+EW+4,  y, EW, CH, color=COL_L_FK, label="eyeDirect", size=8)

    # ── CHEEKS ──────────────────────────────── y=128
    y = 128
    btn("R_cheek_CTL", XFR, y, WFMAIN, CH, color=COL_R_FK, label="cheek")
    btn("L_cheek_CTL", XFL, y, WFMAIN, CH, color=COL_L_FK, label="cheek")

    # ── LIPS / JAW ──────────────────────────── y=162
    y = 162
    WLC = 145   # lip corner width
    WUL = 120   # upper lip width
    XUL = (460 - WUL) // 2
    btn("R_lipCorner_CTL", XFR,  y, WLC, CH, color=COL_R_FK, label="lipCorner")
    btn("C_upperLip_CTL",  XUL,  y, WUL, CH, color=COL_CENTER, label="upperLip")
    btn("L_lipCorner_CTL", 460 - XFR - WLC, y, WLC, CH, color=COL_L_FK, label="lipCorner")

    y += CH + GAP
    WJ = 140
    XJ = (460 - WJ) // 2
    btn("C_upperJaw_CTL", XJ, y, WJ, CH, color=COL_CENTER, label="upperJaw")

    y += CH + GAP
    btn("C_jaw_CTL",       XJ, y, WJ, CH, color=COL_CENTER, label="jaw")

    y += CH + GAP
    btn("C_lowerLip_CTL",  XJ, y, WJ, CH, color=COL_CENTER, label="lowerLip")

    return shapes


# ─────────────────────────────────────────────────────────────────
#  Picker document assembly
# ─────────────────────────────────────────────────────────────────

def build_picker_data(char_name="character"):
    """
    Assemble and return a DWPicker document dict (general + shapes).
    char_name is used only for the picker display name.
    """
    body_shapes = _build_body_shapes()
    face_shapes = _build_face_shapes()

    all_shapes = body_shapes + face_shapes

    general = {
        "name": char_name,
        "version": [1, 0, 4],
        "panels.as_sub_tab": False,
        "panels.orientation": "vertical",
        "panels.zoom_locked": [False, False],
        "panels.colors": [None, None],
        "panels.names": ["Body", "Face"],
        "menu_commands": [],
        "hidden_layers": [],
        "panels": [[1.0, [1.0]], [1.0, [1.0]]],
    }

    return {"general": general, "shapes": all_shapes}


# ─────────────────────────────────────────────────────────────────
#  DWPicker integration
# ─────────────────────────────────────────────────────────────────

def _get_char_name():
    """Try to read character name from scene data; fallback to scene name."""
    try:
        from utils import data_manager
        name = data_manager.DataExportBiped().get_data("basic_structure", "character_name")
        if name:
            return name
    except Exception:
        pass
    scene = cmds.file(q=True, sceneName=True, shortName=True)
    return os.path.splitext(scene)[0] if scene else "character"


def _picker_output_path(char_name):
    """Return the .json output path next to the character's assets folder."""
    try:
        from utils import rig_manager
        assets_dir = rig_manager.get_assets_path()
        if assets_dir:
            char_dir = os.path.join(assets_dir, char_name)
            picker_dir = os.path.join(char_dir, "picker")
            os.makedirs(picker_dir, exist_ok=True)
            return os.path.join(picker_dir, f"{char_name}_picker.json")
    except Exception:
        pass
    # Fallback: temp directory
    import tempfile
    return os.path.join(tempfile.gettempdir(), f"{char_name}_picker.json")


def _load_via_dwpicker(picker_data):
    """
    Embed picker data in the Maya scene using DWPicker's scenedata API.
    Returns True on success, False if DWPicker is not installed.
    """
    try:
        from dwpicker import scenedata
        existing = scenedata.load_local_picker_data() or []
        # Replace existing picker with same name, or append
        name = picker_data["general"]["name"]
        existing = [p for p in existing if p.get("general", {}).get("name") != name]
        existing.append(picker_data)
        scenedata.store_local_picker_data(existing)
        # Refresh the DWPicker UI if open
        try:
            from dwpicker import main as dwmain
            win = dwmain.get_picker_window()
            if win:
                win.reset()
        except Exception:
            pass
        return True
    except ImportError:
        return False


def generate_and_load(load=True):
    """
    Generate the biped body picker and optionally load it into DWPicker.

    Parameters
    ----------
    load : bool
        If True (default), attempts to embed the picker in the Maya scene
        via DWPicker's scenedata API. Falls back to saving a JSON file.
        If False, only writes the JSON file.

    Returns
    -------
    str  — path to the saved JSON file
    """
    char_name   = _get_char_name()
    picker_data = build_picker_data(char_name)
    output_path = _picker_output_path(char_name)

    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(picker_data, fh, indent=2)

    om.MGlobal.displayInfo(f"Picker JSON saved → {output_path}")

    if load:
        ok = _load_via_dwpicker(picker_data)
        if ok:
            om.MGlobal.displayInfo(
                f"[Picker] '{char_name}' picker loaded into DWPicker."
            )
        else:
            om.MGlobal.displayWarning(
                "[Picker] DWPicker not found. "
                f"Open DWPicker and import:\n  {output_path}"
            )

    return output_path
