import os, sys
from maya import cmds
from maya_tools.scripts.biped.autorig import eyebrow_module
from maya_tools.scripts.tools import bifrost_wrinkles

def attributes(node):
    result = {}
    for attr in cmds.listAttr(node, userDefined=True) or []:
        if not any(word in attr.lower() for word in ('wrinkle', 'tangent')):
            continue
        plug = node + '.' + attr
        result[attr] = dict(value=cmds.getAttr(plug), type=cmds.getAttr(plug,type=True),
            default=cmds.attributeQuery(attr,node=node,listDefault=True),
            minimum=cmds.attributeQuery(attr,node=node,minimum=True) if cmds.attributeQuery(attr,node=node,minExists=True) else None,
            maximum=cmds.attributeQuery(attr,node=node,maximum=True) if cmds.attributeQuery(attr,node=node,maxExists=True) else None,
            keyable=cmds.getAttr(plug,keyable=True), lock=cmds.getAttr(plug,lock=True),
            incoming=cmds.listConnections(plug,s=True,d=False,p=True) or [],
            outgoing=cmds.listConnections(plug,s=False,d=True,p=True) or [])
    return result

nodes = [n for n in cmds.ls(type='transform') if any(w in n.lower() for w in ('eyebrow','lip')) and n.endswith('_CTL')]
result = dict(pid=os.getpid(),scene=cmds.file(q=True,sn=True),modified=cmds.file(q=True,modified=True),
    module=eyebrow_module.__file__,wrinkle_module=bifrost_wrinkles.__file__,
    controls={n:attributes(n) for n in nodes},
    auto_nodes=cmds.ls('*eyebrow*AutoTan*') or [], selection=cmds.ls(sl=True))
