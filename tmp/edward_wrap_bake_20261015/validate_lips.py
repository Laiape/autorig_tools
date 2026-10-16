for p in lip_channels:cmds.setAttr(p,0)
with bifrost_wrinkles.primary_inputs_for_skin_export():
 exec(compile((WORK/'lip_audit_after.py').read_text(),'lip_audit_after.py','exec'),globals())
result={'cases':evaluations,'skin_audit':[{k:v for k,v in item.items() if k not in ('influences','lip_columns')} for item in skin_audit]}
