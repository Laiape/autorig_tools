"""Maya's native palette with shared headers, semantic actions and local icons."""
from pathlib import Path
import re

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets

from . import ui_theme

ICON_ROOT = Path(__file__).resolve().parents[2] / "icons" / "red"
_ICONS = {}


def key(text):
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def icon(name, color="#c7d3dc"):
    """Tint existing artwork in memory; installation assets remain unchanged."""
    cache_key = (name, color)
    if cache_key not in _ICONS:
        source = QtGui.QPixmap(str(ICON_ROOT / (name + ".png")))
        if source.isNull():
            return QtGui.QIcon()
        tinted = QtGui.QPixmap(source.size())
        tinted.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(tinted)
        painter.drawPixmap(0, 0, source)
        painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceIn)
        painter.fillRect(tinted.rect(), QtGui.QColor(color))
        painter.end()
        _ICONS[cache_key] = QtGui.QIcon(tinted)
    return _ICONS[cache_key]


def preserve_style(widget, subtree=False):
    """Keep functional color swatches / LIVE state, or an embedded vendor UI."""
    widget.setProperty("arStyleBoundary" if subtree else "arKeepStyle", True)
    return widget


def action(button, role="primary", icon_name=None):
    if _native_only(button):
        return button
    if role not in ui_theme.COLORS and role != "secondary":
        raise ValueError("Unknown AutoRig action role: " + role)
    button.setProperty("arActionRole", role)
    if icon_name:
        button.setProperty("arActionIcon", icon_name)
    # Re-polish only this control; do not change enabled or checked state.
    button.style().unpolish(button)
    button.style().polish(button)
    return button


def _stylesheet():
    rules = []
    for role, color in ui_theme.COLORS.items():
        selector = 'QPushButton[arActionRole="%s"]' % role
        rules += [
            selector + ' { background-color:%s; color:#f5f7f9; border:1px solid %s; border-radius:3px; padding:4px 9px; font-weight:bold; }' % (color, QtGui.QColor(color).lighter(125).name()),
            selector + ':hover { background-color:%s; }' % QtGui.QColor(color).lighter(118).name(),
            selector + ':pressed, ' + selector + ':checked { background-color:%s; }' % QtGui.QColor(color).darker(120).name(),
            selector + ':focus { border:1px solid #b5d4e8; }',
            selector + ':disabled { background-color:palette(button); color:palette(mid); border:1px solid palette(mid); }',
        ]
    return "\n".join(rules)


def _children(widget):
    return [child for child in widget.children() if isinstance(child, QtWidgets.QWidget)]


def _native_only(widget):
    return any(type(node).__name__ in ui_theme.NATIVE_ONLY for node in (widget, *_parents(widget)))


def _restore_native(widget):
    """Restore the opted-out skinning workspace in place, keeping its session."""
    def clear_button(button):
        button.setProperty("arActionRole", None)
        button.setProperty("arActionIcon", None)
        if not button.property("arKeepStyle"):
            button.setStyleSheet("")
        button.setIcon(QtGui.QIcon())
        button.style().unpolish(button); button.style().polish(button)
    def visit(node):
        if node.property("arStyleBoundary"):
            # Only our explicit Paint/Flood accents were changed in this island.
            for button in node.findChildren(QtWidgets.QPushButton):
                if button.property("arActionRole"):
                    clear_button(button)
            return
        name = type(node).__name__
        for attr in ui_theme.VENDOR_BOUNDARIES.get(name, ()):
            control = getattr(node, attr, None)
            if isinstance(control, QtWidgets.QWidget):
                preserve_style(control, subtree=True)
        if name == "RampPanel":
            for record in getattr(node, "editors", {}).values():
                control = record.get("widget")
                if isinstance(control, QtWidgets.QWidget):
                    preserve_style(control, subtree=True)
        for attr in ui_theme.FUNCTIONAL_STYLES.get(name, ()):
            control = getattr(node, attr, None)
            if isinstance(control, QtWidgets.QWidget):
                preserve_style(control)
        if node.objectName() in ("arToolHeader", "arHeaderIcon"):
            layout = node.parentWidget().layout() if node.parentWidget() else None
            if layout:
                layout.removeWidget(node)
            node.hide(); node.deleteLater()
            return
        if not node.property("arKeepStyle"):
            node.setStyleSheet("")
        if isinstance(node, QtWidgets.QPushButton):
            clear_button(node)
        if isinstance(node, QtWidgets.QTabWidget):
            for index in range(node.count()):
                node.setTabIcon(index, QtGui.QIcon())
        for child in _children(node):
            visit(child)
    visit(widget)
    if type(widget).__name__ in ui_theme.NATIVE_ONLY:
        widget.setProperty("arUiManaged", True)
        widget.setWindowIcon(QtGui.QIcon())
        if widget.layout():
            widget.layout().setContentsMargins(6, 6, 6, 6)


def _accent_color(widget):
    return "#3c7799" if widget.palette().color(QtGui.QPalette.Window).lightnessF() > 0.6 else "#82b7d6"


def _vendor_actions(root, kind):
    """Accent only explicit main controls in a vendor island, at runtime."""
    actions = {key(label): value for label, value in ui_theme.VENDOR_ACTIONS.get(kind, {}).items()}
    for button in root.findChildren(QtWidgets.QPushButton):
        selected = actions.get(key(button.text()))
        if selected:
            role, name = selected
            action(button, role, name)
            button.setIcon(icon(name, "#f5f7f9"))
            button.setIconSize(QtCore.QSize(16, 16))
            # A vendor may own its own ancestor stylesheet. Limit the override
            # to this button and retain native enabled / checked behavior.
            button.setStyleSheet(_stylesheet())


def _header(root, profile):
    if not profile.get("header") or root.findChild(QtWidgets.QWidget, "arToolHeader"):
        return
    title = profile["title"]
    # Reuse an existing heading rather than stack two title bars.
    aliases = {key(title)}
    if type(root).__name__ == "ToolFramework":
        aliases.add("autorig tools")
    if type(root).__name__ == "CurveLibraryUI":
        aliases.add("curve library")
    def containing(layout, target):
        if layout is None:
            return None
        if layout.indexOf(target) >= 0:
            return layout
        for index in range(layout.count()):
            nested = layout.itemAt(index).layout()
            found = containing(nested, target) if nested else None
            if found:
                return found
        return None
    for label in root.findChildren(QtWidgets.QLabel):
        if key(label.text()) not in aliases:
            continue
        container = label.parentWidget()
        layout = containing(container.layout(), label) if container else None
        if isinstance(layout, QtWidgets.QHBoxLayout) and layout.indexOf(label) >= 0:
            if not container.findChild(QtWidgets.QLabel, "arHeaderIcon"):
                mark = next((layout.itemAt(i).widget() for i in range(layout.count())
                             if isinstance(layout.itemAt(i).widget(), QtWidgets.QLabel)
                             and layout.itemAt(i).widget().pixmap() is not None
                             and not layout.itemAt(i).widget().pixmap().isNull()), None)
                if mark is None:
                    mark = QtWidgets.QLabel(container)
                    layout.insertWidget(layout.indexOf(label), mark)
                mark.setObjectName("arHeaderIcon")
                mark.setPixmap(icon(profile["icon"], _accent_color(root)).pixmap(24, 24))
            font = label.font(); font.setBold(True); label.setFont(font)
            return
    layout = root.layout()
    if not isinstance(layout, QtWidgets.QVBoxLayout):
        return
    header = QtWidgets.QWidget(root); header.setObjectName("arToolHeader")
    row = QtWidgets.QHBoxLayout(header); row.setContentsMargins(0, 0, 0, 4); row.setSpacing(8)
    mark = QtWidgets.QLabel(); mark.setPixmap(icon(profile["icon"], _accent_color(root)).pixmap(24, 24))
    row.addWidget(mark)
    label = QtWidgets.QLabel(title)
    font = label.font(); font.setBold(True); label.setFont(font)
    row.addWidget(label, 1)
    index = 1 if layout.count() and isinstance(layout.itemAt(0).widget(), QtWidgets.QMenuBar) else 0
    layout.insertWidget(index, header)


def apply_maya_style(widget, profile_name=None):
    """Strip obsolete chrome, then apply only owned semantic accents.

    Vendor boundaries are never traversed. Reapplying is idempotent and styles
    newly populated controls without erasing swatches or live editing feedback.
    """
    if widget is None or widget.property("arStyleBoundary"):
        return
    if _native_only(widget):
        _restore_native(widget)
        return
    profile_name = profile_name or widget.property("arProfile") or type(widget).__name__
    profile = ui_theme.PROFILES.get(profile_name)
    if profile:
        widget.setProperty("arProfile", profile_name)
        widget.setProperty("arUiManaged", True)
    def visit(node, current):
        if node.property("arStyleBoundary"):
            return
        name = type(node).__name__
        for attr in ui_theme.FUNCTIONAL_STYLES.get(name, ()):
            control = getattr(node, attr, None)
            if isinstance(control, QtWidgets.QWidget):
                preserve_style(control)
        for attr in ui_theme.VENDOR_BOUNDARIES.get(name, ()):
            control = getattr(node, attr, None)
            if isinstance(control, QtWidgets.QWidget):
                preserve_style(control, subtree=True)
                _vendor_actions(control, name)
        if name == "RampPanel":
            for record in getattr(node, "editors", {}).values():
                control = record.get("widget")
                if isinstance(control, QtWidgets.QWidget):
                    preserve_style(control, subtree=True)
                    _vendor_actions(control, name)
        nested = ui_theme.PROFILES.get(node.property("arProfile") or name)
        current = nested or current
        if not node.property("arKeepStyle"):
            node.setStyleSheet("")
        if isinstance(node, QtWidgets.QPushButton):
            label = key(node.text())
            role = node.property("arActionRole")
            if current:
                for candidate in ui_theme.COLORS:
                    if label in {key(text) for text in current[candidate]}:
                        role = candidate
                        break
            if node.objectName() == "primary" and not role:
                role = "primary"
            if role:
                action(node, role)
            icon_name = node.property("arActionIcon") or ui_theme.ACTION_ICONS.get(label)
            if not icon_name and role and current:
                icon_name = current["icon"]
            # Keep narrow picker/swatch controls usable and avoid text clipping.
            if label and icon_name and node.maximumWidth() > 65:
                node.setIcon(icon(icon_name, "#f5f7f9" if role in ui_theme.COLORS else node.palette().color(QtGui.QPalette.ButtonText).name()))
                node.setIconSize(QtCore.QSize(16, 16))
        if isinstance(node, QtWidgets.QTabWidget):
            for index in range(node.count()):
                name = ui_theme.TAB_ICONS.get(key(node.tabText(index)))
                if name:
                    node.setTabIcon(index, icon(name, _accent_color(node)))
            node.setIconSize(QtCore.QSize(16, 16))
        for child in _children(node):
            visit(child, current)
    visit(widget, profile)
    widget.setStyleSheet(_stylesheet())
    if profile:
        widget.setWindowIcon(icon(profile["icon"], _accent_color(widget)))
        if profile["header"]:
            layout = widget.layout()
            if layout:
                layout.setContentsMargins(10, 10, 10, 10)
                layout.setSpacing(8)
            _header(widget, profile)


def style_native_window(name, profile_name):
    """Give repository-owned cmds windows the same visual hierarchy."""
    from maya import OpenMayaUI as omui
    try:
        from shiboken6 import wrapInstance
    except ImportError:
        from shiboken2 import wrapInstance
    pointer = omui.MQtUtil.findWindow(name)
    if pointer:
        widget = wrapInstance(int(pointer), QtWidgets.QWidget)
        # Maya owns native layout geometry. Only decorate its controls.
        apply_maya_style(widget, profile_name)
        return widget


def restyle_open_tools():
    """Refresh owned open editors without recreating sessions or scene data."""
    app = QtWidgets.QApplication.instance()
    if not app:
        return 0
    roots = []
    for widget in app.allWidgets():
        if widget.property("arUiManaged") or type(widget).__name__ in ui_theme.PROFILES:
            if not any(parent in roots for parent in _parents(widget)):
                roots.append(widget)
    count = 0
    for widget in roots:
        if not any(parent in roots for parent in _parents(widget)):
            apply_maya_style(widget); count += 1
    return count


def _parents(widget):
    parent = widget.parentWidget()
    while parent:
        yield parent
        parent = parent.parentWidget()
