---
source: https://www.hatrigs.com/event-details/advanced-facial-rigging-workshop-winter-2025
found: 2026-05-05
category: technique
tags: [maya, facial, rigging, jaw, eyes, eyelids, lips, blendshapes, joints, production]
status: NEW
---

# Facial Rigging de Producción en Maya — Jaw, Eyes, Eyelids, Lips

## Descripción
Técnicas de rigging facial de nivel de producción para personajes en Maya. El enfoque moderno de producción AAA/VFX combina joints para movimientos rotativos (mandíbula, párpados, labios) con blendshapes para deformaciones orgánicas (arrugas, volumen, formas no-lineales). La cara superior (ojos, cejas, párpados, mejillas superiores) es crítica para evitar el "uncanny valley". El HAT Rigs Workshop (enero-febrero 2026) ha sido la referencia más reciente del sector.

## Stack técnico
- Autodesk Maya 2022+
- Nodes: `aimConstraint` (ojos), `blendShape`, `skinCluster`, `jointOrient`, `follicle`/`pointOnSurfaceInfo`
- Drivers: SDK (Set Driven Key), RBF, atributos custom en controles
- Python: automatización de setup vía `maya.cmds`

## Detalles técnicos

### Arquitectura general cara
```
UPPER FACE (joints + blendshapes):
  ├── Eyeballs: aim constraint desde eye controls
  ├── Eyelids: joints (básico) + blendshapes (formas complejas)
  ├── Brows: joints con SDK → blendshapes de arrugas
  └── Upper cheeks: blendshapes driven by cheek controls

LOWER FACE (joints + blendshapes):
  ├── Jaw: joint rotativo (básico) + blendshapes de chin/lip interaction
  ├── Lips: joints para curl/pucker + blendshapes para formas complejas
  └── Cheeks: blendshapes driven by smile/compression
```

### Jaw (Mandíbula)
- **Joint-based**: 1 joint jaw con pivote en ATM (articulación temporomandibular)
- Rotación X: apertura/cierre
- Rotación Y: lateral (prognathism correction)
- SDK en rotación jaw → weight de blendshapes de chin stretching y lip contact
- Para personajes realistas: añadir corrective blendshape de "lip rolling" cuando jaw rota

### Eyeball Setup
```python
# Ojo: aim constraint con up vector estabilizado
cmds.aimConstraint(
    'eye_ctrl', 'eyeball_joint',
    aimVector=[0, 0, 1],   # forward axis del ojo
    upVector=[0, 1, 0],    # up axis
    worldUpType='object',
    worldUpObject='head_joint'  # up vector relativo a la cabeza
)
```
- **No usar** worldUpType='scene' — causará flips al rotar la cabeza
- Alternativa matrix-based: multMatrix de la posición del control → aim matrix calculada

### Eyelid Setup — dos niveles
**Nivel básico** (joints rotacionales):
- Upper lid: joint con pivot en el globo ocular → rotación X cierra el párpado
- Lower lid: idem
- SDK: lid_ctrl.translateY → upper_lid_joint.rotateX (apertura)

**Nivel avanzado** (producción AAA):
- Joints de párpado a lo largo del contorno del ojo (6-8 joints por párpado)
- Cada joint con follicle/pointOnSurfaceInfo sobre una superficie NURBS de los párpados
- Controles de squash/stretch del párpado (para wink, blink)
- Blendshapes para formas especiales: fully-closed squeeze, wide open, sleepy
- **Auto-blink**: SDK que el párpado superior sigue parcialmente al inferior (corrección de lid tracking)

### Lips Setup
- Joint-based para movimientos de curl, jaw-follow, pucker
- Blendshapes para shapes complejas: smile, frown, mouth corners up/down
- **Lip seal corrective**: cuando jaw cierra, lip contact debe activarse automáticamente vía RBF/SDK
- Distribución de joints: corners (2), upper lip (2-4), lower lip (2-4), cupid's bow (1)

### Blendshape + Joint: cuándo usar cada uno
| Situación | Recomendado |
|---|---|
| Apertura de mandíbula | Joint (rotación lineal) |
| Arruga en frente al fruncir | Blendshape |
| Curl de labio | Joint |
| Volumen de mejilla al sonreír | Blendshape |
| Parpadeo básico | Joint |
| Forma especial de ojo (sleep, squint) | Blendshape |
| Corrección de skin al rotar | Corrective blendshape (post-skin) |

### Rig facial de metatopología (técnica avanzada)
Para personajes con variantes (ej. Noa/Ulysse en Spanner comparten topología):
- Diseñar la topología para que skin weights del personaje A se transfieran directamente al B
- Permite reusar correctives entre variantes del personaje
- Herramienta: **mGear Blendshape Transfer Tool** (5.3) para transferencia multi-source

## Comparación con autorig_tools
autorig_tools ya cubre facial rig. Los aspectos técnicos más avanzados a revisar son: (1) el uso de `worldUpObject` correcto en los aim constraints de ojos para evitar flips, (2) la implementación del auto-blink (lip seal automático) vía SDK/RBF, y (3) la arquitectura de joints múltiples por párpado para calidad AAA. El HAT Rigs Workshop Winter 2025-2026 es una referencia de industria actual.

## Takeaways aplicables
- Verificar que el aim constraint de los ojos en autorig_tools usa `worldUpType='object'` con un joint de la cabeza como up object — es el error más común en eye rigs (flips al girar el cuerpo).
- Implementar **lip seal automático**: RBF o SDK que al detectar jaw ≤ X grados, active el blendshape de contacto de labios. Elimina posing manual.
- Para calidad AAA, considerar pasar de 1 joint de párpado a una curva de joints (6-8) en el contorno — permite formas de ojo más ricas.
- La herramienta **mGear Blendshape Transfer** (5.3) es muy útil si autorig_tools maneja personajes con variantes de la misma topología.

## Fuente
https://www.hatrigs.com/event-details/advanced-facial-rigging-workshop-winter-2025  
https://www.thegnomonworkshop.com/workshops/creating-stylized-facial-rigs-for-production-in-maya  
https://80.lv/articles/working-on-a-face-rig-for-a-stylized-character-in-maya
