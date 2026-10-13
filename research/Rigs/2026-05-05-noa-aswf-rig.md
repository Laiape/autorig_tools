---
source: https://dpel.aswf.io/noa/
found: 2026-05-05
category: rig
tags: [maya, production-rig, aswf, aws, film, character, yeti, arnold, open-source]
status: NEW
---

# Noa — ASWF Production Character Rig (AWS / Spanner)

## Descripción
Noa es el personaje principal del cortometraje "Spanner" de FuzzyPixel (AWS), disponible gratuitamente a través de la ASWF Digital Production Example Library (DPEL). Es un rig de producción real creado por un equipo VFX profesional que puede descargarse libremente bajo la ASWF Asset License. Incluye geometría, texturas, rig, y sistema de pelo Yeti. Notable por el hecho de que Noa y Ulysse (el otro personaje principal) comparten exactamente la misma topología, lo que facilita la transferencia de skin weights entre ambos.

## Stack técnico
- Platform: Autodesk Maya (versión no especificada; producción ~2023-2024)
- Hair: Yeti (plugin de Peregrine Labs)
- Texturing: Substance Painter
- Render: Arnold (Maya Arnold)
- Repository: aws-samples/nimblestudio-demo-assets (archivado marzo 2026)
- License: ASWF Asset License (libre para uso incluyendo comercial con atribución)
- Download: https://dpel.aswf.io/noa/

## Detalles técnicos

### Archivos disponibles
- **noa_rig.mb**: Maya binary con el personaje riggeado, geometría de pelo de baja resolución y materiales con texturas de baja resolución
- **noa_look.mb**: Maya binary con texturas de alta resolución + sistema Yeti para simulación de pelo
- Nota post-descarga: requiere repathing de texturas y (en look file) del alembic cache

### Características del rig
- Full body biped character rig de nivel de producción de estudio VFX
- Rig + geometría + texturas + groom disponibles en un único asset
- Hair: Yeti hair system (simulable)

### Metatopología compartida (Noa/Ulysse)
- Noa y Ulysse comparten exactamente la misma topología facial y corporal
- Skin weights del personaje A se transfieren directamente al B sin retopología
- Permite mantener un único rig "base" y shape-blendear entre ambos personajes
- Técnica aplicable en pipelines con personajes de la misma familia (hero + variants, NPCs)

### Proyecto Spanner
- Corto animado de FuzzyPixel (AWS internal production team)
- Creado como demo técnico para AWS Nimble Studio
- Rigging del puente del Spanner: separado del rig del personaje (artículo AWS: "Rigging the bridge for Spanner")

## Comparación con autorig_tools
Noa es un ejemplo de rig de producción real, no un rig de demostración simplificado. Su valor es como referencia de calidad y para análisis técnico. La metatopología compartida entre personajes (Noa/Ulysse) es una técnica de pipeline que autorig_tools podría soportar explícitamente. El hecho de que el sistema de pelo (Yeti) esté incluido como parte del asset es un diferencial para rigs de calidad AAA.

## Takeaways aplicables
- Descargar y analizar noa_rig.mb para examinar la arquitectura de rig de nivel VFX: grupos, nomenclatura, jerarquía de transforms, módulos faciales.
- La técnica de **metatopología compartida** (misma topología → transferencia directa de skin weights) es relevante si autorig_tools debe soportar variantes de personaje. Considerar añadir un módulo de transferencia de skin weights entre topologías idénticas.
- El repositorio está **archivado (marzo 2026)**, así que descargar los assets pronto antes de que puedan desaparecer.
- Usar Noa como **benchmark de rendimiento**: medir FPS de viewport con el rig de Noa para comparar con rigs construidos con autorig_tools.

## Fuente
https://dpel.aswf.io/noa/  
https://aws.amazon.com/blogs/media/aws-artist-series-animating-noa/  
https://github.com/aws-samples/nimblestudio-demo-assets/tree/main/spanner/assets/char/noa/rig
