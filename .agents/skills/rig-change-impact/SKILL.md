---
name: rig-change-impact
description: Assess performance and deformation impact before a large Maya rig architecture, driver, skin-layer, solver or detail-system change in Autorig Tools. Use for comparing designs and planning a bounded prototype; do not treat node counts as predicted FPS.
---

# Rig change impact

Read `maya_tools/docs/rig_performance_criteria.md` and the current
`maya_tools/docs/rig_optimization_roadmap_20261015.md` in this checkout.
Resolve the loaded Maya module path before editing; a sibling clone may differ.

State the proposed behavior and the metric being improved: build, posing,
uncached playback, hot replay, file/load size, RAM/VRAM or final export. Record
which behavior must remain exact and which approximation is intentional.

Map the changed graph and all downstream consumers, including bind/rest data,
garments, pins, Bifrost, live targets, LOD and export. Distinguish static rest
precomputation from per-frame work, shared work, transfer/readback boundaries,
serial dependencies and parallel scheduling. Identify rollback and authoring data
that must survive. A hidden mesh or a new driver mesh is not automatically cheap.

Use existing comparable measurements to identify the likely limiting path.
If the necessary evidence is missing, give a qualitative hypothesis and the
smallest experiment that would resolve it. Do not invent a millisecond saving.
An Amdahl bound needs a measured fraction of wall-critical work and explicit
assumptions; inclusive CPU sums or deformation-removing bypass deltas are not
that fraction. Report build cost separately from runtime cost.

Choose a small candidate with the same animation and quality contract, one
architectural change at a time. Define baseline/reference repetitions, affected
and held-out poses, tolerances, persistence checks and acceptance before coding.
Use `rig-performance-audit` for timings and `rig-deformation-equivalence` for
the output gate. Keep benchmarks explicit and out of normal CREATE RIG.

Deliver a decision record: hypothesis, consumer/ownership map, measured evidence,
expected impact with uncertainty, bounded prototype, quality gates and rollback.
Label measured, estimated, proposed and rejected conclusions distinctly. A
major refactor is not justified by a smaller node count or a tiny file export.
