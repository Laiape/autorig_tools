"""Native Maya modeling checker and guided review of Modeling QC Checklist.

Usage: from tools.model_checker import show; show()
"""
import json
import weakref

from maya import cmds, OpenMayaUI as omui
import maya.api.OpenMaya as om
try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from shiboken6 import wrapInstance
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets
    from shiboken2 import wrapInstance

from . import model_checker_core as core
try:
    from maya_tools.scripts.utils import ui_utils
except ImportError:
    from utils import ui_utils

Qt = QtCore.Qt
_window = None


def _maya_main_window():
    pointer = omui.MQtUtil.mainWindow()
    return wrapInstance(int(pointer), QtWidgets.QWidget) if pointer else None


def _remove_callbacks(*groups):
    for group in groups:
        for callback in group:
            try:
                om.MMessage.removeCallback(callback)
            except RuntimeError:
                pass
        group[:] = []


class ModelCheckerWindow(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent or _maya_main_window())
        self.setObjectName("AutoRigModelChecker")
        self.setWindowTitle("Model Checker")
        self.setWindowFlags(self.windowFlags() | Qt.Window)
        self.resize(920, 760)
        self.setMinimumSize(640, 520)
        self.results, self.roots, self.stale = {}, None, False
        self._busy = self._cancelled = False
        self._callbacks, self._watchers = [], []
        self._check_items, self._review_widgets = {}, {}
        self._vertex_sets, self._unmatched = [[], []], []
        self._build()
        ui_utils.apply_maya_style(self)
        self._stale_timer = QtCore.QTimer(self)
        self._stale_timer.setSingleShot(True)
        self._stale_timer.timeout.connect(self._show_stale)
        owner = weakref.ref(self)
        def changed(*args):
            instance = owner()
            if instance is not None and not instance._busy:
                instance._mark_stale()
        def scene_changed(*args):
            instance = owner()
            if instance is not None:
                instance._reset_scene()
        self._changed_callback = changed
        for event in ("Undo", "Redo", "NameChanged"):
            self._callbacks.append(om.MEventMessage.addEventCallback(event, changed))
        for event in ("SceneOpened", "NewSceneOpened"):
            self._callbacks.append(om.MEventMessage.addEventCallback(event, scene_changed))
        self._callbacks.append(om.MDGMessage.addNodeAddedCallback(changed, "dependNode"))
        self._callbacks.append(om.MDGMessage.addNodeRemovedCallback(changed, "dependNode"))
        self._callbacks.append(om.MDGMessage.addConnectionCallback(changed))
        callbacks, watchers = self._callbacks, self._watchers
        self.destroyed.connect(lambda *args: _remove_callbacks(callbacks, watchers))
        self._update_summary()

    def closeEvent(self, event):
        if self._busy:
            self._cancelled = True
            event.ignore()
            return
        _remove_callbacks(self._callbacks, self._watchers)
        super().closeEvent(event)

    def _button(self, label, callback, layout):
        button = QtWidgets.QPushButton(label)
        button.setAutoDefault(False)
        button.clicked.connect(callback)
        layout.addWidget(button)
        return button

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        heading = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("MODEL CHECKER")
        font = title.font(); font.setBold(True); title.setFont(font)
        heading.addWidget(title)
        self.scope_info = QtWidgets.QLabel("Whole scene"); self.scope_info.setWordWrap(True)
        heading.addWidget(self.scope_info, 1); layout.addLayout(heading)
        scope_row = QtWidgets.QHBoxLayout()
        scope_row.addWidget(QtWidgets.QLabel("Scope"))
        self.scope = QtWidgets.QComboBox(); self.scope.addItems(("Whole scene", "Loaded selection"))
        self.scope.setAccessibleName("Check scope")
        self.scope.currentIndexChanged.connect(self._scope_changed)
        scope_row.addWidget(self.scope)
        self.load_scope_btn = self._button("From selection", self._load_scope, scope_row)
        self.load_scope_btn.setToolTip("Pin selected mesh / group roots. Selecting findings will not change this scope.")
        scope_row.addStretch()
        self.run_btn = self._button("Run all checks", self.run_all, scope_row)
        self.run_selected_btn = self._button("Run selected checks", self.run_selected, scope_row)
        self.cancel_btn = self._button("Cancel", self._cancel, scope_row); self.cancel_btn.setEnabled(False)
        layout.addLayout(scope_row)
        settings = QtWidgets.QGroupBox("Check settings")
        settings.setCheckable(True); settings.setChecked(False)
        settings_box = QtWidgets.QVBoxLayout(settings)
        self.settings_body = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(self.settings_body); form.setContentsMargins(0, 0, 0, 0)
        self.tolerance = QtWidgets.QDoubleSpinBox()
        self.tolerance.setDecimals(6); self.tolerance.setRange(0.000001, 1000); self.tolerance.setValue(0.001)
        self.ground_tolerance = QtWidgets.QDoubleSpinBox()
        self.ground_tolerance.setDecimals(4); self.ground_tolerance.setRange(0, 10000); self.ground_tolerance.setValue(0.5)
        self.gpu = QtWidgets.QComboBox()
        self.gpu.addItem("NVIDIA checklist guidance: 2000 vertices", 2000)
        self.gpu.addItem("AMD checklist guidance: 500 vertices", 500)
        form.addRow("Position tolerance (scene units)", self.tolerance)
        form.addRow("Ground tolerance (scene units)", self.ground_tolerance)
        form.addRow("Small-mesh advisory", self.gpu); self.gpu.setToolTip(core.BY_ID["gpu"].tip)
        settings_box.addWidget(self.settings_body); self.settings_body.hide()
        settings.toggled.connect(self.settings_body.setVisible); layout.addWidget(settings)
        for control in (self.tolerance, self.ground_tolerance):
            control.valueChanged.connect(self._invalidate)
        self.gpu.currentIndexChanged.connect(self._invalidate)
        self.tabs = QtWidgets.QTabWidget(); self.tabs.setDocumentMode(True)
        self.tabs.addTab(self._build_automatic(), "Automatic checks")
        self.tabs.addTab(self._build_review(), "Visual review")
        self.tabs.addTab(self._build_vertex_sets(), "Vertex comparison")
        self.tabs.addTab(self._build_report(), "Report")
        self.tabs.currentChanged.connect(lambda index: self._refresh_report() if index == 3 else None)
        layout.addWidget(self.tabs, 1)
        self.progress = QtWidgets.QProgressBar(); self.progress.setMaximum(len(core.CHECKS)); self.progress.setValue(0)
        self.progress.hide(); layout.addWidget(self.progress)
        self.summary = QtWidgets.QLabel(); self.summary.setWordWrap(True)
        self.summary.setTextInteractionFlags(Qt.TextSelectableByMouse); layout.addWidget(self.summary)
        self.status = QtWidgets.QLabel("Select a scope, run checks, then complete the visual review.")
        self.status.setWordWrap(True); self.status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.status)

    def _build_automatic(self):
        page = QtWidgets.QWidget(); box = QtWidgets.QVBoxLayout(page); box.setContentsMargins(0, 8, 0, 0)
        search = QtWidgets.QHBoxLayout()
        self.query = QtWidgets.QLineEdit(); self.query.setPlaceholderText("Filter checks...")
        self.query.setClearButtonEnabled(True); self.query.setAccessibleName("Filter automatic checks")
        self.query.textChanged.connect(self._filter); search.addWidget(self.query, 1)
        self.result_filter = QtWidgets.QComboBox(); self.result_filter.addItems(("All results", "Findings", "Errors", "Not run"))
        self.result_filter.currentIndexChanged.connect(self._filter); search.addWidget(self.result_filter)
        box.addLayout(search)
        splitter = QtWidgets.QSplitter(Qt.Vertical)
        self.check_tree = QtWidgets.QTreeWidget()
        self.check_tree.setHeaderLabels(("Check", "Priority", "Status", "Findings"))
        self.check_tree.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.check_tree.setUniformRowHeights(True); self.check_tree.setAccessibleName("Automatic check results")
        self.check_tree.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        for column in (1, 2, 3):
            self.check_tree.header().setSectionResizeMode(column, QtWidgets.QHeaderView.Interactive)
        self.check_tree.setColumnWidth(1, 75)
        self.check_tree.setColumnWidth(2, 90)
        self.check_tree.setColumnWidth(3, 75)
        groups = {}
        for check in core.CHECKS:
            if check.category not in groups:
                group = QtWidgets.QTreeWidgetItem(self.check_tree, [check.category])
                group.setFlags(group.flags() & ~Qt.ItemIsSelectable); group.setExpanded(True)
                groups[check.category] = group
            item = QtWidgets.QTreeWidgetItem(groups[check.category], [check.label, check.severity, "NOT RUN", ""])
            item.setData(0, Qt.UserRole, check.id); item.setToolTip(0, check.tip)
            self._check_items[check.id] = item
        self.check_tree.itemSelectionChanged.connect(self._refresh_findings); splitter.addWidget(self.check_tree)
        findings = QtWidgets.QWidget(); findings_box = QtWidgets.QVBoxLayout(findings)
        findings_box.setContentsMargins(0, 4, 0, 0)
        self.guidance = QtWidgets.QLabel("Select checks to inspect findings. Double-click a finding to select it in Maya.")
        self.guidance.setWordWrap(True); findings_box.addWidget(self.guidance)
        self.issue_tree = QtWidgets.QTreeWidget(); self.issue_tree.setHeaderLabels(("Finding / diagnostic", "Targets"))
        self.issue_tree.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.issue_tree.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch); self.issue_tree.setColumnWidth(1, 70)
        self.issue_tree.itemDoubleClicked.connect(lambda *args: self._select_issues())
        self.issue_tree.itemSelectionChanged.connect(self._update_fix_button); findings_box.addWidget(self.issue_tree, 1)
        row = QtWidgets.QHBoxLayout(); self._button("Select in Maya", self._select_issues, row)
        self.fix_btn = self._button("Repair selected finding", self._repair, row); self.fix_btn.setEnabled(False)
        self.fix_btn.setToolTip("One finding at a time, with Undo. Live deformers, locked and referenced nodes are protected.")
        row.addStretch(); findings_box.addLayout(row); splitter.addWidget(findings); splitter.setSizes([320, 200])
        box.addWidget(splitter, 1)
        return page

    def _build_review(self):
        page = QtWidgets.QWidget(); box = QtWidgets.QVBoxLayout(page)
        hint = QtWidgets.QLabel("Record Pass, Fail or N/A after inspection. N/A needs a reason. Notes are saved in the JSON report.")
        hint.setWordWrap(True); box.addWidget(hint)
        tree = QtWidgets.QTreeWidget(); tree.setHeaderLabels(("Visual check", "Priority", "Review", "Notes / exception reason"))
        tree.setRootIsDecorated(True); tree.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        tree.setColumnWidth(1, 65); tree.setColumnWidth(2, 95); tree.setColumnWidth(3, 220)
        groups = {}
        for key, category, severity, label in core.MANUAL_CHECKS:
            if category not in groups:
                group = QtWidgets.QTreeWidgetItem(tree, [category]); group.setExpanded(True); groups[category] = group
            item = QtWidgets.QTreeWidgetItem(groups[category], [label, severity]); item.setToolTip(0, label)
            state = QtWidgets.QComboBox(); state.addItems(core.REVIEW_STATES); state.setAccessibleName(label + " review")
            note = QtWidgets.QLineEdit(); note.setPlaceholderText("Inspection notes..."); note.setAccessibleName(label + " notes")
            tree.setItemWidget(item, 2, state); tree.setItemWidget(item, 3, note)
            self._review_widgets[key] = (state, note)
            state.currentIndexChanged.connect(self._update_summary); note.textChanged.connect(self._update_summary)
        box.addWidget(tree, 1)
        row = QtWidgets.QHBoxLayout(); self._button("Reset review", self._reset_review, row)
        self._button("Load review from JSON", self._load_review, row); row.addStretch(); box.addLayout(row)
        return page

    def _build_vertex_sets(self):
        page = QtWidgets.QWidget(); box = QtWidgets.QVBoxLayout(page)
        text = QtWidgets.QLabel("Load two vertex sets to compare lip / eyelid counts and contact positions, or body / clothing alignment. The test measures world positions; inspect loop flow and order visually.")
        text.setWordWrap(True); box.addWidget(text)
        self.vertex_labels = []
        for index, label in enumerate(("A", "B")):
            row = QtWidgets.QHBoxLayout()
            field = QtWidgets.QLabel("Set {}: not loaded".format(label)); field.setWordWrap(True)
            self.vertex_labels.append(field); row.addWidget(field, 1)
            self._button("Load selected vertices as " + label, lambda checked=False, i=index: self._load_vertices(i), row)
            box.addLayout(row)
        row = QtWidgets.QHBoxLayout(); self._button("Compare vertex sets", self._compare_vertices, row)
        self._button("Select unmatched vertices", self._select_unmatched, row); row.addStretch(); box.addLayout(row)
        self.vertex_result = QtWidgets.QPlainTextEdit(); self.vertex_result.setReadOnly(True); box.addWidget(self.vertex_result, 1)
        return page

    def _build_report(self):
        page = QtWidgets.QWidget(); box = QtWidgets.QVBoxLayout(page)
        self.report_preview = QtWidgets.QPlainTextEdit(); self.report_preview.setReadOnly(True); box.addWidget(self.report_preview, 1)
        row = QtWidgets.QHBoxLayout(); self._button("Refresh report", self._refresh_report, row)
        self._button("Copy report", self._copy_report, row); self._button("Export JSON", self._export_report, row)
        box.addLayout(row)
        return page

    def options(self):
        return core.Options(self.tolerance.value(), self.ground_tolerance.value(), self.gpu.currentData())

    def review(self):
        return {key: dict(state=state.currentText(), note=note.text()) for key, (state, note) in self._review_widgets.items()}

    def report(self):
        return core.build_report(self.results, self.review(), self.roots, self.options(), self.stale)

    def _update_summary(self, *args):
        if not hasattr(self, "summary"):
            return
        report = self.report(); counts = report["summary"]
        self.summary.setText("{} | {} blockers | {} warnings | {} errors | {} visual pending | {} not run | {} skipped".format(
            report["verdict"], counts["blockers"], counts["warnings"], counts["errors"], counts["pending"], counts["not_run"], counts["skipped"]))
        if self.tabs.currentIndex() == 3:
            self._refresh_report()

    def _invalidate(self, *args):
        self.results.clear(); self.stale = False; _remove_callbacks(self._watchers)
        self._refresh_checks(); self.status.setText("Settings or scope changed. Run checks again.")

    def _scope_changed(self, index):
        self.roots = None if index == 0 else []
        self.scope_info.setText("Whole scene" if index == 0 else "Load mesh / group roots from selection")
        self._reset_review(); self._invalidate()

    def _load_scope(self):
        roots = core.selection_roots()
        if not roots:
            self.status.setText("Select one or more mesh / group roots in Maya."); return
        self.scope.blockSignals(True); self.scope.setCurrentIndex(1); self.scope.blockSignals(False)
        self.roots = roots
        self.scope_info.setText("{} loaded root(s): {}".format(len(roots), ", ".join(node.split("|")[-1] for node in roots)))
        self.scope_info.setToolTip("\n".join(roots)); self._reset_review(); self._invalidate()

    def _reset_scene(self):
        self._vertex_sets, self._unmatched = [[], []], []
        for index, label in enumerate(self.vertex_labels):
            label.setText("Set {}: not loaded".format("AB"[index]))
        self.vertex_result.clear(); self.scope.setCurrentIndex(0); self.roots = None
        self._reset_review(); self._invalidate(); self.status.setText("Scene changed. Scope and review have been reset.")

    def _reset_review(self):
        for state, note in self._review_widgets.values():
            state.setCurrentIndex(0); note.clear()
        self._update_summary()

    def _mark_stale(self):
        if self.results and not self.stale:
            self.stale = True
            # Maya dirtiness callbacks may run during DG evaluation. Query the
            # scene and update Qt only after returning to the event loop.
            self._stale_timer.start(0)

    def _show_stale(self):
        if self.stale:
            self.status.setText("Scene changed since the scan. Run all checks to refresh results before repair.")
            self._update_summary(); self._update_fix_button()

    def _watch_context(self, context):
        _remove_callbacks(self._watchers)
        for node in set(context.meshes) | set(context.transforms):
            if cmds.objExists(node):
                selection = om.MSelectionList(); selection.add(node)
                self._watchers.append(om.MNodeMessage.addNodeDirtyCallback(selection.getDependNode(0), self._changed_callback))

    def _cancel(self):
        self._cancelled = True

    def run_all(self):
        self._run([check.id for check in core.CHECKS], full=True)

    def run_selected(self):
        ids = [item.data(0, Qt.UserRole) for item in self.check_tree.selectedItems() if item.data(0, Qt.UserRole)]
        if not ids:
            self.status.setText("Select checks in the automatic results list."); return
        self._run(ids)

    def _run(self, ids, full=False):
        if self._busy:
            return
        try:
            context = core.Context(self.roots, self.options())
        except Exception as exc:
            self._mark_stale(); self.status.setText(str(exc)); return
        self._busy = True; self._cancelled = False
        if full:
            self.results.clear()
        else:
            for key in ids:
                self.results.pop(key, None)
        _remove_callbacks(self._watchers)
        controls = (self.run_btn, self.run_selected_btn, self.scope, self.load_scope_btn, self.tolerance, self.ground_tolerance, self.gpu, self.fix_btn, self.tabs)
        for control in controls:
            control.setEnabled(False)
        self.cancel_btn.setEnabled(True); self.progress.setMaximum(len(ids)); self.progress.setValue(0); self.progress.show()
        try:
            for index, check_id in enumerate(ids):
                self.status.setText("Checking: " + core.BY_ID[check_id].label)
                QtWidgets.QApplication.processEvents()
                if self._cancelled:
                    break
                self.results[check_id] = core.run_check(context, check_id); self.progress.setValue(index + 1)
            if full:
                self.stale = False
            self._watch_context(context)
            self.status.setText("Scan cancelled; remaining checks are NOT RUN." if self._cancelled else
                                "Scan complete: {} meshes. Complete visual review before delivery.".format(len(context.meshes)))
        except Exception as exc:
            self.stale = True; self.status.setText("Scan interrupted: " + str(exc))
        finally:
            self._busy = False
            for control in controls:
                control.setEnabled(True)
            self.cancel_btn.setEnabled(False); self.progress.hide(); self._refresh_checks()

    def _refresh_checks(self):
        for key, item in self._check_items.items():
            result = self.results.get(key, core.Result(key)); item.setText(2, result.status)
            item.setText(3, str(len(result.issues)) if result.status != "NOT RUN" else "")
            icon = {"PASS": QtWidgets.QStyle.SP_DialogApplyButton, "FAIL": QtWidgets.QStyle.SP_MessageBoxCritical,
                    "ERROR": QtWidgets.QStyle.SP_MessageBoxCritical, "WARN": QtWidgets.QStyle.SP_MessageBoxWarning,
                    "INFO": QtWidgets.QStyle.SP_MessageBoxInformation}.get(result.status)
            item.setIcon(2, self.style().standardIcon(icon) if icon else QtGui.QIcon()); item.setToolTip(2, result.message)
        self._filter(); self._update_summary()

    def _filter(self, *args):
        text, mode = self.query.text().lower().strip(), self.result_filter.currentIndex()
        for key, item in self._check_items.items():
            result = self.results.get(key, core.Result(key))
            matches = (mode == 0 or mode == 1 and bool(result.issues) or mode == 2 and result.status == "ERROR" or mode == 3 and result.status == "NOT RUN")
            item.setHidden(not (matches and text in (core.BY_ID[key].label + " " + core.BY_ID[key].severity + " " + core.BY_ID[key].category).lower()))
        for index in range(self.check_tree.topLevelItemCount()):
            group = self.check_tree.topLevelItem(index)
            group.setHidden(all(group.child(i).isHidden() for i in range(group.childCount())))
        self._refresh_findings()

    def _refresh_findings(self):
        self.issue_tree.clear()
        ids = [item.data(0, Qt.UserRole) for item in self.check_tree.selectedItems() if item.data(0, Qt.UserRole) and not item.isHidden()]
        self.guidance.setText(core.BY_ID[ids[0]].tip if len(ids) == 1 else
                              "Double-click a finding to select its full paths in Maya. All findings are retained in the report.")
        for key in ids or [key for key, item in self._check_items.items() if not item.isHidden()]:
            result = self.results.get(key)
            if result is None:
                continue
            if result.message:
                QtWidgets.QTreeWidgetItem(self.issue_tree, ["{}: {}".format(core.BY_ID[key].label, result.message), ""])
            for issue in result.issues:
                item = QtWidgets.QTreeWidgetItem(self.issue_tree, [issue.label, str(len(issue.selection))])
                item.setData(0, Qt.UserRole, (key, issue)); item.setToolTip(0, core.BY_ID[key].label + "\n" + "\n".join(issue.selection))
        self._update_fix_button()

    def _selected_issues(self):
        return [item.data(0, Qt.UserRole) for item in self.issue_tree.selectedItems() if item.data(0, Qt.UserRole)]

    def _select_targets(self, targets):
        valid = [target for target in dict.fromkeys(targets) if cmds.objExists(target)]
        if valid:
            try:
                cmds.select(valid, replace=True); self.status.setText("Selected {} target(s) in Maya.".format(len(valid)))
            except Exception as exc:
                self.status.setText(str(exc))
        else:
            self.status.setText("No valid targets. Run checks again if the scene changed.")

    def _select_issues(self):
        self._select_targets([node for _, issue in self._selected_issues() for node in issue.selection])

    def _update_fix_button(self):
        if not hasattr(self, "fix_btn"):
            return
        selected = self._selected_issues()
        self.fix_btn.setEnabled(not self._busy and not self.stale and len(selected) == 1 and selected[0][0] in core.FIXABLE)

    def _repair(self):
        selected = self._selected_issues()
        if self._busy or self.stale or len(selected) != 1:
            return
        try:
            message = core.repair(*selected[0]); self.run_all(); self.status.setText(message + " Full scan refreshed.")
        except Exception as exc:
            self._mark_stale(); self.status.setText("Repair unavailable: " + str(exc))

    def _refresh_report(self):
        self.report_preview.setPlainText(core.report_text(self.report()))

    def _copy_report(self):
        QtWidgets.QApplication.clipboard().setText(core.report_text(self.report()))
        self.status.setText("Full report copied, including diagnostics and visual review.")

    def save_report(self, path):
        with open(path, "w", encoding="utf-8") as stream:
            json.dump(self.report(), stream, indent=2, ensure_ascii=True)

    def _export_report(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export model QC report", "model_qc.json", "JSON report (*.json)")
        if path:
            try:
                self.save_report(path); self.status.setText("Report saved: " + path)
            except Exception as exc:
                self.status.setText("Could not save report: " + str(exc))

    def load_review(self, path):
        with open(path, encoding="utf-8") as stream:
            data = json.load(stream)
        current = self.report()
        if (data.get("schema_version") != 1 or data.get("scene") != current["scene"] or
                data.get("scope") != current["scope"] or data.get("mesh_identity") != current["mesh_identity"]):
            raise ValueError("Review belongs to another scene, mesh inventory or scope. Load its original scene and roots first.")
        reviews = data.get("manual")
        if not isinstance(reviews, list) or any(not isinstance(row, dict) or row.get("state") not in core.REVIEW_STATES or not isinstance(row.get("note", ""), str) for row in reviews):
            raise ValueError("Invalid visual review data.")
        self._reset_review()
        for row in reviews:
            if row.get("id") in self._review_widgets:
                state, note = self._review_widgets[row["id"]]; state.setCurrentText(row["state"]); note.setText(row.get("note", ""))
        self.status.setText("Visual review loaded. Run automatic checks for the current scene state.")

    def _load_review(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Load visual review", "", "JSON report (*.json)")
        if path:
            try:
                self.load_review(path)
            except Exception as exc:
                self.status.setText("Could not load review: " + str(exc))

    def _load_vertices(self, index):
        vertices = cmds.filterExpand(cmds.ls(selection=True, long=True) or [], selectionMask=31, expand=True) or []
        if not vertices:
            self.status.setText("Select polygon vertices in Maya."); return
        self._vertex_sets[index] = list(dict.fromkeys(vertices))
        self.vertex_labels[index].setText("Set {}: {} vertices".format("AB"[index], len(self._vertex_sets[index])))
        self._unmatched = []; self.vertex_result.clear()

    def _compare_vertices(self):
        try:
            data = core.compare_vertex_sets(*self._vertex_sets, tolerance=self.options().tolerance)
            self._unmatched = data["unmatched"]
            self.vertex_result.setPlainText("A: {} vertices\nB: {} vertices\nEqual counts: {}\nVertices without a contact match: {}\nPosition tolerance: {} scene units\n\nPosition / count comparison only. Confirm sealing loops, ordering and topology visually.".format(
                data["count_a"], data["count_b"], data["equal_count"], len(data["unmatched"]), data["tolerance"]))
        except Exception as exc:
            self._unmatched = []; self.vertex_result.setPlainText(str(exc))

    def _select_unmatched(self):
        self._select_targets(self._unmatched)


def show():
    global _window
    # Menu launch reloads this module, so the previous Python global may be
    # gone while its native dialog and callbacks are still alive.
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if widget.objectName() == "AutoRigModelChecker":
            if getattr(widget, "_busy", False):
                widget.raise_(); widget.activateWindow()
                return widget
            widget.close(); widget.deleteLater()
    _window = ModelCheckerWindow(); _window.show()
    return _window
