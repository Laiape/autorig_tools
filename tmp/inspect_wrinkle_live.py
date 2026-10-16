import maya.cmds as c
result={'scene':c.file(q=True,sn=True),'attrs':{n:{a:c.getAttr(n+'.'+a) for a in (c.listAttr(n,ud=True) or []) if 'wrinkle' in a.lower() and c.getAttr(n+'.'+a,type=True) in ('double','float','bool')} for n in c.ls(type='transform') if any('wrinkle' in a.lower() for a in (c.listAttr(n,ud=True) or []))}}
