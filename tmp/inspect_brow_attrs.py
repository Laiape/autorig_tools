from maya import cmds
result={}
for n in ('L_eyebrowMain_CTL','L_eyebrowMid_CTL','C_upperLip_CTL','C_lowerLip_CTL','L_lipCorner_CTL','C_preferences_CTL','C_face_CTL'):
 if cmds.objExists(n):
  result[n]={a:cmds.getAttr(n+'.'+a) for a in cmds.listAttr(n,userDefined=True) or [] if cmds.getAttr(n+'.'+a,type=True) not in ('message',)}
