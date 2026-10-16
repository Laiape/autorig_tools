# Edward exact optimization and complete clothing audit

Parent: `maya_tools/how_it_works.md`.
Policy: `maya_tools/docs/rig_performance_criteria.md`.
Subsequent normal CREATE RIG integration and full-build A/B evidence:
`maya_tools/docs/rig_exact_build_integration_20261015.md`. It filters initial
bindings rather than applying this study's live influence-removal operation.
Roadmap: `maya_tools/docs/rig_optimization_roadmap_20261015.md`.
Measured on 2026-10-15, Maya 2026, i9-14900HX / RTX 5060 Laptop.

## Delivered result

`maya_tools/assets/Edward/scenes/Edward_working_v004.mb` is a new local,
validated native scene. It retains authored wrinkles ON, all controls, 852
joints, 58 skins, 23 PRX, nine blendShape nodes and every facial layer.
It does not replace the artist's open, modified scene. The source models and
previous working versions were not overwritten. Its adjacent
`Edward_working_v004.optimization.json` records the exact source and hash.

The conservative scene profile remains Parallel CPU with cache/GPU override
OFF. The existing shared builder/open hook applies that profile to marked
characters without running this audit or cleanup during normal CREATE RIG.

New exact-cleanup playback cohort, native files reopened, wrinkles OFF:
original median 35.273 ms/f and p95 40.608 ms/f; full cleanup median 31.052 ms/f
and p95 35.287 ms/f. Relative to the median of interleaved reference blocks,
the measured time reduction is 11.88%, outside the descriptive noise band.
These are currentTime plus forced VP2 refresh wall times, including submission.
They are not isolated GPU times or guaranteed shot playback FPS.

Wrinkles ON: original pooled median 112.536 ms/f, full cleanup 110.494 ms/f.
Reference block medians ranged from 98.29 to 122.53 ms/f. The difference is
inside that drift; no stable ON speed improvement is established. Wrinkles
remain ON in the delivered file. OFF results do not justify turning them off.

Whole native original: 171,413,264 bytes; full cleanup: 169,665,824 bytes.
Savings: 1,747,440 bytes, 1.67 MiB, 1.02%. Node count: 16,546 to 11,078.
Neither node count nor isolated export bytes are a prediction of FPS or RAM.

## Step 1: frozen reference and complete consumer inventory

The current unsaved artist rig was exported to an immutable native snapshot
without changing file name, modified flag, frame, selection or evaluators.
SHA256: `2cab775509387ecb2f82e47382eb60168dd980f470797edd243380131c79108b`.
Experiments ran in separately owned Maya processes with isolated preferences.
The live artist Maya was queried read-only again at completion and still held
the same modified source scene, frame, selection and CPU evaluator flags.

Scope: 60 nonintermediate outputs, including all 47 clothing/accessory meshes:
22 in the body/clothing group, nine in boots, and 16 in scissors/gloves.
Head, eyes, hair, hidden low/scalps, mouth and corrective donor are included.
The consumer map separates the direct primary deformation chain from driver
branches. A head skin appearing in a collar's upstream history is shared
driver work, not another direct collar skin.

## Step 2: bounded candidates and rejected changes

- Five GPU policies were explicitly queried and tested. None removed the
  collar discrepancy, approximately 0.1363 scene units. One larger upstream
  CPU/GPU isolation crashed the owned trial. GPU is not the default.
- The existing broad jaw optimizer removed 71 nodes. Position differences were
  small, but maximum normal error exceeded the predeclared 1e-4 threshold.
  That candidate was rejected; its arithmetic replacement is not in v004.
- Shared body/facial/wrinkle driver prototypes from the preceding audit did not
  establish a stable speed advantage. Moving belt-only padding to the visible
  body changed the original shape by up to 1.827831 units. That route remains
  rejected: v004 preserves the original body and belt consumer connections.
- Hot cache completed fast rows, approximately 17.6 ms/f OFF and 19.5 ms/f ON,
  and passed the expanded pose comparison in its tested scope. A later ON
  warmup remained unresponsive for more than nine minutes. That failure is
  retained; cache is not automatically enabled or certified for production.
  New depth/mask invalidation coverage was not claimed after that failure.

## Step 3: accepted cleanup, one component at a time

The explicit `tools/rig_exact_cleanup.py` helper supports undo and rejects
unsupported/driven/referenced cases. It is a candidate tool, not a per-frame
callback or an automatic build postprocessor.

- Share 17 identical native lip calculations. Same node type, input sources,
  values and relevant native flags are required. Coupled blendMatrix target
  weights and drivers survive reconnection. No compose/aim replacement or
  zero-weight arithmetic shortcut is used.
- Replace 5,451 un-driven, one-key scalp point curves by exactly the same
  native point values. Multiple keys, incoming connections, other consumers,
  referenced/locked data and unrelated meshes are excluded. XGen remains.
- Remove 474 exactly zero influence columns from nine explicitly frozen skin
  nodes. Retain every nonzero weight, native DQ mask, normalization method,
  bind rest and actual per-point maximum. Body bindings reduce 388 to 40;
  the 852 joints themselves remain. Tiny positive weights are never pruned.

The zero-only candidate measured 31.427 ms/f OFF, a stable 10.81% time reduction.
The math/static-only candidate measured 35.126 ms/f OFF, inside reference noise.
Most of the demonstrated runtime gain belongs to the zero-dependency cleanup;
the other changes reduce stored graph data without a separate proven FPS gain.

Immediately after native influence edits, some trials slowed to approximately
390-464 ms/f. After native save/reopen they returned to approximately 31 ms/f.
This is why no live cleanup was applied to the artist and no automatic cleanup
was added to CREATE RIG. The delivered, reopened scene is the tested unit.

## Step 4: quality, persistence and reproducibility

All 18 modules are driven through 46 resolved channels in 17 unique semantic
poses plus reverse traversal, with wrinkles OFF and ON separately. Held-out
coverage includes clothing twists/limbs, lip detail/sticky lips, eyelids/brows,
hands and published globalScale. Direct nonuniform character scale channels
were locked/driven and are explicitly omitted, not recorded as a pass.

Each candidate compares 4,080 mesh samples, evaluated world vertex normals
and all 852 joint world matrices. The conservative components and combination
matched the original with maximum error zero. The saved v004 source and the
native-reopened SKC weight-roundtrip file repeated maximum error zero for both
detail modes. The reference contains actual nonzero wrinkle displacement.

Separate persistent-data checks preserve all 60 topologies, UV coordinates and
assignments, materials, hard edges, normal IDs, all 58 skin positive weights,
DQ masks, retained bind matrices/matrix sources, methods, PRX/corrective data,
wrinkle presets and control/joint names. Additional face-vertex normal error
at the original frame is 2.15424e-7, below the original 1e-4 normal threshold.
Float bytes are not treated as a visual failure when numeric error is inside
the predeclared contract. The broad jaw candidate failed that same contract.

Two frozen-input cleanup reconstructions reproduce the accepted data and
results, including exactly 17/5451/474 changes. This does not certify two full
CREATE RIG builds, a different character or the preexisting broad jaw builder.

## Step 5: lossless skin data and import order

`SkinManager.export_skins` now defaults to exact nonzero native weights and DQ
values, without the previous 1e-5 cutoff or five-decimal rounding. Explicit
`lossless=False` retains legacy compact encoding when intentionally requested.
The per-skin `weight_encoding` field identifies the selected representation.

In-place Bifrost could make the native DAG skin API stop at the plugin shape.
The existing owned export scope now temporarily disconnects that input after
exposing the native primary output, then restores every original connection,
including after an exception or nested use. Original deformer routes and
wrinkle presets are captured before entering that temporary scope.

Weight replacement also used to reorder skins whose order already matched.
This could move an interleaved corrective. Matching native skin stacks now
remain in place; a native two-skin/interleaved-blendShape fixture verifies
connections and evaluated geometry, not only the exported text.

Edward's exact experimental SKC is 28,098,019 bytes, 48 polygon skins in 34
mesh entries. The ten curve/surface skins stay in the native scene. All exported
positive weights/DQ values were replaced by index in an owned native copy,
with the original deformer/wrinkle graph retained, saved and reopened. Static
data and complete pose quality both pass. This is not a certification of a
complete deformer/preset rebuild from SKC. The experimental SKC was not made
the automatic latest asset source.

Verification includes seven exact-cleanup native tests, 20 existing skin-manager
integration tests, sparse logical influence reconstruction, new lossless/tiny
weight and DQ checks, in-place Bifrost scope/failure restoration, interleaved
corrective replacement and the existing native wrinkle SKC/preset roundtrip.

## Step 6: every garment, every skin and attributed CPU

Four separate 48-frame Profiler captures use native-reopened original and
optimized files, wrinkles OFF/ON. All four 256 MiB buffers retained sampling
through the end. No Profiler, vertex extraction, export or heavy background
work ran inside the clean timing cohort. Per-module ownership includes SDK
curves, excludes deleted nodes and keeps shared/global work separate.

The updated interactive report contains all 47 clothing/accessory rows, all
23 PRX sources/bind sources, 58 skin rows, nine blendShape rows and 18 module
rows. CPU columns are inclusive EvaluateNode milliseconds divided by 48.
They overlap, and shared driver work repeats across consumers; neither those
columns nor diagnostic bypass deltas are intrinsic wall cost or additive
savings. Zero captured events mean no attributed event in that capture, not
a universal zero runtime cost.

All 60 evaluated mesh copies have measured isolated native MB geometry bytes,
without rig/history/material networks. The subsequent selected-skin export
crashed the owned process; all completed geometry files survived. It was not
retried in the artist. Current weight bytes use exact sparse SKC JSON entries,
which have a different format/scope from native MB. Unchanged PRX/corrective
payloads reuse the prior native audit. Original per-module/skin native bytes
are explicitly historical. Missing native captures are not invented. Serialized
sizes include headers, overlap between scopes and are not process RAM.

## Next work and rollback

Keep v004 as the exact saved candidate and the original artist snapshot as
rollback. Retain full wrinkles and facial/low layers. The largest remaining
optimization study is the Bifrost conversion/detail path, followed by measured
jaw/eyelid/eyebrow subgraphs and expensive garment PRX branches. Each future
replacement must independently pass the same geometry/contact/data gate.
No approximate low-head collar, layer merge, weight pruning, GPU/cache default
or new intermediate driver has been adopted from diagnostic timing alone.

Evidence root in the outer workspace:
`maya_tools/assets/Edward/experiments/exact_optimization_20261015_v001/`.
Key files: `exact_report_data.json`, `consumer_map.json`, raw reopened timing
rows, four `profile_*.summary.json`, `native_reopen_safe_full.quality.json`,
`persistence_data_result.json`, `skc_roundtrip.json`,
`skc_native_roundtrip.quality.json`, `reproducibility.json`, `payloads.json`,
`artist_final_readonly.json`, failure records and `delivery.json`.

The Spanish interactive report is
`C:/Users/LaiaPeris/.cursor/projects/c-proyectos/canvases/edward-driver-routing.canvas.tsx`.
The earlier 19-page PDF remains the baseline audit; its old cohort times must
not be combined with the newer fixed-viewport timing cohort.
