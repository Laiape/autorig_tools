# Chihuahua model opening

Parent: `maya_tools/how_it_works.md`.
Evidence: `docs/validation/chihuahua_open_20261016/`.

Character Manager model imports now use the same content-verified binary cache
as CREATE RIG. Previously that UI called the ASCII file opener directly.
Cache hits restore the authored source filename, ASCII save type and loaded
modified flag, so Save cannot overwrite the disposable cache. Source changes,
Maya API changes and damaged binaries retain the existing invalidation checks.
No evaluation profile, rig graph or authored groom display setting changes.

## Local acceptance

Owned interactive Maya 2026, API 20260303, DG, cache evaluator disabled,
Viewport 2.0 smooth shading. Three source and three cache samples were interleaved
after a source/plugin warmup. Mesh extraction was outside timed regions.

- Source open median 13.288 s, range 12.310-14.537 s.
- Verified cache open median 3.914 s, range 3.800-4.099 s, including content checks.
- Open plus explicit first redraw median 24.112 s source and 13.991 s cache.
- Initial source/plugin warmup open was 16.573 s, excluded from warm medians.

The initial redraw remains expensive: cache samples took 9.186-11.092 s for
that stage alone. This result accelerates file decoding; it does not promise
a four-second fully drawn character or faster rig playback. A hidden owned
interactive window was used, not the artist's viewport, so UI idle latency and
artist panel configuration are outside this comparison. Other Maya sessions
remained open. No cold filesystem or another-machine guarantee is implied.

The exact comparison passed for all 14 mesh shapes: world points, topology,
face-vertex normals, UV sets/assignments and material memberships. All 27
transform matrices, 16 XGen node identities and their connections, texture
path strings, frame and units matched. Source SHA-256 remained unchanged.
These checks preserve the source model; they are not a new full-rig pose audit
or an external texture/XGen dependency availability certification.

The delivered `assets/chihuahua/scenes/chihuahua_model_fast_v001.mb` is a
byte-identical copy of the natively reopened cache, SHA-256
`a7b0ad44a109b5d3091dc8b6162fb999b6a31b7ea40349c96d0abc724abc6fa0`.
It can be opened directly through Maya File > Open. The source
`assets/chihuahua/models/chihuahua_v001.ma` is retained. Directly opening that
original ASCII with Maya File > Open still decodes ASCII; the automatic cache
is used by Character Manager and CREATE RIG.

All 12 native build-pipeline regression cases passed, including the Manager
route, source filename/save type, cache damage rejection and changed-source
invalidation. The loaded Manager method and cache module in the accessible
artist session were updated without changing scene name, unsaved flag, frame
or selection. Other running Maya instances can use Reload UI to read the
updated Manager code; direct binary opening needs no module reload.

Experiment runners live in the outer workspace's
`scripts/chihuahua_open_trial.py` and `scripts/launch_chihuahua_open_trial.py`.
Full local signatures and startup logs remain in
`tmp/chihuahua_open_20261016_v001/`. No profiling runs during ordinary opening.
