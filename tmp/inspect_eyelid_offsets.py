from maya import cmds
result={}
for side in ('L','R'):
    result[side]={}
    for name in ('upperEyelid00','upperEyelid010','upperEyelid020','downEyelid021','downEyelid031','downEyelid041'):
        result[side][name]={suffix:cmds.getAttr(side+'_'+name+suffix) for suffix in ('ContactOffset_BMX.inputMatrix','Skinning_AIM.primaryTargetMatrix','_PMT.target[0].offsetMatrix')}
