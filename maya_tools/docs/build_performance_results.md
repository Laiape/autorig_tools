# Character build startup and crash correction

Parent: `maya_tools/how_it_works.md`.
Evidence: `maya_tools/docs/validation/builds_20261015/`.

## Normal build behavior

The ordinary build no longer runs the history/role health audit. That audit is
diagnostic, not required to construct the character. Request it explicitly with
`AutoRig().build(validate=True)`, or use the existing Test Rig workflows for pose
and deformation review. Saved authored role bindings still restore during builds.
No automatic or CPU health audit queries native GPU partitions.

The old post-build audit called `deformerEvaluator(nodeStatus/message)` on each
mesh while the newly constructed graph was dirty. Three local crash dumps from
08:03, 08:09 and 08:12 had the same access violation in DependEngine.dll. Edward
and Nini stopped at that final audit in the user's screenshots. Removing the
native query allowed both interactive builds and three repeated audits per
character to complete. Native symbols were not available for a deeper DLL diagnosis.

Construction keeps DG evaluation, viewport suspension and disabled undo through
skin, corrective and wrinkle import. Previously the fast session ended before
those stages, and a nested geometry helper could resume refresh prematurely.
Maya state and Script Editor suppression are restored on success and failure.
Progress excludes user input during updates, rejects recursive builds and does
not show BUILD COMPLETE when an import raises an exception.

## Model loading

Only the selected model opens; the redundant empty-scene reset was removed.
ASCII sources can use a local Maya binary copy. The source file remains intact.
SHA-256 content checks and the Maya API version invalidate a stale copy; the
binary hash rejects corruption before opening it. A source that cannot be safely
exported to binary keeps loading through its original file.

The local cache lives under `maya_tools/cache/models` and is ignored by Git.
Preparing the first copy is a one-time cost, repeated after a source change or
on another computer. First renderer/plugin initialization is also separate from
steady-state model loading; a cold startup is not promised to finish within 5 s.

Two interactive Edward model-only comparisons measured:

- ASCII: 6.139 s and 4.846 s.
- Equivalent binary: 1.205 s and 1.090 s.
- Initial binary export: 3.432 s and 3.234 s.
- All 59 mesh point/topology hashes and material memberships matched exactly.

The final full-build test measured model loading plus integrity checks at 2.65 s
for Edward and 0.74 s for Nini after cache preparation. Edward's first preparation
inside that test took 10.16 s including reading and writing the new copy.

## Full build measurements

Interactive Maya 2026 on the local RTX 5060 laptop completed two normal builds
per character without the final audit. The second runs measured:

- Edward: 31.54 s total; model load/checks 2.65 s.
- Nini: 11.50 s total; model load/checks 0.74 s.

The earlier interactive Edward build with the audit measured 45.11 s, including
8.04 s in role/history auditing and 5.97 s opening the ASCII model. The first
isolated baseline measured 105.92 s with cold model/plugin work. These are observed
wall times, not a controlled multiplier: plugin startup, filesystem warming,
viewport initialization and other test processes affect the comparison.

Each phase and the final viewport restoration have separate timing records.
Skin and wrinkle import share one parsed SKC snapshot. A changed path, size or
mtime invalidates that reuse. Bifrost plugin loading and graph compilation are
recorded separately from building and populating its ports and arrays.

## Cross-character coverage and remaining asset work

The build sweep uses every asset with model, guide and build inputs: Edward,
Nini, anne, chihuahua, freya, giraffe, horse, jamal, maui, mechanic, moana and thaiz.
The checked-in summary contains each final result, root, phase durations and log.
Each worker uses a private build cache; testing cannot overwrite the artist's
current cache. Run `scripts/benchmark_rig_builds.py --mayapy <mayapy.exe> --output
<new-directory>` to repeat it. Use `--assets` for a subset and `--validate` to
include the optional audit.

The sweep exposed a clean-session quadruped dependency: matrixNodes must load
before inverseMatrix nodes are created. Math dependencies now load explicitly.
Giraffe also has unequal upper/lower lip guide counts and a nested, capitalized
model root. Sticky lip meeting frames now sample matching normalized stations
without indexing past the shorter lip. Equal-count layouts keep their original
shared meeting graph. Ancestor model groups are excluded from geometry parenting.

Giraffe's legacy inputs still report missing foot helper guides and contain no
skin snapshot. A completed skeleton build does not supply those missing authored
inputs. Review the guide data, export approved skin weights and visually approve
its sticky lip behavior before using that character for production animation.
Smoke-build completion is not full deformation approval of all legacy assets.
Other isolated recipes also log missing socket/brow/foot guide requests, XGen
preview commands or legacy third-party plugins (including mgear_solvers for
Freya). Some guide requests have existing module fallbacks. The per-character
logs retain those messages; this performance pass does not invent replacement
guides, weights or plugin installations. Re-export required guides and restore
the approved plugin environment before a production-quality review.

## Geometry and regressions

Edward's final interactive build matches the pre-fix baseline exactly across
ten body/face combination poses on high head, low head and body: maximum error
0, identical topology, no missing controls. The model-only cache comparison also
matches all 59 meshes and material memberships.

Ten native pipeline regression cases cover audit safety, ordinary builds skipping
the audit, full construction-state ownership, failure cleanup, reentry rejection,
math dependencies, SKC reuse/invalidation, model cache integrity/source changes,
unequal sticky lip sampling and nested model roots. Seven existing suites cover
QA, wrinkles/SKC, detail modes, spine/neck behavior, packages and regional wrinkles.
Reports, timing receipts and logs are stored with this document's evidence.
