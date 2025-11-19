from PySide2 import QtWidgets, QtCore, QtGui
import json
from importlib import reload
import maya.OpenMayaUI as omui
from shiboken2 import wrapInstance
import os

class AnimPicker(QtWidgets.QMainWindow):

    def __init__(self, parent=None):

        """
        Initialize the Animation Picker UI.
        """
        super(AnimPicker, self).__init__(parent) # Call the parent class's constructor

        self.setWindowTitle("Animation Picker") # Set the window title
        self.setMinimumSize(300, 400)
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)

    def background_photo(self, imagePath):

        """
        Set a background photo for the Animation Picker UI.
        """
        
        

    


