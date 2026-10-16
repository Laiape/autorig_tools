sys.path.insert(0,str(ROOT))
from maya_tools.scripts.tools import bifrost_wrinkles
with bifrost_wrinkles.primary_inputs_for_skin_export():
    exec(compile((WORK/'lip_audit.py').read_text(),'lip_audit.py','exec'),globals())
