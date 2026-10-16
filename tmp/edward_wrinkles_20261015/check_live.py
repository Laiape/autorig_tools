from maya import cmds
from maya_tools.scripts.tools import bifrost_wrinkles as bw
result={'scene':cmds.file(q=True,sn=True),'modified':cmds.file(q=True,modified=True),
 'setups':[{'prefix':r['prefix'],'settings':r['settings'],'controls':len(r['controls']),
 'zero_regions':[k for k,v in r['patterns'].items() if not any(v)]} for r in bw.export_setups()]}
