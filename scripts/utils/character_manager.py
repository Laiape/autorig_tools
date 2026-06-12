import os
import datetime
import webbrowser
from functools import partial
from importlib import reload

import maya.cmds as cmds
import maya.mel as mel
import maya.OpenMayaUI as omui

from tools import skin_manager_api
from utils import curve_tool, guides_manager, create_rig
from utils import data_manager
from utils import ui_utils

try:
    from PySide6 import QtWidgets, QtCore, QtGui
    from shiboken6 import wrapInstance
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui
    from shiboken2 import wrapInstance

ALLOWED_ENDINGS = [".ma", ".mb", ".guides", ".curves", ".json", ".skc"]

# ── Palette ──────────────────────────────────────────────────────────────────
C_BG0    = "#b0b0b0"   # medium-dark grey — main bg, header
C_BG1    = "#a4a4a4"   # slightly darker panel — sidebar, footer
C_BG2    = "#989898"   # inputs, table bg
C_BG3    = "#8c8c8c"   # hover / selected bg
C_BORDER = "#787878"   # borders
C_TEXT   = "#1a1a1a"   # main text
C_DIM    = "#555555"   # secondary / dim text
C_BLUE   = "#2667a6"   # dark blue — accent text, borders, selected states
C_BLUE2  = "#5b9bd5"   # medium blue — button fills, bar
C_GREEN  = "#3a8000"   # positive actions
C_RED    = "#cc2222"   # destructive actions
C_YELLOW = "#5b9bd5"   # blue alias

SS_BASE = f"""
QWidget {{ background:{C_BG2}; color:{C_TEXT}; font-family:'Sabandija'; font-size:11px; font-weight:bold; }}
QLabel  {{ background:transparent; font-weight:bold; }}

QMenuBar {{ background:{C_BG0}; color:{C_DIM}; border-bottom:1px solid {C_BORDER}; padding:2px 4px; }}
QMenuBar::item {{ padding:4px 10px; }}
QMenuBar::item:selected {{ background:{C_BG3}; color:{C_BLUE}; }}
QMenu {{ background:{C_BG1}; border:1px solid {C_BORDER}; color:{C_TEXT}; padding:2px; }}
QMenu::item {{ padding:5px 24px; }}
QMenu::item:selected {{ background:{C_BG3}; color:{C_BLUE}; }}
QMenu::separator {{ background:{C_BORDER}; height:1px; margin:3px 8px; }}

QListWidget {{
    background:{C_BG1}; border:none;
    outline:none; padding:2px;
}}
QListWidget::item {{ padding:7px 12px; color:{C_TEXT}; border-left:2px solid transparent; }}
QListWidget::item:selected {{ background:{C_BG3}; color:{C_BLUE}; border-left:2px solid {C_BLUE}; }}
QListWidget::item:hover:!selected {{ background:{C_BG3}; border-left:2px solid {C_BORDER}; }}

QLineEdit {{
    background:{C_BG0}; border:none; border-bottom:1px solid {C_BORDER};
    border-radius:0px; padding:5px 8px; color:{C_TEXT};
}}
QLineEdit:focus {{ border-bottom-color:{C_BLUE}; }}

QTabWidget::pane {{ border:none; border-top:1px solid {C_BORDER}; background:{C_BG2}; }}
QTabBar::tab {{
    background:transparent; color:{C_DIM}; padding:8px 18px;
    border:none; border-bottom:2px solid transparent;
    margin-right:0px; font-size:9px; letter-spacing:3px; font-weight:bold;
}}
QTabBar::tab:selected {{ color:{C_BLUE}; border-bottom:2px solid {C_BLUE}; }}
QTabBar::tab:hover:!selected {{ color:{C_TEXT}; }}

QTableWidget {{
    background:{C_BG1}; border:none; gridline-color:{C_BG2};
    alternate-background-color:{C_BG0}; selection-background-color:{C_BG3}; outline:none;
}}
QTableWidget::item {{ padding:5px 10px; border:none; color:{C_TEXT}; }}
QTableWidget::item:selected {{ background:{C_BG3}; color:{C_BLUE}; }}
QHeaderView::section {{
    background:{C_BG0}; border:none; border-bottom:1px solid {C_BORDER};
    padding:5px 10px; font-size:9px; letter-spacing:3px; color:{C_DIM}; font-weight:bold;
}}
QScrollBar:vertical {{ background:transparent; width:4px; border:none; }}
QScrollBar::handle:vertical {{ background:{C_BORDER}; border-radius:2px; min-height:20px; }}
QScrollBar::handle:vertical:hover {{ background:{C_BLUE}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0px; }}
QScrollBar:horizontal {{ background:transparent; height:4px; border:none; }}
QScrollBar::handle:horizontal {{ background:{C_BORDER}; border-radius:2px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width:0px; }}

QSplitter::handle {{ background:{C_BORDER}; }}
QSplitter::handle:horizontal {{ width:1px; }}

QComboBox {{
    background:{C_BG1}; border:none; border-bottom:1px solid {C_BORDER};
    border-radius:0px; padding:4px 8px; color:{C_TEXT};
}}
QComboBox:hover {{ border-bottom-color:{C_BLUE}; }}
QComboBox::drop-down {{ border:none; width:20px; }}
QComboBox QAbstractItemView {{
    background:{C_BG2}; border:1px solid {C_BLUE};
    selection-background-color:{C_BG3}; color:{C_TEXT};
}}

QToolTip {{ background:{C_BG3}; color:{C_TEXT}; border:1px solid {C_BORDER}; padding:4px; }}
"""


def _btn(text, color=C_BG3, text_color=C_TEXT, border=C_BORDER,
         hover_bg=None, hover_text=None, size=None, bold=False, letter_spacing=0,
         accent=False):
    hover_bg   = hover_bg   or C_BG3
    hover_text = hover_text or C_BLUE
    ls = f"letter-spacing:{letter_spacing}px;" if letter_spacing else ""
    fw = "font-weight:bold;" if bold else ""
    left_border = f"border-left:2px solid {C_BLUE};" if accent else "border-left:2px solid transparent;"
    b = QtWidgets.QPushButton(text.upper())
    b.setStyleSheet(f"""
        QPushButton {{
            background:{color}; color:{text_color};
            border:none; border-bottom:1px solid {C_BORDER};
            {left_border}
            border-radius:0px; padding:6px 14px; {ls} {fw}
        }}
        QPushButton:hover {{
            background:{hover_bg}; color:{hover_text};
            border-left:2px solid {C_BLUE};
        }}
        QPushButton:pressed {{ background:{C_BG0}; color:{C_BLUE}; }}
    """)
    if size:
        b.setFixedSize(*size)
    return b


def _lighten(hex_color):
    c = QtGui.QColor(hex_color)
    return c.lighter(115).name()


def get_maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget)


def get_assets_path():
    complete_path = os.path.realpath(__file__)
    if "Script Editor" in complete_path or "<string>" in complete_path:
        workspace = cmds.workspace(q=True, rootDirectory=True)
        path = os.path.join(workspace, "assets")
    else:
        sep_token = os.sep + "scripts"
        if sep_token in complete_path:
            relative_path = complete_path.split(sep_token)[0]
        else:
            relative_path = os.path.dirname(os.path.dirname(complete_path))
        path = os.path.join(relative_path, "assets")
    if not os.path.exists(path):
        os.makedirs(path)
    return path


# ─────────────────────────────────────────────────────────────────────────────
#  VERSION TAB
# ─────────────────────────────────────────────────────────────────────────────
class VersionTab(QtWidgets.QWidget):

    EXT_MAP = {
        "guides":       ".guides",
        "curves":       ".curves",
        "models":       ".ma",
        "skin_clusters":".skc",
    }

    def __init__(self, asset_path, sub_folder, parent=None):
        super().__init__(parent)
        self.asset_path = asset_path
        self.sub_folder = sub_folder
        self.full_path  = os.path.join(asset_path, sub_folder)
        os.makedirs(self.full_path, exist_ok=True)
        self._build()
        self.refresh()

    def _build(self):
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(6)

        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["VER", "FILE", "▶", "⟳"])
        self.table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.Fixed)
        self.table.setColumnWidth(2, 32)
        self.table.setColumnWidth(3, 32)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        lay.addWidget(self.table)

        row = QtWidgets.QHBoxLayout()
        self.btn_save = _btn("＋  SAVE VERSION", C_BLUE2, "#0d0d10", bold=True, letter_spacing=1, accent=True)
        self.btn_imp  = _btn("↓  IMPORT SELECTED", C_BG1, C_TEXT, bold=True, letter_spacing=1)
        self.btn_save.clicked.connect(self.save_new_version)
        self.btn_imp.clicked.connect(self.import_selected)
        row.addWidget(self.btn_save)
        row.addWidget(self.btn_imp)
        lay.addLayout(row)

    def refresh(self):
        self.table.setRowCount(0)
        if not os.path.exists(self.full_path):
            return
        ext = self.EXT_MAP.get(self.sub_folder, "")
        files = sorted(
            [f for f in os.listdir(self.full_path)
             if any(f.endswith(e) for e in ALLOWED_ENDINGS)],
            reverse=True
        )
        for f in files:
            row = self.table.rowCount()
            self.table.insertRow(row)

            ver = f.split("_v")[-1].split(".")[0] if "_v" in f else "—"
            mtime = os.path.getmtime(os.path.join(self.full_path, f))
            date  = datetime.datetime.fromtimestamp(mtime).strftime("%d/%m/%y")

            vi = QtWidgets.QTableWidgetItem(ver)
            vi.setTextAlignment(QtCore.Qt.AlignCenter)
            vi.setForeground(QtGui.QBrush(QtGui.QColor(C_BLUE)))
            self.table.setItem(row, 0, vi)

            ni = QtWidgets.QTableWidgetItem(f"  {f}   [{date}]")
            ni.setToolTip(os.path.join(self.full_path, f))
            self.table.setItem(row, 1, ni)

            for col, icon, color, border, tip, fn in (
                (2, "▶", C_BLUE, C_BLUE, f"Import {f}", partial(self.import_file, f)),
                (3, "⟳", C_RED,  C_RED,  f"Overwrite {f}", partial(self.replace_file, f)),
            ):
                b = QtWidgets.QPushButton(icon)
                b.setFixedSize(26, 22)
                b.setToolTip(tip)
                b.setStyleSheet(f"""
                    QPushButton {{
                        background:{C_BG3}; border:1px solid {border};
                        color:{color}; font-weight:bold; border-radius:3px;
                    }}
                    QPushButton:hover {{ background:{color}; color:#fff; }}
                """)
                b.clicked.connect(fn)
                w = QtWidgets.QWidget()
                h = QtWidgets.QHBoxLayout(w)
                h.setContentsMargins(0, 0, 0, 0)
                h.setAlignment(QtCore.Qt.AlignCenter)
                h.addWidget(b)
                self.table.setCellWidget(row, col, w)

    def _next_version_path(self):
        ext   = self.EXT_MAP.get(self.sub_folder, ".ma")
        files = [f for f in os.listdir(self.full_path) if f.endswith(ext)]
        ver   = 1
        if files:
            files.sort()
            try:
                ver = int(files[-1].split("_v")[-1].split(".")[0]) + 1
            except Exception:
                pass
        name = f"{os.path.basename(self.asset_path)}_v{ver:03d}{ext}"
        return os.path.join(self.full_path, name)

    def save_new_version(self):
        path = self._next_version_path()
        self._export(path)

    def replace_file(self, filename):
        path = os.path.join(self.full_path, filename)
        reply = QtWidgets.QMessageBox.question(
            self, "Overwrite", f"Overwrite\n{filename}?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if reply == QtWidgets.QMessageBox.Yes:
            self._export(path)

    def _export(self, path):
        try:
            if self.sub_folder == "guides":
                reload(guides_manager)
                guides_manager.get_guides_info(path=path)
            elif self.sub_folder == "curves":
                reload(curve_tool)
                curve_tool.get_all_ctl_curves_data(path=path)
            elif self.sub_folder == "models":
                cmds.file(rename=path)
                cmds.file(save=True, type="mayaAscii")
            elif self.sub_folder == "skin_clusters":
                reload(skin_manager_api)
                skin_manager_api.SkinManager().export_skins(path=path)
            ver = os.path.basename(path)
            cmds.inViewMessage(amg=f"<hl>Saved</hl> {ver}", pos="midCenter", fade=True)
            self.refresh()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Export Error", str(e))

    def import_selected(self):
        row = self.table.currentRow()
        if row < 0:
            cmds.warning("No file selected.")
            return
        filename = self.table.item(row, 1).text().strip().split("   ")[0]
        self.import_file(filename)

    def import_file(self, filename):
        path = os.path.join(self.full_path, filename)
        try:
            if self.sub_folder == "guides":
                reload(guides_manager)
                guides_manager.load_guides_info(filePath=path)
            elif self.sub_folder == "curves":
                reload(curve_tool)
                curve_tool.load_all_ctl_curves_data(path=path)
            elif self.sub_folder == "models":
                cmds.file(path, open=True, force=True)
            elif self.sub_folder == "skin_clusters":
                reload(skin_manager_api)
                skin_manager_api.SkinManager().import_skins(path=path)
            cmds.inViewMessage(amg=f"<hl>Imported</hl> {filename}", pos="midCenter", fade=True)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Import Error", str(e))


# ─────────────────────────────────────────────────────────────────────────────
#  QUICK TOOLS PANEL
# ─────────────────────────────────────────────────────────────────────────────
class QuickToolsWidget(QtWidgets.QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(10)

        def section(title):
            lbl = QtWidgets.QLabel(title.upper())
            lbl.setStyleSheet(f"""
                color:{C_DIM}; font-size:8px; letter-spacing:4px;
                font-weight:bold; padding:10px 0 4px 0;
                border-bottom:1px solid {C_BORDER};
            """)
            lay.addWidget(lbl)

        def row(*btns):
            r = QtWidgets.QHBoxLayout()
            r.setSpacing(4)
            for b in btns:
                r.addWidget(b)
            lay.addLayout(r)

        # ── CONTROLS ──────────────────────────────────────────────────────────
        section("CONTROLS")

        b_reset = _btn("Reset All CTLs", C_BG3, C_TEXT)
        b_reset.setToolTip("Set all *_CTL transforms to 0/0/0 T/R/S")
        b_reset.clicked.connect(self.reset_all_controls)

        b_mirror_l = _btn("Mirror  L → R", C_BG3, C_TEXT)
        b_mirror_l.setToolTip("Mirror selected CTL values from Left to Right")
        b_mirror_l.clicked.connect(lambda: self.mirror_controls("L", "R"))

        b_mirror_r = _btn("Mirror  R → L", C_BG3, C_TEXT)
        b_mirror_r.setToolTip("Mirror selected CTL values from Right to Left")
        b_mirror_r.clicked.connect(lambda: self.mirror_controls("R", "L"))

        row(b_reset)
        row(b_mirror_l, b_mirror_r)

        # ── VISIBILITY ────────────────────────────────────────────────────────
        section("VISIBILITY")

        b_jnts = _btn("Toggle Joints", C_BG3, C_TEXT)
        b_jnts.clicked.connect(lambda: self.toggle_type_vis("joint"))

        b_ctls = _btn("Toggle Controls", C_BG3, C_TEXT)
        b_ctls.clicked.connect(lambda: self.toggle_vis_group("*CTL*"))

        b_geo = _btn("Toggle Geo", C_BG3, C_TEXT)
        b_geo.clicked.connect(lambda: self.toggle_vis_group("*geo_GRP*"))

        row(b_jnts, b_ctls, b_geo)

        # ── SCENE ─────────────────────────────────────────────────────────────
        section("SCENE")

        b_del_hist = _btn("Delete History", C_BG3, C_TEXT)
        b_del_hist.setToolTip("Delete non-deformer history on selected meshes")
        b_del_hist.clicked.connect(self.delete_history)

        b_freeze = _btn("Freeze Transforms", C_BG3, C_TEXT)
        b_freeze.clicked.connect(self.freeze_transforms)

        b_center = _btn("Center Pivot", C_BG3, C_TEXT)
        b_center.clicked.connect(lambda: cmds.xform(cmds.ls(sl=True), cp=True))

        row(b_del_hist, b_freeze)
        row(b_center)

        b_clean = _btn("Delete Unused Nodes", C_BG3, C_TEXT)
        b_clean.clicked.connect(self.delete_unused_nodes)

        b_zero_jnts = _btn("Zero Joint Orients", C_BG3, C_TEXT)
        b_zero_jnts.setToolTip("Zero out joint orient on selected joints")
        b_zero_jnts.clicked.connect(self.zero_joint_orients)

        row(b_clean, b_zero_jnts)

        # ── SKINNING ──────────────────────────────────────────────────────────
        section("SKINNING")

        b_quick_bind = _btn("Quick Bind (sel jnts + mesh)", C_BG3, C_TEXT)
        b_quick_bind.setToolTip("Select joints then mesh → smooth bind")
        b_quick_bind.clicked.connect(self.quick_bind)

        b_copy_skin = _btn("Copy Skin Weights", C_BG3, C_TEXT)
        b_copy_skin.setToolTip("Copy skin weights from first mesh to selected meshes")
        b_copy_skin.clicked.connect(self.copy_skin_weights)

        b_unbind = _btn("Unbind Skin", C_RED, C_TEXT, C_RED)
        b_unbind.clicked.connect(self.unbind_skin)

        row(b_quick_bind)
        row(b_copy_skin, b_unbind)

        # ── PROXY LOCATOR ─────────────────────────────────────────────────────
        section("PROXY LOCATOR")

        b_proxy = _btn("Assign Proxy Locators", C_BG3, C_TEXT)
        b_proxy.setToolTip("Auto-detect body mesh and assign proxy locators to all *_CTL")
        b_proxy.clicked.connect(self.run_proxy_locator)

        b_del_proxy = _btn("Remove Proxy Locators", C_RED, C_TEXT, C_RED)
        b_del_proxy.clicked.connect(self.remove_proxy_locators)

        row(b_proxy, b_del_proxy)

        lay.addStretch()

    # ── CONTROLS ──────────────────────────────────────────────────────────────
    def reset_all_controls(self):
        ctls = cmds.ls("*_CTL", type="transform") or []
        if not ctls:
            cmds.warning("No *_CTL controls found.")
            return
        for ctl in ctls:
            for attr, val in (("tx",0),("ty",0),("tz",0),
                               ("rx",0),("ry",0),("rz",0),
                               ("sx",1),("sy",1),("sz",1)):
                try:
                    if not cmds.getAttr(f"{ctl}.{attr}", lock=True):
                        cmds.setAttr(f"{ctl}.{attr}", val)
                except Exception:
                    pass
        cmds.inViewMessage(amg=f"Reset <hl>{len(ctls)}</hl> controls", pos="midCenter", fade=True)

    def mirror_controls(self, src, dst):
        sel = cmds.ls(sl=True, type="transform") or []
        mirrored = 0
        for node in sel:
            if f"_{src}_" in node or node.startswith(f"{src}_"):
                partner = node.replace(f"_{src}_", f"_{dst}_").replace(f"{src}_", f"{dst}_", 1)
                if cmds.objExists(partner):
                    for attr in ("tx","ty","tz","rx","ry","rz"):
                        try:
                            val = cmds.getAttr(f"{node}.{attr}")
                            mirror_val = -val if attr in ("tx","ry","rz") else val
                            cmds.setAttr(f"{partner}.{attr}", mirror_val)
                        except Exception:
                            pass
                    mirrored += 1
        cmds.inViewMessage(amg=f"Mirrored <hl>{mirrored}</hl> controls", pos="midCenter", fade=True)

    # ── VISIBILITY ────────────────────────────────────────────────────────────
    def toggle_type_vis(self, node_type):
        nodes = cmds.ls(type=node_type) or []
        if not nodes:
            return
        cur = cmds.getAttr(f"{nodes[0]}.visibility")
        for n in nodes:
            try:
                cmds.setAttr(f"{n}.visibility", not cur)
            except Exception:
                pass

    def toggle_vis_group(self, pattern):
        nodes = cmds.ls(pattern, type="transform") or []
        if not nodes:
            cmds.warning(f"No nodes matching {pattern}")
            return
        cur = cmds.getAttr(f"{nodes[0]}.visibility")
        for n in nodes:
            try:
                cmds.setAttr(f"{n}.visibility", not cur)
            except Exception:
                pass

    # ── SCENE ─────────────────────────────────────────────────────────────────
    def delete_history(self):
        sel = cmds.ls(sl=True) or []
        if not sel:
            cmds.warning("Select meshes first.")
            return
        cmds.bakePartialHistory(sel, prePostDeformers=True)
        cmds.inViewMessage(amg="History deleted", pos="midCenter", fade=True)

    def freeze_transforms(self):
        sel = cmds.ls(sl=True) or []
        if not sel:
            cmds.warning("Select objects first.")
            return
        cmds.makeIdentity(sel, apply=True, t=True, r=True, s=True)
        cmds.inViewMessage(amg="Transforms frozen", pos="midCenter", fade=True)

    def delete_unused_nodes(self):
        mel.eval("MLdeleteUnused;")
        cmds.inViewMessage(amg="Unused nodes deleted", pos="midCenter", fade=True)

    def zero_joint_orients(self):
        jnts = cmds.ls(sl=True, type="joint") or []
        if not jnts:
            cmds.warning("Select joints first.")
            return
        for j in jnts:
            for attr in ("jointOrientX","jointOrientY","jointOrientZ"):
                try:
                    cmds.setAttr(f"{j}.{attr}", 0)
                except Exception:
                    pass
        cmds.inViewMessage(amg=f"Zeroed <hl>{len(jnts)}</hl> joint orients", pos="midCenter", fade=True)

    # ── SKINNING ──────────────────────────────────────────────────────────────
    def quick_bind(self):
        sel = cmds.ls(sl=True) or []
        if len(sel) < 2:
            cmds.warning("Select joints then mesh.")
            return
        mesh   = sel[-1]
        joints = sel[:-1]
        cmds.skinCluster(joints + [mesh], toSelectedBones=True,
                         bindMethod=0, skinMethod=0, normalizeWeights=1)
        cmds.inViewMessage(amg=f"Bound <hl>{mesh}</hl>", pos="midCenter", fade=True)

    def copy_skin_weights(self):
        sel = cmds.ls(sl=True) or []
        if len(sel) < 2:
            cmds.warning("Select source mesh then target mesh(es).")
            return
        src = sel[0]
        for dst in sel[1:]:
            try:
                cmds.copySkinWeights(sourceSkin=src, destinationSkin=dst,
                                     noMirror=True, surfaceAssociation="closestPoint",
                                     influenceAssociation="closestJoint")
            except Exception as e:
                cmds.warning(f"Could not copy to {dst}: {e}")
        cmds.inViewMessage(amg="Skin weights copied", pos="midCenter", fade=True)

    def unbind_skin(self):
        sel = cmds.ls(sl=True) or []
        if not sel:
            cmds.warning("Select skinned mesh(es).")
            return
        for obj in sel:
            hist = cmds.listHistory(obj) or []
            scs  = [n for n in hist if cmds.nodeType(n) == "skinCluster"]
            for sc in scs:
                cmds.skinCluster(sc, edit=True, unbind=True)
        cmds.inViewMessage(amg="Skin unbound", pos="midCenter", fade=True)

    # ── PROXY LOCATOR ─────────────────────────────────────────────────────────
    def run_proxy_locator(self):
        try:
            from tools import proxy_locator
            proxy_locator.assign_all_proxy_locators(mesh_transform=None, ctl_suffix="_CTL", radius=10.0)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", str(e))

    def remove_proxy_locators(self):
        nodes = cmds.ls(type="proxyLocator") or []
        if nodes:
            cmds.delete(nodes)
            cmds.inViewMessage(amg=f"Removed <hl>{len(nodes)}</hl> proxy locators",
                               pos="midCenter", fade=True)
        else:
            cmds.warning("No proxy locators found in scene.")


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN WINDOW
# ─────────────────────────────────────────────────────────────────────────────
class AssetManagerUI(QtWidgets.QWidget):

    def __init__(self, parent=get_maya_main_window()):
        super().__init__(parent)
        self.setWindowFlags(QtCore.Qt.Window)
        self.setWindowTitle("Character Manager  —  AutoRig Tools")
        self.resize(820, 620)
        self.setMinimumSize(640, 480)

        self.assets_path   = get_assets_path()
        self.current_asset = None
        self.settings      = QtCore.QSettings("AutoRigTools", "CharacterManager")

        self._build_ui()
        self.refresh_assets()
        self._restore_session()
        ui_utils.apply_maya_style(self)

    # ── BUILD ─────────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._make_menubar())
        root.addWidget(self._make_header())

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.addWidget(self._make_sidebar())
        splitter.addWidget(self._make_center())
        splitter.setSizes([280, 540])
        root.addWidget(splitter, 1)

        root.addWidget(self._make_footer())

    def _make_menubar(self):
        bar = QtWidgets.QMenuBar()

        m_file = bar.addMenu("File")
        m_file.addAction("New Scene",        lambda: cmds.file(new=True, force=True))
        m_file.addAction("Open Scene…",      lambda: cmds.file(open=True, force=True, prompt=True))
        m_file.addAction("Save Scene",       lambda: cmds.file(save=True))
        m_file.addSeparator()
        m_file.addAction("Open Assets Folder", self._open_assets_folder)

        m_tools = bar.addMenu("Tools")
        for name in ("ngSkinTools", "Rabbit Skinning Tools", "Kangaroo", "mGear", "AdonisFx"):
            m_tools.addAction(name, partial(self._open_external, name))

        m_help = bar.addMenu("Help")
        m_help.addAction("GitHub",   lambda: webbrowser.open("https://github.com/Laiape/autorig_tools"))
        m_help.addAction("LinkedIn", lambda: webbrowser.open("https://www.linkedin.com/in/laia-peris-arantzamendi-6b9809277/"))
        m_help.addAction("Web",      lambda: webbrowser.open("https://laiape.github.io/"))
        m_help.addSeparator()
        m_help.addAction("About", lambda: QtWidgets.QMessageBox.information(
            self, "About", "AutoRig Tools v1.0\nCreated by Laia Peris"))
        return bar

    def _make_header(self):
        w = QtWidgets.QWidget()
        w.setFixedHeight(40)
        w.setStyleSheet(f"background:{C_BG0}; border-bottom:1px solid {C_BORDER};")
        lay = QtWidgets.QHBoxLayout(w)
        lay.setContentsMargins(16, 0, 16, 0)

        bar = QtWidgets.QFrame()
        bar.setFixedSize(3, 18)
        bar.setStyleSheet(f"background:{C_BLUE}; border:none;")
        lay.addWidget(bar)
        lay.addSpacing(10)

        title = QtWidgets.QLabel("CHARACTER MANAGER")
        title.setStyleSheet(f"color:{C_TEXT}; font-size:11px; font-weight:bold; letter-spacing:5px;")
        lay.addWidget(title)
        lay.addStretch()

        self.lbl_asset = QtWidgets.QLabel("—")
        self.lbl_asset.setStyleSheet(f"color:{C_BLUE}; font-size:11px; letter-spacing:2px; font-weight:bold;")
        lay.addWidget(self.lbl_asset)
        return w

    def _make_sidebar(self):
        w = QtWidgets.QWidget()
        w.setStyleSheet(f"background:{C_BG1}; border-right:1px solid {C_BORDER};")
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(8, 10, 8, 10)
        lay.setSpacing(6)

        # Search
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("  search asset…")
        self.search.textChanged.connect(self._filter_assets)
        lay.addWidget(self.search)

        # Asset list
        self.asset_list = QtWidgets.QListWidget()
        self.asset_list.currentItemChanged.connect(self._on_asset_selected)
        lay.addWidget(self.asset_list, 1)

        # Thumbnail
        thumb_wrap = QtWidgets.QWidget()
        thumb_wrap.setStyleSheet(f"background:transparent;")
        tw = QtWidgets.QVBoxLayout(thumb_wrap)
        tw.setContentsMargins(0, 4, 0, 0)
        tw.setSpacing(2)

        cam_row = QtWidgets.QHBoxLayout()
        cam_row.addStretch()
        self.cam_btn = QtWidgets.QPushButton("⊙")
        self.cam_btn.setFixedSize(22, 22)
        self.cam_btn.setToolTip("Take viewport screenshot")
        self.cam_btn.setStyleSheet(f"""
            QPushButton {{ background:transparent; border:none; color:{C_DIM}; font-size:14px; }}
            QPushButton:hover {{ color:{C_BLUE}; }}
        """)
        self.cam_btn.clicked.connect(self.take_screenshot)
        cam_row.addWidget(self.cam_btn)
        tw.addLayout(cam_row)

        self.thumbnail = QtWidgets.QLabel("NO IMAGE")
        self.thumbnail.setFixedSize(264, 240)
        self.thumbnail.setAlignment(QtCore.Qt.AlignCenter)
        self.thumbnail.setStyleSheet(f"""
            background:{C_BG0}; border:none; border-top:2px solid {C_BORDER};
            color:{C_DIM}; font-size:9px; letter-spacing:3px;
        """)
        tw.addWidget(self.thumbnail)
        lay.addWidget(thumb_wrap)

        # New / Delete asset
        btn_row = QtWidgets.QHBoxLayout()
        b_new = _btn("＋", C_BG3, C_GREEN, C_GREEN, size=(36, 28))
        b_new.setToolTip("New asset")
        b_new.clicked.connect(self.new_asset)
        b_del = _btn("✕", C_BG3, C_RED, C_RED, size=(36, 28))
        b_del.setToolTip("Delete asset folder")
        b_del.clicked.connect(self.delete_asset)
        btn_row.addWidget(b_new)
        btn_row.addStretch()
        btn_row.addWidget(b_del)
        lay.addLayout(btn_row)

        return w

    def _make_center(self):
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.tabs = QtWidgets.QTabWidget()
        lay.addWidget(self.tabs, 1)
        return w

    def _make_footer(self):
        w = QtWidgets.QWidget()
        w.setFixedHeight(56)
        w.setStyleSheet(f"background:{C_BG1}; border-top:1px solid {C_BORDER};")
        lay = QtWidgets.QHBoxLayout(w)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(8)

        self.btn_load = _btn("LOAD SETTINGS", C_BG1, C_DIM, bold=True, letter_spacing=2)
        self.btn_load.setMinimumHeight(36)
        self.btn_load.setToolTip("Set active asset without building")
        self.btn_load.clicked.connect(self.run_load_settings)

        self.btn_build = QtWidgets.QPushButton("BUILD RIG")
        self.btn_build.setMinimumHeight(36)
        self.btn_build.setStyleSheet(f"""
            QPushButton {{
                background:{C_BLUE2}; color:{C_TEXT};
                border:none; border-left:3px solid {C_BLUE};
                border-radius:0px; padding:6px 20px;
                font-weight:bold; font-size:11px; letter-spacing:4px;
            }}
            QPushButton:hover {{ background:{C_BLUE}; color:{C_BG0}; }}
            QPushButton:pressed {{ background:{C_BLUE2}; color:{C_TEXT}; }}
        """)
        self.btn_build.clicked.connect(self.run_build)

        lay.addWidget(self.btn_load, 1)
        lay.addWidget(self.btn_build, 2)
        return w

    # ── ASSET MANAGEMENT ──────────────────────────────────────────────────────
    def refresh_assets(self):
        self.asset_list.blockSignals(True)
        self.asset_list.clear()
        if os.path.exists(self.assets_path):
            for d in sorted(os.listdir(self.assets_path)):
                if os.path.isdir(os.path.join(self.assets_path, d)):
                    self.asset_list.addItem(d)
        self.asset_list.blockSignals(False)

    def _filter_assets(self, text):
        for i in range(self.asset_list.count()):
            item = self.asset_list.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def _on_asset_selected(self, item):
        if not item:
            return
        self.current_asset = item.text()
        self.lbl_asset.setText(self.current_asset.upper())
        self.settings.setValue("last_asset", self.current_asset)
        self._refresh_tabs()
        self._load_thumbnail()

    def _refresh_tabs(self):
        self.tabs.clear()
        if not self.current_asset:
            return
        asset_dir = os.path.join(self.assets_path, self.current_asset)
        for cat in ("guides", "curves", "models", "skin_clusters"):
            self.tabs.addTab(VersionTab(asset_dir, cat), cat.upper().replace("_", " "))
        # tabs are created dynamically, so re-apply the native style to the new widgets
        ui_utils.apply_maya_style(self)

    def _load_thumbnail(self):
        if not self.current_asset:
            return
        d = os.path.join(self.assets_path, self.current_asset)
        path = None
        for candidate in (
            os.path.join(d, "thumbnail.jpg"),
            os.path.join(d, "thumbnail.png"),
            os.path.join(d, f"{self.current_asset}.jpg"),
            os.path.join(d, f"{self.current_asset}.png"),
        ):
            if os.path.exists(candidate):
                path = candidate
                break
        if path:
            pix = QtGui.QPixmap(path).scaled(
                264, 240, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            self.thumbnail.setPixmap(pix)
            self.thumbnail.setText("")
        else:
            self.thumbnail.setPixmap(QtGui.QPixmap())
            self.thumbnail.setText("NO IMAGE")

    def _restore_session(self):
        last = self.settings.value("last_asset")
        if last:
            items = self.asset_list.findItems(last, QtCore.Qt.MatchExactly)
            if items:
                self.asset_list.setCurrentItem(items[0])
        elif self.asset_list.count():
            self.asset_list.setCurrentRow(0)

    def new_asset(self):
        name, ok = QtWidgets.QInputDialog.getText(self, "New Asset", "Asset name:")
        if not ok or not name.strip():
            return
        path = os.path.join(self.assets_path, name.strip())
        os.makedirs(path, exist_ok=True)
        self.refresh_assets()
        items = self.asset_list.findItems(name.strip(), QtCore.Qt.MatchExactly)
        if items:
            self.asset_list.setCurrentItem(items[0])

    def delete_asset(self):
        if not self.current_asset:
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Delete Asset",
            f"Delete '{self.current_asset}' and all its files?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if reply == QtWidgets.QMessageBox.Yes:
            import shutil
            shutil.rmtree(os.path.join(self.assets_path, self.current_asset), ignore_errors=True)
            self.current_asset = None
            self.refresh_assets()
            self.tabs.clear()

    def take_screenshot(self):
        if not self.current_asset:
            return
        target = os.path.join(self.assets_path, self.current_asset, "thumbnail.jpg")
        try:
            cmds.playblast(
                frame=cmds.currentTime(q=True), format="image",
                compression="jpg", completeFilename=target,
                widthHeight=(400, 400), percent=100,
                forceOverwrite=True, showOrnaments=False, viewer=False
            )
            self._load_thumbnail()
            cmds.inViewMessage(amg="Screenshot saved", pos="midCenter", fade=True)
        except Exception as e:
            cmds.warning(str(e))

    def _open_assets_folder(self):
        import subprocess
        subprocess.Popen(f'explorer "{self.assets_path}"')

    # ── CORE ACTIONS ──────────────────────────────────────────────────────────
    def run_load_settings(self):
        if not self.current_asset:
            cmds.warning("No asset selected.")
            return
        cmds.optionVar(sv=("currentAssetRigName", self.current_asset))
        cmds.inViewMessage(
            amg=f"<hl>{self.current_asset}</hl> set as active asset",
            pos="midCenter", fade=True)

    def run_build(self):
        if not self.current_asset:
            cmds.warning("No asset selected.")
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Build Rig",
            f"This will open a new scene and build '{self.current_asset}'.\nContinue?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if reply != QtWidgets.QMessageBox.Yes:
            return
        cmds.optionVar(sv=("currentAssetRigName", self.current_asset))
        cmds.file(new=True, force=True)
        reload(create_rig)
        create_rig.AutoRig().build()

    def _open_external(self, name):
        try:
            if name == "ngSkinTools":
                import ngSkinTools2; ngSkinTools2.open_ui()
            elif name == "Rabbit Skinning Tools":
                import rabbitSkinningTools as rst; rst.showUI()
            elif name == "Kangaroo":
                import maya.utils, createShelfKangarooBuilder
                maya.utils.executeDeferred(createShelfKangarooBuilder.createShelf)
            elif name == "mGear":
                import mgear.maya; mgear.maya.showMainWindow()
            elif name == "AdonisFx":
                import adonisfx; adonisfx.openAdonisUI()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", f"Could not open {name}:\n{e}")


# ── Launch ────────────────────────────────────────────────────────────────────
global pro_asset_manager
try:
    if pro_asset_manager.isVisible():
        pro_asset_manager.close()
        pro_asset_manager.deleteLater()
except Exception:
    pass
