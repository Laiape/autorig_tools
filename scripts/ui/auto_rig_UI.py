from PySide2 import QtWidgets, QtCore, QtGui
import json
import icon_export
from importlib import reload
import maya.OpenMayaUI as omui
from shiboken2 import wrapInstance
import info

from utils import guides_manager
from autorig import spine_module
from autorig import create_rig


reload(icon_export)
reload(info)
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

        self.populate()
        self.layouts()
        self.stylesheet()

    def svg(self, data, part, module):

        pixmap = QtGui.QPixmap()
        pixmap.loadFromData(QtCore.QByteArray(data[part][module].encode()), "SVG")
        return pixmap
    
    def load_info(self):
        load_path = "C:/Users/laia.peris/Documents/maya/2024/scripts/info.JSON"
        with open(load_path, "r") as file:
            self.data = json.load(file)
            return self.data
        
    def load_icon(self):
        icon_path = "C:/Users/laiap/Documents/maya/2024/scripts/icon.JSON"
        with open(icon_path, "r") as file:
            icon_data = json.load(file)
        return icon_data

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
        
    def populate_tree(self):
        
        self.tree_widget = QtWidgets.QTreeWidget()
        self.tree_widget.setHeaderLabel("Character Structure")
        self.tree_widget.setColumnCount(1)
        self.tree_widget.setColumnWidth(0, 20)

        self.dummy_item = QtWidgets.QTreeWidgetItem(self.tree_widget, ["Dummy"])
        self.dummy_item.setExpanded(True)
        
        self.tree_spine = QtWidgets.QTreeWidgetItem(self.tree_widget, ["Spine"])
        self.tree_spine.setExpanded(True)
        
        self.tree_leg = QtWidgets.QTreeWidgetItem(self.tree_spine, ["Leg"])
        
        self.tree_arm = QtWidgets.QTreeWidgetItem(self.tree_spine, ["Arm"])
        self.tree_arm.setExpanded(True)
        self.tree_fingers = QtWidgets.QTreeWidgetItem(self.tree_arm, ["Fingers"])
        
        self.tree_neck = QtWidgets.QTreeWidgetItem(self.tree_spine, ["Head"])
        self.tree_neck.setExpanded(True)
        
        self.tree_facial = QtWidgets.QTreeWidgetItem(self.tree_neck, ["Facial"])
        self.tree_facial.setExpanded(True)
    
        self.tree_facial_eyes = QtWidgets.QTreeWidgetItem(self.tree_facial, ["Eyes"])
        self.tree_facial_lips = QtWidgets.QTreeWidgetItem(self.tree_facial, ["Lips"])
        self.tree_facial_eyebrows = QtWidgets.QTreeWidgetItem(self.tree_facial, ["Eyebrows"])
        self.tree_facial_ears = QtWidgets.QTreeWidgetItem(self.tree_facial, ["Ears"])
        self.tree_facial_nose = QtWidgets.QTreeWidgetItem(self.tree_facial, ["Nose"])

    def populate_add_module_to_tree(self):

        self.text_line = QtWidgets.QLineEdit()
        self.text_line.setPlaceholderText("Enter new module...")
        self.tree_widget.setItemWidget(self.dummy_item, 0, self.text_line)
        self.introduced_text = self.text_line.text()

      
        
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
        
        self.create_rig_button = QtWidgets.QPushButton("Create Rig")
        self.create_rig_button.setIcon(QtGui.QIcon("*"))
        self.create_rig_button.setIconSize(QtCore.QSize(200,3))
    
        self.create_rig_button.setToolTip("Create all the rig")
        self.delete_rig_button = QtWidgets.QPushButton("Delete Rig")
        self.delete_rig_button.setIcon(QtGui.QIcon("*"))
        self.delete_rig_button.setIconSize(QtCore.QSize(200,3))
 
        self.delete_rig_button.setToolTip("Delete all the rig")
        
    def template_button_connections(self, type):

        print(f"{type} template")
    
    def info_rig_guides_connections(self):

        QtWidgets.QMessageBox.information(self, "Rig Guides Info", info.text, QtWidgets.QMessageBox.Ok)

    def module_create_connections(self, part):

        print(f"{part} module created!")
    
    def rig_connections(self, type):
        print(f"Rig {type}!")

    def create_rig_connections(self):

        from autorig import create_rig
        reload(create_rig)

        build_rig = create_rig.AutoRig()
        build_rig.build()

    def create_connections(self):

        # Connect character template buttons
        self.template_buttons[0].clicked.connect(guides_manager.load_guides_info)
        self.template_buttons[1].clicked.connect(guides_manager.get_guides_info)
        self.template_buttons[2].clicked.connect(guides_manager.delete_guides)
        self.template_buttons[3].clicked.connect(self.info_rig_guides_connections)


        self.arm_module.clicked.connect(lambda: self.module_create_connections("Biped Arm"))
        self.leg_module.clicked.connect(lambda: self.module_create_connections("Biped Leg"))
        self.spine_module.clicked.connect(lambda: self.module_create_connections("Biped Spine"))
        self.neck_module.clicked.connect(lambda: self.module_create_connections("Biped Neck"))
        self.facial_module.clicked.connect(lambda: self.module_create_connections("Biped Facial"))
        self.quadruped_leg.clicked.connect(lambda: self.module_create_connections("Quadruped Leg"))
        self.quadruped_spine.clicked.connect(lambda: self.module_create_connections("Quadruped Spine"))
        self.quadruped_neck.clicked.connect(lambda: self.module_create_connections("Quadruped Neck"))
        self.quadruped_facial.clicked.connect(lambda: self.module_create_connections("Quadruped Facial"))


        self.text_line.textEdited.connect(self.add_module_to_tree_connections)


        self.create_rig_button.clicked.connect(self.create_rig_connections)
        self.delete_rig_button.clicked.connect(lambda: self.rig_connections("deleted"))


    def layouts(self):
        
        self.main_layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.main_layout)

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
        self.tree_layout.addWidget(self.tree_widget)
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
        
    def populate(self):
        
        self.populate_template_menu()
        self.populate_modules_menu()
        self.populate_tree()
        self.populate_rig_attributes()
        self.populate_add_module_to_tree()
        self.populate_create_rig()
        self.create_connections()
        self.stylesheet()

        
        # Set the main layout to the central widget
        central_widget = QtWidgets.QWidget()
        central_widget.setLayout(self.main_layout)
        self.setCentralWidget(central_widget)
        
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







