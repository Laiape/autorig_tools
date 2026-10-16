lip_pose({'C_jaw_CTL.rotateX':30})
mesh='cabeza_low';b='cabeza_low_poseCorrectives_BLS'
g=b+'.inputTarget[0].inputTargetGroup[0]';dpath=g+'.inputTargetItem[6000]'
desired=meshpoints(mesh)
cmds.setAttr(g+'.postDeformersMode',2)
cmds.setAttr(g+'.targetBindMatrix',*cmds.getAttr('cabeza_high_poseCorrectives_BLS.inputTarget[0].inputTargetGroup[4].targetBindMatrix'),type='matrix')
cmds.connectAttr('C_headSkinning_JNT.worldMatrix[0]',g+'.targetMatrix',force=True)
zero=np.zeros_like(desired);write_delta(dpath,zero);baseline=meshpoints(mesh)
basis=[]
for axis in range(3):
    probe=np.zeros_like(desired);probe[:,axis]=1
    write_delta(dpath,probe);basis.append(meshpoints(mesh)-baseline)
response=np.stack(basis,axis=2)
raw=np.einsum('vij,vj->vi',np.linalg.pinv(response),desired-baseline)
write_delta(dpath,raw)
err=float(np.linalg.norm(meshpoints(mesh)-desired,axis=1).max())
lip_pose({})
result={'endpoint_error_cm':err,'mode':cmds.getAttr(g+'.postDeformersMode')}
