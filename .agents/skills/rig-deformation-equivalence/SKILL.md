---
name: rig-deformation-equivalence
description: Validate that a Maya rig driver, skinning, corrective, LOD or wrinkle replacement preserves intended deformation, contacts and persisted data. Use before accepting structural performance changes or cache/GPU output, including intentionally approximate delivery variants.
---

# Rig deformation equivalence

Read `maya_tools/docs/rig_performance_criteria.md`. Capture a versioned original
before changing routes. Establish the accepted reference, output meshes,
topology/coordinate spaces and explicit artistic intent. Prototype agreement
with another prototype does not prove equivalence to the original rig.

Inventory source/bind geometry, every PRX input, skin order, DQ methods/masks,
bindPreMatrix, actual nonzero weights, corrective aliases/indices/targets/rest
data and downstream garments/export. A skin maxInfluences setting does not
describe actual existing weights. Preserve native Orig shapes and ownership.

Choose matching semantic poses for all affected modules and sides, combined
and held-out expressions, forward/reverse transitions, IK/FK, space switches,
global/nonuniform scale, eyelid/lip contacts and clothing. Verify nonzero motion
and actual detail displacement. Compare final outputs outside timed benchmarks.
Default equivalent same-topology max error is <=1e-4 scene units; record both
maximum and affected outputs. Do not silently loosen tolerance after failure.
Include evaluated vertex and face-vertex normals, hard edges, UV coordinates
and assignments, materials and joint world matrices when appearance must stay.
Hash topology and discrete data; compare floating normals numerically against
the declared tolerance rather than treating different float bytes as a new shape.

Test accepted CPU/DG output against GPU and cached states separately. Exercise
random frame access, key edits and relevant depth/mask/rest/mode invalidation;
verify re-enabled detail is current. Report exactly which edits were tested.
Stateful simulations need ordered evaluation/cache tests rather than an
unqualified random-access expectation.

For approximate LOD/bakes define surface/landmark/contact/silhouette tolerances
before fitting, keep fit and held-out samples separate, and preserve the editable
source. A generic low head may not preserve collars. Sequential skin layers and
different driver topologies cannot be blindly merged or reconnected.

Require native save/reopen, relevant SKC/preset round-trips and two reproducible
builds for a structural replacement. Restore original connections and artist
state on failure. Keep intentional artistic differences separate from numeric
equivalence; for example, routing belt-only body padding to the final body is
an artistic change even when all new driver variants match exactly.

Preserve tiny positive skin weights and native DQ masks in data round-trips.
Use lossless SKC export; rounded/thresholded compact data needs its own quality
contract. In-place Bifrost can make the native skin DAG API stop at a plugin
shape: use the owned primary-output export scope and verify that all expected
skin layers are present and every original graph connection is restored.

Deliver source/candidate identities, consumer map, pose/edit coverage, max errors,
contact/appearance findings, persistence evidence and a scoped verdict. Reject
a faster candidate that violates its quality contract; retain failed trials
to prevent repeating unsupported optimizations.
