result={n:{a:{'value':cmds.getAttr(n+'.'+a),'settable':cmds.getAttr(n+'.'+a,settable=True)}
           for a in cmds.listAttr(n,userDefined=True) or [] if 'scale' in a.lower()}
        for n in ('C_masterwalk_CTL','C_character_CTL','Edward') if cmds.objExists(n)}
