---
source: https://sourceforge.net/projects/dqs-maya-plugin/
found: 2026-06-29
category: tool
priority: 3
tags: [maya, C++, plugin, dual-quaternion, skinning, DQS, skinClusterDq]
status: NEW
---

# DQS Maya Plugin (Guido de Haan) — Nodo skinClusterDq de Producción

## Descripción
Plugin de Maya en C++ (versión 1.1.0) que implementa un nodo de skinning `skinClusterDq` con Dual Quaternion Skinning siguiendo el paper de Kavan et al. ("Skinning with Dual Quaternions" / "Geometric Skinning with Approximate Dual Quaternion Blending"). A diferencia del repositorio `brainexcerpts/Dual-Quaternion-Skinning-Sample-Codes` (ya documentado en Tools), que es código de ejemplo educativo en C++ standalone, este es un plugin de Maya completo y cargable como nodo real de skinning en una escena — más cercano a una herramienta de producción lista para usar que a un tutorial de referencia matemática.

## Fundamento matemático / técnico
Implementa la misma base matemática de DQS ya documentada extensamente en `dual-quaternion-skinning-math.md` (DLB — Direct/Dual quaternion Linear Blending, fix de antipodalidad, blending sobre la variedad de cuaterniones duales unitarios en vez de sobre matrices). La diferencia técnica relevante de este plugin específico es que implementa la variante **Geometric Skinning con blending aproximado** del segundo paper de Kavan (2008) — la corrección de bulging mediante precómputo de pesos óptimos por vértice — como nodo nativo de Maya, en vez de requerir reimplementación manual del paso de corrección.

## Implementación en Maya
```python
import maya.cmds as cmds

cmds.loadPlugin('skinClusterDq')
# Reemplaza el skinCluster nativo por el nodo custom skinClusterDq,
# o se usa en paralelo para comparar contra el modo "Dual Quaternion"
# nativo de Maya (skinningMethod=1) que no incluye la corrección geométrica de bulging.
dq_skin = cmds.deformer(mesh, type='skinClusterDq')
```
El valor práctico frente al modo DQS nativo de Maya (`skinCluster.skinningMethod = 1`, que es DQS estándar sin corrección de bulging) es que este plugin incluye la variante geométrica que reduce el artefacto de abultamiento en las articulaciones — exactamente la limitación que el documento `dual-quaternion-skinning-math.md` señala como "Fix — Geometric DQS (Kavan 2008)" pero sin una implementación lista para usar en Maya nativo.

## Comparación con autorig_tools
Si el pipeline de skinning de `autorig_tools` usa actualmente el modo DQS nativo de Maya (`skinningMethod=1` o el modo Weight Blended `2`) y se observa bulging visible en articulaciones de alto rango de movimiento (hombros, caderas), este plugin sería una alternativa directa a evaluar — sustituye el nodo `skinCluster` nativo, no requiere reescribir el sistema de pesos de piel existente. El riesgo de adoptar un plugin de terceros en C++ (sin mantenimiento activo visible, alojado en SourceForge en vez de GitHub, señal de antigüedad/baja actividad reciente) debe sopesarse contra el beneficio: si el bulging actual no es un problema visible en producción, no hay urgencia de migrar.

## Aplicable directamente
PARTIAL — evaluar solo si el bulging de DQS es un problema visible actualmente:
1. Si autorig_tools usa skinningMethod=1/2 nativo y hay bulging visible en articulaciones, descargar y probar este plugin en un entorno de prueba (verificar compatibilidad de versión de Maya antes de cualquier integración en producción, dado que es un plugin antiguo sin actividad reciente confirmada).
2. Alternativa sin riesgo de plugin de terceros: implementar la corrección geométrica de bulging manualmente en Python como post-proceso de pesos (el algoritmo está descrito en `dual-quaternion-skinning-math.md`), evitando dependencia de un binario C++ no mantenido.
3. Si no hay problema de bulging visible actualmente, no es prioritario.

## Fuente
- https://sourceforge.net/projects/dqs-maya-plugin/
- Kavan et al. — "Geometric Skinning with Approximate Dual Quaternion Blending" (ACM TOG 2008)
- Relacionado: archivos existentes `dual-quaternion-skinning-math.md`, `brainexcerpts-dqs-sample-codes.md`
