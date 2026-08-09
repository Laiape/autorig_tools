"""
Curve Library — AutoRig Tools
Grid UI to browse, save and apply NURBS control shapes.
"""

import os
import json
import math

import maya.cmds as cmds
import maya.api.OpenMaya as om
import maya.OpenMayaUI as omui

try:
    from PySide6 import QtWidgets, QtCore, QtGui
    from shiboken6 import wrapInstance
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui
    from shiboken2 import wrapInstance

from maya.scripts.utils import ui_utils

# ── Paths ─────────────────────────────────────────────────────────────────────
_HERE        = os.path.dirname(os.path.realpath(__file__))
LIBRARY_PATH = os.path.join(_HERE, "curve_shapes")
os.makedirs(LIBRARY_PATH, exist_ok=True)

# ── Palette ───────────────────────────────────────────────────────────────────
C_BG0    = "#0d0d10"
C_BG1    = "#13131a"
C_BG2    = "#1a1a24"
C_BG3    = "#22222e"
C_BORDER = "#2a2a3a"
C_TEXT   = "#ccc8e0"
C_DIM    = "#4a4860"
C_AMBER  = "#c8a040"
C_GREEN  = "#4ab878"
C_RED    = "#c04858"

SS = f"""
QWidget {{ background:{C_BG2}; color:{C_TEXT}; font-family:'Segoe UI'; font-size:11px; }}
QLabel  {{ background:transparent; }}
QLineEdit {{
    background:{C_BG0}; border:none; border-bottom:1px solid {C_BORDER};
    padding:5px 8px; color:{C_TEXT};
}}
QLineEdit:focus {{ border-bottom-color:{C_AMBER}; }}
QScrollArea {{ border:none; }}
QScrollBar:vertical {{ background:{C_BG1}; width:4px; border:none; }}
QScrollBar::handle:vertical {{ background:{C_BORDER}; border-radius:2px; min-height:20px; }}
QScrollBar::handle:vertical:hover {{ background:{C_AMBER}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0px; }}
QDoubleSpinBox, QSpinBox {{
    background:{C_BG0}; border:none; border-bottom:1px solid {C_BORDER};
    padding:4px 6px; color:{C_TEXT};
}}
QComboBox {{
    background:{C_BG0}; border:none; border-bottom:1px solid {C_BORDER};
    padding:4px 8px; color:{C_TEXT};
}}
QComboBox QAbstractItemView {{ background:{C_BG2}; border:1px solid {C_BORDER}; color:{C_TEXT}; }}
QToolTip {{ background:{C_BG3}; color:{C_TEXT}; border:1px solid {C_BORDER}; padding:4px; }}
"""


# ─────────────────────────────────────────────────────────────────────────────
#  BUILT-IN SHAPE BUILDERS
# ─────────────────────────────────────────────────────────────────────────────
def _build_circle():
    n = cmds.circle(nr=(0, 1, 0), r=1, d=3, s=8, ch=False)[0]
    return n

def _build_square():
    n = cmds.curve(d=1, p=[(1,0,-1),(1,0,1),(-1,0,1),(-1,0,-1),(1,0,-1)], k=[0,1,2,3,4])
    return n

def _build_triangle():
    n = cmds.curve(d=1,
                   p=[(0,0,-1.15),(1,0,0.58),(-1,0,0.58),(0,0,-1.15)],
                   k=[0,1,2,3])
    return n

def _build_diamond():
    n = cmds.curve(d=1,
                   p=[(0,0,-1),(1,0,0),(0,0,1),(-1,0,0),(0,0,-1)],
                   k=[0,1,2,3,4])
    return n

def _build_cross():
    s, t = 0.3, 1.0
    pts = [(s,0,-t),(s,0,-s),(t,0,-s),(t,0,s),(s,0,s),(s,0,t),
           (-s,0,t),(-s,0,s),(-t,0,s),(-t,0,-s),(-s,0,-s),(-s,0,-t),(s,0,-t)]
    k = list(range(len(pts)))
    n = cmds.curve(d=1, p=pts, k=k)
    return n

def _build_arrow():
    pts = [(0,0,-0.5),(0.5,0,0.2),(0.2,0,0.2),(0.2,0,0.8),
           (-0.2,0,0.8),(-0.2,0,0.2),(-0.5,0,0.2),(0,0,-0.5)]
    k = list(range(len(pts)))
    n = cmds.curve(d=1, p=pts, k=k)
    return n

def _build_arrow4():
    s, h, b = 0.2, 0.8, 0.45
    pts = [
        (0,0,-h),(s,0,-b),(s,0,-s),(b,0,-s),(h,0,0),(b,0,s),(s,0,s),(s,0,b),
        (0,0,h),(-s,0,b),(-s,0,s),(-b,0,s),(-h,0,0),(-b,0,-s),(-s,0,-s),(-s,0,-b),(0,0,-h)
    ]
    k = list(range(len(pts)))
    return cmds.curve(d=1, p=pts, k=k)

def _build_cube():
    s = 1.0
    pts = [
        (-s,s,-s),(s,s,-s),(s,s,s),(-s,s,s),(-s,s,-s),
        (-s,-s,-s),(s,-s,-s),(s,s,-s),(s,s,s),(s,-s,s),
        (s,-s,-s),(-s,-s,-s),(-s,-s,s),(s,-s,s),(s,s,s),
        (-s,s,s),(-s,-s,s),(-s,-s,-s),(-s,s,-s)
    ]
    k = list(range(len(pts)))
    return cmds.curve(d=1, p=pts, k=k)

def _build_sphere():
    c1 = cmds.circle(nr=(0,1,0), r=1, d=3, s=8, ch=False)[0]
    c2 = cmds.circle(nr=(1,0,0), r=1, d=3, s=8, ch=False)[0]
    c3 = cmds.circle(nr=(0,0,1), r=1, d=3, s=8, ch=False)[0]
    for s in (cmds.listRelatives(c2, s=True) or []) + (cmds.listRelatives(c3, s=True) or []):
        cmds.parent(s, c1, r=True, s=True)
    cmds.delete(c2, c3)
    return c1

def _build_locator_ctl():
    s = 1.0
    pts_x = [(-s,0,0),(s,0,0)]
    pts_y = [(0,-s,0),(0,s,0)]
    pts_z = [(0,0,-s),(0,0,s)]
    n = cmds.curve(d=1, p=pts_x, k=[0,1])
    for pts in (pts_y, pts_z):
        tmp = cmds.curve(d=1, p=pts, k=[0,1])
        for sh in cmds.listRelatives(tmp, s=True) or []:
            cmds.parent(sh, n, r=True, s=True)
        cmds.delete(tmp)
    return n

def _build_pin():
    stem = cmds.curve(d=1, p=[(0,0,0),(0,2,0)], k=[0,1])
    head = cmds.circle(nr=(0,1,0), r=0.4, c=(0,2,0), d=3, s=8, ch=False)[0]
    for sh in cmds.listRelatives(head, s=True) or []:
        cmds.parent(sh, stem, r=True, s=True)
    cmds.delete(head)
    return stem

def _build_cog():
    pts = []
    teeth = 8
    for i in range(teeth * 2 + 1):
        angle = math.radians(i * 360.0 / (teeth * 2))
        r = 1.0 if (i % 2 == 0) else 0.75
        pts.append((math.cos(angle) * r, 0, math.sin(angle) * r))
    k = list(range(len(pts)))
    return cmds.curve(d=1, p=pts, k=k)

def _build_circle_arrow():
    pts = []
    for i in range(20):
        a = math.radians(i * 270.0 / 19)
        pts.append((math.cos(a), 0, math.sin(a)))
    head_base = pts[-1]
    angle_end = math.radians(270.0)
    perp = (math.sin(angle_end) * 0.3, 0, -math.cos(angle_end) * 0.3)
    pts.append((head_base[0] + perp[0], 0, head_base[2] + perp[2]))
    mid = (math.cos(math.radians(285)), 0, math.sin(math.radians(285)))
    pts.append(mid)
    pts.append((head_base[0] - perp[0], 0, head_base[2] - perp[2]))
    k = list(range(len(pts)))
    return cmds.curve(d=1, p=pts, k=k)

def _build_hip():
    c = cmds.circle(nr=(0,1,0), r=1, d=3, s=8, ch=False)[0]
    f = cmds.curve(d=1, p=[(-1,0,0),(1,0,0)], k=[0,1])
    b = cmds.curve(d=1, p=[(0,0,-1),(0,0,1)], k=[0,1])
    for tmp in (f, b):
        for sh in cmds.listRelatives(tmp, s=True) or []:
            cmds.parent(sh, c, r=True, s=True)
        cmds.delete(tmp)
    return c

BUILTIN = {
    "Circle":       _build_circle,
    "Square":       _build_square,
    "Triangle":     _build_triangle,
    "Diamond":      _build_diamond,
    "Cross":        _build_cross,
    "Arrow":        _build_arrow,
    "Arrow 4-Way":  _build_arrow4,
    "Cube":         _build_cube,
    "Sphere":       _build_sphere,
    "Locator":      _build_locator_ctl,
    "Pin":          _build_pin,
    "COG":          _build_cog,
    "Circle Arrow": _build_circle_arrow,
    "Hip":          _build_hip,
}

# ─────────────────────────────────────────────────────────────────────────────
#  SHAPE I/O
# ─────────────────────────────────────────────────────────────────────────────
def _capture_shapes(transform):
    """Capture all nurbsCurve shapes under transform → list of dicts."""
    shapes = []
    for sh in cmds.listRelatives(transform, shapes=True, type="nurbsCurve") or []:
        if cmds.getAttr(f"{sh}.intermediateObject"):
            continue
        cvs   = [list(cmds.pointPosition(f"{sh}.cv[{i}]", local=True))
                 for i in range(cmds.getAttr(f"{sh}.degree") +
                                len(cmds.getAttr(f"{sh}.knot")) - 1)]
        knots  = list(cmds.getAttr(f"{sh}.knot"))
        degree = cmds.getAttr(f"{sh}.degree")
        form   = cmds.getAttr(f"{sh}.form")   # 0=open 1=closed 2=periodic
        shapes.append({"cvs": cvs, "knots": knots, "degree": degree, "form": form})
    return shapes

def save_shape_to_library(name, transform):
    shapes = _capture_shapes(transform)
    if not shapes:
        om.MGlobal.displayWarning(f"No nurbsCurve shapes on {transform}")
        return
    path = os.path.join(LIBRARY_PATH, f"{name}.json")
    with open(path, "w") as f:
        json.dump(shapes, f, indent=2)
    om.MGlobal.displayInfo(f"Saved '{name}' to library.")
    return path

def load_shape_from_library(name):
    path = os.path.join(LIBRARY_PATH, f"{name}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    with open(path) as f:
        return json.load(f)

def list_library_shapes():
    return [os.path.splitext(f)[0]
            for f in os.listdir(LIBRARY_PATH) if f.endswith(".json")]

def _apply_shapes_to_transform(shapes_data, transform, scale=1.0, rotate=(0,0,0)):
    """Replace all nurbsCurve shapes on transform with shapes_data."""
    for sh in cmds.listRelatives(transform, shapes=True, type="nurbsCurve") or []:
        cmds.delete(sh)

    rx, ry, rz = [math.radians(a) for a in rotate]

    def _rot(p):
        x, y, z = p
        # Ry
        nx = x * math.cos(ry) + z * math.sin(ry)
        nz = -x * math.sin(ry) + z * math.cos(ry)
        x, z = nx, nz
        # Rx
        ny = y * math.cos(rx) - z * math.sin(rx)
        nz2 = y * math.sin(rx) + z * math.cos(rx)
        y, z = ny, nz2
        # Rz
        nx2 = x * math.cos(rz) - y * math.sin(rz)
        ny2 = x * math.sin(rz) + y * math.cos(rz)
        return [nx2 * scale, ny2 * scale, z * scale]

    for sd in shapes_data:
        pts    = [_rot(p) for p in sd["cvs"]]
        knots  = sd["knots"]
        degree = sd["degree"]
        form   = sd.get("form", 0)
        form_flag = {0: "open", 1: "closed", 2: "periodic"}.get(form, "open")
        tmp = cmds.curve(d=degree, p=pts, k=knots,
                         **({} if form_flag == "open" else {"per": True} if form_flag == "periodic" else {}))
        for sh in cmds.listRelatives(tmp, shapes=True) or []:
            cmds.parent(sh, transform, r=True, s=True)
        cmds.delete(tmp)


def apply_builtin_to_selected(name, scale=1.0, rotate=(0,0,0), color=None):
    sel = cmds.ls(sl=True, type="transform")
    if not sel:
        cmds.warning("Select transforms first.")
        return
    fn = BUILTIN.get(name)
    if not fn:
        cmds.warning(f"Shape '{name}' not found.")
        return
    for t in sel:
        tmp = fn()
        shapes_data = _capture_shapes(tmp)
        cmds.delete(tmp)
        _apply_shapes_to_transform(shapes_data, t, scale=scale, rotate=rotate)
        if color is not None:
            cmds.setAttr(f"{t}.overrideEnabled", True)
            cmds.setAttr(f"{t}.overrideRGBColors", True)
            cmds.setAttr(f"{t}.overrideColorRGB", *color, type="double3")
    cmds.inViewMessage(amg=f"Applied <hl>{name}</hl> to {len(sel)} controls",
                       pos="midCenter", fade=True)

def apply_library_to_selected(name, scale=1.0, rotate=(0,0,0), color=None):
    sel = cmds.ls(sl=True, type="transform")
    if not sel:
        cmds.warning("Select transforms first.")
        return
    shapes_data = load_shape_from_library(name)
    for t in sel:
        _apply_shapes_to_transform(shapes_data, t, scale=scale, rotate=rotate)
        if color is not None:
            cmds.setAttr(f"{t}.overrideEnabled", True)
            cmds.setAttr(f"{t}.overrideRGBColors", True)
            cmds.setAttr(f"{t}.overrideColorRGB", *color, type="double3")
    cmds.inViewMessage(amg=f"Applied <hl>{name}</hl> to {len(sel)} controls",
                       pos="midCenter", fade=True)


# ─────────────────────────────────────────────────────────────────────────────
#  PREVIEW PAINTING
# ─────────────────────────────────────────────────────────────────────────────
# Simplified 2D projections (XZ plane, top-down) for each built-in shape.
_PREVIEWS = {
    "Circle":      [(math.cos(math.radians(a)), math.sin(math.radians(a))) for a in range(0, 361, 12)],
    "Square":      [(-1,-1),(1,-1),(1,1),(-1,1),(-1,-1)],
    "Triangle":    [(0,-1.15),(1,0.58),(-1,0.58),(0,-1.15)],
    "Diamond":     [(0,-1),(1,0),(0,1),(-1,0),(0,-1)],
    "Cross":       [(.3,-1),(.3,-.3),(1,-.3),(1,.3),(.3,.3),(.3,1),(-.3,1),(-.3,.3),
                    (-1,.3),(-1,-.3),(-.3,-.3),(-.3,-1),(.3,-1)],
    "Arrow":       [(0,-.5),(.5,.2),(.2,.2),(.2,.8),(-.2,.8),(-.2,.2),(-.5,.2),(0,-.5)],
    "Arrow 4-Way": [(0,-.8),(.2,-.45),(.2,-.2),(.45,-.2),(.8,0),(.45,.2),(.2,.2),(.2,.45),
                    (0,.8),(-.2,.45),(-.2,.2),(-.45,.2),(-.8,0),(-.45,-.2),(-.2,-.2),(-.2,-.45),(0,-.8)],
    "Cube":        [(-1,-1),(-1,1),(1,1),(1,-1),(-1,-1)],
    "Sphere":      [(math.cos(math.radians(a)), math.sin(math.radians(a))) for a in range(0, 361, 12)],
    "Locator":     [(-1,0),(1,0),(0,0),(0,-1),(0,1)],
    "Pin":         [(0,-1),(0,1)],
    "COG":         [(math.cos(math.radians(i*360/(16))) * (1.0 if i%2==0 else 0.75),
                     math.sin(math.radians(i*360/(16))) * (1.0 if i%2==0 else 0.75))
                    for i in range(17)],
    "Circle Arrow": [(math.cos(math.radians(a)), math.sin(math.radians(a))) for a in range(0, 271, 14)],
    "Hip":         [(math.cos(math.radians(a)), math.sin(math.radians(a))) for a in range(0, 361, 12)],
}


class ShapeCard(QtWidgets.QWidget):
    clicked = QtCore.Signal(str)

    ICON_SIZE = 64

    def __init__(self, name, preview_pts, is_builtin=True, parent=None):
        super().__init__(parent)
        self.name       = name
        self.preview    = preview_pts
        self.is_builtin = is_builtin
        self.selected   = False
        self.setFixedSize(86, 100)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setToolTip(name)

    def setSelected(self, v):
        self.selected = v
        self.update()

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)

        pal = self.palette()
        bg = pal.color(QtGui.QPalette.Button if self.selected else QtGui.QPalette.Base)
        border = pal.color(QtGui.QPalette.Highlight if self.selected else QtGui.QPalette.Mid)

        p.fillRect(self.rect(), bg)
        p.setPen(QtGui.QPen(border, 1))
        p.drawRect(0, 0, self.width()-1, self.height()-1)

        # draw preview in top area
        cx = self.width() / 2
        cy = (self.ICON_SIZE + 10) / 2
        radius = self.ICON_SIZE * 0.38

        pts = self.preview or []
        if pts:
            pen = QtGui.QPen(pal.color(QtGui.QPalette.Highlight if self.selected else QtGui.QPalette.Text), 1.5)
            p.setPen(pen)
            def to_screen(px, py):
                return QtCore.QPointF(cx + px * radius, cy - py * radius)

            for i in range(len(pts) - 1):
                a = to_screen(*pts[i])
                b = to_screen(*pts[i+1])
                p.drawLine(a, b)

        # name label
        p.setPen(pal.color(QtGui.QPalette.Highlight if self.selected else QtGui.QPalette.Text))
        font = QtGui.QFont("Segoe UI", 8)
        p.setFont(font)
        text_rect = QtCore.QRectF(2, self.ICON_SIZE + 8, self.width() - 4, 24)
        p.drawText(text_rect, QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop, self.name)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.clicked.emit(self.name)


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN UI
# ─────────────────────────────────────────────────────────────────────────────
def get_maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget)


class CurveLibraryUI(QtWidgets.QWidget):

    def __init__(self, parent=get_maya_main_window()):
        super().__init__(parent)
        self.setWindowFlags(QtCore.Qt.Window)
        self.setWindowTitle("Curve Library  —  AutoRig Tools")
        self.resize(520, 600)
        self.setMinimumSize(400, 480)

        self._selected_name    = None
        self._selected_builtin = True
        self._cards            = {}

        self._build()
        self._populate()
        ui_utils.apply_maya_style(self)

    # ── layout ────────────────────────────────────────────────────────────────
    def _build(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._header())

        body = QtWidgets.QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._grid_panel(), 1)
        body.addWidget(self._options_panel())
        root.addLayout(body, 1)

        root.addWidget(self._footer())

    def _header(self):
        w = QtWidgets.QWidget()
        w.setFixedHeight(40)
        w.setStyleSheet(f"background:{C_BG0}; border-bottom:1px solid {C_BORDER};")
        lay = QtWidgets.QHBoxLayout(w)
        lay.setContentsMargins(16, 0, 16, 0)

        bar = QtWidgets.QFrame()
        bar.setFixedSize(3, 18)
        bar.setStyleSheet(f"background:{C_AMBER}; border:none;")
        lay.addWidget(bar)
        lay.addSpacing(10)

        lbl = QtWidgets.QLabel("CURVE LIBRARY")
        lbl.setStyleSheet(f"color:{C_TEXT}; font-size:11px; font-weight:bold; letter-spacing:5px;")
        lay.addWidget(lbl)
        lay.addStretch()

        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("search…")
        self.search.setFixedWidth(120)
        self.search.setStyleSheet(f"""
            background:{C_BG1}; border:1px solid {C_BORDER}; border-radius:0;
            padding:3px 8px; color:{C_TEXT}; font-size:10px;
        """)
        self.search.textChanged.connect(self._filter)
        lay.addWidget(self.search)
        return w

    def _grid_panel(self):
        panel = QtWidgets.QWidget()
        panel.setStyleSheet(f"background:{C_BG2};")
        vlay = QtWidgets.QVBoxLayout(panel)
        vlay.setContentsMargins(0, 0, 0, 0)
        vlay.setSpacing(0)

        # Tab bar: BUILT-IN | LIBRARY
        tab_row = QtWidgets.QWidget()
        tab_row.setFixedHeight(32)
        tab_row.setStyleSheet(f"background:{C_BG1}; border-bottom:1px solid {C_BORDER};")
        tlay = QtWidgets.QHBoxLayout(tab_row)
        tlay.setContentsMargins(8, 0, 8, 0)
        tlay.setSpacing(0)

        self.tab_builtin = self._tab_btn("BUILT-IN", True)
        self.tab_library = self._tab_btn("MY LIBRARY", False)
        self.tab_builtin.clicked.connect(lambda: self._switch_tab(True))
        self.tab_library.clicked.connect(lambda: self._switch_tab(False))
        tlay.addWidget(self.tab_builtin)
        tlay.addWidget(self.tab_library)
        tlay.addStretch()
        vlay.addWidget(tab_row)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)

        self.grid_container = QtWidgets.QWidget()
        self.grid_container.setStyleSheet(f"background:{C_BG2};")
        self.grid_layout = QtWidgets.QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(8, 8, 8, 8)
        self.grid_layout.setSpacing(4)
        scroll.setWidget(self.grid_container)
        vlay.addWidget(scroll, 1)
        return panel

    def _tab_btn(self, text, active):
        b = QtWidgets.QPushButton(text)
        b.setCheckable(False)
        b.setFixedHeight(32)
        color = C_AMBER if active else C_DIM
        border = f"border-bottom:2px solid {C_AMBER};" if active else "border-bottom:2px solid transparent;"
        b.setStyleSheet(f"""
            QPushButton {{
                background:transparent; color:{color}; border:none;
                {border} padding:0 14px;
                font-size:9px; letter-spacing:3px; font-weight:bold;
            }}
            QPushButton:hover {{ color:{C_TEXT}; }}
        """)
        return b

    def _options_panel(self):
        w = QtWidgets.QWidget()
        w.setFixedWidth(160)
        w.setStyleSheet(f"background:{C_BG1}; border-left:1px solid {C_BORDER};")
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        def section(t):
            l = QtWidgets.QLabel(t)
            l.setStyleSheet(f"color:{C_DIM}; font-size:8px; letter-spacing:3px; font-weight:bold; padding-top:8px; border-bottom:1px solid {C_BORDER};")
            lay.addWidget(l)

        section("TRANSFORM")

        lay.addWidget(QtWidgets.QLabel("Scale"))
        self.spin_scale = QtWidgets.QDoubleSpinBox()
        self.spin_scale.setValue(1.0)
        self.spin_scale.setRange(0.001, 100.0)
        self.spin_scale.setSingleStep(0.1)
        self.spin_scale.setDecimals(3)
        lay.addWidget(self.spin_scale)

        lay.addWidget(QtWidgets.QLabel("Rotate X"))
        self.spin_rx = QtWidgets.QDoubleSpinBox()
        self.spin_rx.setRange(-360, 360)
        self.spin_rx.setSingleStep(45)
        lay.addWidget(self.spin_rx)

        lay.addWidget(QtWidgets.QLabel("Rotate Y"))
        self.spin_ry = QtWidgets.QDoubleSpinBox()
        self.spin_ry.setRange(-360, 360)
        self.spin_ry.setSingleStep(45)
        lay.addWidget(self.spin_ry)

        lay.addWidget(QtWidgets.QLabel("Rotate Z"))
        self.spin_rz = QtWidgets.QDoubleSpinBox()
        self.spin_rz.setRange(-360, 360)
        self.spin_rz.setSingleStep(45)
        lay.addWidget(self.spin_rz)

        section("COLOR")
        self.chk_color = QtWidgets.QCheckBox("Override color")
        self.chk_color.setStyleSheet(f"color:{C_TEXT};")
        lay.addWidget(self.chk_color)

        self.color_btn = QtWidgets.QPushButton()
        self.color_btn.setFixedHeight(24)
        self._set_color_btn(QtGui.QColor(255, 165, 0))
        self.color_btn.clicked.connect(self._pick_color)
        lay.addWidget(self.color_btn)

        section("LIBRARY")
        self.save_name = QtWidgets.QLineEdit()
        self.save_name.setPlaceholderText("shape name…")
        lay.addWidget(self.save_name)

        b_save = self._btn("SAVE FROM SEL", C_BG3)
        b_save.clicked.connect(self._save_from_selection)
        lay.addWidget(b_save)

        b_del = self._btn("DELETE", C_RED)
        b_del.clicked.connect(self._delete_selected)
        lay.addWidget(b_del)

        lay.addStretch()
        return w

    def _footer(self):
        w = QtWidgets.QWidget()
        w.setFixedHeight(52)
        w.setStyleSheet(f"background:{C_BG0}; border-top:1px solid {C_BORDER};")
        lay = QtWidgets.QHBoxLayout(w)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(8)

        self.lbl_sel = QtWidgets.QLabel("—")
        self.lbl_sel.setStyleSheet(f"color:{C_DIM}; font-size:10px; letter-spacing:1px;")
        lay.addWidget(self.lbl_sel, 1)

        b_apply = QtWidgets.QPushButton("APPLY TO SELECTED")
        b_apply.setMinimumHeight(34)
        b_apply.setStyleSheet(f"""
            QPushButton {{
                background:{C_AMBER}; color:#0d0d10;
                border:none; border-left:3px solid #e8c060;
                border-radius:0px; padding:6px 20px;
                font-weight:bold; font-size:10px; letter-spacing:3px;
            }}
            QPushButton:hover {{ background:#e8c060; }}
            QPushButton:pressed {{ background:{C_AMBER}; }}
        """)
        b_apply.clicked.connect(self._apply)
        lay.addWidget(b_apply)
        return w

    def _btn(self, text, color=C_BG3):
        b = QtWidgets.QPushButton(text)
        b.setStyleSheet(f"""
            QPushButton {{
                background:{color}; color:{C_TEXT}; border:none;
                border-bottom:1px solid {C_BORDER}; border-left:2px solid transparent;
                padding:5px 10px; font-size:9px; letter-spacing:1px;
            }}
            QPushButton:hover {{ border-left:2px solid {C_AMBER}; color:{C_AMBER}; }}
            QPushButton:pressed {{ background:{C_BG0}; }}
        """)
        return b

    # ── logic ─────────────────────────────────────────────────────────────────
    def _populate(self):
        self._showing_builtin = True
        self._refresh_grid()

    def _switch_tab(self, builtin):
        self._showing_builtin = builtin
        active, inactive = (self.tab_builtin, self.tab_library) if builtin else (self.tab_library, self.tab_builtin)
        active.setStyleSheet(active.styleSheet().replace(
            "border-bottom:2px solid transparent", f"border-bottom:2px solid {C_AMBER}").replace(C_DIM, C_AMBER))
        inactive.setStyleSheet(inactive.styleSheet().replace(
            f"border-bottom:2px solid {C_AMBER}", "border-bottom:2px solid transparent").replace(C_AMBER, C_DIM))
        self._refresh_grid()

    def _refresh_grid(self):
        # clear
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cards.clear()

        if self._showing_builtin:
            names = list(BUILTIN.keys())
            previews = _PREVIEWS
        else:
            names = list_library_shapes()
            previews = {}

        cols = 4
        for i, name in enumerate(names):
            pts = previews.get(name, [])
            card = ShapeCard(name, pts, is_builtin=self._showing_builtin)
            card.clicked.connect(self._on_card_clicked)
            self._cards[name] = card
            self.grid_layout.addWidget(card, i // cols, i % cols)

        # spacer
        self.grid_layout.setRowStretch(max(1, len(names) // cols + 1), 1)

    def _filter(self, text):
        text = text.lower()
        for name, card in self._cards.items():
            card.setVisible(text in name.lower())

    def _on_card_clicked(self, name):
        for n, c in self._cards.items():
            c.setSelected(n == name)
        self._selected_name    = name
        self._selected_builtin = self._showing_builtin
        self.lbl_sel.setText(name)

    def _set_color_btn(self, color: QtGui.QColor):
        self._pick_clr = (color.redF(), color.greenF(), color.blueF())
        self.color_btn.setStyleSheet(f"""
            QPushButton {{
                background:{color.name()}; border:none;
                border-bottom:1px solid {C_BORDER};
            }}
        """)

    def _pick_color(self):
        c = QtWidgets.QColorDialog.getColor(parent=self)
        if c.isValid():
            self._set_color_btn(c)

    def _get_options(self):
        scale  = self.spin_scale.value()
        rotate = (self.spin_rx.value(), self.spin_ry.value(), self.spin_rz.value())
        color  = self._pick_clr if self.chk_color.isChecked() else None
        return scale, rotate, color

    def _apply(self):
        if not self._selected_name:
            cmds.warning("Select a shape first.")
            return
        scale, rotate, color = self._get_options()
        if self._selected_builtin:
            apply_builtin_to_selected(self._selected_name, scale, rotate, color)
        else:
            apply_library_to_selected(self._selected_name, scale, rotate, color)

    def _save_from_selection(self):
        name = self.save_name.text().strip()
        if not name:
            cmds.warning("Enter a name first.")
            return
        sel = cmds.ls(sl=True, type="transform")
        if not sel:
            cmds.warning("Select a transform with nurbsCurve shapes.")
            return
        save_shape_to_library(name, sel[0])
        if not self._showing_builtin:
            self._refresh_grid()

    def _delete_selected(self):
        if not self._selected_name or self._selected_builtin:
            cmds.warning("Select a custom library shape to delete.")
            return
        path = os.path.join(LIBRARY_PATH, f"{self._selected_name}.json")
        if os.path.exists(path):
            os.remove(path)
        self._selected_name = None
        self.lbl_sel.setText("—")
        self._refresh_grid()


# ── Launch ────────────────────────────────────────────────────────────────────
def show():
    global _curve_lib_ui
    try:
        _curve_lib_ui.close()
        _curve_lib_ui.deleteLater()
    except Exception:
        pass
    _curve_lib_ui = CurveLibraryUI()
    _curve_lib_ui.show()
