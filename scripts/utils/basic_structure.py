import maya.cmds as cmds
from puiastreTools.tools.curve_tool import controller_creator
from puiastreTools.utils import data_export


def lock_attr(ctl, attrs = ["scaleX", "scaleY", "scaleZ", "visibility"]):
    for attr in attrs:
        cmds.setAttr(f"{ctl}.{attr}", keyable=False, channelBox=False, lock=True)

def condition(main_ctl, vis_trn, value):
    con = cmds.createNode("condition", name = f"{vis_trn}_Visibility_CON", ss=True)
    cmds.setAttr(con + ".secondTerm", value)
    cmds.connectAttr(main_ctl, con + ".firstTerm")
    cmds.setAttr(con + ".colorIfTrueR", 1)
    cmds.setAttr(con + ".colorIfFalseR", 0)
    cmds.connectAttr(con + ".outColorR", vis_trn + ".visibility")

def create_basic_structure(asset_name = "assetName"):

    folder_structure = {
        asset_name: {
            "controls_GRP": {
                "C_characterNode",
                "C_masterWalk",
                "C_preferences"

            },
            "rig_GRP": {
                "modules_GRP",
                "skel_GRP",
                "geoLayering_GRP",
                "skeletonHirearchy_GRP"
            },
            "model_GRP": {
                "PROXY",
                "LOD_100",
                "LOD_200"
            },
            "groom_GRP": {},
            "clothSim_GRP": {}
        }
    }

    main_transform = cmds.createNode("transform", name=asset_name, ss=True)

    ctls = []
    secondary_transforms = []
    rig_transforms = []

    for folder, subfolders in folder_structure[asset_name].items():
        secondary_transform = cmds.createNode("transform", name=folder, parent=main_transform, ss=True)
        secondary_transforms.append(secondary_transform)
        subfolders = sorted(list(subfolders))
        for subfolder in subfolders:
            if subfolder.startswith("C_"):
                ctl, grp = controller_creator(subfolder, ["GRP", "ANM"])
                cmds.setAttr(f"{ctl}.overrideEnabled", 1)
                if ctls:
                    cmds.parent(grp[0], ctls[-1])
                else:
                    cmds.parent(grp[0], secondary_transform)  
                ctls.append(ctl)
            else:
                trn = cmds.createNode("transform", name=subfolder, parent=secondary_transform, ss=True)
                rig_transforms.append(trn)

    print("Controls: ", ctls)
    data_exporter = data_export.DataExport()
    data_exporter.append_data("basic_structure", {"modules_GRP": rig_transforms[1],
                                                  "skel_GRP": rig_transforms[2],
                                                  "masterWalk_CTL": ctls[1],})


    cmds.addAttr(ctls[2], shortName="extraAttributesSep", niceName="EXTRA ATTRIBUTES_____", enumName="_____",attributeType="enum", keyable=False)
    cmds.setAttr(ctls[2]+".extraAttributesSep", channelBox=True)
    cmds.addAttr(ctls[2], shortName="reference", niceName="Reference",attributeType="bool", keyable=False, defaultValue=True)
    cmds.setAttr(ctls[2]+".reference", channelBox=True)

    cmds.addAttr(ctls[2], shortName="showModules", niceName="Show Modules",attributeType="bool", keyable=False, defaultValue=False)
    cmds.addAttr(ctls[2], shortName="showSkeleton", niceName="Show Skeleton",attributeType="bool", keyable=False, defaultValue=True)
    cmds.addAttr(ctls[2], shortName="meshLods", niceName="LODS", enumName="PROXY:LOD100:LOD200",attributeType="enum", keyable=False)
    cmds.setAttr(ctls[2]+".showModules", channelBox=True)
    cmds.setAttr(ctls[2]+".showSkeleton", channelBox=True)
    cmds.setAttr(ctls[2]+".meshLods", channelBox=True)

    cmds.setAttr(secondary_transforms[2]+".overrideDisplayType", 2)
    cmds.connectAttr(ctls[2]+".reference", secondary_transforms[2]+".overrideEnabled")
        
    cmds.addAttr(ctls[1], shortName="extraAttributesSep", niceName="EXTRA ATTRIBUTES_____", enumName="_____",attributeType="enum", keyable=True)
    cmds.addAttr(ctls[1], shortName="globalScale", niceName="Global Scale", minValue=0.001,defaultValue=1, keyable=True)
    cmds.setAttr(ctls[1]+".extraAttributesSep", channelBox=True, lock=True)
    cmds.connectAttr(ctls[1]+".globalScale", ctls[1] + ".scaleX", force=True)
    cmds.connectAttr(ctls[1]+".globalScale", ctls[1] + ".scaleY", force=True)
    cmds.connectAttr(ctls[1]+".globalScale", ctls[1] + ".scaleZ", force=True)

    condition(f"{ctls[2]}.meshLods", rig_transforms[6], 0)
    condition(f"{ctls[2]}.meshLods", rig_transforms[4], 1)
    condition(f"{ctls[2]}.meshLods", rig_transforms[5], 2)

    cmds.connectAttr(f"{ctls[2]}.showModules", rig_transforms[1]+ ".visibility")
    cmds.connectAttr(f"{ctls[2]}.showSkeleton", rig_transforms[2] + ".visibility")

    lock_attr(ctls[2], ["tx", "tz", "ty", "rx", "ry", "rz", "scaleX", "scaleY", "scaleZ", "visibility"])
    lock_attr(ctls[0])
    lock_attr(ctls[1])

    cmds.select(clear=True)

""""

    SETS WIP


    sets = {         
        f"{asset_name}_RIG_SET": {
            "__EXPORT__SET": {
                "__EXPORT__GEO_SET": {
                    secondary_transforms[4],
                    secondary_transforms[3],
                    secondary_transforms[2],
                },
                "__EXPORT__LOCATORS_SET": {},
                "__EXPORT__SKELETON_HIERARCHY_SET": {
                    rig_transforms[3]
                }

            },
            "CONTROLS_SET": {
                ctls[0],
                ctls[1],
                ctls[2],
            }
        }
    }

    set_node = cmds.sets(name=f"{asset_name}_RIG_SET", empty=True)
    for set_name, contents in sets[f"{asset_name}_RIG_SET"].items():
        secondary_set = cmds.sets(name=set_name, empty=True)
        cmds.sets(secondary_set, add=set_node)
        for item, inside in contents.items():
            print(item)
            print(inside)
            if item == "__EXPORT__SET":
                export_set = cmds.sets(name=item, empty=True)
                cmds.sets(export_set, add=secondary_set)

            else:
                cmds.sets(item, add=secondary_set)

         
"""



# create_basic_structure()