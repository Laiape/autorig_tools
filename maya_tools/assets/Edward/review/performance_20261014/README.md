# Edward performance evidence

Results and interpretation: `maya_tools/docs/rig_performance_results.md`.

`approved_animation.performance.json` is the accepted C/Animation report used
by the frozen package gate. Complete comparison reports are stored as gzip
JSON; decompress with `python -m gzip -d <report>.performance.json.gz` on a copy.
`timing_index.json` records the uncompressed SHA-256 and summary metrics.

`regressions.json` merges final test runs after repairs. `rebuild_validation.json`
records two clean builds and native reopen. `regional_compact_comparison.json`
compares the exact regional and dense outputs. `cache_quality.json` and
`collar_proxy_comparison.json` are rejected trials, not approvals. The Profiler
summaries contain inclusive overlapping event durations, separate from timing.

Raw captures and regenerable packages are excluded from Git. Source scene and
asset versions are preserved under the character's ordinary asset folders.
