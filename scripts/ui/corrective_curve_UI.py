"""
corrective_curve_UI.py
======================
UI del sistema POSE -> CURVA -> JOINTS (correctives.corrective_curve): el rigger
esculpe el perfil de la zona como curva por pose y una batería de joints monta la
curva y lo reproduce en el skinning.

Flujo:
  1. Dibuja la curva BASE por la zona (línea de nudillos, pliegue de muñeca…) y
     bindéala a las joints de deformación ("Bind curve to selected joints").
  2. Duplica la curva base ("Duplicate as target"), pon el rig en la pose
     problemática y esculpe los CVs del duplicado hasta que la silueta case
     (el resultado se ve en vivo: el blendShape va front-of-chain).
  3. Carga el driver (plug del canal seleccionado en el channelBox), ajusta el
     rango y "Create / Add pose": crea las joints sobre la curva (o añade la
     pose al setup existente si repites con la misma curva base).
  4. Pinta las joints nuevas en el skinCluster de correctivas (C_corrective_SKC).

Launch:
    from ui import corrective_curve_UI
    corrective_curve_UI.show()
"""

from importlib import reload

import maya.cmds as cmds
import maya.OpenMayaUI as omui

try:
    from PySide6 import QtWidgets, QtCore
    from PySide6.QtCore import Qt
    from shiboken6 import wrapInstance
except ImportError:
    from PySide2 import QtWidgets, QtCore
    from PySide2.QtCore import Qt
    from shiboken2 import wrapInstance

from utils import correctives

reload(correctives)

_WIN = None


def _maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget)


def _first_selected(type_filter=None):
    sel = cmds.ls(selection=True, long=False) or []
    if not sel:
        return None
    if type_filter:
        for s in sel:
            shapes = cmds.listRelatives(s, shapes=True) or []
            if cmds.nodeType(s) == type_filter or any(cmds.nodeType(sh) == type_filter for sh in shapes):
                return s
        return None
    return sel[0]


def _channelbox_plug():
    """Plug del canal seleccionado en el channelBox (nodo + attr marcados)."""
    cb = "mainChannelBox"
    nodes = cmds.channelBox(cb, query=True, mainObjectList=True) or []
    attrs = cmds.channelBox(cb, query=True, selectedMainAttributes=True) or []
    if nodes and attrs:
        return f"{nodes[0]}.{attrs[0]}"
    return None


class CorrectiveCurveUI(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super(CorrectiveCurveUI, self).__init__(parent or _maya_main_window())
        self.setWindowTitle("Corrective Curve — Pose → Curve → Joints")
        self.setMinimumWidth(420)
        self.setWindowFlags(self.windowFlags() ^ Qt.WindowContextHelpButtonHint)
        self._build()

    # ------------------------------------------------------------------ layout

    def _build(self):
        lay = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)

        self.name_le = QtWidgets.QLineEdit()
        self.name_le.setPlaceholderText("L_knuckles")
        form.addRow("Name prefix:", self.name_le)

        self.curve_le = QtWidgets.QLineEdit()
        form.addRow("Base curve:", self._pick_row(self.curve_le, "nurbsCurve"))

        self.parent_le = QtWidgets.QLineEdit()
        form.addRow("Parent joint:", self._pick_row(self.parent_le, "joint"))

        self.target_le = QtWidgets.QLineEdit()
        form.addRow("Target curve (pose):", self._pick_row(self.target_le, "nurbsCurve"))

        self.driver_le = QtWidgets.QLineEdit()
        self.driver_le.setPlaceholderText("nodo.atributo (bend_driver, ctl, peso de BLS…)")
        drv_row = QtWidgets.QWidget()
        drv_lay = QtWidgets.QHBoxLayout(drv_row)
        drv_lay.setContentsMargins(0, 0, 0, 0)
        drv_lay.setSpacing(4)
        drv_lay.addWidget(self.driver_le)
        drv_btn = QtWidgets.QPushButton("Load channel")
        drv_btn.setToolTip("Coge el canal seleccionado en el channelBox")
        drv_btn.clicked.connect(self._load_channel)
        drv_lay.addWidget(drv_btn)
        form.addRow("Driver plug:", drv_row)

        rng_row = QtWidgets.QWidget()
        rng_lay = QtWidgets.QHBoxLayout(rng_row)
        rng_lay.setContentsMargins(0, 0, 0, 0)
        self.min_sb = QtWidgets.QDoubleSpinBox()
        self.min_sb.setRange(-10000, 10000)
        self.min_sb.setValue(0.0)
        self.max_sb = QtWidgets.QDoubleSpinBox()
        self.max_sb.setRange(-10000, 10000)
        self.max_sb.setValue(1.0)
        rng_lay.addWidget(QtWidgets.QLabel("min"))
        rng_lay.addWidget(self.min_sb)
        rng_lay.addWidget(QtWidgets.QLabel("max"))
        rng_lay.addWidget(self.max_sb)
        form.addRow("Driver range:", rng_row)

        self.joints_sb = QtWidgets.QSpinBox()
        self.joints_sb.setRange(1, 64)
        self.joints_sb.setValue(5)
        form.addRow("Num joints:", self.joints_sb)

        lay.addLayout(form)

        helpers = QtWidgets.QHBoxLayout()
        bind_btn = QtWidgets.QPushButton("Bind curve to selected joints")
        bind_btn.setToolTip("skinCluster de la curva base a las joints seleccionadas\n"
                            "(la curva DEBE seguir al rig)")
        bind_btn.clicked.connect(self._bind_curve)
        helpers.addWidget(bind_btn)
        dup_btn = QtWidgets.QPushButton("Duplicate as target")
        dup_btn.setToolTip("Duplica la curva base como target de pose para esculpir")
        dup_btn.clicked.connect(self._duplicate_target)
        helpers.addWidget(dup_btn)
        lay.addLayout(helpers)

        create_btn = QtWidgets.QPushButton("Create / Add pose")
        create_btn.setStyleSheet("font-weight: bold;")
        create_btn.clicked.connect(self._create)
        lay.addWidget(create_btn)

        self.status = QtWidgets.QLabel("")
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setWordWrap(True)
        lay.addWidget(self.status)

    def _pick_row(self, line_edit, type_filter):
        row = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)
        h.addWidget(line_edit)
        btn = QtWidgets.QPushButton("Pick")
        btn.setFixedWidth(50)
        btn.clicked.connect(lambda: self._pick(line_edit, type_filter))
        h.addWidget(btn)
        return row

    # ------------------------------------------------------------------ slots

    def _pick(self, line_edit, type_filter):
        node = _first_selected(type_filter)
        if node:
            line_edit.setText(node)
        else:
            self.status.setText(f"Selecciona un nodo de tipo {type_filter}")

    def _load_channel(self):
        plug = _channelbox_plug()
        if plug:
            self.driver_le.setText(plug)
        else:
            self.status.setText("Marca un canal en el channelBox primero")

    def _bind_curve(self):
        curve = self.curve_le.text()
        jnts = [j for j in (cmds.ls(selection=True) or []) if cmds.nodeType(j) == "joint"]
        if not (curve and cmds.objExists(curve) and jnts):
            self.status.setText("Necesito la curva base en el campo y joints seleccionadas")
            return
        skc = cmds.skinCluster(jnts, curve, toSelectedBones=True,
                               name=f"{curve}_SKC")[0]
        self.status.setText(f"Curva bindeada: {skc} ({len(jnts)} joints)")

    def _duplicate_target(self):
        curve = self.curve_le.text()
        if not (curve and cmds.objExists(curve)):
            self.status.setText("Pon primero la curva base")
            return
        dup = cmds.duplicate(curve, name=f"{curve}_target#")[0]
        # el duplicado es el REST: se esculpe mientras el rig está en la pose
        for attr in ("tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz"):
            cmds.setAttr(f"{dup}.{attr}", lock=False)
        self.target_le.setText(dup)
        cmds.select(dup)
        self.status.setText(f"Target creado: {dup} — esculpe sus CVs con el rig posado")

    def _create(self):
        name = self.name_le.text().strip()
        curve = self.curve_le.text().strip()
        target = self.target_le.text().strip()
        driver = self.driver_le.text().strip()
        parent = self.parent_le.text().strip() or None
        if not (name and curve and target and driver):
            self.status.setText("Faltan campos: name, base curve, target y driver")
            return
        for node in (curve, target):
            if not cmds.objExists(node):
                self.status.setText(f"No existe: {node}")
                return
        node, _, attr = driver.partition(".")
        if not (attr and cmds.objExists(node) and
                cmds.attributeQuery(attr.split("[")[0], node=node, exists=True)):
            self.status.setText(f"Driver no válido: {driver}")
            return
        result = correctives.corrective_curve(
            name, curve, [(target, driver, self.min_sb.value(), self.max_sb.value())],
            num_joints=self.joints_sb.value(), parent_joint=parent)
        self.status.setText(
            f"OK: {len(result['joints'])} joints sobre {curve} — "
            f"pinta sus pesos en el skinCluster de correctivas (*corrective*)")


def show():
    global _WIN
    try:
        _WIN.close()
        _WIN.deleteLater()
    except Exception:
        pass
    _WIN = CorrectiveCurveUI()
    _WIN.show()
