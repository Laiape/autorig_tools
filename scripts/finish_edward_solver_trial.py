"""Summarize measured solver A/B evidence, keeping failed quality explicit."""
import hashlib
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'maya_tools/assets/Edward/experiments/custom_solvers_20261016_v001'
quality = json.loads((FOLDER / 'quality_summary.json').read_text())
missing_influences = json.loads((FOLDER / 'missing_skin_influences.json').read_text())
builds = {v: json.loads((FOLDER / (v + '_build.json')).read_text()) for v in ('maya', 'custom')}
cohorts = []
environments = []
for scenario in ('FK', 'IK'):
    for detail in (0, 1):
        row = {'scenario': scenario, 'wrinkles': bool(detail), 'variants': {}}
        for variant, blocks in (('maya', ('A1', 'A3')), ('custom', ('B1', 'B2'))):
            reports = [json.loads((FOLDER / ('timing_%s_%s_%s_detail%d_B.json' % (b, variant, scenario, detail))).read_text()) for b in blocks]
            medians = [r['median_ms'] for d in reports for r in d['runs']]
            row['variants'][variant] = {'median_of_six_pass_medians_ms': statistics.median(medians),
                'pass_medians_ms': medians, 'p95_per_pass_range_ms': [min(r['p95_ms'] for d in reports for r in d['runs']), max(r['p95_ms'] for d in reports for r in d['runs'])],
                'max_ms': max(d['timing']['max_ms'] for d in reports),
                'samples': sum(d['timing']['samples'] for d in reports),
                'block_medians_ms': [statistics.median(r['median_ms'] for r in d['runs']) for d in reports],
                'warmup_seconds': [d['warmup_wall_seconds'] for d in reports],
                'reports_with_raw_samples': sum('raw_passes_ms' in d for d in reports)}
            for d in reports:
                environments.append(d['environment'])
                assert d['state'] == 'B' and not d['profiler_during_timing']
                assert d['workload']['animated_channels']
                if detail:
                    assert d['verified_wrinkle_displacement_cm'] > 1e-4
        a = row['variants']['maya']['median_of_six_pass_medians_ms']
        b = row['variants']['custom']['median_of_six_pass_medians_ms']
        drift = abs(row['variants']['maya']['block_medians_ms'][0] - row['variants']['maya']['block_medians_ms'][1])
        noise = max(drift, .05 * a)
        row.update(delta_ms=a-b, reduced_frame_time_percent=(a-b)/a*100,
                   reference_drift_ms=drift, descriptive_noise_band_ms=noise,
                   timing_verdict='inconclusive' if abs(a-b) <= noise else ('custom_faster' if b < a else 'custom_slower'))
        cohorts.append(row)
viewport_signatures = {json.dumps(e['viewports']['modelPanel4'], sort_keys=True) for e in environments}
assert len(viewport_signatures) == 1, 'Viewport changed during benchmark'
summary = {'scope': 'Full Edward rebuild with Maya versus custom limb modules using frozen SKC v073; not a solver-only feature-equivalent replacement.',
    'quality_passed': quality['equivalent_at_1e_4_cm'], 'quality': {k: v for k, v in quality.items() if k not in ('worst_meshes', 'worst_joint_positions', 'worst_joint_rotations', 'per_case')},
    'cohorts': cohorts, 'missing_skin_influences': missing_influences,
    'evaluation': 'Parallel CPU, Cached Playback OFF, GPU deformation override OFF',
    'measurement': 'Interactive currentTime plus forced VP2 refresh wall time; excludes preparation, graph diagnostics and geometry comparison.',
    'order': 'A1 Maya, B1 custom, B2 custom, A3 Maya, three measured passes per block/cohort. A2 is excluded because its viewport changed to 1319x907; the comparable cohort is 879x686.',
    'frames': [1,48], 'discarded_frames_per_measured_pass': 8,
    'noise_policy': 'Descriptive maximum of reference-block drift and 5% of reference median; not a statistical confidence interval.',
    'viewport': environments[0]['viewports']['modelPanel4'], 'maya': environments[0]['maya'],
    'logical_cpus': environments[0]['logical_cpus'], 'gpu_device': environments[0]['gpu_device'],
    'builds': {v: {'seconds_one_build': d['build_seconds'], 'nodes': d['nodes'], 'joints': len(d['joints']),
        'skins': len(d['skin_nodes']), 'controls': len(d['controls']), 'ik_handles': len(d['ik_handles']),
        'cycles': d['cycles'], 'scene': d['scene'], 'scene_sha256': d['scene_sha256']} for v,d in builds.items()},
    'limitations': ['No existing animation keys in artist scene; synthetic bilateral test clips.',
        'Custom modules omit AutoClavicle and muscle correctives. Timing gains cannot be assigned to equivalent solver math.',
        'Current SKC is reused without rebinding or animation migration; results describe the direct rebuild option.',
        'GPU, Cached Playback and production-shot animation migration are not approved by this CPU test.',
        'One build per variant; build duration is descriptive, not a build-speed benchmark.',
        'Initial reports retain per-pass statistics; later reports also retain raw full-pass samples.',
        'All four A2 reports are preserved but excluded because the viewport changed size. A3 repeats the reference with a fixed-size window.']}
(FOLDER / 'summary.json').write_text(json.dumps(summary, indent=2))
lines = ['# Edward custom limb solver comparison', '',
    'Parent: `maya_tools/how_it_works.md`. Date: 2026-10-16.', '',
    '## Decision', '',
    'The direct custom-module rebuild is not deformation-equivalent to the current',
    'Edward delivery. Keep the current Maya solver modules for this release.',
    'Performance below describes the current implementations, including missing',
    'custom-module features; it is not an accepted equivalent optimization.', '',
    '## Frozen inputs and procedure', '',
    'Both complete rigs use the same frozen current checkout, model v003, guides',
    'v013, curves v002, build v001, lossless skin v073 and wrinkles v004. Only',
    '`solver_mode` changed in the disposable working recipe. Product settings',
    'and the artist scene were preserved. The artist had no keyed controls.', '',
    'Both builds contain 318 controls and 81 skins with no reported cycles.',
    'Maya/custom node counts are 11785/12016; joints 852/824; ikHandles 10/2.',
    'Custom retains the two spine handles and adds two toe skin joints.', '',
    '## Animation and deformation', '',
    'Thirty bilateral cases, forward/reverse, compare 59 matching polygon outputs',
    '(3540 mesh comparisons), topology, positions, face-vertex normals and common',
    'limb skin-joint matrices. All requested channels resolved in both variants.',
    'The fixed same-topology limit is 1e-4 cm. The candidate fails it.', '',
    '- Maximum mesh difference: 40.4480 cm on boot polySurface891 in FK neutral.',
    '- IK neutral: 11.3290 cm maximum on brazaletes1; body maximum 1.4414 cm.',
    '- Left FK bend: wrist position differs by 9.7090 cm and orientation by 10 deg.',
    '- Left IK bend: body maximum differs by 3.1273 cm.',
    '- Forward/reverse maximum within each variant: Maya 2.8801e-5 cm, custom zero.', '',
    'Custom modules omit 24 existing keyable attributes: bilateral AutoClavicle,',
    'StartAngle and Factor; six biceps/triceps controls per arm; and three front',
    'thigh controls per leg. AutoClavicle and muscle pushes are enabled in the',
    'reference. Custom adds Soft_Start and pvOrientation controls. Equal control',
    'names therefore do not preserve the old animation/volume contract.', '',
    'Four corrective influences used by the delivery SKC do not exist in the',
    'custom build: bilateral bicepsCorrective_ENV and tricepsCorrective_ENV.',
    'They carry nonzero weights in the body and brazaletes1 skin records.',
    'This directly prevents lossless reuse of those two skins. See',
    '`missing_skin_influences.json` for the stored nonzero vertex counts.', '',
    'The test reuses the delivery SKC. Bind-frame and foot orientation differences',
    'are part of the direct-switch result; this is not a fresh custom skin bind.', '',
    '## Interactive performance', '',
    'Parallel CPU, cache/GPU deformation OFF. Same camera and viewport. Four ABBA',
    'blocks, three measured 48-frame passes per cohort/block; first eight frames',
    'discarded from every measured pass. Values below are medians of six pass',
    'medians per variant. Each cohort includes limb and common facial motion.',
    'The 879x686 viewport cohort uses A1/B1/B2/A3. All four original A2 reports',
    'are excluded and preserved: the viewport had changed to 1319x907. The A3',
    'reference repeats all four cases with the window size locked.',
    'Wrinkles ON has verified nonzero displacement (about 0.1752 cm).', '']
for row in cohorts:
    a = row['variants']['maya']['median_of_six_pass_medians_ms']; b = row['variants']['custom']['median_of_six_pass_medians_ms']
    lines.append('- %s, wrinkles %s: Maya %.3f ms/frame; custom %.3f ms/frame; frame-time reduction %.2f%%. Verdict: %s. Reference drift %.3f ms.' %
                 (row['scenario'], 'ON' if row['wrinkles'] else 'OFF', a, b, row['reduced_frame_time_percent'], row['timing_verdict'], row['reference_drift_ms']))
lines += ['', 'These are viewport wall times, not isolated GPU times or a guaranteed',
    'production playback rate. No solver-only FPS gain is established. Initial',
    'reports store per-pass statistics; later reports include raw full passes.', '',
    'One build per variant took 37.904/35.597 seconds. This single pair does not',
    'establish a reproducible build-time improvement. No native data reduction',
    'or node-count result substitutes for performance or quality acceptance.', '',
    '## Possible future implementation', '',
    'A compatible optimization would replace only the IK calculation inside the',
    'existing module contract, retaining AutoClavicle, muscle correctives, bendy',
    'frames, bind matrices, foot outputs and animation channels. Match both sides',
    'through FK/IK blends, soft/reach/pin/roll, spaces and scale, then repeat',
    'geometry, persistence and timing checks before proposing a delivery switch.', '',
    '## Evidence', '',
    'Raw files and both native scenes are in the outer experiment workspace:',
    '`maya_tools/assets/Edward/experiments/custom_solvers_20261016_v001/`.',
    'See `summary.json`, `quality_summary.json`, `quality_rows.json`,',
    '`joint_rows.json`, `*_build.json`, `timing_*.json` and the frozen manifest.',
    'Opt-in scripts are `scripts/edward_solver_trial_*.py`,',
    '`scripts/edward_solver_compare.py`, `scripts/run_edward_solver_timings.py`',
    'and `scripts/finish_edward_solver_trial.py` in the outer workspace.', '']
doc = ROOT / 'autorig_tools/maya_tools/docs/rig_custom_solver_comparison_20261016.md'
text = '\n'.join(lines); text.encode('ascii'); doc.write_text(text)
print(json.dumps({'cohorts': cohorts, 'doc': str(doc), 'quality_passed': summary['quality_passed']}, indent=2))
