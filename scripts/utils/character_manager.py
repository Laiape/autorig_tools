import os
import shutil
import glob
import datetime
import webbrowser
from tools import skin_manager_api
from utils import curve_tool, guides_manager
from utils import create_rig
import maya.cmds as cmds
import maya.OpenMayaUI as omui
from functools import partial
from importlib import reload

# --- COMPATIBILIDAD PYSIDE ---
try:
    from PySide6 import QtWidgets, QtCore, QtGui
    from shiboken6 import wrapInstance
    PYSIDE_VERSION = 6
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui
    from shiboken2 import wrapInstance
    PYSIDE_VERSION = 2

ALLOWED_ENDINGS = [".ma", ".mb", ".guides", ".curves", ".json"]

def get_maya_main_window():
    """ Obtiene la ventana principal de Maya para hacer parenting """
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget)

def get_assets_path():
    """ Lógica para encontrar la carpeta assets dinámicamente """
    complete_path = os.path.realpath(__file__)
    
    # Caso: Ejecutando desde Script Editor (fallback)
    if "Script Editor" in complete_path or "<string>" in complete_path:
        workspace = cmds.workspace(q=True, rootDirectory=True)
        path = os.path.join(workspace, "assets")
        if not os.path.exists(path): 
            # Si no existe en workspace, intenta crear una dummy para que no falle el script
            try: os.makedirs(path)
            except: pass
        return path

    # Caso: Ejecutando desde archivo .py
    sep_token = os.sep + "scripts"
    if sep_token in complete_path:
        relative_path = complete_path.split(sep_token)[0]
    else:
        relative_path = os.path.dirname(os.path.dirname(complete_path))
    
    path = os.path.join(relative_path, "assets")
    if not os.path.exists(path): os.makedirs(path)
    return path

# --- WIDGET PERSONALIZADO PARA CADA PESTAÑA (GUIDES, MODELS, ETC) ---
class VersionTab(QtWidgets.QWidget):
    def __init__(self, asset_path, sub_folder, parent=None):
        super(VersionTab, self).__init__(parent)
        self.asset_path = asset_path
        self.sub_folder = sub_folder # ej: "guides", "models"
        self.full_path = os.path.join(self.asset_path, self.sub_folder)
        
        # Crear carpeta si no existe
        if not os.path.exists(self.full_path):
            try: os.makedirs(self.full_path)
            except: pass

        self.setup_ui()
        self.refresh_list()

    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # TABLA
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Version", "Name", "+", "Rep"])
        self.table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents) # Version
        self.table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)          # Name
        self.table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.Fixed)            # +
        self.table.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.Fixed)            # Rep
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        # BOTONES INFERIORES (Save New / Import)
        btn_layout = QtWidgets.QHBoxLayout()
        
        self.btn_save_ver = QtWidgets.QPushButton("+ SAVE NEW VERSION")
        self.btn_save_ver.setStyleSheet("""
            QPushButton {
                background-color: #1e3a52;
                color: #7ecfff;
                border: 1px solid #4a88b8;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 9px;
                letter-spacing: 2px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #24425e; color: #a8e0ff; border-color: #6aaad0; }
        """)
        self.btn_save_ver.clicked.connect(self.save_new_version)
        
        self.btn_import = QtWidgets.QPushButton("↓ IMPORT SELECTED")
        self.btn_import.setStyleSheet("""
            QPushButton {
                background-color: #38384a;
                color: #9898b8;
                border: 1px solid #4a4a5e;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 9px;
                letter-spacing: 2px;
                font-weight: bold;
            }
            QPushButton:hover { color: #e0e0f8; border-color: #6868a0; background-color: #42425a; }
        """)
        self.btn_import.clicked.connect(self.import_selected)
        
        btn_layout.addWidget(self.btn_save_ver)
        btn_layout.addWidget(self.btn_import)
        layout.addLayout(btn_layout)

    def refresh_list(self):
        self.table.setRowCount(0)
        if not os.path.exists(self.full_path): return

        # Buscar archivos .ma o .mb
        files = sorted([f for f in os.listdir(self.full_path) if any(f.endswith(ext) for ext in ALLOWED_ENDINGS)], reverse=True)

        for f in files:
            row = self.table.rowCount()
            self.table.insertRow(row)

            # --- LÓGICA DE NOMBRES ---
            version_part = f.split("_")[-1].split(".")[0]
            name_part = f
            
            # Columna 0: VER (v001)
            item_version = QtWidgets.QTableWidgetItem(version_part)
            item_version.setToolTip(f) 
            item_version.setTextAlignment(QtCore.Qt.AlignCenter)
            self.table.setItem(row, 0, item_version)

            # Columna 1: NAME (jamal_guides.ma)
            item_name = QtWidgets.QTableWidgetItem(name_part)
            self.table.setItem(row, 1, item_name)
            
            # --- COLUMNA 2: BOTÓN IMPORTAR (Open) ---
            btn_load = QtWidgets.QPushButton("▶")
            btn_load.setFixedSize(28, 22)
            btn_load.setStyleSheet("""
                QPushButton {
                    background-color: #1e3a52;
                    border: 1px solid #4a88b8;
                    color: #7ecfff;
                    font-weight: bold;
                    font-size: 10px;
                    border-radius: 3px;
                }
                QPushButton:hover { background-color: #24425e; color: #a8e0ff; }
            """)
            btn_load.setToolTip(f"Import version: {f}")
            btn_load.clicked.connect(partial(self.import_file, f))
            
            cell_widget_load = QtWidgets.QWidget()
            lay_load = QtWidgets.QHBoxLayout(cell_widget_load)
            lay_load.setContentsMargins(0,0,0,0)
            lay_load.setAlignment(QtCore.Qt.AlignCenter)
            lay_load.addWidget(btn_load)
            self.table.setCellWidget(row, 2, cell_widget_load)

            # --- COLUMNA 3: BOTÓN REPLACE (Replace) ---
            btn_rep = QtWidgets.QPushButton("⟳")
            btn_rep.setFixedSize(28, 22)
            btn_rep.setStyleSheet("""
                QPushButton {
                    background-color: #4a2020;
                    border: 1px solid #a85050;
                    color: #e08080;
                    font-weight: bold;
                    font-size: 12px;
                    border-radius: 3px;
                }
                QPushButton:hover { background-color: #5a2828; color: #f0a0a0; }
            """)
            btn_rep.setToolTip(f"OVERWRITE {f} with current selection/scene")
            btn_rep.clicked.connect(partial(self.replace_file, f))
            
            cell_widget_rep = QtWidgets.QWidget()
            lay_rep = QtWidgets.QHBoxLayout(cell_widget_rep)
            lay_rep.setContentsMargins(0,0,0,0)
            lay_rep.setAlignment(QtCore.Qt.AlignCenter)
            lay_rep.addWidget(btn_rep)
            self.table.setCellWidget(row, 3, cell_widget_rep)

    def save_new_version(self):
        """
        Calcula la siguiente versión y ejecuta el exportador correspondiente.
        """
        # 1. Mapeo de extensiones por pestaña
        extension_map = {
            "guides": ".guides",
            "controllers": ".curves",
            "models": ".ma",
            "skin_clusters": ".skc"
        }
        ext = extension_map.get(self.sub_folder, ".ma")

        # 2. Lógica de incremento de versión (v001, v002...)
        files = [f for f in os.listdir(self.full_path) if f.endswith(ext)]
        version = 1
        if files:
            files.sort()
            try:
                last = files[-1]
                if "_v" in last:
                    ver_str = last.split("_v")[-1].split(".")[0]
                    version = int(ver_str) + 1
            except: pass
        
        # 3. Construir path final
        asset_name = os.path.basename(self.asset_path)
        new_name = f"{asset_name}_v{version:03d}{ext}"
        full_path = os.path.join(self.full_path, new_name)

        # 4. EJECUTAR EXPORTACIÓN (Basado en tu run_exports)
        try:
            if self.sub_folder == "guides":
                reload(guides_manager)
                guides_manager.get_guides_info(path=full_path)

            elif self.sub_folder == "controllers":
                reload(curve_tool)
                curve_tool.get_all_ctl_curves_data(path=full_path)

            elif self.sub_folder == "models":
                cmds.file(rename=full_path)
                cmds.file(save=True, type="mayaAscii")

            elif self.sub_folder == "skin":
                reload(skin_manager_api)
                skinner = skin_manager_api.SkinManager()
                skinner.export_skins(path=full_path)

            # Feedback de éxito
            cmds.inViewMessage(amg=f'<hl>{self.sub_folder.capitalize()}</hl> v{version:03d} Exported.', 
                               pos='midCenter', fade=True)
            
            # Actualizar la tabla para ver el nuevo archivo
            self.refresh_list()

        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Export Error", 
                                          f"Failed to export {self.sub_folder}:\n{str(e)}")

    def replace_file(self, filename):
        path = os.path.join(self.full_path, filename)
        try:
            if self.sub_folder == "guides":
                reload(guides_manager)
                guides_manager.get_guides_info(path=path)

            elif self.sub_folder == "controllers":
                reload(curve_tool)
                curve_tool.get_all_ctl_curves_data(path=path)

            elif self.sub_folder == "models":
                cmds.file(rename=path)
                cmds.file(save=True, type="mayaAscii")

            elif self.sub_folder == "skin":
                reload(skin_manager_api)
                skinner = skin_manager_api.SkinManager()
                skinner.export_skins(path=path)

            # Feedback de éxito
            cmds.inViewMessage(amg=f'<hl>{self.sub_folder.capitalize()}</hl> {path} Exported.', 
                               pos='midCenter', fade=True)
            
            # Actualizar la tabla para ver el nuevo archivo
            self.refresh_list()

        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Export Error", 
                                          f"Failed to export {self.sub_folder}:\n{str(e)}")
            print(f"Replaced: {path}")
            self.refresh_list()

    def import_selected(self):
        row = self.table.currentRow()
        if row >= 0:
            item = self.table.item(row, 0)
            self.import_file(item.text())

    def import_file(self, filename):

        full_path = os.path.join(self.full_path, filename)
        try:
            if self.sub_folder == "guides":
                reload(guides_manager)
                guides_manager.load_guides_info(filePath=full_path)

            elif self.sub_folder == "controllers":
                reload(curve_tool)
                curve_tool.get_all_ctl_curves_data(path=full_path)

            elif self.sub_folder == "models":
                cmds.file(open=full_path)

            elif self.sub_folder == "skin":
                reload(skin_manager_api)
                skinner = skin_manager_api.SkinManager()
                skinner.import_skins(path=full_path)

            # Feedback de éxito
            cmds.inViewMessage(amg=f'<hl>{self.sub_folder.capitalize()}</hl> Imported.', 
                            pos='midCenter', fade=True)
        
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Import Error", 
                                          f"Failed to import {self.sub_folder}:\n{str(e)}")


# --- UI PRINCIPAL ---
class AssetManagerUI(QtWidgets.QWidget):
    def __init__(self, parent=get_maya_main_window()):
        super(AssetManagerUI, self).__init__(parent)
        self.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.WindowStaysOnTopHint)
        self.setWindowTitle("Pipeline")
        self.setMinimumWidth(500)
        self.setMinimumHeight(500) # Más alto para acomodar tablas
        
        self.assets_path = get_assets_path()
        self.current_asset = None
        self.settings = QtCore.QSettings("MyCompany", "AutoRigTools")

        self.setup_ui()
        self.setup_stylesheet()
        self.refresh_assets()
        self.restore_last_session()

    def setup_ui(self):
        # LAYOUT PRINCIPAL
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0) # Sin márgenes externos por el menú
        main_layout.setSpacing(0)

        # 1. MENU BAR (Tools | Help)
        self.menu_bar = QtWidgets.QMenuBar()
        self.menu_bar.setStyleSheet("background-color: #333; color: #ddd;")
        
        tools_menu = self.menu_bar.addMenu("Tools")
        # 1. MENU BAR (Tools | Help)
        self.menu_bar = QtWidgets.QMenuBar()
        self.menu_bar.setStyleSheet("background-color: #333; color: #ddd;")
        
        # --- Menú Tools ---
        tools_menu = self.menu_bar.addMenu("Tools")
        tools_menu.addAction("New Scene", lambda: cmds.file(new=True, force=True))

        tools_menu.addSeparator()
        # Añade las herramientas externas
        tools_menu.addAction("ngSkinTools", lambda: self.run_external_tool("ngSkinTools"))
        tools_menu.addAction("Rabbit Skinning Tools", lambda: self.run_external_tool("Rabbit"))
        tools_menu.addAction("Kangaroo", lambda: self.run_external_tool("Kangaroo"))
        tools_menu.addAction("mGear", lambda: self.run_external_tool("mGear"))
        tools_menu.addAction("AdonisFx", lambda: self.run_external_tool("AdonisFx"))
        
        # --- Menú Help ---
        help_menu = self.menu_bar.addMenu("Help")
        # Acciones con enlaces externos
        help_menu.addAction("GitHub", lambda: webbrowser.open("https://github.com/Laiape/autorig_tools"))
        help_menu.addAction("LinkedIn", lambda: webbrowser.open("https://www.linkedin.com/in/laia-peris-arantzamendi-6b9809277/"))
        help_menu.addAction("Web", lambda: webbrowser.open("https://laiape.github.io/"))
        
        # Puedes añadir un separador antes del About si quieres
        help_menu.addSeparator()
        help_menu.addAction("About", lambda: QtWidgets.QMessageBox.information(self, "About", "AutoRig Tools v1.0\nCreated by Laia Peris"))
        
        main_layout.addWidget(self.menu_bar)
        

        # CONTAINER CENTRAL (Con padding)
        content_widget = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content_widget)
        content_layout.setContentsMargins(15, 15, 15, 15)
        content_layout.setSpacing(10)
        main_layout.addWidget(content_widget)

        # 2. SECCIÓN SUPERIOR (HEADER)
        # Usamos un GridLayout para posicionar Dropdown izq y Foto derecha
        top_grid = QtWidgets.QGridLayout()
        top_grid.setColumnStretch(0, 1) # Izquierda se estira
        top_grid.setColumnStretch(1, 0) # Derecha fijo

        # [IZQUIERDA] Path + Dropdown
        left_panel = QtWidgets.QVBoxLayout()
        self.path_label = QtWidgets.QLabel("// assets > ...")
        self.path_label.setObjectName("PathLabel")
        
        lbl_lib = QtWidgets.QLabel("▸ ASSET LIBRARY")
        lbl_lib.setObjectName("SectionHeader")
        
        self.asset_combo = QtWidgets.QComboBox()
        self.asset_combo.setMinimumHeight(28)
        self.asset_combo.currentIndexChanged.connect(self.on_asset_changed)
        
        left_panel.addWidget(self.path_label)
        left_panel.addSpacing(5)
        left_panel.addWidget(lbl_lib)
        left_panel.addWidget(self.asset_combo)
        left_panel.addStretch()

        top_grid.addLayout(left_panel, 0, 0)

        # [DERECHA] Foto + Cámara
        right_panel = QtWidgets.QVBoxLayout()
        
        # Botón cámara alineado a la derecha de la foto
        cam_layout = QtWidgets.QHBoxLayout()
        cam_layout.addStretch()
        self.cam_btn = QtWidgets.QPushButton()
        self.cam_btn.setFixedSize(20, 20)
        self.cam_btn.setObjectName("CamBtn")
        if QtGui.QImageReader.imageFormat(":/camera.png"):
             self.cam_btn.setIcon(QtGui.QIcon(":/camera.png"))
        else: self.cam_btn.setText("O")
        self.cam_btn.clicked.connect(self.take_screenshot)
        cam_layout.addWidget(self.cam_btn)

        self.image_label = QtWidgets.QLabel()
        self.image_label.setFixedSize(120, 120)
        self.image_label.setObjectName("Thumbnail")
        self.image_label.setAlignment(QtCore.Qt.AlignCenter)

        right_panel.addLayout(cam_layout)
        right_panel.addWidget(self.image_label)

        top_grid.addLayout(right_panel, 0, 1)
        
        content_layout.addLayout(top_grid)

        # 3. TABS CENTRALES (Guides, Controllers, Models, Skc)
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setObjectName("MainTabs")
        content_layout.addWidget(self.tabs)

        # 4. BOTONES INFERIORES GLOBALES (Load Settings / Build)
        action_layout = QtWidgets.QHBoxLayout()
        self.btn_load_settings = QtWidgets.QPushButton("LOAD SETTINGS")
        self.btn_load_settings.setObjectName("LoadBtn")
        self.btn_load_settings.setMinimumHeight(40)
        self.btn_load_settings.clicked.connect(self.run_load_settings)

        self.btn_build = QtWidgets.QPushButton("BUILD RIG")
        self.btn_build.setObjectName("BuildBtn")
        self.btn_build.setMinimumHeight(40)
        self.btn_build.clicked.connect(self.run_build)

        action_layout.addWidget(self.btn_load_settings, stretch=1)
        action_layout.addWidget(self.btn_build, stretch=2)
        content_layout.addLayout(action_layout)


    def refresh_tabs(self):
        """ Reconstruye las pestañas cuando cambia el asset """
        self.tabs.clear()
        if not self.current_asset: return

        asset_dir = os.path.join(self.assets_path, self.current_asset)
        
        # Definir las categorías que quieres
        categories = ["guides", "curves", "models", "skin_clusters"]
        
        for cat in categories:

            tab = VersionTab(asset_dir, cat)
            self.tabs.addTab(tab, cat.upper())


    def setup_stylesheet(self):
        self.setStyleSheet("""
            /* === BASE === */
            QWidget {
                background-color: #2e2e36;
                color: #e8e8f0;
                font-family: 'Segoe UI', sans-serif;
                font-size: 11px;
            }

            /* === MENU BAR === */
            QMenuBar {
                background-color: #26262e;
                color: #b0b0c0;
                border-bottom: 1px solid #3a3a46;
                padding: 2px 4px;
                font-size: 11px;
            }
            QMenuBar::item { padding: 4px 10px; border-radius: 3px; }
            QMenuBar::item:selected { background-color: #3a3a48; color: #7ecfff; }
            QMenu {
                background-color: #32323e;
                border: 1px solid #4a4a58;
                color: #e0e0f0;
            }
            QMenu::item:selected { background-color: #3e3e50; color: #7ecfff; }
            QMenu::separator { background-color: #3a3a48; height: 1px; margin: 3px 8px; }

            /* === LABELS === */
            QLabel#PathLabel {
                font-size: 10px;
                color: #7878a0;
                letter-spacing: 1px;
                padding: 2px 0;
            }
            QLabel#SectionHeader {
                color: #7ecfff;
                font-weight: bold;
                font-size: 9px;
                letter-spacing: 3px;
                padding-bottom: 2px;
            }

            /* === COMBO BOX === */
            QComboBox {
                background-color: #38384a;
                border: 1px solid #4a4a5e;
                border-radius: 4px;
                padding: 4px 8px;
                color: #e8e8f8;
                font-size: 12px;
                selection-background-color: #3e3e58;
            }
            QComboBox:hover { border-color: #7ecfff; }
            QComboBox::drop-down { border: none; width: 24px; }
            QComboBox QAbstractItemView {
                background-color: #32323e;
                border: 1px solid #7ecfff;
                selection-background-color: #2e3a4e;
                color: #e0e0f0;
                outline: none;
            }

            /* === TABS === */
            QTabWidget::pane {
                border: 1px solid #3a3a4a;
                background-color: #2e2e36;
                top: -1px;
            }
            QTabBar::tab {
                background: #26262e;
                color: #6868888;
                padding: 7px 18px;
                border: 1px solid transparent;
                border-bottom: none;
                margin-right: 2px;
                font-size: 9px;
                letter-spacing: 2px;
                font-weight: bold;
                color: #78789a;
            }
            QTabBar::tab:selected {
                background: #2e2e36;
                color: #7ecfff;
                border: 1px solid #3a3a4a;
                border-bottom: 2px solid #7ecfff;
            }
            QTabBar::tab:hover:!selected { color: #a0a0c0; }

            /* === TABLE === */
            QTableWidget {
                background-color: #28282e;
                border: 1px solid #3a3a46;
                gridline-color: #32323e;
                alternate-background-color: #2c2c34;
                selection-background-color: #2e3a4e;
                outline: none;
            }
            QTableWidget::item { padding: 5px 8px; border: none; color: #d0d0e8; }
            QTableWidget::item:selected {
                background-color: #2e3a4e;
                color: #7ecfff;
            }
            QHeaderView::section {
                background-color: #26262e;
                border: none;
                border-bottom: 1px solid #3a3a4a;
                border-right: 1px solid #32323e;
                padding: 5px 8px;
                font-size: 9px;
                letter-spacing: 2px;
                color: #6a6a8a;
                font-weight: bold;
            }
            QScrollBar:vertical {
                background: #28282e;
                width: 6px;
                border: none;
            }
            QScrollBar::handle:vertical { background: #4a4a60; border-radius: 3px; min-height: 20px; }
            QScrollBar::handle:vertical:hover { background: #7ecfff; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }

            /* === ACTION BUTTONS (bottom) === */
            QPushButton#LoadBtn {
                background-color: #38384a;
                color: #9898b8;
                border: 1px solid #4a4a5e;
                border-radius: 4px;
                font-size: 10px;
                letter-spacing: 2px;
                font-weight: bold;
            }
            QPushButton#LoadBtn:hover {
                background-color: #42425a;
                color: #e0e0f8;
                border-color: #6060808;
            }
            QPushButton#LoadBtn:pressed { background-color: #2e2e3e; }

            QPushButton#BuildBtn {
                background-color: #1e3a52;
                color: #7ecfff;
                border: 1px solid #4a88b8;
                border-radius: 4px;
                font-size: 11px;
                letter-spacing: 3px;
                font-weight: bold;
            }
            QPushButton#BuildBtn:hover {
                background-color: #24425e;
                color: #a8e0ff;
                border-color: #6aaad0;
            }
            QPushButton#BuildBtn:pressed { background-color: #162e42; }

            /* === THUMBNAIL === */
            QLabel#Thumbnail {
                background-color: #22222a;
                border: 1px solid #3a3a4a;
                border-radius: 4px;
                color: #505068;
                font-size: 10px;
            }
            QPushButton#CamBtn {
                background-color: transparent;
                border: none;
                color: #505068;
            }
            QPushButton#CamBtn:hover {
                background-color: #3a3a4a;
                color: #7ecfff;
                border-radius: 10px;
            }

            /* === VERSION TAB BUTTONS (Save / Import) === */
            QPushButton {
                background-color: #38384a;
                color: #9898b8;
                border: 1px solid #4a4a5e;
                border-radius: 4px;
                padding: 5px 12px;
                font-size: 10px;
                letter-spacing: 1px;
            }
            QPushButton:hover {
                background-color: #42425a;
                color: #e0e0f8;
                border-color: #6868888;
            }
            QPushButton:pressed { background-color: #2e2e3e; }
        """)

    # --- FUNCIONES CORE ---
    def refresh_assets(self):
        self.asset_combo.blockSignals(True)
        self.asset_combo.clear()
        if os.path.exists(self.assets_path):
            dirs = sorted([d for d in os.listdir(self.assets_path) if os.path.isdir(os.path.join(self.assets_path, d))])
            self.asset_combo.addItems(dirs)
        self.asset_combo.blockSignals(False)

    def on_asset_changed(self):
        self.current_asset = self.asset_combo.currentText()
        if not self.current_asset: return
        
        self.path_label.setText(f"// assets > {self.current_asset}")
        
        # 1. Update Image
        full_path = os.path.join(self.assets_path, self.current_asset)
        self.load_thumbnail(full_path)
        
        # 2. Update Tabs
        self.refresh_tabs()
        
        # 3. Save Settings
        self.settings.setValue("last_selected_asset", self.current_asset)

    def load_thumbnail(self, asset_dir):
        thumb_path = None
        if os.path.exists(os.path.join(asset_dir, "thumbnail.jpg")):
            thumb_path = os.path.join(asset_dir, "thumbnail.jpg")
        else:
            for ext in ['png', 'jpg']:
                p = os.path.join(asset_dir, f"{self.current_asset}.{ext}")
                if os.path.exists(p):
                    thumb_path = p
                    break
        
        if thumb_path:
            pix = QtGui.QPixmap(thumb_path).scaled(120, 120, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            self.image_label.setPixmap(pix)
        else:
            self.image_label.setPixmap(QtGui.QPixmap())
            self.image_label.setText("No Img")

    def take_screenshot(self):
        if not self.current_asset: return
        target = os.path.join(self.assets_path, self.current_asset, "thumbnail.jpg")
        try:
            cmds.viewHeadExtents(cmds.getPanel(wf=True), hud=False)
            cmds.playblast(frame=cmds.currentTime(q=True), format="image", compression="jpg",
                           completeFilename=target, widthHeight=(300, 300), percent=100, 
                           forceOverwrite=True, showOrnaments=False, viewer=False)
            self.load_thumbnail(os.path.join(self.assets_path, self.current_asset))
        except: pass

    def restore_last_session(self):
        last = self.settings.value("last_selected_asset")
        if last:
            idx = self.asset_combo.findText(last)
            if idx != -1: self.asset_combo.setCurrentIndex(idx)
        # Forzar refresh inicial
        if self.asset_combo.count() > 0: self.on_asset_changed()


    def run_load_settings(self):
        """
        Setea paths, importa guías, modelos y todo lo necesario sin construir el rig final.
        """
        if not self.current_asset: return
        
        asset_root = os.path.join(self.assets_path, self.current_asset)
        print(f"\n--- CARGANDO SETTINGS PARA: {self.current_asset} ---")
        print(f"Path Root: {asset_root}")
        cmds.inViewMessage(amg=f"<hl>{self.current_asset}</hl> Settings Loaded Successfully", pos='midCenter', fade=True)
        cmds.optionVar(sv=("currentAssetRigName", self.current_asset))

        return self.current_asset

    def run_build(self):
        
        """
        Construye el rig completo a partir de las guías y modelos importados.
        """
        if not self.current_asset: return
        
        asset_root = os.path.join(self.assets_path, self.current_asset)
        print(f"\n--- BUILDING RIG FOR: {self.current_asset} ---")
        print(f"Path Root: {asset_root}")
        cmds.optionVar(sv=("currentAssetRigName", self.current_asset))
        
        cmds.file(new=True, force=True)
        reload(create_rig)
        rig = create_rig.AutoRig()
        rig.build()

        char_name = self.current_asset

        cmds.inViewMessage(
        amg=f'Completed <hl>{char_name.upper()} RIG</hl> build.',
        pos='midCenter',
        fade=True,
        alpha=0.8)

    def run_external_tool(self, tool_name):
        try:
            if tool_name == "ngSkinTools":
                import ngSkinTools2
                ngSkinTools2.open_ui()
            if tool_name == "Rabbit":
                import rabbitSkinningTools as rst
                rst.showUI()
            elif tool_name == "Kangaroo":
                import maya.utils
                import createShelfKangarooBuilder
                def main():
                    createShelfKangarooBuilder.createShelf()

                maya.utils.executeDeferred(main)
            elif tool_name == "mGear":
                import mgear.maya
                mgear.maya.showMainWindow()
            elif tool_name == "AdonisFx":
                import adonisfx
                adonisfx.openAdonisUI()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", f"Could not open {tool_name}:\n{str(e)}")

    def run_exports(self, file_type):
        
        try:
            if file_type == "guides":
                reload(guides_manager)
                guides_manager.get_guides_info()
            elif file_type == "controllers":
                reload(curve_tool)
                curve_tool.get_all_ctl_curves_data()
            elif file_type == "models":
                cmds.file(rename=os.path.join(self.assets_path, self.current_asset, "models", f"{self.current_asset}_models.ma"))
                cmds.file(save=True, type="mayaAscii")
            elif file_type == "skin":
                reload(skin_manager_api)
                skinner = skin_manager_api.SkinManager()
                skinner.export_skins()
            cmds.inViewMessage(amg=f'{file_type.capitalize()} Exported.', pos='midCenter', fade=True)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", f"Could not export {file_type}:\n{str(e)}")


global pro_asset_manager
try:
    if pro_asset_manager.isVisible():
        pro_asset_manager.close()
        pro_asset_manager.deleteLater()
except: pass