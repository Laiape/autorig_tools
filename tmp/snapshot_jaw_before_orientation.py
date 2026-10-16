from maya import cmds
from pathlib import Path
folder=Path(r'C:/proyectos/auto-rig/tmp/jaw_orientation_20261015')
result={'scene':cmds.file(q=True,sn=True),'modified':cmds.file(q=True,modified=True),'mode':cmds.evaluationManager(q=True,mode=True),'time':cmds.currentTime(q=True),'selection':cmds.ls(sl=True,long=True)}
result['controls']={}
for node in ('C_jaw_CTL','L_lipCorner_CTL','R_lipCorner_CTL','C_upperLip_CTL','C_lowerLip_CTL'):
 result['controls'][node]={}
 for attr in ('rx','tx','ty','tz','autoNarrow','autoWide','Roll','stickyLips','stickyFalloff'):
  p=node+'.'+attr
  if cmds.objExists(p):result['controls'][node][attr]={'value':cmds.getAttr(p),'incoming':cmds.listConnections(p,s=True,d=False,p=True) or [],'settable':cmds.getAttr(p,settable=True)}
backup=folder/'artist_before_orientation.mb'
if backup.exists():raise RuntimeError('Backup already exists')
cmds.file(str(backup),exportAll=True,type='mayaBinary',force=False,preserveReferences=True)
result['backup']=str(backup)
