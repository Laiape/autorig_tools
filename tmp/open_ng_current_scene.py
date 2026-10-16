from maya import cmds
import ngSkinTools2
scene_before=cmds.file(q=True,sn=True)
ngSkinTools2.open_ui()
from ngSkinTools2.ui import mainwindow
result={'scene':cmds.file(q=True,sn=True),'scene_unchanged':cmds.file(q=True,sn=True)==scene_before,'opened':True}
