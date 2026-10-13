---
source: https://www.animationmentor.com/blog/free-animation-rig-download-now/
found: 2026-06-22
category: rig
priority: 3
tags: [maya, rigging, rig, facial, free, production]
status: NEW
---

# Ray — Rig de Animation Mentor (Victor Vinyals / DreamWorks)

## Descripción
Ray es un rig de personaje gratuito distribuido por Animation Mentor, diseñado por Victor Vinyals (rigger de DreamWorks) y probado por animadores de DreamWorks. Es uno de los pocos rigs gratuitos con un facial rig considerado de calidad suficiente para "acting real" en vez de solo pose básica de boca — referencia útil de benchmark de calidad facial gratuito, en la misma categoría que Malcolm (AnimSchool, ya cubierto en este vault el 2026-05-05).

## Fundamento matemático / técnico
No hay documentación técnica pública detallada de la arquitectura interna de Ray (es un asset binario .ma/.mb, no un repo de código abierto), pero las fuentes coinciden en: rig de cuerpo completo con IK/FK y switching, sistema facial con suficiente "layering" para permitir overlapping de expresiones combinadas (no solo blend lineal de poses extremas), y poses pre-construidas (faciales, manos, cuerpo completo) para acelerar blocking — un patrón de "pose library" que vale la pena comparar contra el propio sistema de SDK/RBF de Laia para ver si su pipeline ya ofrece una librería de poses equivalente para animadores.

## Implementación en Maya
- Distribución: archivo de escena Maya, sin código fuente del rig en sí.
- Descarga vía Animation Mentor (gratis para estudiantes/uso educativo) o vía CGTarian con términos de uso personal/educativo, crédito requerido, sin uso comercial.
- Compatible con versiones recientes de Maya según las fuentes consultadas (sin versión mínima específica documentada).

## Comparación con autorig_tools
Como es un rig cerrado (sin código), no hay nada que importar directamente al pipeline de Laia. Su valor es de benchmark de calidad: es una referencia pública y ampliamente usada en la industria de animación para evaluar qué nivel de control facial y de poses pre-construidas se considera "producción seria" en un rig gratuito — útil como punto de comparación cuando Laia evalúe la usabilidad para animadores de sus propios rigs faciales (jaw, eyes, eyelids, brows, lips) generados por autorig_tools.

## Aplicable directamente
NO — Sin código fuente disponible, no hay nada técnico que extraer. Su uso recomendado es solo como rig de referencia para probar feel/usabilidad animator-facing, no como fuente de implementación.

## Fuente
https://www.animationmentor.com/blog/free-animation-rig-download-now/
https://www.cgtarian.com/maya-character-rigs/download-free-3d-character-ray.html
https://www.therookies.co/blog/resources/best-free-character-rigs-2026
