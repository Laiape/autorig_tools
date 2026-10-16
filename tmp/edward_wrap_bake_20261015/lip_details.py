from ngSkinTools2 import api as ngapi
with bifrost_wrinkles.primary_inputs_for_skin_export():
    result={'ng_layers':[(s,safe(lambda s=s:[{'id':l.id,'name':l.name,'enabled':l.enabled,'opacity':l.opacity} for l in ngapi.Layers(s).list()])) for s in ('C_mouth_local_SKC','skinCluster41')], 'head_skins':[(s,cmds.getAttr(s+'.skinningMethod'),cmds.getAttr(s+'.maxInfluences'),cmds.getAttr(s+'.maintainMaxInfluences')) for s in headskins], 'targets':[]}
    for b in ('cabeza_high_poseCorrectives_BLS','cabeza_low_poseCorrectives_BLS'):
        for i in cmds.getAttr(b+'.weight',mi=True):
            g=b+'.inputTarget[0].inputTargetGroup[%s]'%i
            result['targets'].append({'bs':b,'index':i,'mode':safe(lambda:cmds.getAttr(g+'.postDeformersMode')),'items':cmds.getAttr(g+'.inputTargetItem',mi=True),'record':posebs.pose_record(b,i),'aliases':cmds.aliasAttr(b+'.weight[%s]'%i,q=True)})
