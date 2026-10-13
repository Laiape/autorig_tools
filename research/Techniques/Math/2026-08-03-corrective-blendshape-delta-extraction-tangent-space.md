---
source: https://help.autodesk.com/view/MAYAUL/2024/ENU/?guid=GUID-C954C197-6D56-4EB8-BEA0-70DD1BBBAD6B
found: 2026-08-03
category: math
priority: 1
tags: [maya, rigging, math, correctives, blendshape, delta, tangent-space, PSD, skinning]
status: NEW
---


# Corrective Blendshape Delta Extraction — Tangent Space Math


## Descripción
La matemática de cómo se extraen los deltas de un blendShape correctivo en espacio tangente (local), vs el espacio objeto (world-relative). Este conocimiento es fundamental para el sistema de correctives de autorig_tools: determina si los correctives se comportan correctamente cuando el personaje se rota en world space, y es la base matemática de los "Tangent Space" targets de Maya y de los sistemas PSD/RBF que los utilizan.


## Fundamento matemático / técnico


### El Problema de los Deltas en Object Space


Un corrective blendshape se define como el desplazamiento D = C - S, donde:
- S = posición de vértice en la malla deformada (skinned pose)
- C = posición de vértice en la malla corregida (sculpted correction)


**Problema**: D está en object space. Si el personaje rota, D también rota → el correctivo se aplica en la dirección incorrecta.


Ejemplo: corrective de "shoulder forward" → si el personaje se rota 90° Y en world space, el bulge del hombro aparecerá en la dirección equivocada.


### Espacio Tangente (Tangent Space Deltas)


La solución es expresar D en un sistema de referencia local por vértice. Para cada vértice i, se construye una base ortonormal (frame local) F_i:


**Frame construction per vertex:**
```
n_i = vertex normal (unit vector)
t_i = vertex tangent (from UV or geometry, unit vector, ⊥ n_i)
b_i = bitangent = n_i × t_i (unit vector)


F_i = [t_i | b_i | n_i]  (3×3 orthonormal matrix, column vectors)
```


**Delta in tangent space:**
```
D_local_i = F_i⁻¹ · (C_i - S_i)
           = F_iᵀ · D_object_i        (F_i is orthonormal, so F_i⁻¹ = F_iᵀ)
```


**Reconstruction at runtime:**
```
offset_i = F_i_current · D_local_i
```


where F_i_current is computed from the current deformed normals/tangents.


### Maya's Tangent Space BlendShape Mode


Maya's blendShape node has `origin` attribute:
- `origin=0` (Local): delta D_i = target_i - base_i in object space (default, buggy with rotation)
- `origin=1` (World): delta in world space (worse)
- Tangent Space (via `tangentSpace` attribute or `-ts` flag): computes F_i from the deformed mesh at runtime


**When Tangent Space is ACTIVE in Maya:**
1. At bind time: Maya stores D_local_i = F_rest⁻¹ · (C_i - S_i)
2. At runtime: reconstructs F_i_current from deformed vertex normals/tangents
3. Applies: offset_i = F_i_current · D_local_i


**Key invariant**: rotating the character in world space does NOT change D_local, only F_i_current rotates → offset remains geometrically correct.


### Pre-Skin vs Post-Skin Correctives — Frame Computation Differs


**Pre-skin corrective** (Front of Chain blendShape):
- Sculpted relative to rest/bind pose
- F_i computed from rest mesh normals/tangents
- Simpler, but only works for topology-level corrections


**Post-skin corrective** (blendShape after skinCluster):
- Sculpted relative to deformed skinned pose
- F_i computed from skinned deformed normals at target pose
- Correct for muscle/joint correctives
- The delta is smaller (less sculpting needed) because skin already approximates the correct shape


### Delta Extraction — Python Implementation in Maya


```python
import maya.cmds as cmds
import maya.api.OpenMaya as om


def extract_corrective_delta_in_tangent_space(
    base_mesh,    # rest or skinned mesh
    corrected_mesh,  # sculpted correction
    tangent_space=True
):
    """
    Extract per-vertex delta. If tangent_space=True, delta is in local frame.
    Returns list of (Δx, Δy, Δz) per vertex in local or object space.
    """
    sel = om.MSelectionList()
    sel.add(base_mesh)
    sel.add(corrected_mesh)
    base_dag = sel.getDagPath(0)
    corr_dag = sel.getDagPath(1)
    
    base_fn = om.MFnMesh(base_dag)
    corr_fn = om.MFnMesh(corr_dag)
    
    base_pts = base_fn.getPoints(om.MSpace.kObject)
    corr_pts = corr_fn.getPoints(om.MSpace.kObject)
    
    deltas = []
    
    if not tangent_space:
        for b, c in zip(base_pts, corr_pts):
            deltas.append(om.MVector(c) - om.MVector(b))
        return deltas
    
    # Build tangent space frames from base mesh normals
    normals = base_fn.getVertexNormals(False, om.MSpace.kObject)
    # For tangent: use edge-based tangent (UV tangent preferred)
    # Simplified: use arbitrary perpendicular vector
    for i, (b, c, n) in enumerate(zip(base_pts, corr_pts, normals)):
        n_vec = om.MVector(n).normal()
        # Build tangent (arbitrary, perpendicular to normal)
        up = om.MVector(0, 1, 0) if abs(n_vec.y) < 0.99 else om.MVector(1, 0, 0)
        t_vec = (n_vec ^ up).normal()   # cross product → tangent
        b_vec = (n_vec ^ t_vec).normal()  # bitangent
        
        # Frame matrix (rows = basis vectors for inverse transform)
        # F_i^T · delta = local delta
        d_world = om.MVector(c) - om.MVector(b)
        d_local = om.MVector(
            d_world * t_vec,
            d_world * b_vec,
            d_world * n_vec
        )
        deltas.append(d_local)
    
    return deltas
```


### Why This Matters for PSD/RBF Systems


In an RBF corrective system, the driven values are blendShape weights. If the blendShape target was extracted in object space, it will only look correct at the exact world-space orientation where it was sculpted. 


Tangent space extraction ensures:
- The same corrective works regardless of world orientation
- The RBF driver can use local joint angles as inputs (not world-space orientations)
- Deltas are smaller in post-skin mode → RBF interpolation is more stable


### Inverse Problem: Solving Weights from Geometry (2024 research)


A 2024 arxiv paper (Refined Inverse Rigging, 2401.16496) formalizes solving blendshape weights from a target geometry via NNLS:


    min_{w ≥ 0} ||B·w - v_target||²


where B is the blendshape basis matrix (cols = per-shape deltas), w is the weight vector, and v_target is the target geometry.


This is used in facial capture pipelines to fit blendshape weights to scanned geometry.


## Implementación en Maya


**Node-level in Maya (blendShape node):**
```python
# Create post-skin corrective with Tangent Space
bs = cmds.blendShape(corrected_mesh, skinned_mesh, 
                      name='corrective_BS',
                      origin='world',  # important for post-skin
                      tangentSpace=True,
                      after=True)[0]  # after=True → post-skin position


# Drive the weight with SDK from joint rotation
cmds.setDrivenKeyframe(f'{bs}.{corrected_mesh}', 
                        currentDriver=f'{joint}.rotateX')
```


**Practical deformation order check:**
```python
def get_deformer_order(mesh):
    """Return deformers in evaluation order (blendShapes, skinCluster, etc.)"""
    history = cmds.listHistory(mesh, pruneDagObjects=True, interestLevel=1)
    return [n for n in history if cmds.nodeType(n) in 
            ['blendShape', 'skinCluster', 'deltaMush', 'cluster']]
```


## Comparación con autorig_tools


El sistema de correctives RBF/SDK de autorig_tools muy probablemente usa blendShapes en object space (el default de Maya). El riesgo: los correctives de hombro y cadera que se ven bien en la pose de referencia pueden degradarse cuando el personaje rota en world space. La solución inmediata es pasar los targets a `tangentSpace=True` en el nodo blendShape. El código de extracción de deltas es también directamente integrable en el pipeline de sculpting de correctives para obtener un delta más pequeño y numéricamente estable.


## Aplicable directamente


**YES** — Verificar si los blendShapes de correctives existentes en autorig_tools usan `tangentSpace=True`. Si no, añadirlo al comando de creación. Para nuevos correctives: usar el flujo de extracción post-skin con tangent space. Tiempo estimado: 1-2 horas para auditar y actualizar el código de correctives de autorig_tools.


## Fuente
- https://help.autodesk.com/view/MAYAUL/2024/ENU/?guid=GUID-C954C197-6D56-4EB8-BEA0-70DD1BBBAD6B (Maya 2024 BlendShape options)
- https://arxiv.org/pdf/2401.16496 (Refined Inverse Rigging 2024 - NNLS blendshape solving)
- https://lesterbanks.com/2016/10/corrective-blend-shapes-extracting-deltas/ (practical delta extraction)
- https://www.tumblr.com/cgreminders/66537300400/maya-extracting-corrective-blendshapes