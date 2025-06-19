import maya.cmds as cmds
from functools import partial
from importlib import reload
from PySide2 import QtWidgets, QtCore, QtGui


def reload_ui():

    from scripts.ui import option_menu
    reload(option_menu)
    option_menu.LaiaUI.make_ui()

def export_guides(*args):

    from scripts.utils import guides_manager_self
    reload(guides_manager_self)
    guides_manager_self.get_guides_info()

def import_guides(*args):

    from scripts.utils import guides_manager_self
    reload(guides_manager_self)
    guides_manager_self.load_guides_info()

def export_curves(*args):

<<<<<<< HEAD
    from scripts.utils import curve_tool
    reload(curve_tool)
    curve_tool.get_all_ctl_curves_data()
=======
    from scripts.utils import controller_creator
    reload(controller_creator)
    controller_creator.export_curves_to_file()

def mirror_curves(*args):

    from scripts.utils import controller_creator
    reload(controller_creator)
    # controller_creator.mirror_curves() 
    # Line commented out until function is implemented

>>>>>>> 26b521417e4bbe8bce532416d58ab9636969d418

class UI(QtWidgets.QMainWindow):

    def __init__(self, parent=None):
        super(UI, self).__init__(parent)
        self.setWindowTitle("Auto Rig")

        self.main_layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.main_layout)

    def make_ui(self):

        self.populate_ui()
        self.layouts()

    def populate_ui(self):

        if cmds.menu("SelfMenu", exists=True):
            cmds.deleteUI("SelfMenu")
        cmds.menu("SelfMenu", label="Auto Rig", subMenu=True, tearOff=True, boldFont=True, parent="MayaWindow")

        self.settings = cmds.menuItem(label="Settings", subMenu=True, tearOff=True, boldFont=True)
        cmds.menuItem(label="Reload UI", command=reload_ui)

        cmds.setParent("..", menu=True)
        cmds.menuItem(dividerLabel="\n ", divider=True)

        self.guides = cmds.menuItem(label="Guides", subMenu=True, tearOff=True, boldFont=True)
        cmds.menuItem(label="Export Guides", command=export_guides)
        cmds.menuItem(label="Import Guides", command=import_guides)

        cmds.setParent("..", menu=True)
        cmds.menuItem(dividerLabel="\n ", divider=True)

        self.curves = cmds.menuItem(label="Curves", subMenu=True, tearOff=True, boldFont=True)
        cmds.menuItem(label="Export Curves", command=export_curves)
        cmds.menuItem(label="Mirror Curves", command=mirror_curves)



    def layouts(self):

        self.main_layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.main_layout)

        self.first_row = QtWidgets.QHBoxLayout()
        self.first_row.addWidget(self.settings)
        self.second_row = QtWidgets.QHBoxLayout()
        self.second_row.addWidget(self.guides)
        self.third_row = QtWidgets.QHBoxLayout()
        self.third_row.addWidget(self.curves)
        self.fourth_row = QtWidgets.QHBoxLayout()

        for layout in [self.first_row, self.second_row, self.third_row, self.fourth_row]:
            
            layout.setParent(self.main_layout)

