import maya.api.OpenMaya as om
import maya.cmds as cmds

def maya_useNewAPI():
    pass

class IkFkMatchCommand(om.MPxCommand):
    COMMAND_NAME = "ikFkMatch"
    VENDOR = 'Laia'
    VERSION = '1.0'

    LONG_FLAGS = ["fkJoints", "ikControllers", "ikJoints", "fkCtls", "type"]
    SHORT_FLAGS = ["fkJ", "ikC", "ikJ", "fkC", "ty"]

    def __init__(self):
        super(IkFkMatchCommand, self).__init__()
        self.fk_joints = []
        self.ik_handle = None
        self.pv_ctl = None
        self.ik_joints = []
        self.fk_ctls = []
        self.match_type = None

    def get_world_position(self, obj):
        sel = om.MSelectionList()
        sel.add(obj)
        dag_path = sel.getDagPath(0)
        mfn = om.MFnTransform(dag_path)
        return mfn.translation(om.MSpace.kWorld)

    def doIt(self, arg_list):
        try:
            arg_db = om.MArgDatabase(self.syntax(), arg_list)
        except:
            self.displayError("Error while parsing arguments")
            raise

        if arg_db.isFlagSet("fkJ"):
            self.fk_joints = arg_db.flagArgumentString("fkJ", 0).split(',')

        if arg_db.isFlagSet("ikJ"):
            self.ik_joints = arg_db.flagArgumentString("ikJ", 0).split(',')

        if arg_db.isFlagSet("ikC"):
            self.ik_controllers = arg_db.flagArgumentString("ikC", 0).split(',')

        if arg_db.isFlagSet("fkC"):
            self.fk_ctls = arg_db.flagArgumentString("fkC", 0).split(',')

        if arg_db.isFlagSet("ty"):
            self.match_type = arg_db.flagArgumentString("ty", 0)

        self.redoIt(self.match_type)
        self.displayInfo("Info: IkFkMatchCommand executed successfully")

    def redoIt(self, match_type):
        self.match_type = match_type

        if match_type.lower() == "fk" or match_type == "0":
            self.fk_to_ik(self.fk_joints, self.ik_controllers)

        elif match_type.lower() == "ik" or match_type == "1":
            self.ik_to_fk(self.ik_joints, self.fk_ctls)

        return match_type

    def undoIt(self):

        if self.match_type.lower() == "fk" or self.match_type == "0":

            cmds.xform(self.ik_controllers[0], ws=True, t=self.undo_ik_root_tr)
            cmds.xform(self.ik_controllers[0], ws=True, ro=self.undo_ik_root_ro)
            cmds.xform(self.ik_controllers[1], ws=True, t=self.undo_ik_pv_tr)
            cmds.xform(self.ik_controllers[1], ws=True, ro=self.undo_ik_pv_ro)
            cmds.xform(self.ik_controllers[2], ws=True, t=self.undo_ik_controller_tr)
            cmds.xform(self.ik_controllers[2], ws=True, ro=self.undo_ik_controller_ro)

            
        if self.match_type.lower() == "ik" or self.match_type == "1":

            cmds.xform(self.fk_ctls[0], ws=True, t=self.undo_fk_ctl_00_tr)
            cmds.xform(self.fk_ctls[0], ws=True, ro=self.undo_fk_ctl_00_ro)
            cmds.xform(self.fk_ctls[1], ws=True, t=self.undo_fk_ctl_01_tr)
            cmds.xform(self.fk_ctls[1], ws=True, ro=self.undo_fk_ctl_01_ro)
            cmds.xform(self.fk_ctls[2], ws=True, t=self.undo_fk_ctl_02_tr)
            cmds.xform(self.fk_ctls[2], ws=True, ro=self.undo_fk_ctl_02_ro)
            
            

    def isUndoable(self):
        return True

    def fk_to_ik(self, fk_joints, ik_controllers):
        shoulder_pos = self.get_world_position(fk_joints[0])
        elbow_pos = self.get_world_position(fk_joints[1])
        wrist_pos = self.get_world_position(fk_joints[2])

        ik_root = ik_controllers[0]
        ik_pv = ik_controllers[1]
        ik_controller = ik_controllers[2]

        self.undo_ik_root_tr = cmds.xform(ik_root, q=True, ws=True, t=True)
        self.undo_ik_root_ro = cmds.xform(ik_root, q=True, ws=True, ro=True)
        self.undo_ik_pv_tr = cmds.xform(ik_pv, q=True, ws=True, t=True)
        self.undo_ik_pv_ro = cmds.xform(ik_pv, q=True, ws=True, ro=True)
        self.undo_ik_controller_tr = cmds.xform(ik_controller, q=True, ws=True, t=True)
        self.undo_ik_controller_ro = cmds.xform(ik_controller, q=True, ws=True, ro=True)
        

        shoulder_vector = om.MVector(shoulder_pos)
        elbow_vector = om.MVector(elbow_pos)
        wrist_vector = om.MVector(wrist_pos)

        mid_point = (shoulder_vector + wrist_vector) / 2.0
        pole_vector = (elbow_vector - mid_point).normalize() * 10.0
        pv_position = elbow_vector + pole_vector

        cmds.xform(ik_controller, ws=True, t=wrist_pos)
        cmds.xform(ik_root, ws=True, t=shoulder_pos)
        cmds.xform(ik_pv, ws=True, t=pv_position)

    def ik_to_fk(self, joints, fk_ctls):
        

        self.undo_fk_ctl_00_tr = cmds.xform(fk_ctls[0], q=True, ws=True, t=True)
        self.undo_fk_ctl_00_ro = cmds.xform(fk_ctls[0], q=True, ws=True, ro=True)
        self.undo_fk_ctl_01_tr = cmds.xform(fk_ctls[1], q=True, ws=True, t=True)
        self.undo_fk_ctl_01_ro = cmds.xform(fk_ctls[1], q=True, ws=True, ro=True)
        self.undo_fk_ctl_02_tr = cmds.xform(fk_ctls[2], q=True, ws=True, t=True)
        self.undo_fk_ctl_02_ro = cmds.xform(fk_ctls[2], q=True, ws=True, ro=True)
       


        for joint, ctl in zip(joints, fk_ctls):
            rotation = cmds.xform(joint, q=True, ws=True, ro=True)
            translation = cmds.xform(joint, q=True, ws=True, t=True)
            cmds.xform(ctl, ws=True, ro=rotation)
            cmds.xform(ctl, ws=True, t=translation)
            

    @staticmethod
    def creator():
        return IkFkMatchCommand()

    @staticmethod
    def create_syntax():
        syntax = om.MSyntax()
        syntax.enableEdit = True
        syntax.enableQuery = True

        syntax.addFlag("fkJ", "fkJoints", om.MSyntax.kString)
        syntax.addFlag("ikC", "ikControllers", om.MSyntax.kString)
        syntax.addFlag("ikJ", "ikJoints", om.MSyntax.kString)
        syntax.addFlag("fkC", "fkCtls", om.MSyntax.kString)
        syntax.addFlag("ty", "type", om.MSyntax.kString)

        return syntax

def initializePlugin(plugin):
    plugin_fn = om.MFnPlugin(plugin, IkFkMatchCommand.VENDOR, IkFkMatchCommand.VERSION)
    try:
        plugin_fn.registerCommand(IkFkMatchCommand.COMMAND_NAME, IkFkMatchCommand.creator, IkFkMatchCommand.create_syntax)
    except:
        raise RuntimeError("Failed to register command: " + IkFkMatchCommand.COMMAND_NAME)

def uninitializePlugin(plugin):
    plugin_fn = om.MFnPlugin(plugin)
    try:
        plugin_fn.deregisterCommand(IkFkMatchCommand.COMMAND_NAME)
    except:
        om.MGlobal.displayError(f"Failed to deregister command: {IkFkMatchCommand.COMMAND_NAME}")

# -------------------------
# Test setup (optional)
# -------------------------

if __name__ == '__main__':
    import maya.cmds as cmds

    plugin_name = "EX01_API_perisLaia.py"

    if cmds.pluginInfo(plugin_name, q=True, loaded=True):
        cmds.unloadPlugin(plugin_name)
    if not cmds.pluginInfo(plugin_name, q=True, loaded=True):
        cmds.loadPlugin(plugin_name)

    # Example command call
    cmds.ikFkMatch(
        fkJ="fk00_jnt,fk01_jnt,fk02_jnt",
        ikH="ik_handle",
        pvC="pv_ctl",
        ikJ="ik_joint00,ik_joint01,ik_joint02",
        fkC="fk00_ctl,fk01_ctl,fk02_ctl",
        ty="0"
    )
