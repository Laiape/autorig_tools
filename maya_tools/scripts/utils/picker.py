"""
DWPicker generator (body + face), layout ANATÓMICO sobre silueta.

Genera un picker de DWPicker con dos paneles ("Body" y "Face") para los
personajes construidos con autorig_tools. Los controles se colocan
anatómicamente sobre una silueta de cuerpo / cara (vista frontal espejada:
R_ = derecha del personaje = izquierda del visor en rojo; L_ = azul/teal;
C_ = centro). El layout es fijo — solo cambian los nombres de los controles.

Usage (en Maya, tras construir el rig):
    from utils import picker
    picker.generate_and_load()

    # Solo guardar el JSON:
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

CANVAS_W = 700
CANVAS_H = 800

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


def _label_bg(text, x, y, w, h, color="#1A1A1A", text_color="#777777", panel=0,
              shape_type="square", corners=0):
    """Return a non-interactive background/section-label shape dict."""
    return {
        "id": str(uuid.uuid4()),
        "panel": panel,
        "background": True,
        "visibility_layer": None,
        "children": [],
        "shape.ignored_by_focus": True,
        "shape": shape_type,
        "shape.space": "world",
        "shape.anchor": "top_left",
        "shape.path": [],
        "shape.left": float(x),
        "shape.top": float(y),
        "shape.width": float(w),
        "shape.height": float(h),
        "shape.cornersx": corners,
        "shape.cornersy": corners,
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
    Layout ANATÓMICO sobre una silueta de cuerpo (vista frontal espejada):
      R_ (lado derecho del personaje) -> IZQUIERDA del visor (rojo)
      L_ (lado izquierdo)             -> DERECHA del visor (azul/teal)
      C_                              -> centro (azul/oro)
    """
    P = 0
    shapes = []
    CX = 350  # línea central
    SIL = "#2D2D2D"  # color de la silueta

    def btn(name, x, y, w, h, **kw):
        kw.setdefault("panel", P)
        shapes.append(_btn(name, x, y, w, h, **kw))

    def bg(text, x, y, w, h, **kw):
        kw.setdefault("panel", P)
        shapes.append(_label_bg(text, x, y, w, h, **kw))

    def sil(x, y, w, h, c=10):
        bg("", x, y, w, h, color=SIL, shape_type="rounded_rect", corners=c)

    # ── SILUETA (fondo) ────────────────────────────────────────────
    bg("", 0, 0, CANVAS_W, CANVAS_H, color="#191919")
    sil(CX - 58, 40, 116, 116, 58)        # cabeza
    sil(CX - 24, 150, 48, 30, 6)          # cuello
    sil(CX - 152, 176, 304, 58, 24)       # hombros
    sil(CX - 118, 224, 236, 222, 30)      # torso
    sil(CX - 120, 432, 240, 82, 28)       # pelvis
    sil(CX - 214, 192, 70, 150, 26)       # R brazo sup (izq visor)
    sil(CX - 236, 330, 64, 150, 22)       # R antebrazo
    sil(CX - 258, 478, 82, 94, 16)        # R mano
    sil(CX + 144, 192, 70, 150, 26)       # L brazo sup (der visor)
    sil(CX + 172, 330, 64, 150, 22)       # L antebrazo
    sil(CX + 176, 478, 82, 94, 16)        # L mano
    sil(CX - 110, 498, 88, 160, 26)       # R muslo
    sil(CX - 102, 652, 76, 122, 20)       # R gemelo
    sil(CX - 114, 766, 96, 30, 10)        # R pie
    sil(CX + 22, 498, 88, 160, 26)        # L muslo
    sil(CX + 26, 652, 76, 122, 20)        # L gemelo
    sil(CX + 18, 766, 96, 30, 10)         # L pie

    # ── GLOBAL (fila superior) ─────────────────────────────────────
    btn("C_character_CTL",  CX - 172, 6,  118, 22, color=COL_GLOBAL,  label="character", size=8)
    btn("C_masterwalk_CTL", CX - 48,  6,  96,  22, color=COL_GLOBAL,  label="master",    size=8)
    btn("C_settings_CTL",   CX + 54,  6,  118, 22, color="#333355",   label="settings",  size=8)

    # ── CABEZA / CUELLO ────────────────────────────────────────────
    btn("C_head_CTL",   CX - 42, 66,  84, 28, color=COL_CENTER,   label="head")
    btn("C_neck_CTL",   CX - 34, 126, 68, 20, color=COL_CENTER,   label="neck",   size=8)
    btn("C_throat_CTL", CX - 28, 150, 56, 16, color=COL_CTR_SOFT, label="throat", size=7)

    # ── CLAVÍCULAS (hombros) ───────────────────────────────────────
    btn("R_clavicle_CTL", CX - 150, 182, 72, 20, color=COL_R_CLAV, label="clav", size=8)
    btn("L_clavicle_CTL", CX + 78,  182, 72, 20, color=COL_L_CLAV, label="clav", size=8)

    # ── COLUMNA (spine, torso) ─────────────────────────────────────
    sx, sw = CX - 33, 66
    btn("C_localChest_CTL", sx + 2, 206, 62, 16, color=COL_CTR_SOFT, label="locChest", size=7)
    spy = 226
    for i in (7, 6, 5, 4, 3, 2, 1, 0):
        btn(f"C_spine0{i}_CTL", sx, spy, sw, 22, color=COL_CENTER, label=f"spine{i}", size=7)
        spy += 25
    btn("C_body_CTL",     CX - 42, 432, 84, 22, color=COL_CENTER,   label="body")
    btn("C_localHip_CTL", CX - 34, 458, 68, 18, color=COL_CTR_SOFT, label="locHip", size=7)

    # ── BRAZOS (FK por el brazo, IK junto a la mano) ───────────────
    for s, sgn, c_fk, c_ik in (("R", -1, COL_R_FK, COL_R_IK), ("L", 1, COL_L_FK, COL_L_IK)):
        ax = CX + (sgn * 210 if sgn < 0 else 144)   # x base del brazo FK
        ix = CX + (sgn * 300 if sgn < 0 else 224)   # x columna IK (fuera)
        ox = 0 if sgn < 0 else 0
        # FK chain
        btn(f"{s}_shoulderFk_CTL", ax,            200, 66, 22, color=c_fk, label="shldFk", size=7)
        btn(f"{s}_elbowFk_CTL",    ax + sgn * 16,  260, 66, 22, color=c_fk, label="elbFk",  size=7)
        btn(f"{s}_wristFk_CTL",    ax + sgn * 28,  340, 66, 22, color=c_fk, label="wrstFk", size=7)
        btn(f"{s}_armSettings_CTL",ax + sgn * 28,  366, 66, 16, color=COL_SETTINGS, label="IK/FK", size=7)
        # IK (columna fuera del brazo)
        btn(f"{s}_armPv_CTL",      ix, 300, 60, 20, color=c_ik, label="armPv",  size=7)
        btn(f"{s}_armIkWrist_CTL", ix, 484, 72, 22, color=c_ik, label="ikWrist",size=7)
        btn(f"{s}_armIkRoot_CTL",  ix, 508, 72, 18, color=c_ik, label="ikRoot", size=7)
        # dedos (en la mano)
        hx = CX + (sgn * 254 if sgn < 0 else 178)
        btn(f"{s}_fingersAttributes_CTL", hx, 542, 80, 18, color=COL_SETTINGS, label="fingers", size=7)

    # ── PIERNAS (FK por la pierna, IK junto al pie) ────────────────
    for s, c_fk, c_ik, lx, ix, fx in (
        ("R", COL_R_FK, COL_R_IK, CX - 102, CX - 178, CX - 112),
        ("L", COL_L_FK, COL_L_IK, CX + 30,  CX + 120, CX + 18),
    ):
        btn(f"{s}_legSettings_CTL", lx, 486, 74, 16, color=COL_SETTINGS, label="IK/FK", size=7)
        btn(f"{s}_hipFk_CTL",   lx, 510, 74, 22, color=c_fk, label="hipFk",  size=7)
        btn(f"{s}_kneeFk_CTL",  lx + (4 if s == "R" else -4), 600, 70, 22, color=c_fk, label="kneeFk", size=7)
        btn(f"{s}_ankleFk_CTL", lx + (4 if s == "R" else -4), 662, 70, 22, color=c_fk, label="anklFk", size=7)
        btn(f"{s}_ballFk_CTL",  fx + 24, 724, 64, 16, color=c_fk, label="ballFk", size=7)
        # IK (columna fuera de la pierna)
        btn(f"{s}_legRootIk_CTL", ix, 520, 58, 20, color=c_ik, label="rootIk", size=7)
        btn(f"{s}_legPv_CTL",     ix, 600, 58, 20, color=c_ik, label="legPv", size=7)
        btn(f"{s}_ankleIk_CTL",   ix, 690, 58, 20, color=c_ik, label="anklIk", size=7)
        btn(f"{s}_heel_CTL",      ix, 714, 58, 18, color=c_ik, label="heel",  size=7)
        # toe + ball en el pie
        btn(f"{s}_toeIk_CTL",  fx, 768, 56, 18, color=c_ik, label="toe", size=7)
        btn(f"{s}_ballIk_CTL", fx + 60, 768, 34, 18, color=c_ik, label="bl", size=6)

    return shapes


# ─────────────────────────────────────────────────────────────────
#  Face picker layout  (panel 1)
# ─────────────────────────────────────────────────────────────────
#
#  Layout mirrors the face viewed front-on:
#    R_ controls (char's right) → viewer's LEFT  (x ~ 5)
#    Center (C_)                → centered
#    L_ controls (char's left)  → viewer's RIGHT (x ~ 270+)
#
#  Eyelid controller names (from eyelid_module curve_cvs_into_guides):
#    {S}_eyelidIn, eyelidInUp, eyelidUp, eyelidOutUp  (upper corners+upper)
#    {S}_eyelidInDown, eyelidDown, eyelidOutDown       (lower)
#    {S}_eyelidOut                                     (outer corner, shared)
#
#  Secondary lips naming (jaw_module_nurbs, 8 CVs, mid_point=3):
#    R_upperLip00-02, C_upperLip03, L_upperLip04-07  (same for lower)

_BROW_SEC_R = ["Out", "OutTan", "Mid", "InTan", "In"]   # R: outer→inner (left→right)
_BROW_SEC_L = ["In", "InTan", "Mid", "OutTan", "Out"]   # L: inner→outer (left→right)

_ELD_BTN_W  = 35   # eyelid button width
_ELD_BTN_G  = 2    # eyelid button gap

# Secondary lips: R=indices 00-02, C=03, L=04-07
_LIP_LABELS  = ["00","01","02","03","04","05","06","07"]
_LIP_SIDES   = ["R","R","R","C","L","L","L","L"]


def _build_face_shapes():
    P = 1
    shapes = []

    def btn(name, x, y, w, h, **kw):
        kw["panel"] = P
        shapes.append(_btn(name, x, y, w, h, **kw))

    def bg(text, x, y, w, h, **kw):
        kw["panel"] = P
        shapes.append(_label_bg(text, x, y, w, h, **kw))

    def sep(label, y, color="#111111", text_color="#555555"):
        bg(f"  {label}", 0, y, CW_FACE, 13, color=color, text_color=text_color)

    CX = 260            # línea central de la cara
    SIL = "#2D2D2D"

    # ── SILUETA: óvalo de la cara + orejas ──────────────────────
    bg("", 0, 0, 520, 600, color="#161616")
    bg("", CX - 155, 28, 310, 500, color="#221E1B", shape_type="rounded_rect", corners=135)
    bg("", CX - 188, 210, 36, 96, color=SIL, shape_type="rounded_rect", corners=14)   # oreja R (izq)
    bg("", CX + 152, 210, 36, 96, color=SIL, shape_type="rounded_rect", corners=14)   # oreja L (der)

    btn("C_face_CTL", CX - 62, 8, 124, 22, color=COL_CTR_SOFT, label="face", size=9)
    for i in range(3):
        btn(f"R_ear0{i}_CTL", CX - 185, 214 + i*30, 32, 26, color=COL_R_FK, label=f"e{i}", size=6)
        btn(f"L_ear0{i}_CTL", CX + 153, 214 + i*30, 32, 26, color=COL_L_FK, label=f"e{i}", size=6)

    # ── CEJAS (encima de los ojos) ──────────────────────────────
    by = 56
    btn("R_eyebrowMain_CTL", CX - 184, by, 112, 18, color=COL_R_FK,   label="browMain", size=6)
    btn("C_eyebrowMid_CTL",  CX - 30,  by, 60,  18, color=COL_CENTER, label="mid",      size=6)
    btn("L_eyebrowMain_CTL", CX + 72,  by, 112, 18, color=COL_L_FK,   label="browMain", size=6)
    for i, n in enumerate(_BROW_SEC_R):
        btn(f"R_eyebrow{n}_CTL", CX - 184 + i*23, by + 20, 21, 15, color=COL_R_FK, label=n[:2], size=6)
    for i, n in enumerate(_BROW_SEC_L):
        btn(f"L_eyebrow{n}_CTL", CX + 72 + i*23,  by + 20, 21, 15, color=COL_L_FK, label=n[:2], size=6)

    # ── OJOS (clúster por ojo: párpado sup / ojo / párpado inf) ──
    ey = 104
    bg("", CX - 188, ey - 4, 128, 84, color="#13100E", shape_type="rounded_rect", corners=10)
    bg("", CX + 60,  ey - 4, 128, 84, color="#13100E", shape_type="rounded_rect", corners=10)
    ELD_R    = ["Out", "OutUp",   "Up",   "InUp",   "In"]
    ELD_L    = ["In",  "InUp",    "Up",   "OutUp",  "Out"]
    ELD_R_LO = ["Out", "OutDown", "Down", "InDown", "In"]
    ELD_L_LO = ["In",  "InDown",  "Down", "OutDown","Out"]
    ew = 25
    for i, n in enumerate(ELD_R):
        btn(f"R_eyelid{n}_CTL", CX - 186 + i*ew, ey, ew - 3, 15, color=COL_R_FK, label=n[:3], size=6)
    for i, n in enumerate(ELD_L):
        btn(f"L_eyelid{n}_CTL", CX + 62 + i*ew,  ey, ew - 3, 15, color=COL_L_FK, label=n[:3], size=6)
    btn("R_eye_CTL",       CX - 186, ey + 17, 60, 22, color=COL_R_IK,  label="eye",    size=7)
    btn("R_eyeDirect_CTL", CX - 124, ey + 17, 60, 22, color=COL_R_FK,  label="direct", size=6)
    btn("C_eyeMain_CTL",   CX - 28,  ey + 17, 56, 22, color=COL_CENTER,label="eyeMain",size=6)
    btn("L_eye_CTL",       CX + 126, ey + 17, 60, 22, color=COL_L_IK,  label="eye",    size=7)
    btn("L_eyeDirect_CTL", CX + 64,  ey + 17, 60, 22, color=COL_L_FK,  label="direct", size=6)
    for i, n in enumerate(ELD_R_LO):
        btn(f"R_eyelid{n}_CTL", CX - 186 + i*ew, ey + 41, ew - 3, 15, color=COL_R_FK, label=n[:3], size=6)
    for i, n in enumerate(ELD_L_LO):
        btn(f"L_eyelid{n}_CTL", CX + 62 + i*ew,  ey + 41, ew - 3, 15, color=COL_L_FK, label=n[:3], size=6)

    # ── MEJILLAS (laterales, bajo los ojos) ─────────────────────
    cy = 198
    btn("R_cheek_CTL", CX - 184, cy, 96, 18, color=COL_R_FK, label="cheek", size=6)
    btn("L_cheek_CTL", CX + 88,  cy, 96, 18, color=COL_L_FK, label="cheek", size=6)
    for i, (sfx, lbl) in enumerate(zip(["", "00", "01", "02"], ["rt", "0", "1", "2"])):
        btn(f"R_cheekbone{sfx}_CTL", CX - 184 + i*24, cy + 20, 22, 15, color=COL_R_FK, label=lbl, size=6)
        btn(f"L_cheekbone{sfx}_CTL", CX + 88 + i*24,  cy + 20, 22, 15, color=COL_L_FK, label=lbl, size=6)

    # ── NARIZ (centro) ──────────────────────────────────────────
    ny = 196
    btn("C_baseNose_CTL", CX - 27, ny,      54, 17, color=COL_CENTER, label="base", size=6)
    btn("C_noseMain_CTL", CX - 27, ny + 19, 54, 17, color=COL_CENTER, label="main", size=6)
    btn("C_noseTip_CTL",  CX - 27, ny + 38, 54, 17, color=COL_CENTER, label="tip",  size=6)
    btn("R_nose_CTL",     CX - 70, ny + 19, 38, 17, color=COL_R_FK, label="nose",  size=6)
    btn("L_nose_CTL",     CX + 32, ny + 19, 38, 17, color=COL_L_FK, label="nose",  size=6)
    btn("R_nosetril_CTL", CX - 70, ny + 38, 38, 17, color=COL_R_FK, label="ntril", size=6)
    btn("L_nosetril_CTL", CX + 32, ny + 38, 38, 17, color=COL_L_FK, label="ntril", size=6)

    # ── BOCA ────────────────────────────────────────────────────
    my = 296
    btn("R_lipCorner_CTL", CX - 178, my, 72,  20, color=COL_R_FK,   label="corner",  size=6)
    btn("C_upperLip_CTL",  CX - 70,  my, 140, 20, color=COL_CENTER, label="upperLip",size=7)
    btn("L_lipCorner_CTL", CX + 106, my, 72,  20, color=COL_L_FK,   label="corner",  size=6)

    # secondary lips (naming mirror: R 00-03, C 00, L 00-03)
    _LIP_SEQ = [("R","00"), ("R","01"), ("R","02"), ("R","03"), ("C","00"),
                ("L","03"), ("L","02"), ("L","01"), ("L","00")]
    LIP_COL = {"R": COL_R_FK, "C": COL_CENTER, "L": COL_L_FK}
    lw = 28.0
    lx0 = CX - (len(_LIP_SEQ) * lw) / 2.0
    for i, (sd, lb) in enumerate(_LIP_SEQ):
        btn(f"{sd}_upperLip{lb}_CTL", lx0 + i*lw, my + 22, lw - 1, 14, color=LIP_COL[sd], label=lb, size=6)

    btn("C_upperJaw_CTL", CX - 60, my + 40, 120, 18, color=COL_CENTER, label="upperJaw", size=6)
    btn("C_jaw_CTL",      CX - 60, my + 60, 120, 20, color=COL_CENTER, label="jaw",      size=7)
    btn("C_lowerLip_CTL", CX - 60, my + 82, 120, 18, color=COL_CENTER, label="lowerLip", size=6)

    for i, (sd, lb) in enumerate(_LIP_SEQ):
        btn(f"{sd}_lowerLip{lb}_CTL", lx0 + i*lw, my + 102, lw - 1, 14, color=LIP_COL[sd], label=lb, size=6)

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
        from maya_tools.scripts.utils import data_manager
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
        from maya_tools.scripts.utils import rig_manager
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
