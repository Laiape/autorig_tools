"""
ui_utils.py
===========
Shared helpers for the PySide tool UIs.

`apply_maya_style` strips every custom stylesheet from a widget and all of its
descendants so the window inherits Maya's native Qt theme instead of a bespoke
dark/branded theme.  Call it at the end of a window's __init__ (and again after
creating widgets dynamically) to get the native Maya look.
"""

try:
    from PySide6 import QtWidgets
except ImportError:
    from PySide2 import QtWidgets


def apply_maya_style(widget):
    """
    Clear the stylesheet of `widget` and every child widget so they fall back to
    Maya's native palette.  Safe to call repeatedly (e.g. after adding rows).

    Args:
        widget (QtWidgets.QWidget): the root widget to clean (usually the window).
    """
    if widget is None:
        return

    widget.setStyleSheet("")
    for child in widget.findChildren(QtWidgets.QWidget):
        child.setStyleSheet("")
