---
name: rig-performance-audit
description: Measure and explain Maya rig build, control-interaction, playback, cache and serialized-data costs with comparable baselines and separate quality checks. Use for Autorig performance audits and regression evidence, not static node-count guesses.
---

# Rig performance audit

Read `maya_tools/docs/rig_performance_criteria.md`. Reuse existing Test Rig,
`tools/rig_benchmark.py`, `tools/rig_performance.py` and package evidence rather
than introducing a separate product flow. Edward-specific experiment scripts
are examples, not portable character discovery or universal costs.

Preserve the current artist scene and unsaved edits before a trial. Identify
the loaded checkout and freeze scene/input/code hashes. Use an owned disposable
Maya process for unsafe native exports or disruptive experiments. Set a bounded
timeout for preparation; a hung trial produces failure evidence, not a timing.

Resolve semantic controls once during preparation. Exercise both sides and all
affected modules with real time curves and correct IK/FK states. Verify actual
motion and visible output through every ancestor. Fix viewport, camera, shading,
frame/FPS, Smooth Mesh Preview, plugins and hardware within a comparison cohort.

Capture clean wall times separately from Profiler and vertex extraction. Compare
DG, Parallel CPU, Parallel GPU and hot cached replay; measure cold fill/wait and
control edits separately. Warm up, discard initial frames, use at least three
passes and interleaved references. Report median/p95/max, pass medians, samples,
dispersion and drift. A difference inside noise is inconclusive. Forced refresh
includes submission overhead and does not isolate GPU execution.
Measure post-edit and native-reopened states separately for binding cleanup.
Removing exact-zero columns can preserve all geometry yet leave Maya much
slower until reopen. A cached warmup that hangs is failure evidence even if
earlier hot samples were fast; do not silently discard the failed repetition.

Use `rig-deformation-equivalence` to check geometry, cache jumps/edits and
persistence outside timing. CPU/DG accepted output is the authority when GPU
differs; comparing cache only to uncached GPU can reject the correct result or
approve the wrong one. Scope cache acceptance to the tested scene and edits.

For diagnostic bypasses, record the omitted deformation and downstream effects.
Group deltas are marginal/nonadditive. Never call them intrinsic subsystem cost
or an accepted optimization. Do not mass-freeze modules as a routine estimator.

Attribute inclusive Profiler CPU to deepest module ownership, including SDKs,
with separate shared/global/deformer buckets. Do not turn inclusive CPU into
wall time/FPS. For disk data use native scoped exports and complete-scene saves;
state overlap/header scope and missing external files. Never call serialized
payload RAM. High skins behind Bifrost need the owned primary-output export
scope; use the existing safe export helper and restore every original route.

Save raw samples, environment, failures, quality scope, reference drift and
decision (accept/reject/inconclusive). Restore keys, connections, frame,
selection, modified state, evaluators and caches after trials. No FPS claim
from batch Maya alone. Present a readable report with measured findings,
limitations and prioritized next experiments, not only a profiler dump.
