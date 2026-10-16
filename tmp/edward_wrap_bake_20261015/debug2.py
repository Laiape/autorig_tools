with bifrost_wrinkles.primary_inputs_for_skin_export():
 result=[(s,cmds.deformer(s,q=True,g=True),safe(lambda:meshweights(s)[1].fullPathName())) for s in headskins]
