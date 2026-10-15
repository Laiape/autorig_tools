"""Measure complete character builds in disposable Maya processes with private caches."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]


def available_assets():
    return sorted(p.name for p in (ROOT/'maya_tools/assets').iterdir()
                  if p.is_dir() and list((p/'build').glob('*.build'))
                  and list((p/'guides').glob('*.guides'))
                  and (list((p/'models').glob('*.ma')) or list((p/'models').glob('*.mb'))))


def worker(asset, output, validate=False):
    os.environ['MAYA_SKIP_USERSETUP_PY'] = '1'
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    os.environ['AUTORIG_BUILD_CACHE_DIR'] = str(output/'cache')
    os.environ['MAYA_APP_DIR'] = str(output/'maya_profile')
    (output/'maya_profile').mkdir(parents=True, exist_ok=True)
    sys.path[:0] = [str(ROOT), str(ROOT/'maya_tools/scripts')]
    result = dict(asset=asset, success=False, started=time.time())
    status = 1
    try:
        from PySide6 import QtWidgets
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        import maya.standalone
        maya.standalone.initialize(name='python')
        from maya import cmds
        from maya_tools.scripts.utils import create_rig
        from maya_tools.scripts.framework import context
        context.service().set_asset(asset)
        cmds.optionVar(stringValue=('currentAssetRigName', asset))
        started = time.perf_counter()
        build = create_rig.AutoRig().build(validate=validate)
        result['build_seconds'] = time.perf_counter()-started
        timing = json.loads(Path(build['timing_report']).read_text(encoding='utf-8'))
        (output/'buildtiming.json').write_text(json.dumps(timing, indent=2), encoding='utf-8')
        roots = [n for n in cmds.ls(type='transform', long=True) or []
                 if n.rsplit('|', 1)[-1].casefold() == asset.casefold()]
        result.update(maya=cmds.about(version=True), batch=cmds.about(batch=True),
                      root_exists=len(roots) == 1, root=roots[0] if len(roots) == 1 else None, nodes=len(cmds.ls()),
                      joints=len(cmds.ls(type='joint')), skins=len(cmds.ls(type='skinCluster')),
                      optional_health_audit=validate,
                      timing_report=str(output/'buildtiming.json'))
        if not result['root_exists'] or result['joints'] == 0:
            raise RuntimeError('The build did not produce a character skeleton.')
        result['success'] = timing['status'] == 'complete'
        status = 0 if result['success'] else 1
    except BaseException:
        result['error'] = traceback.format_exc()
        traceback.print_exc()
    finally:
        result['completed'] = time.time()
        (output/'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        sys.stdout.flush()
        sys.stderr.flush()
        # This process is exclusively owned by this benchmark. Avoid Bifrost's
        # problematic interpreter teardown after recording the actual result.
        if os.name == 'nt':
            kernel = ctypes.windll.kernel32
            kernel.GetCurrentProcess.restype = ctypes.c_void_p
            kernel.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            kernel.TerminateProcess(kernel.GetCurrentProcess(), status)
        os._exit(status)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mayapy', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--assets', nargs='+', help='Default: every asset with models, guides and build settings')
    parser.add_argument('--timeout', type=int, default=300)
    parser.add_argument('--validate', action='store_true', help='Also run the optional CPU history/role health audit')
    parser.add_argument('--worker', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        worker(args.worker, args.output.resolve(), args.validate)
        return
    assets = args.assets or available_assets()
    if not args.mayapy or not args.mayapy.is_file() or not assets:
        parser.error('Provide a valid --mayapy and at least one buildable asset.')
    unknown = set(assets)-set(available_assets())
    if unknown:
        parser.error('Assets need models, guides and build settings: ' + ', '.join(sorted(unknown)))
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    suite = dict(version=1, started=time.time(), success=False, results=[])
    for asset in assets:
        target = output/asset
        target.mkdir()
        try:
            with (target/'maya.log').open('wb') as stream:
                command = [str(args.mayapy), '-u', str(Path(__file__).resolve()),
                           '--worker', asset, '--output', str(target)]
                if args.validate:
                    command.append('--validate')
                process = subprocess.run(command, cwd=ROOT,
                                         stdout=stream, stderr=subprocess.STDOUT, timeout=args.timeout)
            code = process.returncode
        except subprocess.TimeoutExpired:
            code = -1
        path = target/'result.json'
        result = json.loads(path.read_text()) if path.exists() else dict(
            asset=asset, success=False, error='Worker timed out or exited without a receipt.')
        result.update(exit_code=code, success=code == 0 and result.get('success', False))
        suite['results'].append(result)
        (output/'result.json').write_text(json.dumps(suite, indent=2), encoding='utf-8')
        print(('PASS ' if result['success'] else 'FAIL ') + asset, flush=True)
    suite.update(success=all(r['success'] for r in suite['results']), completed=time.time())
    (output/'result.json').write_text(json.dumps(suite, indent=2), encoding='utf-8')
    raise SystemExit(0 if suite['success'] else 1)


if __name__ == '__main__':
    main()
