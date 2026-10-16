from maya import cmds
kinds=cmds.allNodeTypes()
candidates=[k for k in kinds if any(w in k.lower() for w in ('vector','normaliz','matrix','dotproduct','crossproduct','length'))]
result={'types':candidates,'attributes':{}}
for kind in ('normalize','length','crossProduct','dotProduct','axisFromMatrix','rowFromMatrix','vectorMatrixMult','pointMatrixMult','distanceBetween'):
 if kind in kinds:
  result['attributes'][kind]=cmds.attributeInfo(type=kind,allAttributes=True)
