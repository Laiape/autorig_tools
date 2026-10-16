lip_pose({'C_jaw_CTL.rotateX':30})
before=meshpoints('cabeza_low')
result=posebs.convert_target_to_transform_space('cabeza_low','cabeza_low_poseCorrectives_BLS',0,'C_headSkinning_JNT')
error=float(np.linalg.norm(meshpoints('cabeza_low')-before,axis=1).max())
lip_pose({})
result={'conversion':result,'endpoint_error_cm':error}
