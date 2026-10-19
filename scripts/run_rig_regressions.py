"""Run the rig performance/deformation regression set in isolated Maya workers."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import subprocess
import time

TESTS = (
    'test_native_node_types.py',
    'test_quadruped_leg_push.py',
    'test_eyelid_persistence.py',
    'test_surface_reversals.py',
    'test_edward_skin_revision.py',
    'test_build_pipeline.py',
    'test_jaw_single_surface.py',
    'test_jaw_directional_defaults.py',
    'test_jaw_auto_wide.py', 'test_jaw_lips.py', 'test_lip_u_response.py',
    'test_jaw_auto_wide_edward.py',
    'test_rig_performance.py', 'test_bifrost_wrinkles.py', 'test_wrinkle_regions_native.py',
    'test_rig_compute_bypass.py', 'test_wrinkle_skin_roundtrip.py', 'test_wrinkle_presets.py',
    'test_wrinkle_regions_ui.py', 'test_rig_validation.py', 'test_facial_contact_validation.py',
    'test_hybrid_bake.py', 'test_rig_package.py', 'test_rig_package_ui.py',
    'test_ik_fk_settings_match.py', 'test_spine_chest_stretch.py', 'test_eye_head_deformation.py',
    'test_neck_stretch_squash.py', 'test_biped_spine_and_foot.py', 'test_general_rig_ui.py',
    'test_pose_blendshapes.py', 'test_orientation_correctives.py', 'test_regional_wrinkle_workflow.py',
    'test_rig_performance_policy.py', 'test_rig_benchmark_protocol.py')


def run(mayapy, output, tests=TESTS, workers=2):
    repo = Path(__file__).resolve().parents[1]
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('Choose a new regression output directory.')
    output.mkdir(parents=True)
    suite = {'success': False, 'tests': [], 'started': time.time()}

    def one(name):
        script = repo / 'maya_tools/scripts/tools/tests' / name
        log = output / (script.stem + '.log')
        start = time.perf_counter()
        environment = os.environ.copy()
        # Concurrent Maya startup writes preferences/toolclips even in batch.
        profile = output / 'maya_profiles' / script.stem
        profile.mkdir(parents=True)
        environment['MAYA_APP_DIR'] = str(profile)
        try:
            with log.open('wb') as stream:
                process = subprocess.run([str(mayapy), str(repo / 'scripts/run_maya_test.py'), str(script)],
                                         cwd=str(repo), env=environment, stdout=stream,
                                         stderr=subprocess.STDOUT, timeout=300)
            code = process.returncode
        except subprocess.TimeoutExpired:
            code = -1
        text = log.read_text(encoding='utf-8', errors='replace')
        return {'test': name, 'success': code == 0, 'exit_code': code,
                'seconds': time.perf_counter() - start, 'log': str(log),
                'last_lines': text.splitlines()[-12:]}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for future in as_completed([pool.submit(one, name) for name in tests]):
            result = future.result()
            suite['tests'].append(result)
            print(('PASS' if result['success'] else 'FAIL') + ' ' + result['test'], flush=True)
            (output / 'result.json').write_text(json.dumps(suite, indent=2), encoding='utf-8')
    suite['success'] = all(r['success'] for r in suite['tests'])
    suite['completed'] = time.time()
    (output / 'result.json').write_text(json.dumps(suite, indent=2), encoding='utf-8')
    return suite


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mayapy', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--tests', nargs='+', help='Optional subset of regression filenames')
    args = parser.parse_args()
    report = run(Path(args.mayapy), args.output, tests=args.tests or TESTS, workers=args.workers)
    raise SystemExit(0 if report['success'] else 1)
