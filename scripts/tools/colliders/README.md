# colliders (sin UI)

Deformers de colisión **bell / skirt / plane** para Maya. Fork de funcionalidad de
[azagoruyko/colliders](https://github.com/azagoruyko/colliders) (Apache 2.0, Sergey
Azagoruyko). Se ha quitado la UI; solo quedan las funciones que crean y cablean los nodos.
Útil para arreglar interpenetraciones / "faltas" (p.ej. en anne).

## Importante
Los nodos de colisión (`bellCollider`, `skirtBellCollider`, `planeCollider`) son C++:
viven en `plugins/<versionMaya>/colliders.mll`. Hay builds para **2022, 2023, 2025**.
`load_plugin()` carga el de tu versión; si no existe (p.ej. **2026**) prueba el más
reciente como fallback. Si el de 2025 no carga en 2026, recompila desde `sources/` con
`CMakeLists.txt` (ver `UPSTREAM_README.md`) y deja el `.mll` en `plugins/2026/`.

## Uso integrado con el rig (recomendado — usa tus joints `_ENV`)
```python
from tools.colliders import (load_plugin, create_skirt_collider_from_rig,
                             create_bell_collider_on)
load_plugin()

# Falda: cableada a los _ENV del rig (hip/knee/heel/waist) automáticamente
node, bell, surf, joints = create_skirt_collider_from_rig(prefix="anne_",
                                                          with_heels=True,
                                                          attach_joints=True)

# Falta puntual: bell collider sobre un joint _ENV, que sigue a la pose
node, bell, rings, curve = create_bell_collider_on("L_legUpper00_ENV", numRings=1)
```

Plantillas de los `_ENV` (overrideables con `names=`):
`hip={side}_legUpper00_ENV`, `knee={side}_legLower00_ENV`, `heel={side}_legAnkle_ENV`,
`waist=C_localHip_ENV`.

## Uso directo (genérico, sin el rig)
```python
from tools.colliders import load_plugin, createBellCollider, createSkirtBellCollider, attachJointsToSurface
load_plugin()
node, bell, rings, curve = createBellCollider(numRings=1, prefix="test_")
node, bell, surf = createSkirtBellCollider(prefix="test_",
    leftHipObj="L_legUpper00_ENV", leftKneeObj="L_legLower00_ENV", leftHeelObj="L_legAnkle_ENV",
    rightHipObj="R_legUpper00_ENV", rightKneeObj="R_legLower00_ENV", rightHeelObj="R_legAnkle_ENV",
    waistObj="C_localHip_ENV")
joints = attachJointsToSurface(surf, u_num=7, v_num=5, prefix="test_")
```

## Atribución
Código y nodos originales: Sergey Azagoruyko — https://github.com/azagoruyko/colliders
Licencia Apache 2.0 (ver `LICENSE`). Aquí solo se ha separado la funcionalidad de la UI.
