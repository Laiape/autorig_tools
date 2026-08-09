import maya.cmds as cmds
import maya.api.OpenMaya as om

# Deformer nodes that Maya defaults to isHistoricallyInteresting=2
DEFORMER_TYPES = {
    "skinCluster", "blendShape", "cluster", "wire", "jiggle",
    "deltaMush", "tension", "proximityWrap", "shrinkWrap",
    "nonLinear", "softMod", "tweak", "groupParts",
}

def restore_all():
    """
    Resets isHistoricallyInteresting on every node that was hidden by
    hide_connections / hide_all_utility_nodes, so skin clusters and other
    deformers appear again in listHistory and the Node Editor.

    - Deformer nodes  -> 2  (Maya default for important deformers)
    - Everything else -> 1  (visible in history, not cluttering Node Editor)
    """
    restored = 0

    for node in cmds.ls(dependencyNodes=True, long=False) or []:
        try:
            if not cmds.attributeQuery("isHistoricallyInteresting", node=node, exists=True):
                continue
            if cmds.getAttr(f"{node}.isHistoricallyInteresting") != 0:
                continue

            value = 2 if cmds.nodeType(node) in DEFORMER_TYPES else 1
            cmds.setAttr(f"{node}.isHistoricallyInteresting", value)
            restored += 1

        except Exception:
            pass

    om.MGlobal.displayInfo(f"restore_node_visibility: {restored} nodes restored.")
    return restored


if __name__ == "__main__":
    restore_all()
