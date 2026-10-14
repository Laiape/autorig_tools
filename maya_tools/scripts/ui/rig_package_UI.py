"""Local frozen rig package creation, verification and validated rebuilds."""
from pathlib import Path
import os,sys,json
from maya import cmds
try:
    from PySide6 import QtWidgets,QtCore
except ImportError:
    from PySide2 import QtWidgets,QtCore
from maya_tools.scripts.tools import rig_package
from maya_tools.scripts.utils import ui_utils
_window=None

class RigPackageUI(QtWidgets.QDialog):
    def __init__(self,parent=None):
        super(RigPackageUI,self).__init__(parent)
        self.setWindowTitle('Validated Rig Packages');self.resize(620,240)
        layout=QtWidgets.QVBoxLayout(self)
        self.path=QtWidgets.QLineEdit();self.path.setPlaceholderText('Package directory containing manifest.json')
        row=QtWidgets.QHBoxLayout();row.addWidget(self.path)
        choose=QtWidgets.QPushButton('Choose package...');choose.clicked.connect(self.choose);row.addWidget(choose);layout.addLayout(row)
        for label,callback in (('Create frozen candidate from current asset',self.create),('Verify hashes and publish status',self.verify),('Validate candidate in isolated Maya',self.validate),('Rebuild validated package in a fresh scene',self.build)):
            button=QtWidgets.QPushButton(label);button.clicked.connect(lambda checked=False,f=callback:self.run(f));layout.addWidget(button)
        note=QtWidgets.QLabel('A candidate must pass two rebuild comparisons and native scene reopen before it is marked validated. Save your current scene before rebuilding.')
        note.setWordWrap(True);layout.addWidget(note)
        self.status=QtWidgets.QLabel('Choose an existing package or create a frozen candidate.');self.status.setWordWrap(True);layout.addWidget(self.status)
        ui_utils.apply_maya_style(self)

    def run(self,callback):
        try:callback()
        except Exception as exc:self.status.setText(str(exc));cmds.warning(str(exc))

    def choose(self):
        path=QtWidgets.QFileDialog.getExistingDirectory(self,'Rig package')
        if path:self.path.setText(path)

    def create(self):
        from maya_tools.scripts.tools.skin_manager_api import SkinManager
        asset=SkinManager().asset_name
        parent=QtWidgets.QFileDialog.getExistingDirectory(self,'Parent directory for a new package')
        if not parent:return
        version=1
        while (Path(parent)/('%s_v%03d'%(asset,version))).exists():version+=1
        destination=Path(parent)/('%s_v%03d'%(asset,version))
        source=Path(__file__).resolve().parents[3]
        rig_package.create(source,asset,destination)
        self.path.setText(str(destination));self.status.setText('Frozen candidate created. Hashes verified; publish validation is pending.')

    def verify(self):
        report=rig_package.verify(self.path.text())
        self.status.setText('%s: %s. %d file hashes verified.'%(report['asset'],report['status'],len(report['files'])))

    def build(self):
        result=rig_package.build(self.path.text())
        self.status.setText('Rebuilt %s from its validated recipe.'%result['asset'])

    def validate(self):
        if getattr(self,'process',None) and self.process.state()!=QtCore.QProcess.NotRunning:
            raise ValueError('Package validation is already running.')
        package=Path(self.path.text());rig_package.verify(package)
        output=package/'publish_checks'
        if output.exists():raise ValueError('This package already has validation results. Create a new candidate for another validation.')
        location=Path(os.environ.get('MAYA_LOCATION',Path(sys.executable).parent.parent))
        executable=location/'bin/mayapy.exe'
        if not executable.is_file():raise ValueError('Maya mayapy executable is unavailable.')
        runner=Path(rig_package.__file__).with_name('rig_package_validate.py')
        self.process=QtCore.QProcess(self)
        self.process.setProgram(str(executable));self.process.setArguments([str(runner),str(package),str(output)])
        self.process.finished.connect(lambda code,status:self.validation_finished(output,code))
        self.process.start();self.status.setText('Validating two clean builds and native scene reopen in isolated Maya...')

    def validation_finished(self,output,code):
        path=output/'result.json'
        result=json.loads(path.read_text()) if path.exists() else {'success':False,'error':'Maya terminated before writing validation results.'}
        self.status.setText('Package validated and ready to rebuild.' if code==0 and result['success'] else 'Validation failed: '+result.get('error','Geometry comparison failed.'))

def show():
    global _window
    if _window:_window.close()
    _window=RigPackageUI();_window.show();return _window
