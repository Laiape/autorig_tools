"""General rig workflows embedded in the existing Test Rig window."""
import json
from pathlib import Path
from maya import cmds
try:
    from PySide6 import QtWidgets
except ImportError:
    from PySide2 import QtWidgets
from maya_tools.scripts.tools import rig_roles, rig_profiles, rig_validation, rig_pose_library, rig_surface_contact
from maya_tools.scripts.utils import ui_utils


class GeneralRigPanel(QtWidgets.QWidget):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.root = None
        layout = QtWidgets.QVBoxLayout(self)
        self.root_label = QtWidgets.QLabel('Select the character root and load it.')
        layout.addWidget(self.root_label)
        button = QtWidgets.QPushButton('Load selected character root')
        button.clicked.connect(lambda: self.action(self.load_root))
        layout.addWidget(button)
        self.tabs = QtWidgets.QTabWidget()
        layout.addWidget(self.tabs)
        self.status = QtWidgets.QLabel('')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self._bindings_tab()
        self._profiles_tab()
        self._library_tab()
        self._contact_tab()
        self._migration_tab()
        ui_utils.apply_maya_style(self)

    def action(self, function):
        try:
            return function()
        except Exception as exc:
            self.status.setText(str(exc))
            cmds.warning(str(exc))

    def require_root(self):
        if not self.root or not cmds.objExists(self.root):
            raise ValueError('Load the character root first.')
        self.root = rig_roles.path(self.root)
        return self.root

    def load_root(self):
        selected = cmds.ls(selection=True, long=True, type='transform') or []
        if len(selected) != 1:
            raise ValueError('Select one character root transform.')
        self.root = selected[0]
        from maya_tools.scripts.framework import context as framework_context
        framework_context.service().set_root(self.root)
        self.root_label.setText(self.root)
        self.refresh_bindings()

    def _button(self, layout, label, function):
        button = QtWidgets.QPushButton(label)
        button.clicked.connect(lambda: self.action(function))
        layout.addWidget(button)
        return button

    def _bindings_tab(self):
        widget = QtWidgets.QWidget(); layout = QtWidgets.QVBoxLayout(widget)
        self.binding_list = QtWidgets.QListWidget()
        self.binding_list.itemDoubleClicked.connect(lambda item: self.action(self.select_binding))
        layout.addWidget(self.binding_list)
        row = QtWidgets.QHBoxLayout()
        self._button(row, 'Discover repository roles', self.discover)
        self._button(row, 'Refresh', self.refresh_bindings)
        layout.addLayout(row)
        form = QtWidgets.QFormLayout()
        self.role = QtWidgets.QLineEdit('body.head'); self.module = QtWidgets.QLineEdit('neck')
        self.side = QtWidgets.QComboBox(); self.side.addItems(rig_roles.SIDES)
        self.kind = QtWidgets.QComboBox(); self.kind.addItems(rig_roles.KINDS)
        self.index = QtWidgets.QSpinBox(); self.index.setMaximum(10000)
        for label, field in [('Role', self.role), ('Module', self.module), ('Side', self.side), ('Kind', self.kind), ('Index', self.index)]:
            form.addRow(label, field)
        layout.addLayout(form)
        self._button(layout, 'Bind selected node to this role', self.bind_selected)
        row = QtWidgets.QHBoxLayout()
        self._button(row, 'Export bindings...', self.export_bindings)
        self._button(row, 'Import bindings...', self.import_bindings)
        layout.addLayout(row)
        self.tabs.addTab(widget, 'Rig roles')

    def refresh_bindings(self):
        self.binding_list.clear()
        self._bindings = rig_roles.bindings(self.require_root())
        self.binding_list.addItems([b['key'] + '  ->  ' + b['node'].rsplit('|', 1)[-1] for b in self._bindings])

    def select_binding(self):
        index = self.binding_list.currentRow()
        if index >= 0:
            cmds.select(self._bindings[index]['node'], replace=True)

    def discover(self):
        result = rig_roles.discover(self.require_root())
        self.refresh_bindings()
        self.status.setText('Added %d roles. %d other controls need explicit bindings.' % (len(result['added']), len(result['unbound_controls'])))

    def bind_selected(self):
        nodes = cmds.ls(selection=True, long=True, objectsOnly=True) or []
        if len(nodes) != 1:
            raise ValueError('Select one control, joint, mesh or reference.')
        rig_roles.bind(self.require_root(), nodes[0], self.role.text().strip(), self.side.currentText(),
                       self.module.text().strip(), self.index.value(), self.kind.currentText())
        self.refresh_bindings()
        self.status.setText('Role bound. Maya Undo restores the previous binding.')

    def export_bindings(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Export rig role bindings', '', 'Role bindings (*.roles.json)')
        if path:
            with Path(path).open('x', encoding='utf-8') as stream:
                json.dump(rig_roles.snapshot(self.require_root()), stream, indent=2)
            self.status.setText('Bindings exported. For different naming, import with an explicit node_map in Python.')

    def import_bindings(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Import rig role bindings', '', 'Role bindings (*.roles.json)')
        if path:
            rig_roles.restore(self.require_root(), json.loads(Path(path).read_text(encoding='utf-8')))
            self.refresh_bindings()
            self.status.setText('Imported role bindings. Existing semantic keys take precedence over name hints.')

    def _profiles_tab(self):
        widget = QtWidgets.QWidget(); layout = QtWidgets.QVBoxLayout(widget)
        self.profile_choice = QtWidgets.QComboBox(); self.profile_choice.addItems(['custom', 'body', 'face', 'hands'])
        self.profile_choice.activated.connect(lambda _: self.profile_editor.setPlainText(json.dumps(rig_profiles.preset(self.profile_choice.currentText()), indent=2)))
        layout.addWidget(self.profile_choice)
        self.profile_editor = QtWidgets.QPlainTextEdit(json.dumps(rig_profiles.preset('custom'), indent=2))
        self.profile_editor.setMinimumHeight(170)
        layout.addWidget(self.profile_editor)
        row = QtWidgets.QHBoxLayout()
        self._button(row, 'Load profile...', self.load_profile)
        self._button(row, 'Save profile...', self.save_profile)
        layout.addLayout(row)
        self._button(layout, 'Run profile on loaded meshes...', self.run_profile)
        self.difference_pose=QtWidgets.QLineEdit('neutral')
        self.difference_pose.setPlaceholderText('Pose name for geometry difference preview')
        layout.addWidget(self.difference_pose)
        self._button(layout,'Load current report for difference preview...',self.load_current_report)
        self._button(layout,'Create colored difference snapshot against baseline',self.difference_preview)
        self.tabs.addTab(widget, 'Validation profiles')

    def profile(self):
        return rig_profiles.validate(json.loads(self.profile_editor.toPlainText()))

    def load_profile(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Load validation profile', '', 'Rig profiles (*.rigprofile.json)')
        if path:
            profile = rig_profiles.validate(json.loads(Path(path).read_text(encoding='utf-8')))
            self.profile_editor.setPlainText(json.dumps(profile, indent=2))

    def save_profile(self):
        profile = self.profile()
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Save validation profile', '', 'Rig profiles (*.rigprofile.json)')
        if path:
            with Path(path).open('x', encoding='utf-8') as stream:
                json.dump(profile, stream, indent=2)

    def run_profile(self):
        root = self.require_root()
        if not self.owner._report_meshes:
            raise ValueError('Load meshes in Build comparison first.')
        profile = self.profile()
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'New semantic validation report', '', 'Rig QA (*.rigqa.json)')
        if path:
            report = rig_validation.run_report(root, self.owner._report_meshes, path,
                baseline=self.owner._baseline.text().strip() or None, cases=profile)
            self._last_report=report
            self.status.setText('Profile %s: %s. %d missing channels; %d transitions.' %
                (profile['name'], 'PASS' if report['quality_pass'] else 'REVIEW REQUIRED', len(report['missing_channels']), len(report['transitions'])))

    def _library_tab(self):
        widget=QtWidgets.QWidget();layout=QtWidgets.QVBoxLayout(widget)
        self.pose_bank=rig_pose_library.library()
        self.pose_list=QtWidgets.QListWidget();layout.addWidget(self.pose_list)
        self.pose_name=QtWidgets.QLineEdit('pose_01');layout.addWidget(self.pose_name)
        self._button(layout,'Capture current bound controls and viewport camera',self.capture_pose)
        self._button(layout,'Apply selected pose to free controls',self.apply_pose)
        row=QtWidgets.QHBoxLayout()
        self._button(row,'Load library...',self.load_library);self._button(row,'Save library...',self.save_library)
        layout.addLayout(row)
        self._button(layout,'Compare library poses on loaded meshes...',self.review_library)
        self.tabs.addTab(widget,'Pose library')

    def capture_pose(self):
        item=rig_pose_library.capture(self.require_root(),self.pose_name.text().strip())
        if any(p['name']==item['name'] for p in self.pose_bank['poses']):
            raise ValueError('Choose a new pose name; saved poses are preserved.')
        self.pose_bank['poses'].append(item);self.pose_list.addItem(item['name'])
        self.status.setText('Pose captured. %d controls are unbound; %d channels were skipped.' % (len(item['unbound_controls']),len(item['skipped_channels'])))

    def apply_pose(self):
        index=self.pose_list.currentRow()
        if index<0:raise ValueError('Choose a saved pose.')
        rig_pose_library.apply(self.require_root(),self.pose_bank['poses'][index])
        self.status.setText('Applied pose. Maya Undo restores control values.')

    def load_library(self):
        path,_=QtWidgets.QFileDialog.getOpenFileName(self,'Load pose library','','Pose library (*.rigposes.json)')
        if path:
            data=json.loads(Path(path).read_text(encoding='utf-8'));rig_pose_library.profile(data)
            self.pose_bank=data;self.pose_list.clear();self.pose_list.addItems([p['name'] for p in data['poses']])

    def save_library(self):
        rig_pose_library.profile(self.pose_bank)
        path,_=QtWidgets.QFileDialog.getSaveFileName(self,'Save pose library','','Pose library (*.rigposes.json)')
        if path:
            with Path(path).open('x',encoding='utf-8') as stream:json.dump(self.pose_bank,stream,indent=2)

    def review_library(self):
        root=self.require_root()
        if not self.owner._report_meshes:raise ValueError('Load meshes in Build comparison first.')
        path,_=QtWidgets.QFileDialog.getSaveFileName(self,'New pose-library review','','Rig QA (*.rigqa.json)')
        if path:
            report=rig_pose_library.review(root,self.owner._report_meshes,self.pose_bank,path,self.owner._baseline.text().strip() or None)
            self._last_report=report
            self.status.setText('Saved %d poses and viewport captures where available. Comparison: %s.' % (len(report['poses']),'PASS' if report['quality_pass'] else 'REVIEW REQUIRED'))

    def load_current_report(self):
        path,_=QtWidgets.QFileDialog.getOpenFileName(self,'Current report for comparison','','Rig QA (*.rigqa.json)')
        if path:
            report=json.loads(Path(path).read_text(encoding='utf-8'))
            if not report.get('poses'):raise ValueError('Choose a report containing measured poses.')
            self._last_report=report
            self.status.setText('Current report loaded. Choose its baseline in Build comparison.')

    def difference_preview(self):
        if not getattr(self,'_last_report',None) or not self.owner._report_meshes or not self.owner._baseline.text().strip():
            raise ValueError('Load current meshes, a measured report and its baseline first.')
        baseline=json.loads(Path(self.owner._baseline.text().strip()).read_text(encoding='utf-8'))
        result=rig_pose_library.color_difference(self.require_root(),self.owner._report_meshes[0],self._last_report,baseline,self.difference_pose.text().strip())
        cmds.select(result['preview'],replace=True)
        self.status.setText('Created colored snapshot. Maximum difference %.6g scene units; red reaches 0.1 units. Original mesh preserved.'%result['max_difference'])

    def _contact_tab(self):
        widget=QtWidgets.QWidget();layout=QtWidgets.QVBoxLayout(widget)
        label=QtWidgets.QLabel('Bind the source and target meshes in Rig roles. Regions and limits are saved with the validation profile.')
        label.setWordWrap(True);layout.addWidget(label)
        default={'name':'garment_body','source':{'role':'body.garment','module':'body'},
                 'target':{'role':'body.render','module':'body'},'mode':'closed','max_penetration':.01,'tolerance':1e-5}
        self.contact_editor=QtWidgets.QPlainTextEdit(json.dumps(default,indent=2));layout.addWidget(self.contact_editor)
        self._button(layout,'Measure current pose',self.measure_contact)
        self._button(layout,'Select offending vertices',self.select_contact_vertices)
        self._button(layout,'Add contact check to current profile',self.add_contact)
        self.tabs.addTab(widget,'Surface contact')

    def measure_contact(self):
        self._contact_result=rig_surface_contact.measure(self.require_root(),json.loads(self.contact_editor.toPlainText()))
        r=self._contact_result
        self.status.setText('%s. Maximum gap %.6g; penetration %.6g; %d offending and %d uncertain vertices. Vertex samples do not certify all triangle intersections.' %
            ('PASS' if r['pass'] else 'REVIEW REQUIRED',r['max_gap'],r['max_penetration'],len(r['offending_vertices']),len(r['uncertain_vertices'])))

    def select_contact_vertices(self):
        r=getattr(self,'_contact_result',None)
        if not r:raise ValueError('Measure this contact region first.')
        cmds.select([r['source']+'.vtx[%d]'%i for i in r['offending_vertices']+r['uncertain_vertices']],replace=True)

    def add_contact(self):
        spec=json.loads(self.contact_editor.toPlainText())
        rig_surface_contact.measure(self.require_root(),spec)
        profile=self.profile();profile.setdefault('contacts',[]).append(spec)
        self.profile_editor.setPlainText(json.dumps(profile,indent=2))
        self.status.setText('Contact check added. Run the profile to measure it in each pose.')

    def _migration_tab(self):
        widget=QtWidgets.QWidget();layout=QtWidgets.QVBoxLayout(widget)
        self.migration_destination=None
        self._button(layout,'Load selected fresh destination root',self.load_migration_destination)
        self._button(layout,'Preview migration from loaded character',self.preview_migration)
        self.migration_view=QtWidgets.QPlainTextEdit();self.migration_view.setReadOnly(True);layout.addWidget(self.migration_view)
        self._button(layout,'Apply compatible migration to fresh destination',self.apply_migration)
        self.tabs.addTab(widget,'Version migration')

    def load_migration_destination(self):
        selected=cmds.ls(selection=True,long=True,type='transform') or []
        if len(selected)!=1:raise ValueError('Select one fresh destination character root.')
        self.migration_destination=selected[0]
        self.status.setText('Destination: '+selected[0])

    def preview_migration(self):
        from maya_tools.scripts.tools import rig_migration
        if not self.migration_destination:raise ValueError('Load a fresh destination root first.')
        plan=rig_migration.preview(self.require_root(),self.migration_destination)
        self.migration_view.setPlainText(json.dumps(plan,indent=2))
        self.status.setText('Migration compatible.' if plan['ready'] else 'Migration needs review. Resolve the listed issues before applying.')

    def apply_migration(self):
        from maya_tools.scripts.tools import rig_migration
        if not self.migration_destination:raise ValueError('Load a fresh destination root first.')
        result=rig_migration.apply(self.require_root(),self.migration_destination)
        self.migration_view.setPlainText(json.dumps(result,indent=2))
        self.status.setText('Migrated to destination. Source preserved; Maya Undo removes the candidate. Run the validation profile before saving a new version.')
