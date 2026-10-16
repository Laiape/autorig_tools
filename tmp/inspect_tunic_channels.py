from maya import cmds
import os
result = {'pid':os.getpid(),'scene':cmds.file(q=True,sn=True),'modified':cmds.file(q=True,modified=True),
          'selection':cmds.ls(sl=True),'controls':{}}
for n in cmds.ls(type='transform'):
    if n.endswith(('_CTL','_CTRL')) and any(w in n.lower() for w in ('tunic','dress','skirt')):
        attrs=cmds.listAttr(n,userDefined=True) or []
        result['controls'][n]={'attrs':attrs,'keyable':cmds.listAttr(n,keyable=True),
          'inputs':cmds.listConnections(n,s=True,d=False,p=True,c=True),
          'outputs':cmds.listConnections(n,s=False,d=True,p=True,c=True)}
