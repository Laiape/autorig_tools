import maya.cmds as cmds

def node(type, name, parent, input, output, in_node, out_node):

    """
    Create a node of the specified type with given attributes and parent it to the specified parent node.
    """

    node = cmds.createNode(type, name=name, ss=True)
    
    if parent:
        cmds.parent(node, parent)
    
    if input and output:
        cmds.connectAttr(input, node + in_node, force=True)
        cmds.connectAttr(node + out_node, output, force=True)
    
    return node