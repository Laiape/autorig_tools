result={n:{a:{'value':cmds.getAttr(n+'.'+a),'settable':cmds.getAttr(n+'.'+a,settable=True)}
           for a in ('translateX','rotateY','scaleX','scaleY','scaleZ')}
        for n in ('C_masterwalk_CTL','C_character_CTL','C_freeze_CTL','Edward') if cmds.objExists(n)}
