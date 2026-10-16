"""Freeze current asset inputs, then validate two builds in isolated Maya."""
import argparse
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from maya_tools.scripts.tools import rig_package

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--asset', required=True)
    parser.add_argument('--version', required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--mayapy', type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    package = repo / 'maya_tools/assets' / args.asset / 'packages' / args.version
    report = args.report.resolve()
    policy = {'shot_fps': 24, 'state': 'C', 'detail': 0, 'report': 'validation/' + report.name}
    manifest = rig_package.create(repo, args.asset, package, reports=[report], performance_policy=policy)
    print('Frozen package: ' + str(package), flush=True)
    log = repo / 'maya_tools/assets' / args.asset / 'validation' / (args.version + '.log')
    with log.open('wb') as stream:
        process = subprocess.run([str(args.mayapy), str(repo / 'maya_tools/scripts/tools/rig_package_validate.py'),
                                  str(package), str(package / 'publish_checks')],
                                 cwd=str(repo), stdout=stream, stderr=subprocess.STDOUT)
    print('Validation exit %d; log: %s' % (process.returncode, log), flush=True)
    raise SystemExit(process.returncode)
