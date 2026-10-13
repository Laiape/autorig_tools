---
source: https://animschool.edu/DownloadOffer.aspx
found: 2026-05-05
category: rig
tags: [maya, free-rig, animation-rig, biped, picker, animschool, reference]
status: NEW
---

# Malcolm 2.0 — AnimSchool Free Maya Rig

## Descripción
Malcolm 2.0 es el rig de personaje gratuito de AnimSchool, ampliamente utilizado en escuelas de animación y como referencia de rig de bípedo. Aunque no es un rig de producción AAA, es el rig gratuito más descargado de la comunidad Maya y sirve como referencia de UX para animadores: sus controles, picker, y sistema de poses son la referencia del sector para rigs de animación educativa.

## Stack técnico
- Platform: Autodesk Maya 2017+
- Required plugin: AnimSchool Picker (para la UI de selección de controles)
- Files: malcolm_v200.ma + picker files (Body, Face, Outfits)
- Workflow: reference el archivo (no importar) para updates más fáciles
- License: gratuito para uso personal y educativo

## Detalles técnicos

### Características del rig
- Bípedo completo: cuerpo + cara + ropa (outfits intercambiables)
- Controles FK/IK en extremidades con space switching
- Facial rig con controles directos
- AnimSchool Picker: interfaz visual de selección de controles (custom panel en Maya)
- Sistema de poses guardables

### Limitaciones técnicas
- Requiere Maya 2017+; crashes reportados en ciertas versiones de Maya 2018 (fix: update 4-5)
- El picker requiere el plugin de AnimSchool (separado del archivo de rig)
- Diseñado para animación, no como referencia de rigging técnico avanzado

### Uso como referencia
- Referencia de UX para animadores: disposición de controles, naming conventions del picker
- Comparar el sistema de selección y pose del picker con el approach de autorig_tools
- Usado en producciones educativas globalmente como rig estándar de práctica

## Comparación con autorig_tools
Malcolm no es una referencia de rigging técnico avanzado sino de **UX para animadores**. El AnimSchool Picker muestra cómo una interfaz visual de selección de controles bien diseñada acelera el workflow de animación. autorig_tools puede comparar su picker/UI contra Malcolm para identificar gaps de usabilidad. No es relevante como referencia de arquitectura técnica (matrix nodes, etc.).

## Takeaways aplicables
- Si autorig_tools incluye una UI de animator (picker), analizar la disposición de controles del Malcolm Picker como referencia de ergonomía.
- El workflow de **reference (no import)** para el rig facilita updates sin romper escenas de animación existentes — patrón de distribución recomendable para rigs de autorig_tools.
- Para rigs de práctica y demos de autorig_tools, considerar publicar un personaje similar con el rig construido con autorig_tools.

## Fuente
https://animschool.edu/DownloadOffer.aspx  
https://animationmethods.com/rigs.html
