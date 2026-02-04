import os
from utils import create_rig
from importlib import reload
import maya.cmds as cmds
import maya.OpenMayaUI as omui

# --- COMPATIBILIDAD PYSIDE 2 (Maya <2025) / PYSIDE 6 (Maya 2025+) ---
try:
    from PySide6 import QtWidgets, QtCore, QtGui
    from shiboken6 import wrapInstance
    PYSIDE_VERSION = 6
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui
    from shiboken2 import wrapInstance
    PYSIDE_VERSION = 2

# --- UTILS ---
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

# --- UI PRINCIPAL ---
class AssetManagerUI(QtWidgets.QWidget):
    def __init__(self, parent=get_maya_main_window()):
        super(AssetManagerUI, self).__init__(parent)
        
        # CONFIGURACIÓN DE VENTANA
        # WindowStaysOnTopHint: Mantiene la UI siempre visible sobre Maya
        self.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.WindowStaysOnTopHint)
        self.setWindowTitle("Asset Manager Pro")
        self.setMinimumWidth(420)
        self.setMinimumHeight(240)
        
        # DATOS
        self.assets_path = get_assets_path()
        self.current_asset = None
        
        # SISTEMA DE GUARDADO (Persistencia)
        # "MyCompany" es la organización, "AutoRigTools" es la aplicación
        self.settings = QtCore.QSettings("MyCompany", "AutoRigTools")
        
        self.setup_ui()
        self.setup_stylesheet()
        
        # INICIALIZACIÓN
        self.refresh_assets()
        self.restore_last_session() # Cargar el último asset usado

    def setup_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)

        # --- SECCIÓN SUPERIOR: INFO + DROPDOWN + FOTO ---
        top_layout = QtWidgets.QHBoxLayout()
        
        # [Columna Izquierda]: Breadcrumbs y Dropdown
        left_col = QtWidgets.QVBoxLayout()
        left_col.setSpacing(6)
        
        self.path_label = QtWidgets.QLabel("assets > ...")
        self.path_label.setObjectName("PathLabel")
        
        label_combo = QtWidgets.QLabel("ASSET LIBRARY")
        label_combo.setObjectName("SectionHeader")
        
        self.asset_combo = QtWidgets.QComboBox()
        self.asset_combo.setMinimumHeight(28)
        self.asset_combo.currentIndexChanged.connect(self.on_asset_changed)
        
        left_col.addWidget(self.path_label)
        left_col.addSpacing(5)
        left_col.addWidget(label_combo)
        left_col.addWidget(self.asset_combo)
        left_col.addStretch()
        
        # [Columna Derecha]: Cámara y Thumbnail
        right_col = QtWidgets.QVBoxLayout()
        right_col.setSpacing(2)
        
        # Botón Cámara (Pequeño y discreto)
        cam_row = QtWidgets.QHBoxLayout()
        cam_row.addStretch()
        self.cam_btn = QtWidgets.QPushButton()
        self.cam_btn.setFixedSize(24, 24)
        self.cam_btn.setObjectName("CamBtn")
        self.cam_btn.setToolTip("Take Snapshot (Playblast)")
        # Intentar cargar icono interno de Maya
        if QtGui.QImageReader.imageFormat(":/camera.png"):
            self.cam_btn.setIcon(QtGui.QIcon(":/camera.png"))
        else:
            self.cam_btn.setText("O") # Fallback texto
            
        self.cam_btn.clicked.connect(self.take_screenshot)
        cam_row.addWidget(self.cam_btn)
        
        # Imagen
        self.image_label = QtWidgets.QLabel()
        self.image_label.setFixedSize(130, 130)
        self.image_label.setObjectName("Thumbnail")
        self.image_label.setAlignment(QtCore.Qt.AlignCenter)
        
        right_col.addLayout(cam_row)
        right_col.addWidget(self.image_label)
        
        top_layout.addLayout(left_col, stretch=1)
        top_layout.addLayout(right_col, stretch=0)
        
        main_layout.addLayout(top_layout)

        # --- SECCIÓN INFERIOR: BOTONES DE ACCIÓN ---
        # Usamos un layout horizontal para poner Load Settings y Build juntos
        action_layout = QtWidgets.QHBoxLayout()
        action_layout.setSpacing(10)

        self.btn_load_settings = QtWidgets.QPushButton("LOAD SETTINGS")
        self.btn_load_settings.setObjectName("LoadBtn")
        self.btn_load_settings.setMinimumHeight(40)
        self.btn_load_settings.setToolTip("Sets paths, imports guides and models without building.")
        self.btn_load_settings.clicked.connect(self.run_load_settings)

        self.btn_build = QtWidgets.QPushButton("BUILD RIG")
        self.btn_build.setObjectName("BuildBtn")
        self.btn_build.setMinimumHeight(40)
        self.btn_build.setToolTip("Full build process.")
        self.btn_build.clicked.connect(self.run_build)

        # Proporción 1:2 para dar más importancia al Build
        action_layout.addWidget(self.btn_load_settings, stretch=1)
        action_layout.addWidget(self.btn_build, stretch=2)

        main_layout.addLayout(action_layout)

    def setup_stylesheet(self):
        self.setStyleSheet("""
            QWidget { background-color: #2b2b2b; color: #d0d0d0; font-family: 'Segoe UI', sans-serif; }
            
            /* Textos */
            QLabel#PathLabel { font-weight: bold; font-size: 12px; color: #ffffff; }
            QLabel#SectionHeader { color: #5285a6; font-weight: bold; font-size: 10px; letter-spacing: 1px; }
            
            /* Dropdown */
            QComboBox {
                background-color: #1e1e1e; border: 1px solid #3d3d3d; 
                border-radius: 4px; padding-left: 10px; color: white;
            }
            QComboBox::drop-down { border: none; width: 25px; }
            QComboBox::down-arrow { image: url(:/teArrowDown.png); width: 10px; }
            QComboBox QAbstractItemView { background-color: #1e1e1e; selection-background-color: #5285a6; }

            /* Thumbnail */
            QLabel#Thumbnail { 
                background-color: #1a1a1a; border: 1px solid #3d3d3d; border-radius: 6px; 
            }
            
            /* Botón Cámara */
            QPushButton#CamBtn { background-color: transparent; border: none; }
            QPushButton#CamBtn:hover { background-color: #444; border-radius: 12px; }

            /* Botón Load Settings (Secundario - Gris) */
            QPushButton#LoadBtn { 
                background-color: #444444; color: #ddd; font-weight: bold; font-size: 11px;
                border: 1px solid #333; border-radius: 4px;
            }
            QPushButton#LoadBtn:hover { background-color: #555555; border: 1px solid #666; }
            QPushButton#LoadBtn:pressed { background-color: #333; }

            /* Botón Build (Primario - Azul) */
            QPushButton#BuildBtn { 
                background-color: #2d5a73; color: white; font-weight: bold; font-size: 13px; 
                border: 1px solid #224a63; border-radius: 4px;
            }
            QPushButton#BuildBtn:hover { background-color: #3d6a83; border: 1px solid #5285a6; }
            QPushButton#BuildBtn:pressed { background-color: #1e3d4f; }
        """)

    # --- LÓGICA DE PERSISTENCIA ---
    def restore_last_session(self):
        """ Recupera el último asset guardado en QSettings """
        last_asset = self.settings.value("last_selected_asset")
        if last_asset:
            index = self.asset_combo.findText(last_asset)
            if index != -1:
                self.asset_combo.setCurrentIndex(index)
    
    def save_current_session(self):
        """ Guarda el asset actual para la próxima vez """
        if self.current_asset:
            self.settings.setValue("last_selected_asset", self.current_asset)

    # --- FUNCIONALIDAD ---
    def refresh_assets(self):
        self.asset_combo.blockSignals(True) # Evitar disparar eventos mientras llenamos
        self.asset_combo.clear()
        
        if os.path.exists(self.assets_path):
            # Listar carpetas
            dirs = sorted([d for d in os.listdir(self.assets_path) if os.path.isdir(os.path.join(self.assets_path, d))])
            self.asset_combo.addItems(dirs)
        
        self.asset_combo.blockSignals(False)
        
        # Forzar actualización manual del primero si existe
        if self.asset_combo.count() > 0:
            self.on_asset_changed()

    def on_asset_changed(self):
        self.current_asset = self.asset_combo.currentText()
        if not self.current_asset: return
        
        # 1. Actualizar Path UI
        full_path = os.path.join(self.assets_path, self.current_asset)
        self.path_label.setText(f"assets > {self.current_asset}")
        
        # 2. Cargar Imagen
        self.load_thumbnail(full_path)
        
        # 3. Guardar persistencia inmediatamente
        self.save_current_session()

    def load_thumbnail(self, asset_dir):
        # Buscar imagen
        thumb_path = None
        # Prioridad 1: thumbnail.jpg
        if os.path.exists(os.path.join(asset_dir, "thumbnail.jpg")):
            thumb_path = os.path.join(asset_dir, "thumbnail.jpg")
        else:
            # Prioridad 2: nombre_asset.png/jpg
            for ext in ['png', 'jpg', 'jpeg']:
                p = os.path.join(asset_dir, f"{self.current_asset}.{ext}")
                if os.path.exists(p):
                    thumb_path = p
                    break
        
        if thumb_path:
            pix = QtGui.QPixmap(thumb_path)
            scaled = pix.scaled(130, 130, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            self.image_label.setPixmap(scaled)
            self.image_label.setText("")
        else:
            self.image_label.setPixmap(QtGui.QPixmap())
            self.image_label.setText("No Preview")

    def take_screenshot(self):
        if not self.current_asset: return
        
        target_file = os.path.join(self.assets_path, self.current_asset, "thumbnail.jpg")
        
        # Playblast limpio
        try:
            cmds.viewHeadExtents(cmds.getPanel(wf=True), hud=False) # Ocultar HUD temporalmente
            cmds.playblast(frame=cmds.currentTime(q=True), 
                           format="image", compression="jpg",
                           completeFilename=target_file, 
                           widthHeight=(300, 300), percent=100, 
                           forceOverwrite=True, showOrnaments=False, viewer=False)
            print(f"Thumbnail guardado: {target_file}")
            self.load_thumbnail(os.path.join(self.assets_path, self.current_asset)) # Recargar
        except Exception as e:
            cmds.warning(f"Error capturando pantalla: {e}")

    # --- ACCIONES DEL RIG ---
    def run_load_settings(self):
        """
        Setea paths, importa guías, modelos y todo lo necesario sin construir el rig final.
        """
        if not self.current_asset: return
        
        asset_root = os.path.join(self.assets_path, self.current_asset)
        print(f"\n--- CARGANDO SETTINGS PARA: {self.current_asset} ---")
        print(f"Path Root: {asset_root}")
        
        # AQUÍ CONECTAS CON TU LÓGICA DE BACKEND
        # Ejemplo:
        # import my_pipeline_module
        # my_pipeline_module.set_environment(self.current_asset)
        # my_pipeline_module.import_guides(self.current_asset)
        # my_pipeline_module.import_model(self.current_asset)
        
        # Feedback visual simple
        cmds.inViewMessage(amg=f"<hl>{self.current_asset}</hl> Settings Loaded Successfully", pos='midCenter', fade=True)

        return self.current_asset

    def run_build(self):
        """
        Ejecuta el proceso completo de construcción.
        """
        if not self.current_asset: return
        print(f"\n--- CONSTRUYENDO RIG PARA: {self.current_asset} ---")

        import create_rig
        
        cmds.file(new=True, force=True)
        reload(create_rig)
        rig = create_rig.AutoRig()
        rig.build()

# --- LANZADOR SEGURO ---
global pro_asset_manager_instance

def show_ui():
    global pro_asset_manager_instance
    
    # Cerrar instancia previa si existe
    try:
        if pro_asset_manager_instance.isVisible():
            pro_asset_manager_instance.close()
            pro_asset_manager_instance.deleteLater()
    except:
        pass
    
    pro_asset_manager_instance = AssetManagerUI()
    pro_asset_manager_instance.show()

show_ui()