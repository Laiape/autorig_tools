"""Maya API 2.0 tool and undo command; registers no persistent scene nodes."""
from maya import cmds
from maya.api import OpenMaya as om, OpenMayaUI as omui

from ng_nurbs_bridge import brush, core


def maya_useNewAPI():
    pass


class CommitCommand(om.MPxCommand):
    @staticmethod
    def creator():
        return CommitCommand()

    def doIt(self, arguments):
        token = arguments.asString(0)
        self.identity, self.layer_id, self.before, self.after = brush._commits.pop(token)
        # Dabs are already applied; the command now owns both snapshots.

    def isUndoable(self):
        return True

    def _apply(self, state):
        bridge = core.Bridge(core.node_for(self.identity))
        bridge.validate()
        core.apply_snapshot(bridge, self.layer_id, state)
        if brush.active():
            brush.active().preview()

    def undoIt(self):
        self._apply(self.before)

    def redoIt(self):
        self._apply(self.after)


class SurfaceContext(omui.MPxContext):
    def __init__(self):
        super(SurfaceContext, self).__init__()
        self.setTitleString('NURBS Skin - ngSkinTools layers')
        self.setHelpString('LMB: paint. Shift: smooth. Ctrl: invert. Radius: NURBS Skin. Esc: cancel stroke.')

    def toolOnSetup(self, event):
        pass

    def toolOffCleanup(self):
        controller = brush.active()
        if controller:
            controller.cancel()
        brush._controller = None

    def _dab(self, event, manager):
        controller = brush.active()
        if not controller:
            return
        try:
            position = event.position
            view = omui.M3dView.active3dView()
            origin, direction = om.MPoint(), om.MVector()
            view.viewToWorld(int(position[0]), int(position[1]), origin, direction)
            controller.dab(origin, direction, inverted=event.isModifierControl(), smooth=event.isModifierShift())
            controller.draw(manager)
            view.refresh(False, True)
        except Exception as error:
            controller.error = str(error)
            controller.cancel()
            cmds.warning('NURBS Skin: '+str(error))

    def doPress(self, event, manager, frame):
        if event.mouseButton() == omui.MEvent.kLeftMouse:
            self._dab(event, manager)

    def doDrag(self, event, manager, frame):
        self._dab(event, manager)

    def doRelease(self, event, manager, frame):
        controller = brush.active()
        if controller:
            try:
                controller.finish()
            except Exception as error:
                controller.error = str(error)
                cmds.warning('NURBS Skin: '+str(error))

    def abortAction(self):
        if brush.active():
            brush.active().cancel()
            brush.active().preview()

    def drawFeedback(self, manager, frame):
        if brush.active():
            brush.active().draw(manager)


class ContextCommand(omui.MPxContextCommand):
    @staticmethod
    def creator():
        return ContextCommand()

    def makeObj(self):
        return SurfaceContext()


def initializePlugin(obj):
    plugin = om.MFnPlugin(obj, 'NG NURBS Bridge', '1.0.0', 'Any')
    plugin.registerCommand(brush.COMMIT_COMMAND, CommitCommand.creator)
    try:
        plugin.registerContextCommand(brush.CONTEXT_COMMAND, ContextCommand.creator)
    except BaseException:
        plugin.deregisterCommand(brush.COMMIT_COMMAND)
        raise


def uninitializePlugin(obj):
    brush.stop()
    plugin = om.MFnPlugin(obj)
    plugin.deregisterContextCommand(brush.CONTEXT_COMMAND)
    plugin.deregisterCommand(brush.COMMIT_COMMAND)
