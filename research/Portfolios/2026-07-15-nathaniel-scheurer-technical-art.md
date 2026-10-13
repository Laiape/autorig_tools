---
url: https://nathanielscheurer.com
found: 2026-07-15
category: portfolio
credits: Sin créditos de producción documentados — estudiante/recién graduado de TGA (The Game Assembly, programa de Technical Art)
tags: rigging, technical-art, auto-rigger, FACS, RBF, ARKit, game-engine, game-ready, student-portfolio
status: NEW
---


# Nathaniel Scheurer — Technical Art (TGA Graduate)


## Perfil profesional
Nathaniel Scheurer es un Technical Artist recién graduado del programa Technical Art de TGA (The Game Assembly). No tiene créditos de producción de estudio documentados. Su portfolio es notable no por los créditos sino por la densidad y especificidad de la documentación técnica de sus proyectos: un auto-rigger modular propio, un rig facial FACS ARKit-compatible con correctives de RBF, y un pipeline de export a game engine. Perfil de interés para el research de Laia exclusivamente por los patrones de contenido — cómo documenta sistemas técnicos complejos en un portfolio sin créditos de producción, que es exactamente la situación de Laia con su auto-rig propio.


## Estructura del portfolio
- **nathanielscheurer.com** (sitio personal): Multi-disciplina — rigging + texturing + modeling en secciones separadas
- No blog ni write-ups externos encontrados
- No GitHub ni open-source tools documentados
- No Zerply, IMDb ni plataformas adicionales encontradas
- Proyectos principales documentados: Auto-Rigger, FACS Facial Rig (orc head), RBF Correctives


## Cómo presenta los proyectos
Cada proyecto con descripción detallada de arquitectura interna:


**Auto-Rigger:**
- Descripción del sistema: "modular guide joint system — user selects from a list of limb types, aligns them to character proportions, parents guides together to map out the skeleton hierarchy"
- Features de cada módulo: IK/FK switches, soft IK, automatic pole vectors, foot roll setups
- Feature de animación: custom "keying sets" para acelerar workflow de animación
- Pipeline de export: "import references → extract mesh and skeleton from complex rig hierarchy → bake all animation directly to deformation joints → clean scene → output lightweight FBX" — todo automatizado
- Goal declarado: "rig any humanoid or creature in hours instead of weeks"
- Origen del proyecto: "began developing this auto-rigger on his first day in the Technical Art program at TGA"


**FACS Facial Rig (orc head):**
- Base head sculpteado manualmente
- FACS blendshapes generadas y transferidas a la topología del orc
- Custom correctives sculptados para la zona de colmillos (fix de anatomía rota en los transfers automáticos)
- ARKit-compatible — diseñado para mocap con face tracking
- Unreal Engine Pose Wrangler para drivers de RBF en lugar de SDK tradicional
- Objetivo declarado: export de corrective drivers directamente a Unreal Engine


## Cómo comunica sus skills
- Descripción de arquitectura interna del sistema — no solo qué hace sino cómo está construido por dentro
- Especificación de target externo: "ARKit-compatible" como requirement del facial system
- Decisión técnica documentada explícitamente: "RBF instead of traditional set driven keys" — con el motivo (export a Unreal es más directo con Pose Wrangler)
- Game-engine pipeline como output documentado del auto-rigger — no implícito
- Múltiples disciplinas en el site pero proyecto técnico principal tiene su propia sección con arquitectura detallada
- Sin métricas cuantificadas (no joint counts, no time-saved claims)


## Lo que tiene que Laia no tiene
1. **Documentación de la arquitectura interna del auto-rig** — Nathaniel describe cómo funciona su sistema por dentro: limb types seleccionables, guide joint system, qué features están automatizadas, qué requiere configuración manual. Laia tiene "Architecture Overview" y "Build Sequence" en pipeline.html pero aparentemente no documenta la arquitectura interna del propio auto-rig como sistema modular. Añadir 4-5 frases con: qué módulos soporta (biped, quadruped, facial), cómo se configura la jerarquía, qué está automatizado, qué requiere input manual. Esta información es exactamente lo que un Rigging Supervisor usa para evaluar si un auto-rig es de producción o de ejercicio.


2. **Compatibilidad con estándar externo documentada como spec del rig** (ARKit, FACS, mocap curves): Nathaniel nombra "ARKit-compatible" como especificación del facial system — no como bonus sino como requirement de diseño. Laia tiene un facial system completo (jaw/eyes/teeth/tongue/lips) pero no documenta si es compatible con ningún estándar externo. Si el facial system puede mapear a FACS, si exporta a ARKit, o si admite mocap curve retargeting, documentarlo como una especificación técnica del sistema en pipeline.html.


3. **Pipeline de export al engine como feature documentada del auto-rig**: Nathaniel documenta el pipeline completo de entrega al engine como parte del sistema: extract mesh + skeleton, bake animation, clean scene, output FBX. Para posicionarse en estudios AAA, el rig de Laia necesita comunicar que llega al engine — no solo que existe en Maya. Añadir en pipeline.html una frase de "delivery pipeline": si soporta FBX export, si fue testado en Unity o Unreal, qué skeleton hierarchy conventions usa.


## Aplicable a Laiape.github.io
1. Añadir en pipeline.html, dentro de la sección Architecture Overview o como subsección propia, 4-5 frases describiendo la arquitectura interna del auto-rig: qué módulos existen, cómo se construye la jerarquía, qué features están automatizadas. El modelo exacto es la descripción del guide joint system de Nathaniel.
2. Añadir como spec del facial system el estándar externo de compatibilidad — aunque sea "designed for ARKit retargeting" o "FACS-compatible blendshape structure" si es el caso.
3. Añadir en pipeline.html una frase de "export pipeline": si el rig soporta entrega a game engine, qué workflow. Una frase, no una sección. Pero debe estar para un reclutador de AAA studio.


## Fuente
https://nathanielscheurer.com