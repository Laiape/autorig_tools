lip_pose({})
result=[]
for b,i in [('cabeza_high_poseCorrectives_BLS',4),('cabeza_low_poseCorrectives_BLS',0)]:
    g=b+'.inputTarget[0].inputTargetGroup[%s]'%i
    result.append({'bs':b,'mode':cmds.getAttr(g+'.postDeformersMode'),'matrix_source':cmds.listConnections(g+'.targetMatrix',s=True,d=False,p=True),'matrix':cmds.getAttr(g+'.targetMatrix'),'bind':cmds.getAttr(g+'.targetBindMatrix')})
