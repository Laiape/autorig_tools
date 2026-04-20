"""
Rig Tools — AutoRig Tools
Inspired by Morgan Loomis' ml_tools:
  - Arc Tracer
  - World Bake
  - Color Control (gradient)
  - Parent Shape
  - Reset Channels
  - Rotation Order Switcher
"""

import maya.cmds as cmds
import maya.mel as mel
import maya.api.OpenMaya as om
import maya.OpenMayaUI as omui

import math

try:
    from PySide6 import QtWidgets, QtCore, QtGui
    from shiboken6 import wrapInstance
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui
    from shiboken2 import wrapInstance

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
C_PURPLE = "#8868c8"

SS = f"""
QWidget {{ background:{C_BG2}; color:{C_TEXT}; font-family:'Segoe UI'; font-size:11px; }}
QLabel  {{ background:transparent; }}
QLineEdit {{
    background:{C_BG0}; border:none; border-bottom:1px solid {C_BORDER};
    padding:5px 8px; color:{C_TEXT};
}}
QLineEdit:focus {{ border-bottom-color:{C_AMBER}; }}
QSpinBox, QDoubleSpinBox {{
    background:{C_BG0}; border:none; border-bottom:1px solid {C_BORDER};
    padding:4px 6px; color:{C_TEXT};
}}
QCheckBox {{ spacing:6px; color:{C_TEXT}; }}
QCheckBox::indicator {{ width:14px; height:14px; background:{C_BG0}; border:1px solid {C_BORDER}; }}
QCheckBox::indicator:checked {{ background:{C_AMBER}; border-color:{C_AMBER}; }}
QComboBox {{
    background:{C_BG0}; border:none; border-bottom:1px solid {C_BORDER};
    padding:4px 8px; color:{C_TEXT};
}}
QComboBox QAbstractItemView {{ background:{C_BG2}; border:1px solid {C_BORDER}; color:{C_TEXT}; }}
QScrollBar:vertical {{ background:{C_BG1}; width:4px; border:none; }}
QScrollBar::handle:vertical {{ background:{C_BORDER}; border-radius:2px; min-height:20px; }}
QScrollBar::handle:vertical:hover {{ background:{C_AMBER}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0px; }}
QSlider::groove:horizontal {{ background:{C_BG0}; height:3px; border:none; }}
QSlider::handle:horizontal {{
    background:{C_AMBER}; width:12px; height:12px;
    margin:-5px 0; border-radius:6px;
}}
QSlider::sub-page:horizontal {{ background:{C_AMBER}; }}
QToolTip {{ background:{C_BG3}; color:{C_TEXT}; border:1px solid {C_BORDER}; padding:4px; }}
"""


def get_maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget)


def _flat_btn(text, color=C_BG3, text_color=C_TEXT, accent_color=None):
    ac = accent_color or C_AMBER
    b = QtWidgets.QPushButton(text)
    b.setStyleSheet(f"""
        QPushButton {{
            background:{color}; color:{text_color};
            border:none; border-bottom:1px solid {C_BORDER};
            border-left:2px solid transparent;
            padding:6px 14px;
        }}
        QPushButton:hover {{ border-left:2px solid {ac}; color:{ac}; }}
        QPushButton:pressed {{ background:{C_BG0}; }}
    """)
    return b


def _accent_btn(text):
    b = QtWidgets.QPushButton(text)
    b.setStyleSheet(f"""
        QPushButton {{
            background:{C_AMBER}; color:#0d0d10;
            border:none; border-left:3px solid #e8c060;
            padding:7px 18px; font-weight:bold; letter-spacing:2px;
        }}
        QPushButton:hover {{ background:#e8c060; }}
        QPushButton:pressed {{ background:{C_AMBER}; }}
    """)
    return b


def _section_label(text):
    l = QtWidgets.QLabel(text)
    l.setStyleSheet(f"""
        color:{C_DIM}; font-size:8px; letter-spacing:4px;
        font-weight:bold; padding:10px 0 4px 0;
        border-bottom:1px solid {C_BORDER};
    """)
    return l


# ═════════════════════════════════════════════════════════════════════════════
#  1. ARC TRACER
# ═════════════════════════════════════════════════════════════════════════════
class ArcTracer:
    """
    Draws a NURBS curve tracing the world-space path of a selected object
    across a frame range. Keyframes marked with locators.
    Inspired by ml_arcTracer by Morgan Loomis.
    """
    GROUP = "arcTracer_GRP"

    @classmethod
    def trace(cls, start=None, end=None, mark_keys=True, color=(1, 1, 0)):
        sel = cmds.ls(sl=True)
        if not sel:
            cmds.warning("Select an object to trace.")
            return

        if start is None:
            start = int(cmds.playbackOptions(q=True, min=True))
        if end is None:
            end = int(cmds.playbackOptions(q=True, max=True))

        obj = sel[0]
        pts = []
        keyed_frames = set()

        if mark_keys:
            keys = cmds.keyframe(obj, q=True, time=(start, end)) or []
            keyed_frames = set(int(k) for k in keys)

        for f in range(start, end + 1):
            pos = cmds.xform(obj, q=True, ws=True, t=True,
                             time=f) if hasattr(cmds.xform, "time") else None
            if pos is None:
                cmds.currentTime(f, update=False)
                pos = cmds.xform(obj, q=True, ws=True, t=True)
            pts.append(pos)

        if len(pts) < 2:
            cmds.warning("Not enough frames to trace.")
            return

        if not cmds.objExists(cls.GROUP):
            cmds.createNode("transform", name=cls.GROUP)

        crv = cmds.curve(d=1, p=pts, k=list(range(len(pts))))
        crv = cmds.rename(crv, f"arc_{obj}_curve")
        cmds.parent(crv, cls.GROUP)
        cmds.setAttr(f"{crv}.overrideEnabled", True)
        cmds.setAttr(f"{crv}.overrideRGBColors", True)
        cmds.setAttr(f"{crv}.overrideColorRGB", *color, type="double3")

        if mark_keys:
            for f in keyed_frames:
                idx = f - start
                if 0 <= idx < len(pts):
                    loc = cmds.spaceLocator(name=f"arc_{obj}_key_{f}")[0]
                    cmds.setAttr(f"{loc}.t", *pts[idx], type="double3")
                    cmds.setAttr(f"{loc}.localScale", 0.1, 0.1, 0.1, type="double3")
                    cmds.setAttr(f"{loc}.overrideEnabled", True)
                    cmds.setAttr(f"{loc}.overrideRGBColors", True)
                    cmds.setAttr(f"{loc}.overrideColorRGB", 1, 0.2, 0.2, type="double3")
                    cmds.parent(loc, cls.GROUP)

        cmds.inViewMessage(amg=f"Arc traced: <hl>{obj}</hl>  [{start}–{end}]",
                           pos="midCenter", fade=True)

    @classmethod
    def clear(cls):
        if cmds.objExists(cls.GROUP):
            cmds.delete(cls.GROUP)
        cmds.inViewMessage(amg="Arcs cleared", pos="midCenter", fade=True)


# ═════════════════════════════════════════════════════════════════════════════
#  2. WORLD BAKE
# ═════════════════════════════════════════════════════════════════════════════
class WorldBake:
    """
    Bake selected objects to world-space locators, then restore.
    Inspired by ml_worldBake by Morgan Loomis.
    """
    _ATTR = "worldBake_source"

    @classmethod
    def to_locators(cls, bake_every_frame=True):
        sel = cmds.ls(sl=True)
        if not sel:
            cmds.warning("Select objects to bake.")
            return

        start = int(cmds.playbackOptions(q=True, min=True))
        end   = int(cmds.playbackOptions(q=True, max=True))

        locators = []
        for obj in sel:
            loc = cmds.spaceLocator(name=f"worldBake_{obj}")[0]
            if not cmds.attributeQuery(cls._ATTR, node=loc, exists=True):
                cmds.addAttr(loc, ln=cls._ATTR, dt="string")
            cmds.setAttr(f"{loc}.{cls._ATTR}", obj, type="string")
            locators.append(loc)

            con = cmds.parentConstraint(obj, loc, mo=False)[0]
            cmds.bakeResults(loc, t=(start, end),
                             simulation=bake_every_frame,
                             sampleBy=1, at=["tx","ty","tz","rx","ry","rz"])
            cmds.delete(con)

        cmds.select(locators)
        cmds.inViewMessage(amg=f"Baked <hl>{len(locators)}</hl> objects to locators",
                           pos="midCenter", fade=True)

    @classmethod
    def from_locators(cls):
        sel = cmds.ls(sl=True)
        if not sel:
            cmds.warning("Select the bake locators.")
            return

        start = int(cmds.playbackOptions(q=True, min=True))
        end   = int(cmds.playbackOptions(q=True, max=True))

        for loc in sel:
            if not cmds.attributeQuery(cls._ATTR, node=loc, exists=True):
                cmds.warning(f"{loc} is not a worldBake locator.")
                continue
            obj = cmds.getAttr(f"{loc}.{cls._ATTR}")
            if not cmds.objExists(obj):
                cmds.warning(f"Source '{obj}' not found.")
                continue
            con = cmds.parentConstraint(loc, obj, mo=False)[0]
            cmds.bakeResults(obj, t=(start, end),
                             simulation=True, sampleBy=1,
                             at=["tx","ty","tz","rx","ry","rz"])
            cmds.delete(con)

        cmds.inViewMessage(amg="Restored from locators", pos="midCenter", fade=True)


# ═════════════════════════════════════════════════════════════════════════════
#  3. COLOR CONTROL  (gradient)
# ═════════════════════════════════════════════════════════════════════════════
def _lerp_hsv(h1, s1, v1, h2, s2, v2, t):
    return (h1 + (h2 - h1) * t, s1 + (s2 - s1) * t, v1 + (v2 - v1) * t)

def color_controls_gradient(objects, color_a, color_b):
    """Apply gradient from color_a to color_b across objects list."""
    n = max(len(objects) - 1, 1)
    c1 = QtGui.QColor(*[int(x * 255) for x in color_a])
    c2 = QtGui.QColor(*[int(x * 255) for x in color_b])
    h1, s1, v1 = c1.hsvHueF(), c1.saturationF(), c1.valueF()
    h2, s2, v2 = c2.hsvHueF(), c2.saturationF(), c2.valueF()

    for i, obj in enumerate(objects):
        t = i / n
        h, s, v = _lerp_hsv(h1, s1, v1, h2, s2, v2, t)
        clr = QtGui.QColor.fromHsvF(max(0.0, h), s, v)
        r, g, b = clr.redF(), clr.greenF(), clr.blueF()
        try:
            cmds.setAttr(f"{obj}.overrideEnabled", True)
            cmds.setAttr(f"{obj}.overrideRGBColors", True)
            cmds.setAttr(f"{obj}.overrideColorRGB", r, g, b, type="double3")
        except Exception as e:
            cmds.warning(f"Could not color {obj}: {e}")

def set_solid_color(objects, color):
    r, g, b = color
    for obj in objects:
        try:
            cmds.setAttr(f"{obj}.overrideEnabled", True)
            cmds.setAttr(f"{obj}.overrideRGBColors", True)
            cmds.setAttr(f"{obj}.overrideColorRGB", r, g, b, type="double3")
        except Exception as e:
            cmds.warning(f"Could not color {obj}: {e}")

def clear_color_overrides(objects):
    for obj in objects:
        try:
            cmds.setAttr(f"{obj}.overrideEnabled", False)
        except Exception:
            pass


# ═════════════════════════════════════════════════════════════════════════════
#  4. PARENT SHAPE
# ═════════════════════════════════════════════════════════════════════════════
def parent_shape():
    """
    Transfer shape nodes from source transforms to the last selected transform.
    Inspired by ml_parentShape by Morgan Loomis.
    """
    sel = cmds.ls(sl=True, type="transform")
    if len(sel) < 2:
        cmds.warning("Select source(s) then target transform last.")
        return

    sources = sel[:-1]
    target  = sel[-1]

    for src in sources:
        for sh in cmds.listRelatives(src, shapes=True) or []:
            if cmds.getAttr(f"{sh}.intermediateObject"):
                continue
            cmds.parent(sh, target, r=True, s=True)
            cmds.rename(sh, f"{target}Shape")
        if not cmds.listRelatives(src, allDescendents=True):
            cmds.delete(src)

    cmds.inViewMessage(amg=f"Shapes transferred to <hl>{target}</hl>",
                       pos="midCenter", fade=True)


def unparent_shape():
    """Extract shapes from selected transform into individual transforms."""
    sel = cmds.ls(sl=True, type="transform")
    if not sel:
        cmds.warning("Select transforms to unparent shapes from.")
        return
    created = []
    for t in sel:
        for sh in cmds.listRelatives(t, shapes=True) or []:
            if cmds.getAttr(f"{sh}.intermediateObject"):
                continue
            grp = cmds.createNode("transform", name=f"{sh}_GRP")
            cmds.parent(sh, grp, r=True, s=True)
            created.append(grp)
    cmds.inViewMessage(amg=f"Unparented <hl>{len(created)}</hl> shapes",
                       pos="midCenter", fade=True)


# ═════════════════════════════════════════════════════════════════════════════
#  5. RESET CHANNELS
# ═════════════════════════════════════════════════════════════════════════════
def reset_channels(selected_only=False):
    """
    Reset keyable/unlocked attributes to their default values.
    Inspired by ml_resetChannels by Morgan Loomis.
    """
    sel = cmds.ls(sl=True)
    if not sel:
        cmds.warning("Select objects to reset.")
        return

    reset_count = 0
    for obj in sel:
        attrs = cmds.listAttr(obj, keyable=True, unlocked=True) or []
        for attr in attrs:
            try:
                default = cmds.attributeQuery(attr, node=obj, listDefault=True)
                if default is not None:
                    cmds.setAttr(f"{obj}.{attr}", default[0])
                    reset_count += 1
            except Exception:
                pass

    cmds.inViewMessage(amg=f"Reset <hl>{reset_count}</hl> attributes", pos="midCenter", fade=True)


# ═════════════════════════════════════════════════════════════════════════════
#  6. ROTATION ORDER SWITCHER
# ═════════════════════════════════════════════════════════════════════════════
ROT_ORDERS = ["xyz", "yzx", "zxy", "xzy", "yxz", "zyx"]

def switch_rotation_order(new_order_str, bake=True):
    """
    Switch rotation order on selected controls, preserving animation.
    Inspired by ml_convertRotationOrder by Morgan Loomis.
    """
    sel = cmds.ls(sl=True, type="transform")
    if not sel:
        cmds.warning("Select transforms.")
        return

    new_idx = ROT_ORDERS.index(new_order_str.lower())
    start   = int(cmds.playbackOptions(q=True, min=True))
    end     = int(cmds.playbackOptions(q=True, max=True))

    for obj in sel:
        if bake:
            cmds.bakeResults(obj, t=(start, end), sampleBy=1,
                             at=["rx", "ry", "rz"], simulation=False)
        cmds.xform(obj, preserve=True, rotateOrder=new_order_str)
        cmds.setAttr(f"{obj}.rotateOrder", new_idx)

    cmds.inViewMessage(amg=f"Rotation order → <hl>{new_order_str.upper()}</hl>",
                       pos="midCenter", fade=True)


# ═════════════════════════════════════════════════════════════════════════════
#  MAIN UI
# ═════════════════════════════════════════════════════════════════════════════
class RigToolsUI(QtWidgets.QWidget):

    def __init__(self, parent=get_maya_main_window()):
        super().__init__(parent)
        self.setWindowFlags(QtCore.Qt.Window)
        self.setWindowTitle("Rig Tools  —  AutoRig Tools")
        self.resize(380, 640)
        self.setMinimumWidth(320)
        self.setStyleSheet(SS)
        self._color_a = (0.2, 0.6, 1.0)
        self._color_b = (1.0, 0.3, 0.3)
        self._solid_color = (1.0, 0.65, 0.0)
        self._build()

    def _build(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._header())

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border:none; }")
        body = QtWidgets.QWidget()
        body.setStyleSheet(f"background:{C_BG2};")
        vlay = QtWidgets.QVBoxLayout(body)
        vlay.setContentsMargins(14, 10, 14, 14)
        vlay.setSpacing(4)

        self._build_arc_tracer(vlay)
        self._build_world_bake(vlay)
        self._build_color_control(vlay)
        self._build_parent_shape(vlay)
        self._build_reset_channels(vlay)
        self._build_rot_order(vlay)

        vlay.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

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
        lbl = QtWidgets.QLabel("RIG TOOLS")
        lbl.setStyleSheet(f"color:{C_TEXT}; font-size:11px; font-weight:bold; letter-spacing:5px;")
        lay.addWidget(lbl)
        return w

    # ── Arc Tracer ────────────────────────────────────────────────────────────
    def _build_arc_tracer(self, lay):
        lay.addWidget(_section_label("ARC TRACER"))

        frame_row = QtWidgets.QHBoxLayout()
        frame_row.addWidget(QtWidgets.QLabel("Start"))
        self.arc_start = QtWidgets.QSpinBox()
        self.arc_start.setRange(-9999, 9999)
        self.arc_start.setValue(int(cmds.playbackOptions(q=True, min=True)))
        frame_row.addWidget(self.arc_start)
        frame_row.addWidget(QtWidgets.QLabel("End"))
        self.arc_end = QtWidgets.QSpinBox()
        self.arc_end.setRange(-9999, 9999)
        self.arc_end.setValue(int(cmds.playbackOptions(q=True, max=True)))
        frame_row.addWidget(self.arc_end)
        lay.addLayout(frame_row)

        self.arc_keys = QtWidgets.QCheckBox("Mark keyframes")
        self.arc_keys.setChecked(True)
        lay.addWidget(self.arc_keys)

        btn_row = QtWidgets.QHBoxLayout()
        b_trace = _accent_btn("TRACE ARC")
        b_trace.clicked.connect(self._trace_arc)
        b_clear = _flat_btn("CLEAR", C_BG3, C_RED, C_RED)
        b_clear.clicked.connect(ArcTracer.clear)
        btn_row.addWidget(b_trace, 2)
        btn_row.addWidget(b_clear, 1)
        lay.addLayout(btn_row)

    def _trace_arc(self):
        ArcTracer.trace(
            start=self.arc_start.value(),
            end=self.arc_end.value(),
            mark_keys=self.arc_keys.isChecked()
        )

    # ── World Bake ────────────────────────────────────────────────────────────
    def _build_world_bake(self, lay):
        lay.addWidget(_section_label("WORLD BAKE"))

        self.bake_every = QtWidgets.QCheckBox("Bake every frame")
        self.bake_every.setChecked(True)
        lay.addWidget(self.bake_every)

        btn_row = QtWidgets.QHBoxLayout()
        b_to  = _flat_btn("→  TO LOCATORS")
        b_to.clicked.connect(lambda: WorldBake.to_locators(self.bake_every.isChecked()))
        b_from = _flat_btn("←  FROM LOCATORS")
        b_from.clicked.connect(WorldBake.from_locators)
        btn_row.addWidget(b_to)
        btn_row.addWidget(b_from)
        lay.addLayout(btn_row)

    # ── Color Control ─────────────────────────────────────────────────────────
    def _build_color_control(self, lay):
        lay.addWidget(_section_label("COLOR CONTROL"))

        # Solid color
        solid_row = QtWidgets.QHBoxLayout()
        solid_row.addWidget(QtWidgets.QLabel("Solid:"))
        self.solid_swatch = self._swatch(self._solid_color)
        self.solid_swatch.clicked.connect(self._pick_solid)
        solid_row.addWidget(self.solid_swatch)
        b_solid = _flat_btn("APPLY")
        b_solid.clicked.connect(lambda: set_solid_color(
            cmds.ls(sl=True) or [], self._solid_color))
        solid_row.addWidget(b_solid, 1)
        lay.addLayout(solid_row)

        # Gradient
        grad_row = QtWidgets.QHBoxLayout()
        grad_row.addWidget(QtWidgets.QLabel("Gradient:"))
        self.swatch_a = self._swatch(self._color_a)
        self.swatch_a.clicked.connect(self._pick_a)
        self.swatch_b = self._swatch(self._color_b)
        self.swatch_b.clicked.connect(self._pick_b)
        b_grad = _flat_btn("APPLY GRADIENT")
        b_grad.clicked.connect(self._apply_gradient)
        grad_row.addWidget(self.swatch_a)
        grad_row.addWidget(self.swatch_b)
        grad_row.addWidget(b_grad, 1)
        lay.addLayout(grad_row)

        b_clear = _flat_btn("CLEAR COLOR OVERRIDES", C_BG3, C_RED, C_RED)
        b_clear.clicked.connect(lambda: clear_color_overrides(cmds.ls(sl=True) or []))
        lay.addWidget(b_clear)

    def _swatch(self, rgb):
        b = QtWidgets.QPushButton()
        b.setFixedSize(28, 22)
        self._set_swatch(b, rgb)
        return b

    def _set_swatch(self, btn, rgb):
        r, g, bl = [int(x * 255) for x in rgb]
        btn.setStyleSheet(f"""
            QPushButton {{
                background:rgb({r},{g},{bl}); border:1px solid {C_BORDER};
                border-radius:0;
            }}
            QPushButton:hover {{ border-color:{C_AMBER}; }}
        """)

    def _pick_solid(self):
        c = QtWidgets.QColorDialog.getColor(parent=self)
        if c.isValid():
            self._solid_color = (c.redF(), c.greenF(), c.blueF())
            self._set_swatch(self.solid_swatch, self._solid_color)

    def _pick_a(self):
        c = QtWidgets.QColorDialog.getColor(parent=self)
        if c.isValid():
            self._color_a = (c.redF(), c.greenF(), c.blueF())
            self._set_swatch(self.swatch_a, self._color_a)

    def _pick_b(self):
        c = QtWidgets.QColorDialog.getColor(parent=self)
        if c.isValid():
            self._color_b = (c.redF(), c.greenF(), c.blueF())
            self._set_swatch(self.swatch_b, self._color_b)

    def _apply_gradient(self):
        sel = cmds.ls(sl=True)
        if not sel:
            cmds.warning("Select objects.")
            return
        color_controls_gradient(sel, self._color_a, self._color_b)

    # ── Parent Shape ──────────────────────────────────────────────────────────
    def _build_parent_shape(self, lay):
        lay.addWidget(_section_label("PARENT SHAPE"))

        info = QtWidgets.QLabel("Select sources then target last.")
        info.setStyleSheet(f"color:{C_DIM}; font-size:10px; padding:2px 0;")
        lay.addWidget(info)

        btn_row = QtWidgets.QHBoxLayout()
        b_parent   = _flat_btn("PARENT SHAPE  (Ctrl+P)")
        b_parent.clicked.connect(parent_shape)
        b_unparent = _flat_btn("UNPARENT SHAPE")
        b_unparent.clicked.connect(unparent_shape)
        btn_row.addWidget(b_parent)
        btn_row.addWidget(b_unparent)
        lay.addLayout(btn_row)

    # ── Reset Channels ────────────────────────────────────────────────────────
    def _build_reset_channels(self, lay):
        lay.addWidget(_section_label("RESET CHANNELS"))

        b = _accent_btn("RESET SELECTED TO DEFAULTS")
        b.clicked.connect(reset_channels)
        lay.addWidget(b)

    # ── Rotation Order ────────────────────────────────────────────────────────
    def _build_rot_order(self, lay):
        lay.addWidget(_section_label("ROTATION ORDER"))

        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("Order:"))
        self.rot_combo = QtWidgets.QComboBox()
        self.rot_combo.addItems([o.upper() for o in ROT_ORDERS])
        row.addWidget(self.rot_combo, 1)
        lay.addLayout(row)

        self.rot_bake = QtWidgets.QCheckBox("Bake animation before switching")
        self.rot_bake.setChecked(True)
        lay.addWidget(self.rot_bake)

        b = _flat_btn("SWITCH ROTATION ORDER")
        b.clicked.connect(self._switch_rot)
        lay.addWidget(b)

    def _switch_rot(self):
        order = ROT_ORDERS[self.rot_combo.currentIndex()]
        switch_rotation_order(order, bake=self.rot_bake.isChecked())


# ── Launch ────────────────────────────────────────────────────────────────────
def show():
    global _rig_tools_ui
    try:
        _rig_tools_ui.close()
        _rig_tools_ui.deleteLater()
    except Exception:
        pass
    _rig_tools_ui = RigToolsUI()
    _rig_tools_ui.show()
