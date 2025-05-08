import maya.cmds as cmds

def create_basic_groups():

    char_grp = cmds.createNode("transform", name="character", ss=True)
    rig_grp = cmds.createNode("transform", name="rig_GRP", ss=True, p=char_grp)
    ctl_grp = cmds.createNode("transform", name="controls_GRP", ss=True, p=char_grp)
    geo_grp = cmds.createNode("transform", name="geometry_GRP", ss=True, p=char_grp)
    skin_grp = cmds.createNode("transform", name="skinning_GRP", ss=True, p=rig_grp)

    return ctl_grp
def masterWalk():
    """
    Create the master walk group.
    """

    ctl_grp = create_basic_groups()

    master_walk_grp = cmds.createNode("transform", name="C_masterWalk_GRP", ss=True, p=ctl_grp)
    
    return master_walk_grp