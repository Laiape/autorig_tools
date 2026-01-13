try:
    from PySide6 import QtWidgets, QtCore, QtGui
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui

from shiboken2 import wrapInstance
import json
import os
from importlib import reload

import maya.OpenMayaUI as omui
import maya.api.OpenMaya as om
import maya.cmds as cmds

# Importaciones de tus módulos
from autorig_tools.scripts.biped.tools import skin_manager_ng # Asegúrate que el archivo anterior se llame skin_manager.py
from biped.autorig import create_rig
import biped.utils as data_manager
from biped.utils import guides_manager

reload(skin_manager_ng)
reload(create_rig)
reload(data_manager)
reload(guides_manager)

class UI(QtWidgets.QMainWindow):
    
    def __init__(self, parent=None):
        super(UI, self).__init__(parent)
        self.setWindowTitle("Auto Rig Pro")
        self.setFixedSize(500, 550)

        # Widget Central
        self.central_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QtWidgets.QVBoxLayout(self.central_widget)

        self.main_window_setup()
        self.populate()
        self.stylesheet()

    def main_window_setup(self):
        self.main_tab = QtWidgets.QTabWidget()
        
        self.auto_rig_tab = QtWidgets.QWidget()
        self.curves_tab = QtWidgets.QWidget()
        self.skin_cluster_tab = QtWidgets.QWidget()

        self.main_tab.addTab(self.auto_rig_tab, "Auto Rig")
        self.main_tab.addTab(self.curves_tab, "Curves")
        self.main_tab.addTab(self.skin_cluster_tab, "Skin Cluster")
        
        self.main_layout.addWidget(self.main_tab)

    def load_icon(self):
        # Ajusta esta ruta a tu estructura de carpetas
        complete_path = os.path.realpath(__file__)
        relative_path = complete_path.split("scripts")[0]
        final_path = os.path.join(relative_path, "icons", "icon.JSON")

        if os.path.exists(final_path):
            with open(final_path, "r") as file:
                return json.load(file)
        return {}

    def svg(self, data, part, module):
        if part in data and module in data[part]:
            pixmap = QtGui.QPixmap()
            pixmap.loadFromData(QtCore.QByteArray(data[part][module].encode()), "SVG")
            return pixmap
        return QtGui.QPixmap()

    # --- POPULATE METHODS ---
    
    def populate_template_menu(self):
        data = self.load_icon()
        self.header_label = QtWidgets.QLabel("Character Template")
        self.template_buttons = []
        
        if "top" in data:
            for name, svg_str in data["top"].items():
                pixmap = QtGui.QPixmap()
                pixmap.loadFromData(QtCore.QByteArray(svg_str.encode()), "SVG")
                btn = QtWidgets.QPushButton()
                btn.setIcon(QtGui.QIcon(pixmap))
                btn.setIconSize(QtCore.QSize(25, 25))
                btn.setToolTip(f"{name} template")
                self.template_buttons.append(btn)

    def populate_modules_menu(self):
        data = self.load_icon()
        self.modules_tabs = QtWidgets.QTabWidget()
        self.biped_tab = QtWidgets.QWidget()
        self.quadruped_tab = QtWidgets.QWidget()
        
        self.modules_tabs.addTab(self.biped_tab, "Biped")
        self.modules_tabs.addTab(self.quadruped_tab, "Quadruped")

        # Biped Buttons
        self.arm_module = QtWidgets.QPushButton(" Arm")
        self.leg_module = QtWidgets.QPushButton(" Leg")
        self.spine_module = QtWidgets.QPushButton(" Spine")
        self.neck_module = QtWidgets.QPushButton(" Neck")
        self.facial_module = QtWidgets.QPushButton(" Facial")
        
        self.modules_buttons = [self.arm_module, self.leg_module, self.spine_module, self.neck_module, self.facial_module]
        
        # Quadruped Buttons
        self.quadruped_leg = QtWidgets.QPushButton(" Q-Leg")
        self.quadruped_spine = QtWidgets.QPushButton(" Q-Spine")
        self.quadruped_modules_buttons = [self.quadruped_leg, self.quadruped_spine]

    def populate_rig_attributes(self):
        self.rig_attributes_label = QtWidgets.QLabel("Rig Attributes")
        self.rig_attributes_tabs = QtWidgets.QTabWidget()
        
        # Arm
        self.rig_attributes_biped_arm = QtWidgets.QWidget()
        self.twist_joints_number = QtWidgets.QSpinBox()
        self.twist_joints_number.setRange(0, 7)
        self.twist_joints_number.setValue(5)
        self.curvature_checkbox = QtWidgets.QCheckBox("Curvature")
        
        # Spine
        self.rig_attributes_biped_spine = QtWidgets.QWidget()
        self.spine_twist_joints_number = QtWidgets.QSpinBox()
        self.spine_twist_joints_number.setValue(5)

        self.rig_attributes_tabs.addTab(self.rig_attributes_biped_arm, "Arm")
        self.rig_attributes_tabs.addTab(self.rig_attributes_biped_spine, "Spine")

    def populate_skin_cluster_interactions(self):
        self.export_skin_weights_button = QtWidgets.QPushButton(" Export Skin Cluster")
        self.import_skin_weights_button = QtWidgets.QPushButton(" Import Skin Cluster")
        
        self.local_skin_cluster_header = QtWidgets.QGroupBox("LOCAL SKIN CLUSTERS")
        self.body_skin_cluster_header = QtWidgets.QGroupBox("BODY SKIN CLUSTERS")

    # --- CONNECTIONS ---

    def create_connections(self):
        # Template (Basado en tu código original)
        if len(self.template_buttons) >= 3:
            self.template_buttons[0].clicked.connect(guides_manager.load_guides_info)
            self.template_buttons[1].clicked.connect(guides_manager.get_guides_info)
            self.template_buttons[2].clicked.connect(guides_manager.delete_guides)

        # Rig Creation
        self.create_rig_button = QtWidgets.QPushButton("CREATE BIPED RIG")
        self.create_rig_button.setMinimumHeight(40)
        self.create_rig_button.clicked.connect(self.create_biped_rig_connections)

        # Skinning (Aquí usamos el SkinManager que creamos)
        self.export_skin_weights_button.clicked.connect(self.export_skin_weights_connections)
        self.import_skin_weights_button.clicked.connect(self.import_skin_weights_connections)

    def export_skin_weights_connections(self):
        skinner = skin_manager_ng.SkinManager()
        skinner.export_skins()
        cmds.inViewMessage(amg='Skins Exportadas.', pos='midCenter', fade=True)

    def import_skin_weights_connections(self):
        # 1. Creamos la instancia (los paréntesis () ejecutan el __init__)
        skinner = skin_manager_ng.SkinManager() 

        # 2. Ahora llamamos al método desde el objeto creado
        skinner.import_skins()
        cmds.inViewMessage(amg='Skins Importadas y Reordenadas.', pos='midCenter', fade=True)

    def create_biped_rig_connections(self):
        rig = create_rig.AutoRig()
        rig.build()

    # --- LAYOUTS (Organización limpia) ---

    def layouts(self):
        # Auto Rig Tab Layout
        ar_layout = QtWidgets.QVBoxLayout(self.auto_rig_tab)
        
        # Templates
        t_header = QtWidgets.QHBoxLayout()
        t_header.addWidget(self.header_label)
        ar_layout.addLayout(t_header)
        
        t_btns = QtWidgets.QHBoxLayout()
        for b in self.template_buttons: t_btns.addWidget(b)
        t_btns.addStretch()
        ar_layout.addLayout(t_btns)
        
        # Modules
        ar_layout.addWidget(self.modules_tabs)
        biped_l = QtWidgets.QHBoxLayout(self.biped_tab)
        for b in self.modules_buttons: biped_l.addWidget(b)
        
        quad_l = QtWidgets.QHBoxLayout(self.quadruped_tab)
        for b in self.quadruped_modules_buttons: quad_l.addWidget(b)

        # Attributes
        ar_layout.addWidget(self.rig_attributes_label)
        ar_layout.addWidget(self.rig_attributes_tabs)
        
        # Build Button
        ar_layout.addStretch()
        ar_layout.addWidget(self.create_rig_button)

        # Skin Tab Layout
        skin_l = QtWidgets.QVBoxLayout(self.skin_cluster_tab)
        skin_l.addWidget(self.export_skin_weights_button)
        skin_l.addWidget(self.import_skin_weights_button)
        
        box_l = QtWidgets.QHBoxLayout()
        box_l.addWidget(self.local_skin_cluster_header)
        box_l.addWidget(self.body_skin_cluster_header)
        skin_l.addLayout(box_l)
        skin_l.addStretch()

    def populate(self):
        self.populate_template_menu()
        self.populate_modules_menu()
        self.populate_rig_attributes()
        self.populate_skin_cluster_interactions()
        self.create_connections()
        self.layouts()

    def stylesheet(self):
        self.setStyleSheet("""
            QMainWindow, QTabWidget { background-color: #2b2b2b; color: #eee; }
            QPushButton { 
                background-color: #444; 
                border: 1px solid #666; 
                border-radius: 4px; 
                padding: 4px; 
                color: white;
            }
            QPushButton:hover { background-color: #1e90ff; }
            QLabel { font-weight: bold; }
            QGroupBox { border: 1px solid #666; margin-top: 10px; padding-top: 10px; color: #888; }
        """)

# --- RUN ---
def run_ui():
    maya_win = wrapInstance(int(omui.MQtUtil.mainWindow()), QtWidgets.QWidget)
    
    global rig_ui_window
    try:
        rig_ui_window.close()
        rig_ui_window.deleteLater()
    except:
        pass

    rig_ui_window = UI(parent=maya_win)
    rig_ui_window.show()

run_ui()