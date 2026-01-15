import maya.cmds as cmds

def auto_collision_rig(collider_list, target_obj, axis='Z', direction=1):
    """
    Creates a distance-based collision system.
    
    Args:
        collider_list (list): List of strings (joint/object names) that act as pushers.
        target_obj (str): The object to be pushed (e.g., a secondary bone).
        axis (str): Push axis ('X', 'Y', or 'Z').
        direction (int): 1 for positive, -1 for negative.
    """
    prefix = target_obj + "_autoPush"
    
    # 1. Create Offset Hierarchy for the target
    # This prevents 'double transforms' and keeps the joint's actual channels clean.
    target_parent = cmds.listRelatives(target_obj, parent=True)
    auto_offset_grp = cmds.group(empty=True, name=f"{prefix}_Offset_GRP")
    
    # Match the group to the target's position/orientation
    cmds.delete(cmds.parentConstraint(target_obj, auto_offset_grp, maintainOffset=False))
    
    if target_parent:
        cmds.parent(auto_offset_grp, target_parent[0])
    cmds.parent(target_obj, auto_offset_grp)
    
    # 2. Add Control Attributes to the target object
    if not cmds.attributeQuery("collisionSettings", node=target_obj, exists=True):
        cmds.addAttr(target_obj, longName="collisionSettings", attributeType="enum", enumName="______", keyable=True)
        cmds.setAttr(f"{target_obj}.collisionSettings", lock=True)
        cmds.addAttr(target_obj, longName="collideRadius", attributeType="float", defaultValue=5.0, keyable=True)
        cmds.addAttr(target_obj, longName="pushAmount", attributeType="float", defaultValue=3.0, keyable=True)

    # 3. Setup Distance Logic
    # We use a plusMinusAverage node set to 'Minimum' to find which collider is closest.
    min_dist_node = cmds.createNode('plusMinusAverage', name=f"{prefix}_minDist")
    cmds.setAttr(f"{min_dist_node}.operation", 3) # Operation 3 = Minimum
    
    # Get the target's world position via Decompose Matrix
    decomp_target = cmds.createNode('decomposeMatrix', name=f"{prefix}_target_dcm")
    cmds.connectAttr(f"{auto_offset_grp}.worldMatrix[0]", f"{decomp_target}.inputMatrix")

    # Connect each collider
    for i, col in enumerate(collider_list):
        col_dcm = cmds.createNode('decomposeMatrix', name=f"{col}_dcm")
        dist_node = cmds.createNode('distanceBetween', name=f"{col}_to_target_dist")
        
        cmds.connectAttr(f"{col}.worldMatrix[0]", f"{col_dcm}.inputMatrix")
        cmds.connectAttr(f"{col_dcm}.outputTranslate", f"{dist_node}.point1")
        cmds.connectAttr(f"{decomp_target}.outputTranslate", f"{dist_node}.point2")
        
        # Feed distance into the 'Minimum' selector
        cmds.connectAttr(f"{dist_node}.distance", f"{min_dist_node}.input1D[{i}]")

    # 4. Remap and Output
    remap_node = cmds.createNode('remapValue', name=f"{prefix}_remap")
    cmds.setAttr(f"{remap_node}.value[0].value_Interp", 2) # Set to Spline for smooth falloff
    
    cmds.connectAttr(f"{min_dist_node}.output1D", f"{remap_node}.inputValue")
    cmds.connectAttr(f"{target_obj}.collideRadius", f"{remap_node}.inputMax")
    cmds.connectAttr(f"{target_obj}.pushAmount", f"{remap_node}.outputMin")
    
    # Direction Multiplier
    mult_node = cmds.createNode('multDoubleLinear', name=f"{prefix}_dir_mult")
    cmds.setAttr(f"{mult_node}.input2", direction)
    
    cmds.connectAttr(f"{remap_node}.outValue", f"{mult_node}.input1")
    cmds.connectAttr(f"{mult_node}.output", f"{auto_offset_grp}.translate{axis}")

    print(f"Collision system successfully created for: {target_obj}")


    

# selection = cmds.ls(sl=True)
# if len(selection) >= 2:
#     input_colliders = selection[:-1]
#     input_target = selection[-1]
    
#     auto_collision_rig(input_colliders, input_target, axis='Z', direction=1)
# else:
#     cmds.warning("Please select at least one collider and one target object.")