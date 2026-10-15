"""Embedded prototype for complete-loop facial skinning in NG."""
import json
import re
from maya import cmds
try:
    from PySide6 import QtWidgets
except ImportError:
    from PySide2 import QtWidgets
from maya_tools.scripts.tools import facial_loop_skinning as tool
from maya_tools.scripts.utils import ui_utils


class LoopRiggerPanel(QtWidgets.QWidget):
    def __init__(self, ng_panel):
        super(LoopRiggerPanel, self).__init__(ng_panel)
        self.ng = ng_panel
        self.owner = ng_panel.owner
        self.plan = None
        self.skin = None
        self.joints = []
        self.preview_group = None
        layout = QtWidgets.QVBoxLayout(self)
        hint = QtWidgets.QLabel('Select a seed edge loop. Each joint gets its COMPLETE transverse loop. Edit its NG mask afterwards to localize the effect.')
        hint.setWordWrap(True); layout.addWidget(hint)
        form = QtWidgets.QFormLayout()
        self.preset = QtWidgets.QComboBox(); self.preset.addItems(['Lip Rigger', 'Eye Rigger', 'Eyebrow Rigger', 'Other'])
        form.addRow('Region', self.preset)
        self.name = QtWidgets.QLineEdit('Lips')
        form.addRow('NG group name', self.name)
        self.paired = QtWidgets.QCheckBox('Rotate / Non Rotate: two layers, matching weights')
        self.paired.setChecked(True)
        form.addRow(self.paired)
        self.mirror = QtWidgets.QCheckBox('Mirror L to R across X (L_ / R_ joint names)')
        form.addRow(self.mirror)
        self.tolerance = QtWidgets.QDoubleSpinBox(); self.tolerance.setRange(.0001, 100)
        self.tolerance.setDecimals(4); self.tolerance.setValue(.05)
        form.addRow('Anchor tolerance', self.tolerance)
        layout.addLayout(form)
        self.target = QtWidgets.QLabel('No seed loop loaded')
        self.target.setWordWrap(True); layout.addWidget(self.target)
        for label, callback in (
            ('1. Load selected seed loop', self.load_seed),
            ('2. Preview complete columns', self.preview),
            ('Load selected existing joints', self.load_joints),
            ('Or create joints on every seed vertex', self.create_joints),
        ):
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(lambda checked=False, c=callback: self.owner.run_action(c))
            layout.addWidget(button)
        self.joint_info = QtWidgets.QLabel('No joints loaded')
        self.joint_info.setWordWrap(True); layout.addWidget(self.joint_info)
        self.create = QtWidgets.QPushButton('3. Create / update region layers')
        self.create.clicked.connect(lambda: self.owner.run_action(self.create_layers))
        ui_utils.action(self.create, "primary", "skin")
        layout.addWidget(self.create)
        self.details = QtWidgets.QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setPlaceholderText('Lips has two weight layers: Rotate above Non Rotate. All joints of each type share its layer. Load upper and lower loops into the same region; coincident corner anchors share their loop 50/50.')
        layout.addWidget(self.details, 1)
        row = QtWidgets.QHBoxLayout()
        for label, callback in (('Select affected vertices', self.select_vertices), ('Clear preview', self.clear_preview)):
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(lambda checked=False, c=callback: self.owner.run_action(c))
            row.addWidget(button)
        layout.addLayout(row)
        self.preset.currentTextChanged.connect(self.change_preset)
        self.review = None
        self.review_box = QtWidgets.QGroupBox('Nini review scene')
        box = QtWidgets.QVBoxLayout(self.review_box)
        self.review_region = QtWidgets.QComboBox(); box.addWidget(self.review_region)
        self.review_joint = QtWidgets.QComboBox(); box.addWidget(self.review_joint)
        row = QtWidgets.QHBoxLayout()
        for label, callback in (('Solo region', lambda: self.solo_review(False)),
                                ('Solo layer', lambda: self.solo_review(True)), ('Show all', self.show_all_review)):
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(lambda checked=False, c=callback: self.owner.run_action(c))
            row.addWidget(button)
        box.addLayout(row)
        self.review_timeline_hint = QtWidgets.QLabel()
        self.review_timeline_hint.setWordWrap(True)
        box.addWidget(self.review_timeline_hint)
        layout.insertWidget(0, self.review_box)
        self.review_region.currentIndexChanged.connect(self.refresh_review_joints)
        self.refresh_review()
        ui_utils.apply_maya_style(self)

    def refresh_review(self):
        self.review = None
        if cmds.objExists('Nini_LOOP_REVIEW_INFO.reviewData'):
            self.review = json.loads(cmds.getAttr('Nini_LOOP_REVIEW_INFO.reviewData'))
        self.review_box.setVisible(bool(self.review))
        self.review_region.clear()
        if self.review:
            for region in self.review['regions']:
                self.review_region.addItem(region['layer_name'], region)
            poses = self.review.get('poses',[])
            self.review_timeline_hint.setText('Frame 1: neutral. ' + ' / '.join(
                '{}: {}'.format(p['frame'],p['label']) for p in poses[:3]))
        self.refresh_review_joints()

    def refresh_review_joints(self):
        self.review_joint.clear()
        region = self.review_region.currentData()
        if region:
            for record in region.get('weight_layers', region.get('joint_layers', [])):
                self.review_joint.addItem(record['layer_name'], record)

    def solo_review(self, joint_only=False):
        if not self.review: return
        skin = self.review['skin']
        chosen = self.review_region.currentData()
        joint = self.review_joint.currentData()
        for region in self.review['regions']:
            tool.resolve_layer(skin, region).enabled = region['layer_id'] == chosen['layer_id']
        layer = tool.resolve_layer(skin, chosen)
        parent = layer.parent
        while parent:
            parent.enabled = True; parent = parent.parent
        for record in chosen.get('weight_layers', chosen.get('joint_layers', [])):
            child = tool.resolve_layer(skin, record)
            child.enabled = not joint_only or record['layer_id'] == joint['layer_id']
        if joint_only: layer = tool.resolve_layer(skin, joint)
        layer.set_current()
        self.ng.select_cluster(skin)
        self.ng.session.events.layerListChanged.emitIfChanged()
        self.ng.session.events.currentLayerChanged.emitIfChanged()
        self.ng.editor_tabs.setCurrentIndex(0)

    def show_all_review(self):
        if not self.review: return
        from ngSkinTools2.api import Layers
        for layer in Layers(self.review['skin']).list(): layer.enabled = True
        self.ng.select_cluster(self.review['skin'])
        self.ng.session.events.layerListChanged.emitIfChanged()

    def change_preset(self, label):
        self.name.setText('Lips' if label == 'Lip Rigger' else label.replace(' ', '_'))
        self.paired.setChecked(label == 'Lip Rigger')

    def load_seed(self):
        mesh = self.owner.current_mesh
        if not mesh or not cmds.objExists(mesh):
            raise ValueError('Load a polygon mesh in Skinning Manager first.')
        self.skin = self.ng.skin_cluster.currentData() or self.ng.choices.get(mesh)
        if not self.skin:
            skins = self.ng.clusters_for(mesh)
            if len(skins) == 1: self.skin = skins[0]
        if not self.skin:
            raise ValueError('Choose the target skinCluster above NG before loading a loop.')
        plan = tool.from_selection(mesh)
        self.clear_preview()
        self.plan = plan
        self.target.setText('{}\n{}: {} anchors, {} affected vertices'.format(self.skin, mesh.rsplit('|', 1)[-1], len(plan['seed']), len(plan['affected'])))
        self.details.setPlainText('\n'.join(plan['warnings']) or 'Complete quad loops; no ambiguous continuations.')
        self.joints = []; self.update_joint_info()

    def preview(self):
        self.require_plan()
        self.clear_preview()
        self.preview_group = tool.preview_columns(self.plan)

    def clear_preview(self):
        if self.preview_group and cmds.objExists(self.preview_group):
            cmds.delete(self.preview_group)
        self.preview_group = None

    def require_plan(self):
        if not self.plan or not cmds.objExists(self.plan['mesh']):
            raise ValueError('Load the seed loop first.')

    def select_vertices(self):
        self.require_plan()
        cmds.select(['{}.vtx[{}]'.format(self.plan['mesh'], vertex) for vertex in self.plan['affected']], replace=True)

    def load_joints(self):
        self.joints = cmds.ls(selection=True, long=True, type='joint') or []
        if not self.joints: raise ValueError('Select the existing facial joints.')
        self.update_joint_info()

    def update_joint_info(self):
        nr = [joint for joint in self.joints if 'nonrot' in joint.lower().replace('_', '')]
        self.joint_info.setText('{} Rotate / ordinary, {} Non Rotate joints loaded'.format(len(self.joints) - len(nr), len(nr)))

    def create_joints(self):
        self.require_plan()
        prefix = re.sub(r'[^A-Za-z0-9_]', '_', self.name.text().strip()) or 'Loop_Rigger'
        cmds.undoInfo(openChunk=True, chunkName='Create facial loop joints')
        try:
            if self.paired.isChecked():
                _, rotate, non_rotate = tool.create_joint_pairs(self.plan, prefix)
                self.joints = rotate + non_rotate
            else:
                _, self.joints = tool.create_joints(self.plan, prefix)
        finally:
            cmds.undoInfo(closeChunk=True)
        self.update_joint_info()

    def create_layers(self):
        self.require_plan()
        if not self.skin or not cmds.objExists(self.skin):
            raise ValueError('The target skinCluster was removed. Load the seed again.')
        non_rotate = [joint for joint in self.joints if 'nonrot' in joint.lower().replace('_', '')]
        rotate = [joint for joint in self.joints if joint not in non_rotate]
        if not self.paired.isChecked():
            rotate, non_rotate = self.joints, []
        if self.paired.isChecked() and not non_rotate:
            raise ValueError('Load both Rotate and Non Rotate lip joints.')
        group, metadata = tool.create_ng_region(self.plan, rotate, self.skin,
            self.name.text().strip() or 'Loop_Rigger', non_rotate_joints=non_rotate,
            tolerance=self.tolerance.value(), mirror=self.mirror.isChecked())
        record = json.loads(cmds.getAttr(metadata + '.loopRegionData'))
        self.details.setPlainText('Updated {} weight layers in {} ({} joints per layer).\nComplete loops; no falloff. Shared upper/lower corner anchors: 50/50. Paint the region mask in NG.\n{}'.format(
            len(record['weight_layers']), group.name, len(record['assignments']), '\n'.join(self.plan['warnings'])))
        self.ng.select_cluster(self.skin)
        self.ng.session.events.targetChanged.emitIfChanged()
        self.ng.session.events.layerListChanged.emitIfChanged()
        self.ng.session.events.currentLayerChanged.emitIfChanged()
        self.ng.editor_tabs.setCurrentIndex(0)
