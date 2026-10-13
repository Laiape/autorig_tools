---
source: https://github.com/mayjackass/ML-Corrective-Deformer-Maya-Public
found: 2026-05-05
category: tool
tags: [maya, python, machine-learning, correctives, blendshapes, deformation, pytorch, neural-network]
status: NEW
---

# ML-Corrective-Deformer-Maya — Deformador Correctivo via Machine Learning

## Descripción
Sistema de deformación correctiva basado en redes neuronales para Autodesk Maya que automatiza la creación de corrective blendshapes. Aprende el mapping de ángulos de joints → desplazamientos de vértices desde pares pose/shape proporcionados por el artista o extraídos de simulaciones. Actualmente en Fase 1 (prototipo Python); la Fase 3 planea implementación C++/LibTorch con CUDA.

## Stack técnico
- Language: Python 3.7+
- Platform: Autodesk Maya 2020+
- ML Framework: PyTorch 1.8+, TorchScript, ONNX export
- Maya integration: MPxDeformerNode (Maya Python API)
- Dependencies: numpy, PyTorch
- Stars: 14 | Version: 1.0.0 Phase 1 | Last updated: October 17, 2025
- Status: active development (research/prototype)

## Detalles técnicos

### Arquitectura de Red Neuronal
Tres opciones de arquitectura:
1. **Standard**: 4-layer feedforward, hidden dims [256, 512, 512, 256]
2. **Compact**: PCA-compressed, hidden dims [128, 256, 128] — menor footprint en memoria
3. **Residual**: deep network con skip connections, 4+ bloques residuales — mejor para deformaciones complejas

### Input/Output
- **Input**: ángulos de joint normalizados en rango [-1, 1] (num_samples × num_joints)
- **Output**: vertex displacement vectors (num_samples × num_vertices × 3)
- Datos de entrenamiento en formato `.npz`

### Performance (Fase 1 - Python)
- Soporta ~1,000 vértices
- 24-30 FPS en viewport
- Latencia: 10-20ms por frame

### Performance objetivo (Fase 3 - C++/LibTorch/CUDA)
- 10,000+ vértices
- 60+ FPS
- Latencia: <5ms con aceleración CUDA

### Implementación Maya
- Implementado como `MPxDeformerNode` — el nodo de deformación custom evalúa la red neuronal en cada frame
- Export a TorchScript y ONNX para portabilidad a otras plataformas
- Pipeline: recopilar datos → entrenar modelo → exportar → cargar nodo deformador

### Pipeline de datos
```
utils/          ← herramientas de recopilación de datos de training
ml_training/    ← framework de entrenamiento PyTorch
models/         ← modelos entrenados (.pt, .onnx)
phase1_python_prototype/  ← implementación actual del deformador
```

## Comparación con autorig_tools
autorig_tools usa correctives basados en RBF/SDK, que son deterministas y artísticamente controlables. Este sistema ML propone un enfoque de aprendizaje automático que reduce trabajo manual pero introduce una caja negra. Para producción AAA/VFX, el control artístico y la predictibilidad suelen ser más importantes que la automatización total. Sin embargo, el concepto de usar ML para proponer correctives iniciales (que luego el artista refina) es interesante como herramienta de asistencia. El uso de MPxDeformerNode es un patrón técnico aplicable independientemente del ML.

## Takeaways aplicables
- El patrón de **MPxDeformerNode en Python** para deformadores custom es directamente aplicable en autorig_tools para casos donde los deformadores estándar de Maya no son suficientes.
- El **formato .npz para almacenar pares pose/corrective** puede ser un formato útil para exportar/importar librerías de correctives en autorig_tools.
- A medio plazo, un pipeline "ML-assisted correctives" podría funcionar como paso intermedio: la red propone las deltas, el artista las aprueba/edita, y se convierte en correctives estáticos (no runtime ML). Esto mantiene predictibilidad en producción.
- El uso de **ONNX export** para portabilidad a motores (UE5, Unity) es muy relevante para pipelines multiplatforma.

## Fuente
https://github.com/mayjackass/ML-Corrective-Deformer-Maya-Public
