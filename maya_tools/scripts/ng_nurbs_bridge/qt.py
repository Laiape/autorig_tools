"""Maya's bundled Qt binding only."""
try:
    from PySide6 import QtCore, QtWidgets
    from shiboken6 import wrapInstance, isValid
except ImportError:
    from PySide2 import QtCore, QtWidgets
    from shiboken2 import wrapInstance, isValid
