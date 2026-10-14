"""Shared native character picker runtime; distributed without AutoRig imports."""
import json
from pathlib import Path

import maya.cmds as cmds
import maya.OpenMayaUI as omui
try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from shiboken6 import wrapInstance
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets
    from shiboken2 import wrapInstance

ROOT = Path(__file__).resolve().parent
_WINDOW = None


def enum(owner, scope, name):
    scoped = getattr(owner, scope, None)
    return getattr(scoped, name) if scoped is not None and hasattr(scoped, name) else getattr(owner, name)


LEFT = enum(QtCore.Qt, "MouseButton", "LeftButton")
MIDDLE = enum(QtCore.Qt, "MouseButton", "MiddleButton")
SHIFT = enum(QtCore.Qt, "KeyboardModifier", "ShiftModifier")
CTRL = enum(QtCore.Qt, "KeyboardModifier", "ControlModifier")


def main_window():
    pointer = omui.MQtUtil.mainWindow()
    return wrapInstance(int(pointer), QtWidgets.QWidget) if pointer else None


def shape_path(options):
    path = QtGui.QPainterPath()
    rect = QtCore.QRectF(0, 0, options["shape.width"], options["shape.height"])
    kind = options["shape"]
    if kind == "custom":
        points = options["shape.path"]
        if not points:
            raise ValueError("Empty controller path")
        path.moveTo(*points[0]["point"])
        for i, point in enumerate(points):
            next_point = points[(i + 1) % len(points)]
            path.cubicTo(*(point["tangent_out"] or point["point"]),
                         *(next_point["tangent_in"] or next_point["point"]), *next_point["point"])
        path.closeSubpath()
    elif kind == "round":
        path.addEllipse(rect)
    elif kind == "rounded_rect":
        path.addRoundedRect(rect, options["shape.cornersx"], options["shape.cornersy"])
    else:
        path.addRect(rect)
    return path


class ControllerItem(QtWidgets.QGraphicsPathItem):
    def __init__(self, options, picker):
        super(ControllerItem, self).__init__(shape_path(options))
        self.options, self.picker = options, picker
        self.selected_in_maya, self.hovered = False, False
        self.setPos(options["shape.left"], options["shape.top"])
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(LEFT)
        self.setToolTip("\n".join(options["action.targets"]))
        self.setZValue(2 if options.get("visibility_layer") == "Fine eyelids" else 1)
        if options["text.content"]:
            label = QtWidgets.QGraphicsSimpleTextItem(options["text.content"], self)
            font = QtGui.QFont("Arial")
            font.setPixelSize(int(options["text.size"]))
            label.setFont(font)
            label.setBrush(QtGui.QColor(options["text.color"]))
            label.setAcceptedMouseButtons(enum(QtCore.Qt, "MouseButton", "NoButton"))
            bounds = label.boundingRect()
            label.setPos((options["shape.width"]-bounds.width())/2,
                         (options["shape.height"]-bounds.height())/2)
        self.update_style()

    def update_style(self):
        color = QtGui.QColor(self.options["bgcolor.normal"])
        if self.hovered:
            color = color.lighter(120)
        self.setBrush(color)
        border = "#ffffff" if self.selected_in_maya else "#dadada" if self.hovered else self.options["bordercolor.normal"]
        self.setPen(QtGui.QPen(QtGui.QColor(border), 2.5 if self.selected_in_maya else 1.6))

    def hoverEnterEvent(self, event):
        self.hovered = True
        self.update_style()
        super(ControllerItem, self).hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.hovered = False
        self.update_style()
        super(ControllerItem, self).hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == LEFT:
            self.picker.select_targets(self.options["action.targets"], event.modifiers())
            event.accept()
        else:
            super(ControllerItem, self).mousePressEvent(event)


class PickerView(QtWidgets.QGraphicsView):
    def __init__(self, scene):
        super(PickerView, self).__init__(scene)
        self._pan = None
        self.setRenderHints(enum(QtGui.QPainter, "RenderHint", "Antialiasing") |
                            enum(QtGui.QPainter, "RenderHint", "SmoothPixmapTransform"))
        self.setBackgroundBrush(QtGui.QColor("#070909"))
        self.setFrameShape(enum(QtWidgets.QFrame, "Shape", "NoFrame"))
        self.setTransformationAnchor(enum(QtWidgets.QGraphicsView, "ViewportAnchor", "AnchorUnderMouse"))
        self.setMinimumSize(280, 350)

    def fit(self):
        self.resetTransform()
        self.fitInView(self.sceneRect(), enum(QtCore.Qt, "AspectRatioMode", "KeepAspectRatio"))

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1/1.15
        scale = self.transform().m11()*factor
        if .15 <= scale <= 5:
            self.scale(factor, factor)
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == MIDDLE:
            self._pan = event.pos()
            event.accept()
        else:
            super(PickerView, self).mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._pan is not None:
            delta = event.pos()-self._pan
            self._pan = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value()-delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value()-delta.y())
            event.accept()
        else:
            super(PickerView, self).mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == MIDDLE:
            self._pan = None
            event.accept()
        else:
            super(PickerView, self).mouseReleaseEvent(event)


class CharacterPicker(QtWidgets.QDialog):
    def __init__(self, parent=None, root_uuid=None):
        super(CharacterPicker, self).__init__(parent)
        self.instance_root_uuid = root_uuid
        self.setObjectName("CharacterMayaPicker")
        self.config = json.loads((ROOT/"picker_config.json").read_text())
        self.setWindowTitle(self.config["character"] + " Picker")
        self.setAttribute(enum(QtCore.Qt, "WidgetAttribute", "WA_DeleteOnClose"))
        self.resize(1050, 830)
        self.document = json.loads((ROOT/"picker.json").read_text())
        self.controls = [s for s in self.document["shapes"] if not s["background"]]
        self.items, self.views, self.jobs = [], [], []
        self.resolved, self._last_selection = {}, None
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        toolbar = QtWidgets.QHBoxLayout()
        toolbar.addWidget(QtWidgets.QLabel("Namespace"))
        self.namespace = QtWidgets.QLineEdit()
        self.namespace.setPlaceholderText("Root or reference namespace")
        self.namespace.setMaximumWidth(200)
        toolbar.addWidget(self.namespace)
        use_selection = QtWidgets.QPushButton("Use Selection")
        use_selection.clicked.connect(self.namespace_from_selection)
        toolbar.addWidget(use_selection)
        refresh = QtWidgets.QPushButton("Refresh")
        refresh.clicked.connect(self.refresh_targets)
        toolbar.addWidget(refresh)
        self.secondary = QtWidgets.QCheckBox("Secondary")
        self.secondary.setChecked(True)
        self.fine = QtWidgets.QCheckBox("Fine Eyelids")
        toolbar.addWidget(self.secondary)
        toolbar.addWidget(self.fine)
        toolbar.addStretch()
        fit = QtWidgets.QPushButton("Fit")
        fit.clicked.connect(self.fit_views)
        toolbar.addWidget(fit)
        layout.addLayout(toolbar)
        splitter = QtWidgets.QSplitter(enum(QtCore.Qt, "Orientation", "Horizontal"))
        layout.addWidget(splitter, 1)
        for panel in range(2):
            if not any(s["panel"] == panel for s in self.controls):
                continue
            scene = QtWidgets.QGraphicsScene(self)
            width, height = self.config["panels"][panel]["size"]
            scene.setSceneRect(0, 0, width, height)
            image = ROOT/self.config["panels"][panel]["background"]
            if image.suffix.lower() == ".svg":
                try:
                    from PySide6 import QtSvg
                except ImportError:
                    from PySide2 import QtSvg
                renderer = QtSvg.QSvgRenderer(str(image))
                if not renderer.isValid():
                    raise RuntimeError("Invalid picker background: " + str(image))
                pixmap = QtGui.QPixmap(int(width), int(height))
                pixmap.fill(QtGui.QColor("#989898"))
                painter = QtGui.QPainter(pixmap)
                renderer.render(painter)
                painter.end()
            else:
                pixmap = QtGui.QPixmap(str(image))
            if pixmap.isNull():
                raise RuntimeError("Missing picker background: " + str(image))
            backdrop = scene.addPixmap(pixmap)
            backdrop.setScale(float(width)/pixmap.width())
            backdrop.setZValue(-1)
            for shape in self.controls:
                if shape["panel"] == panel:
                    item = ControllerItem(shape, self)
                    self.items.append(item)
                    scene.addItem(item)
            view = PickerView(scene)
            self.views.append(view)
            splitter.addWidget(view)
        self.status = QtWidgets.QLabel()
        layout.addWidget(self.status)
        self.setStyleSheet("QDialog {background:#989898; color:#1a1a1a;} "
                           "QLabel,QCheckBox {color:#1a1a1a;} "
                           "QPushButton,QLineEdit {background:#b0b0b0; color:#1a1a1a; padding:4px;}")
        self.namespace.editingFinished.connect(self.refresh_targets)
        self.secondary.toggled.connect(self.update_layers)
        self.fine.toggled.connect(self.update_layers)
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_selection)
        self.timer.start(250)
        for event in ("SceneOpened", "NewSceneOpened"):
            self.jobs.append(cmds.scriptJob(event=[event, self.refresh_targets]))
        self.destroyed.connect(self.cleanup)
        self.update_layers()
        self.auto_namespace()
        self.refresh_targets()
        QtCore.QTimer.singleShot(0, self.fit_views)

    def auto_namespace(self):
        roots = cmds.ls("C_character_CTL", "*:C_character_CTL", long=True) or []
        roots = [node for node in roots if self.belongs_to_character(node)]
        if len(roots) == 1:
            leaf = roots[0].rsplit("|", 1)[-1]
            self.namespace.setText(leaf.rsplit(":", 1)[0] if ":" in leaf else "")

    def belongs_to_character(self, node):
        if self.instance_root_uuid:
            roots = cmds.ls(self.instance_root_uuid, long=True) or []
            return bool(roots) and (node == roots[0] or node.startswith(roots[0]+"|"))
        character = self.config["character"].lower()
        return any(part.rsplit(":", 1)[-1].lower() == character for part in node.split("|"))

    def namespace_from_selection(self, *_):
        selection = cmds.ls(selection=True, long=True) or []
        if not selection:
            cmds.warning("Select a character controller first.")
            return
        if not self.belongs_to_character(selection[0]):
            cmds.warning("Select a control belonging to " + self.config["character"] + ".")
            return
        leaf = selection[0].rsplit("|", 1)[-1]
        self.namespace.setText(leaf.rsplit(":", 1)[0] if ":" in leaf else "")
        self.refresh_targets()

    def target_name(self, name):
        namespace = self.namespace.text().strip().strip(":")
        return namespace + ":" + name if namespace else name

    def refresh_targets(self, *_):
        names = {n for s in self.controls for n in s["action.targets"]}
        matches = cmds.ls([self.target_name(n) for n in names], long=True) or []
        grouped = {}
        for node in matches:
            if not self.belongs_to_character(node):
                continue
            grouped.setdefault(node.rsplit("|", 1)[-1], []).append(node)
        self.resolved = {name: grouped[self.target_name(name)][0] for name in names
                         if len(grouped.get(self.target_name(name), [])) == 1}
        self.missing = sorted(name for name in names if not grouped.get(self.target_name(name)))
        self.ambiguous = {name: grouped[self.target_name(name)] for name in sorted(names)
                          if len(grouped.get(self.target_name(name), [])) > 1}
        self._last_selection = None
        self.status.setText("%s / %s controls found | Click: select | Shift: add | Ctrl: toggle | Wheel: zoom | Middle mouse: pan" % (len(self.resolved),len(names)))
        self.status.setToolTip("Missing: " + ", ".join(self.missing) + "\nAmbiguous: " +
                               "\n".join(name+": "+", ".join(paths) for name, paths in self.ambiguous.items()))
        self.update_selection()

    def select_targets(self, targets, modifiers):
        nodes = list(dict.fromkeys(self.resolved[name] for name in targets if name in self.resolved))
        if not nodes:
            self.refresh_targets()
            nodes = list(dict.fromkeys(self.resolved[name] for name in targets if name in self.resolved))
        if not nodes:
            cmds.warning("Picker target is absent. Load the matching character rig and check Namespace.")
            return
        if modifiers & CTRL:
            cmds.select(nodes, toggle=True)
        elif modifiers & SHIFT:
            cmds.select(nodes, add=True)
        else:
            cmds.select(nodes, replace=True)
        self.update_selection()

    def update_selection(self):
        selection = frozenset(cmds.ls(selection=True, long=True) or [])
        if selection == self._last_selection:
            return
        self._last_selection = selection
        for item in self.items:
            nodes = [self.resolved.get(n) for n in item.options["action.targets"]]
            selected = bool(nodes) and all(node in selection for node in nodes)
            if selected != item.selected_in_maya:
                item.selected_in_maya = selected
                item.update_style()

    def update_layers(self, *_):
        for item in self.items:
            layer = item.options.get("visibility_layer")
            item.setVisible(self.fine.isChecked() if layer == "Fine eyelids" else
                            self.secondary.isChecked() if layer == "Secondary" else True)

    def fit_views(self, *_):
        for view in self.views:
            view.fit()

    def cleanup(self, *_):
        for job in self.jobs:
            if cmds.scriptJob(exists=job):
                cmds.scriptJob(kill=job, force=True)
        self.jobs = []

    def closeEvent(self, event):
        self.timer.stop()
        self.cleanup()
        super(CharacterPicker, self).closeEvent(event)


def show(root_uuid=None):
    global _WINDOW
    if int(cmds.about(apiVersion=True)) < 20240000:
        raise RuntimeError("Character Picker requires Maya 2024 or later.")
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if widget.objectName() == "CharacterMayaPicker":
            widget.close()
    _WINDOW = CharacterPicker(main_window(), root_uuid=root_uuid)
    _WINDOW.show()
    _WINDOW.raise_()
    return _WINDOW
