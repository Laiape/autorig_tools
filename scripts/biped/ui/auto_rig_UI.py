from PySide2 import QtWidgets, QtCore, QtGui
import json
# import icon_export
from importlib import reload
import maya.OpenMayaUI as omui
from shiboken2 import wrapInstance
# import info
import os
import maya.api.OpenMaya as om

from biped.utils import guides_manager
from biped.autorig import spine_module_de_boor as spine_module
from biped.autorig import create_rig
import biped.utils.data_manager as data_manager
from biped.utils import rig_manager


# reload(icon_export)
# reload(info)
reload(guides_manager)
reload(spine_module)
reload(create_rig)


class UI(QtWidgets.QMainWindow):
    
    def __init__(self, parent=None):
        super(UI, self).__init__(parent)
        self.setWindowTitle("Auto Rig")
        # self.setGeometry(300, 300, 400, 300)
        self.setFixedSize(500, 400)

        self.main_layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.main_layout)
        self.main_window_setup()
        self.populate()
        self.layouts()
        self.stylesheet()

    def svg(self, data, part, module):

        pixmap = QtGui.QPixmap()
        pixmap.loadFromData(QtCore.QByteArray(data[part][module].encode()), "SVG")
        return pixmap
        
    def load_icon(self):

        complete_path = os.path.realpath(__file__)
        relative_path = complete_path.split("\scripts")[0]
        icons_path = os.path.join(relative_path, "icons")
        final_path = os.path.join(icons_path, "icon.JSON")

        with open(final_path, "r") as file:
            icon_data = json.load(file)
        return icon_data

    def main_window_setup(self):

        self.main_tab = QtWidgets.QTabWidget()
        self.auto_rig_tab = QtWidgets.QWidget()
        self.curves_tab = QtWidgets.QWidget()
        self.skin_cluster_tab = QtWidgets.QWidget()

        self.main_tab.addTab(self.auto_rig_tab, "Auto Rig")
        self.main_tab.addTab(self.curves_tab, "Curves")
        self.main_tab.addTab(self.skin_cluster_tab, "Skin Cluster")

    
    def populate_template_menu(self):
        
        data = self.load_icon()
        
        self.header_label = QtWidgets.QLabel("Character Template")
        self.header_label.setStyleSheet("font-weight: bold; font-size: 10px;")
        self.header_label.setAlignment(QtCore.Qt.AlignLeft)
        
        
        self.template_buttons = []
        
        for name, icon_path in data["top"].items():
            # Convert the SVG string to a QPixmap
            pixmap = QtGui.QPixmap()
            pixmap.loadFromData(QtCore.QByteArray(icon_path.encode()), "SVG")
            button = QtWidgets.QPushButton()
            button.setIcon(QtGui.QPixmap(pixmap))
            button.setIconSize(QtCore.QSize(25, 25))
            button.setToolTip(name + " template")

            self.template_buttons.append(button)
           
    def populate_modules_menu(self):
        
        data = self.load_icon()
        
        self.modules_tabs = QtWidgets.QTabWidget()
        self.biped_tab = QtWidgets.QWidget()
        self.quadruped_tab = QtWidgets.QWidget()
        
        
        self.modules_tabs.addTab(self.biped_tab, "Biped")
        self.modules_tabs.addTab(self.quadruped_tab, "Quadruped")

        pixmap = self.svg(data, "bottom", "arm")
        #Biped Module
        self.arm_module = QtWidgets.QPushButton("")
        self.arm_module.setIcon(QtGui.QPixmap(pixmap))
        self.arm_module.setIconSize(QtCore.QSize(24, 24))
        self.arm_module.setToolTip("Build arm module")
        self.arm_module.setStyleSheet("padding: 5px;")
        self.arm_module.setObjectName("modulesButtons")
        
        pixmap = self.svg(data, "bottom", "leg")
        self.leg_module = QtWidgets.QPushButton("")
        self.leg_module.setIcon(QtGui.QPixmap(pixmap))
        self.leg_module.setIconSize(QtCore.QSize(24, 24))
        self.leg_module.setToolTip("Build leg module")
        self.leg_module.setStyleSheet("padding: 5px;")
        self.leg_module.setObjectName("modulesButtons")
        
        pixmap = self.svg(data, "bottom", "spine")
        self.spine_module = QtWidgets.QPushButton("")
        self.spine_module.setIcon(QtGui.QPixmap(pixmap))
        self.spine_module.setToolTip("Build spine module")
        self.spine_module.setIconSize(QtCore.QSize(24, 24))
        self.spine_module.setStyleSheet("padding: 5px;")
        self.spine_module.setObjectName("modulesButtons")
   
        pixmap = self.svg(data, "bottom", "neck")
        self.neck_module = QtWidgets.QPushButton("")
        self.neck_module.setIcon(QtGui.QPixmap(pixmap))
        self.neck_module.setToolTip("Build neck module")
        self.neck_module.setIconSize(QtCore.QSize(24, 24))
        self.neck_module.setStyleSheet("padding: 5px;")
        self.neck_module.setObjectName("modulesButtons")

        pixmap = self.svg(data, "bottom", "facial")
        self.facial_module = QtWidgets.QPushButton("")
        self.facial_module.setIcon(QtGui.QPixmap(pixmap))
        self.facial_module.setToolTip("Build facial module")
        self.facial_module.setIconSize(QtCore.QSize(24, 24))
        self.facial_module.setStyleSheet("padding: 5px;")
        self.facial_module.setObjectName("modulesButtons")

        self.modules_buttons = [self.arm_module, self.leg_module, self.spine_module, self.neck_module, self.facial_module]
        
        # Quadruped Module
        pixmap = self.svg(data, "bottom", "paw")
        self.quadruped_leg = QtWidgets.QPushButton("")
        self.quadruped_leg.setIcon(QtGui.QPixmap(pixmap))
        self.quadruped_leg.setToolTip("Build leg module")
        self.quadruped_leg.setIconSize(QtCore.QSize(24, 24))
        self.quadruped_leg.setStyleSheet("padding: 5px;")
        self.quadruped_leg.setObjectName("modulesButtons")
        
        pixmap = self.svg(data, "bottom", "spine")
        self.quadruped_spine = QtWidgets.QPushButton("")
        self.quadruped_spine.setIcon(QtGui.QPixmap(pixmap))
        self.quadruped_spine.setToolTip("Build spine module")
        self.quadruped_spine.setIconSize(QtCore.QSize(24, 24))
        self.quadruped_spine.setStyleSheet("padding: 5px;")
        self.quadruped_spine.setObjectName("modulesButtons")

        pixmap = self.svg(data, "bottom", "neck")
        self.quadruped_neck = QtWidgets.QPushButton("")
        self.quadruped_neck.setIcon(QtGui.QPixmap(pixmap))
        self.quadruped_neck.setToolTip("Build neck module")
        self.quadruped_neck.setIconSize(QtCore.QSize(24, 24))
        self.quadruped_neck.setStyleSheet("padding: 5px;")
        self.quadruped_neck.setObjectName("modulesButtons")
        
        pixmap = self.svg(data, "bottom", "bunny")
        self.quadruped_facial = QtWidgets.QPushButton("")
        self.quadruped_facial.setIcon(QtGui.QPixmap(pixmap))
        self.quadruped_facial.setToolTip("Build facial module")
        self.quadruped_facial.setIconSize(QtCore.QSize(24, 24))
        self.quadruped_facial.setStyleSheet("padding: 5px;")
        self.quadruped_facial.setObjectName("modulesButtons")
        
        self.quadruped_modules_buttons = [self.quadruped_leg, self.quadruped_spine, self.quadruped_neck, self.quadruped_facial]
        
      
        
    def add_module_to_tree_connections(self):

        self.tree_widget_add = print(self.introduced_text + " added to the tree")

        

    def populate_rig_attributes(self):
        
        self.rig_attributes_label = QtWidgets.QLabel(" Rig Attributes")
        self.rig_attributes_label.setStyleSheet("font-weight: bold; font-size: 10px;")
        
        
        self.rig_attributes_tabs = QtWidgets.QTabWidget()
        self.rig_attributes_biped_arm = QtWidgets.QWidget()
        self.rig_attributes_biped_leg = QtWidgets.QWidget()
        self.rig_attributes_biped_spine = QtWidgets.QWidget()
        self.rig_attributes_biped_neck = QtWidgets.QWidget()
        self.rig_attributes_biped_facial = QtWidgets.QWidget()
        self.rig_attributes_quadruped = QtWidgets.QWidget()
        
        self.rig_attributes_tabs.addTab(self.rig_attributes_biped_arm, "Arm")
        self.rig_attributes_tabs.addTab(self.rig_attributes_biped_leg, "Leg")
        self.rig_attributes_tabs.addTab(self.rig_attributes_biped_spine, "Spine")
        self.rig_attributes_tabs.addTab(self.rig_attributes_biped_neck, "Neck")
        
    
        # Arm Attributes
        self.twist_joints_number = QtWidgets.QSpinBox()
        self.twist_joints_number.setRange(0, 7)
        self.twist_joints_number.setValue(5)
        self.twist_joints_number.setFixedWidth(70)
        self.twist_joints_label = QtWidgets.QLabel("Twist Joints: (0-7)")
        self.twist_joints_label.setStyleSheet("font-weight: bold; font-size: 10px;")
        self.twist_joints_number.setSingleStep(1)
        self.curvature_checkbox = QtWidgets.QCheckBox("Curvature")
        self.curvature_checkbox.setChecked(True)
        self.soft_ik_checkbox = QtWidgets.QCheckBox("Soft IK")
        self.soft_ik_checkbox.setChecked(True)
        self.auto_stretch_checkbox = QtWidgets.QCheckBox("Stretch")
        self.auto_stretch_checkbox.setChecked(True)
        self.finger_extra_attributes = QtWidgets.QCheckBox("Finger Attributes")
        self.finger_extra_attributes.setChecked(True)

       
        
        
        # Leg Attributes
        self.leg_twist_joints_number = QtWidgets.QSpinBox()
        self.leg_twist_joints_number.setRange(0, 7)
        self.leg_twist_joints_number.setValue(5)
        self.leg_twist_joints_number.setFixedWidth(70)
        self.leg_twist_joints_label = QtWidgets.QLabel("Twist Joints: (0-7)")
        self.leg_twist_joints_label.setStyleSheet("font-weight: bold; font-size: 10px;")
        self.leg_twist_joints_number.setSingleStep(1)
        self.leg_curvature_checkbox = QtWidgets.QCheckBox("Curvature")
        self.leg_curvature_checkbox.setChecked(True)
        self.leg_soft_ik_checkbox = QtWidgets.QCheckBox("Soft IK")
        self.leg_soft_ik_checkbox.setChecked(True)
        self.leg_auto_stretch_checkbox = QtWidgets.QCheckBox("Stretch")
        self.leg_auto_stretch_checkbox.setChecked(True)
        self.leg_finger_extra_attributes = QtWidgets.QCheckBox("Foot Attributes")
        self.leg_finger_extra_attributes.setChecked(True)
        
        
        # Spine Attributes
        self.spine_twist_joints_number = QtWidgets.QSpinBox()
        self.spine_twist_joints_number.setRange(0, 10)
        self.spine_twist_joints_number.setValue(5)
        self.spine_twist_joints_number.setFixedWidth(70)
        self.spine_twist_joints_label = QtWidgets.QLabel("Spine Joints: (0-10)")
        self.spine_twist_joints_label.setStyleSheet("font-weight: bold; font-size: 10px;")
        self.spine_twist_joints_number.setSingleStep(1)
        self.spine_reverse_twist_checkbox = QtWidgets.QCheckBox("Reverse Spine")
        self.spine_reverse_twist_checkbox.setChecked(True)
        self.spine_volume_checkbox = QtWidgets.QCheckBox("Volume Preservation")
        self.spine_volume_checkbox.setChecked(True)
        self.spine_stretch_checkbox = QtWidgets.QCheckBox("Stretch")
        self.spine_stretch_checkbox.setChecked(True)
        
        # Neck Attributes
        self.neck_volume_checkbox = QtWidgets.QCheckBox("Volume Preservation")
        self.neck_volume_checkbox.setChecked(True)
        self.neck_stretch_checkbox = QtWidgets.QCheckBox("Stretch")
        self.neck_stretch_checkbox.setChecked(True)
        self.neck_follow_checkbox = QtWidgets.QCheckBox("Follow")
        self.neck_follow_checkbox.setChecked(True)
    
    def populate_create_rig(self):
        
        self.create_rig_button = QtWidgets.QPushButton("Create Biped Rig")
        self.create_rig_button.setIcon(QtGui.QIcon("*"))
        self.create_rig_button.setIconSize(QtCore.QSize(200,3))
        self.create_rig_button.setToolTip("Create all biped rig")

        self.delete_rig_button = QtWidgets.QPushButton("Create Quadruped Rig")
        self.delete_rig_button.setIcon(QtGui.QIcon("*"))
        self.delete_rig_button.setIconSize(QtCore.QSize(200,3))
        import quadruped.autorig.create_rig
        reload(quadruped.autorig.create_rig)

    def populate_curves_interactions(self):

        data = self.load_icon()

        # pixmap = self.svg(data, "curves", "export")
        self.export_curves_button = QtWidgets.QPushButton("Export Curves")
        # self.export_curves_button.setIcon(QtGui.QPixmap(pixmap))
        self.export_curves_button.setToolTip("Export all the curves in the scene")
        self.export_curves_button.setIconSize(QtCore.QSize(24, 24))
        self.export_curves_button.setStyleSheet("padding: 5px;")
        self.export_curves_button.setObjectName("modulesButtons")

        # Curve creator: shapes, colors, sizes, offset_grps, etc.
        # Shapes: circle, square, cube, sphere, arrow, diamond, cross, star, heart, custom (load from file)

    def populate_skin_cluster_interactions(self):

        data = self.load_icon()

        pixmap = self.svg(data, "skin_cluster", "export")
        self.export_skin_weights_button = QtWidgets.QPushButton("")
        self.export_skin_weights_button.setIcon(QtGui.QPixmap(pixmap))
        self.export_skin_weights_button.setText("Export Skin Cluster")
        self.export_skin_weights_button.setToolTip("Export all the skin cluster weights of the selected mesh")
        self.export_skin_weights_button.setIconSize(QtCore.QSize(24, 24))
        self.export_skin_weights_button.setObjectName("modulesButtons")

        pixmap = self.svg(data, "skin_cluster", "import")
        self.import_skin_weights_button = QtWidgets.QPushButton("")
        self.import_skin_weights_button.setIcon(QtGui.QPixmap(pixmap))
        self.import_skin_weights_button.setText("Import Skin Cluster")
        self.import_skin_weights_button.setToolTip("Import all the skin cluster weights of the selected mesh")
        self.import_skin_weights_button.setIconSize(QtCore.QSize(24, 24))
        self.import_skin_weights_button.setObjectName("modulesButtons")

        # Local skin cluster
        self.local_skin_cluster_header = QtWidgets.QGroupBox("LOCAL SKIN CLUSTERS")
        self.local_skin_cluster_header.setStyleSheet("font-weight: bold; font-size: 10px;")

        self.body_skin_cluster_header = QtWidgets.QGroupBox("BODY SKIN CLUSTERS")
        self.body_skin_cluster_header.setStyleSheet("font-weight: bold; font-size: 10px;")

        self.local_skin_cluster_box = QtWidgets.QFrame()
        self.local_skin_cluster_box.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.local_skin_cluster_box.setFrameShadow(QtWidgets.QFrame.Raised)

        self.body_skin_cluster_box = QtWidgets.QFrame()
        self.body_skin_cluster_box.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.body_skin_cluster_box.setFrameShadow(QtWidgets.QFrame.Raised)

    def template_button_connections(self, type):

        print(f"{type} template")
    
    # def info_rig_guides_connections(self):

    #     QtWidgets.QMessageBox.information(self, "Rig Guides Info", info.text, QtWidgets.QMessageBox.Ok)

    def module_create_connections(self, part):

        print(f"{part} module created!")
    
    def rig_connections(self, type):
        print(f"Rig {type}!")

    def create_biped_rig_connections(self):

        import shutil

        # rig_build_info = {
        #     "rig_attributes": self.get_rig_attributes()
        # }

        try:
            complete_path = os.path.realpath(__file__)
            relative_path = complete_path.split("\scripts")[0]
            relative_folder = os.path.join(relative_path, "build")
            final_path = os.path.join(relative_folder, "character.build")
        except:
            relative_path = r"H:\GIT\biped_autorig"
            relative_folder = os.path.join(relative_path, "build")
            final_path = os.path.join(relative_folder, "character.build")

        # with open(final_path, 'w') as f:
        #     json.dump(rig_build_info, f, indent=4)

        build_rig = create_rig.AutoRig()
        build_rig.build()

        character_name = data_manager.DataExportBiped().get_data("basic_structure", "character_name")
        new_path = os.path.join(relative_folder, f"{character_name}_v001.build")
        
        try:
            if os.path.exists(new_path):
                os.remove(new_path)

            os.rename(final_path, new_path)
            # Prepare target assets folder and move the build file there
            target_dir = os.path.join(relative_path, "assets", character_name, "build")
            os.makedirs(target_dir, exist_ok=True)
            target_path = os.path.join(target_dir, os.path.basename(new_path))

            try:
                if os.path.exists(target_path):
                    os.remove(target_path)
                shutil.move(new_path, target_path)
                new_path = target_path  # update path for the success message below
            except Exception as e:
                om.MGlobal.displayError(f"Error moving file to assets: {e}")
                return
            print(f"Rig properties exported successfully to {new_path}!")
        except Exception as e:
            om.MGlobal.displayError(f"Error renaming file: {e}")
            return

    def create_quadruped_rig_connections(self):
        from quadruped.autorig import create_rig
        reload(create_rig)

        build_rig = create_rig.AutoRig()
        build_rig.build()


    def export_curves_connections(self):

        from biped.utils import curve_tool
        reload(curve_tool)

        curve_tool.get_all_ctl_curves_data()
        print("Curves exported successfully!")

    def export_skin_weights_connections(self):

        from biped.tools import skin_cluster
        reload(skin_cluster)

        skin_cluster.export_joint_weights_json()
        print("Skin weights exported successfully!")

    def import_skin_weights_connections(self):
        from biped.tools import skin_cluster

        reload(skin_cluster)

        skin_cluster.import_joint_weights_json()
        print("Skin weights imported successfully!")

    def create_connections(self):

        # Connect character template buttons
        self.template_buttons[0].clicked.connect(guides_manager.load_guides_info)
        self.template_buttons[1].clicked.connect(guides_manager.get_guides_info)
        self.template_buttons[2].clicked.connect(guides_manager.delete_guides)
        # self.template_buttons[3].clicked.connect(self.info_rig_guides_connections)


        self.arm_module.clicked.connect(lambda: self.module_create_connections("Biped Arm"))
        self.leg_module.clicked.connect(lambda: self.module_create_connections("Biped Leg"))
        self.spine_module.clicked.connect(lambda: self.module_create_connections("Biped Spine"))
        self.neck_module.clicked.connect(lambda: self.module_create_connections("Biped Neck"))
        self.facial_module.clicked.connect(lambda: self.module_create_connections("Biped Facial"))
        self.quadruped_leg.clicked.connect(lambda: self.module_create_connections("Quadruped Leg"))
        self.quadruped_spine.clicked.connect(lambda: self.module_create_connections("Quadruped Spine"))
        self.quadruped_neck.clicked.connect(lambda: self.module_create_connections("Quadruped Neck"))
        self.quadruped_facial.clicked.connect(lambda: self.module_create_connections("Quadruped Facial"))

        self.create_rig_button.clicked.connect(self.create_biped_rig_connections)
        self.delete_rig_button.clicked.connect(self.create_quadruped_rig_connections)

        self.export_curves_button.clicked.connect(self.export_curves_connections)
        self.export_skin_weights_button.clicked.connect(self.export_skin_weights_connections)
        self.import_skin_weights_button.clicked.connect(self.import_skin_weights_connections)


    def layouts(self):
        
        self.main_tab_layout = QtWidgets.QVBoxLayout()
        self.auto_rig_tab.setLayout(self.main_tab_layout)
        self.curves_tab_layout = QtWidgets.QVBoxLayout()
        self.curves_tab.setLayout(self.curves_tab_layout)
        self.skin_cluster_tab_layout = QtWidgets.QVBoxLayout()
        self.skin_cluster_tab.setLayout(self.skin_cluster_tab_layout)
        
        self.main_layout = QtWidgets.QVBoxLayout()
        self.main_tab_layout.addLayout(self.main_layout)
        # self.skin_cluster_tab_layout.addLayout(self.main_layout)

        # Template Layout
        self.template_layout_header = QtWidgets.QHBoxLayout()
        self.template_layout_header.addWidget(self.header_label)
        self.template_layout_header.addStretch()
        
        self.templates_layout = QtWidgets.QHBoxLayout()
        for button in self.template_buttons:
            self.templates_layout.addWidget(button)
            
        self.templates_layout.addStretch()
        
        # Modules Layout
        self.modules_layout = QtWidgets.QVBoxLayout()
        
        # Add buttons to the Biped tab
        self.biped_tab_layout = QtWidgets.QHBoxLayout()
        self.biped_tab.setLayout(self.biped_tab_layout)
      
        
        for button in self.modules_buttons:
            self.biped_tab_layout.addWidget(button)
        
        # Add buttons to the Quadruped tab
        self.quadruped_tab_layout = QtWidgets.QHBoxLayout()
        self.quadruped_tab.setLayout(self.quadruped_tab_layout)
        for button in self.quadruped_modules_buttons:
            self.quadruped_tab_layout.addWidget(button)
            
            
        # Add the modules tabs to the modules layout
        self.modules_layout.addWidget(self.modules_tabs)
        
        # Add the biped and quadruped to the modules layout
        self.modules_layout.addLayout(self.biped_tab_layout)
        self.modules_layout.addLayout(self.quadruped_tab_layout)
        
        self.modules_layout.addStretch()
        
        
        self.tree_attrs_layout = QtWidgets.QHBoxLayout()
        # Tree Layout
        self.tree_layout = QtWidgets.QVBoxLayout()
        self.tree_layout.addStretch()
        self.tree_attrs_layout.addLayout(self.tree_layout)
        
        #Attrs Layout
        self.attrs_layout = QtWidgets.QVBoxLayout()
        self.attrs_layout.addWidget(self.rig_attributes_label)
        self.attrs_layout.addWidget(self.rig_attributes_tabs)  # Add the rig attributes tabs
        self.attrs_layout.addStretch()
        self.tree_attrs_layout.addLayout(self.attrs_layout)
        
        
        # Arm Attrs Layout
        arm_layout = QtWidgets.QVBoxLayout()
        arm_layout.addWidget(self.twist_joints_label)
        arm_layout.addWidget(self.twist_joints_number)
        arm_layout.addWidget(self.curvature_checkbox)
        arm_layout.addWidget(self.soft_ik_checkbox)
        arm_layout.addWidget(self.auto_stretch_checkbox)
        arm_layout.addWidget(self.finger_extra_attributes)
        arm_layout.addStretch()
        self.rig_attributes_biped_arm.setLayout(arm_layout)
        
        
        # Leg Attrs Layout
        leg_layout = QtWidgets.QVBoxLayout()
        leg_layout.addWidget(self.leg_twist_joints_label)
        leg_layout.addWidget(self.leg_twist_joints_number)
        leg_layout.addWidget(self.leg_curvature_checkbox)
        leg_layout.addWidget(self.leg_soft_ik_checkbox)
        leg_layout.addWidget(self.leg_auto_stretch_checkbox)
        leg_layout.addWidget(self.leg_finger_extra_attributes)
        leg_layout.addStretch()
        self.rig_attributes_biped_leg.setLayout(leg_layout)
        
        # Spine Attrs Layout
        spine_layout = QtWidgets.QVBoxLayout()
        spine_layout.addWidget(self.spine_twist_joints_label)
        spine_layout.addWidget(self.spine_twist_joints_number)
        spine_layout.addWidget(self.spine_reverse_twist_checkbox)
        spine_layout.addWidget(self.spine_volume_checkbox)
        spine_layout.addWidget(self.spine_stretch_checkbox)
        spine_layout.addStretch()
        self.rig_attributes_biped_spine.setLayout(spine_layout)

        # Neck Attrs Layout
        neck_layout = QtWidgets.QVBoxLayout()
        neck_layout.addWidget(self.neck_volume_checkbox)
        neck_layout.addWidget(self.neck_stretch_checkbox)
        neck_layout.addWidget(self.neck_follow_checkbox)


        neck_layout.addStretch()
        self.rig_attributes_biped_neck.setLayout(neck_layout)
        
        self.attrs_layout.addStretch()
        
        # Build rig layout
        self.build_rig_layout = QtWidgets.QHBoxLayout()
        self.build_rig_layout.addWidget(self.create_rig_button)
        self.build_rig_layout.addWidget(self.delete_rig_button)
        
        self.build_rig_layout.addStretch()
        
        
        # Set the main layout to the central widget
        self.main_layout.setAlignment(QtCore.Qt.AlignTop)
        
        
        # Add all layouts to the main layout
        self.main_layout.addLayout(self.template_layout_header)
        self.main_layout.addLayout(self.templates_layout)
        self.main_layout.addLayout(self.modules_layout)
        self.main_layout.addLayout(self.tree_attrs_layout)
        self.main_layout.addLayout(self.build_rig_layout)


        # Curves Layout
        self.curves_layout = QtWidgets.QVBoxLayout()
        self.curves_layout.addWidget(self.export_curves_button)
        self.curves_tab_layout.addLayout(self.curves_layout)

        # Skin Cluster Layout
        self.skin_cluster_layout = QtWidgets.QVBoxLayout()
        # Skin Cluster Buttons
        self.skin_cluster_layout.addWidget(self.export_skin_weights_button)
        self.skin_cluster_layout.addWidget(self.import_skin_weights_button)
        self.skin_cluster_tab_layout.addLayout(self.skin_cluster_layout)

        # Skin Cluster Boxes
        skin_cluster_box_main_layout = QtWidgets.QHBoxLayout()
        left_header_layout = QtWidgets.QVBoxLayout()
        left_header_layout.addWidget(self.local_skin_cluster_header)
        left_header_layout.addStretch()
        right_header_layout = QtWidgets.QVBoxLayout()
        right_header_layout.addWidget(self.body_skin_cluster_header)
        right_header_layout.addStretch()

        skin_cluster_box_main_layout.addLayout(left_header_layout)
        skin_cluster_box_main_layout.addLayout(right_header_layout)
        

        second_box_layout = QtWidgets.QHBoxLayout()
        second_box_layout.addWidget(self.local_skin_cluster_box)
        second_box_layout.addWidget(self.body_skin_cluster_box)
        self.skin_cluster_layout.addLayout(second_box_layout)

        self.skin_cluster_layout.addLayout(skin_cluster_box_main_layout)
        self.skin_cluster_layout.addLayout(second_box_layout)


    def get_rig_attributes(self):

        """
        Get the rig attributes from the UI elements, based on the selected modules.
        """

        rig_attributes = {
            "arm": {
                "twist_joints": self.twist_joints_number.value(),
                "curvature": self.curvature_checkbox.isChecked(),
                "soft_ik": self.soft_ik_checkbox.isChecked(),
                "auto_stretch": self.auto_stretch_checkbox.isChecked(),
                "finger_extra_attributes": self.finger_extra_attributes.isChecked()
            },
            "leg": {
                "twist_joints": self.leg_twist_joints_number.value(),
                "curvature": self.leg_curvature_checkbox.isChecked(),
                "soft_ik": self.leg_soft_ik_checkbox.isChecked(),
                "auto_stretch": self.leg_auto_stretch_checkbox.isChecked(),
                "foot_extra_attributes": self.leg_finger_extra_attributes.isChecked()
            },
            "spine": {
                "spine_joints": self.spine_twist_joints_number.value(),
                "reverse_spine": self.spine_reverse_twist_checkbox.isChecked(),
                "volume_preservation": self.spine_volume_checkbox.isChecked(),
                "stretch": self.spine_stretch_checkbox.isChecked()
            },
            "neck": {
                "volume_preservation": self.neck_volume_checkbox.isChecked(),
                "stretch": self.neck_stretch_checkbox.isChecked(),
                "follow": self.neck_follow_checkbox.isChecked()
            }
        }

        return rig_attributes


    def populate(self):
        
        self.populate_template_menu()
        self.populate_modules_menu()
        self.populate_rig_attributes()
        self.populate_create_rig()
        self.populate_curves_interactions()
        self.populate_skin_cluster_interactions()
        self.create_connections()
        self.stylesheet()

        
        # Set the main tab widget as the central widget
        self.setCentralWidget(self.main_tab)
        
    def stylesheet(self):

        self.setStyleSheet("""
            QMainWindow {
            background-color: #2e2e2e; /* Dark gray */
            color: white;
            }
            QLabel {
            color: white;
            font-size: 15px;
            font-weight: bold;
            }
            QTreeWidget {
            background-color: #3a3a3a; /* Medium gray */
            color: white;
            border: 1px solid #ffffff; /* White */
            border-radius: 5px;
            }
            QTreeWidget::item {
            background-color: #3a3a3a; /* Medium gray */
            color: white;
            }
            QTreeWidget::item:hover {
            background-color: #ffffff; /* White */
            color: black;
            }
            QTreeView::branch:open:has-children {
            font-weight: bold; /* Make arrows bold */
            }
            QTreeView::branch:closed:has-children {
            font-weight: bold; /* Make arrows bold */
            }
            QTabWidget {
            background-color: #3a3a3a; /* Medium gray */
            color: white;
            border: 1px solid #ffffff; /* White */
            border-radius: 5px;
            }
            QTabWidget::tab {
            background-color: #ffffff; /* White */
            color: black;
            border: 1px solid #1e90ff; /* Dodger blue */
            border-radius: 5px;
            }
            QTabWidget::tab:selected {
            background-color: #1e90ff; /* Dodger blue */
            color: white;
            }
            QPushButton {
            background-color: #ffffff; /* White */
            color: black;
            border: 1px solid #1e90ff; /* Dodger blue */
            border-radius: 10px; /* Rounded buttons */
            padding: 5px;
            }
            QPushButton:hover {
            background-color: #1e90ff; /* Dodger blue */
            color: white;
            }
            QCheckBox {
            color: white;
            font-size: 13px;
            }
            QSpinBox {
            background-color: #3a3a3a; /* Medium gray */
            color: white;
            border: 1px solid #ffffff; /* White */
            border-radius: 5px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
            background-color: #ffffff; /* White */
            border: none;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
            background-color: #1e90ff; /* Dodger blue */
            }
        """)





maya_main_window_ptr = omui.MQtUtil.mainWindow()
maya_main_window = wrapInstance(int(maya_main_window_ptr), QtWidgets.QWidget)

global ui  # Optional: makes it easier to test multiple times
try:
    ui.close()  # Close the existing window if it's open
except:
    pass

ui = UI(parent=maya_main_window)
ui.populate()
ui.show()







