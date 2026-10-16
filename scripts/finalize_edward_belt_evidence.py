"""Write compact, hashed evidence for the opt-in belt comparison experiments."""
import ast
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'maya_tools/assets/Edward/experiments/belt_blendshape_20261016_v001'
OUT=ROOT/'autorig_tools/maya_tools/docs/validation/belt_blendshape_20261016'
OUT.mkdir(parents=True,exist_ok=True)


def read(name):return json.loads((FOLDER/name).read_text())


def identity(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(4*1024*1024),b''):digest.update(chunk)
    return {'path':str(path),'bytes':path.stat().st_size,'sha256':digest.hexdigest()}


manifest=read('manifest.json')
scripts=sorted((ROOT/'scripts').glob('edward_belt_*.py'))+[ROOT/'scripts/launch_edward_belt_review.py',Path(__file__).resolve()]
for script in scripts:
    source=script.read_text(encoding='utf-8');source.encode('ascii');ast.parse(source,filename=str(script))
report=ROOT/'autorig_tools/maya_tools/docs/rig_belt_blendshape_trial_20261016.md'
report.read_text(encoding='utf-8').encode('ascii')
summary={'date':'2026-10-16','decision':'Reject all candidates for exact production replacement; artist review copies opened as requested.',
         'artist_source_preserved':read('snapshot.json'),'source':identity(FOLDER/'Edward_artist_baseline.ma'),
         'runtime_checkout':str(ROOT/'autorig_tools'),'production_runtime_changed':False,
         'tolerance_cm':manifest['tolerance'],'capture_poses':len(manifest['fit']),'held_out_poses':len(manifest['held_out']),
         'blendshape_quality':read('quality_all_summary.json'),'skin_only_quality':read('skin_only_quality_summary.json'),
         'native_blendshape_reopen':read('native_reopen_quality_summary.json'),
         'native_skin_reopen':read('skin_only_native_reopen_summary.json'),
         'timing_scope':read('batch_dg_timing_with_skin.json')['scope'],
         'timing_summary_ms':read('batch_dg_timing_with_skin.json')['summary'],
         'focused_review_scenes':{label:dict(record,identity=identity(Path(record['path']))) for label,record in manifest['artist_comparison_scenes'].items()},
         'opened_windows':{label:read('artist_window_'+label+'_ready.json') for label in ('BLENDSHAPE','SKIN')},
         'gui_checks':{label:json.loads((ROOT/'tmp/edward_belt_blendshape_20261016'/file).read_text()) for label,file in
                       (('BLENDSHAPE','gui_blendshape_check.json'),('SKIN','gui_skin_check.json'))},
         'environment':{'maya':'2026.3.3','cpu':'Intel Core i9-14900HX','logical_processors':32,
                        'installed_ram_bytes':33970483200,'gpu':'NVIDIA GeForce RTX 5060 Laptop GPU'},
         'scripts':[identity(p) for p in scripts],'checks':{'python_syntax':True,'new_code_and_report_ascii':True},
         'raw_folder':str(FOLDER),'limitations':['Finite independent FK pose targets do not guarantee arbitrary poses or IK.',
             'All variants fail held-out geometry/normal/scale gates.',
             'Batch DG two-output latency is not viewport or full-rig FPS.',
             'Review files retain original PRX for visual comparison and are not delivery-size/performance packages.',
             'No production rebuild or SKC integration follows a rejected geometry prototype.']}
(OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps({'summary':str(OUT/'summary.json'),'scripts_syntax_checked':len(scripts),
                  'opened_windows':{k:v['success'] for k,v in summary['opened_windows'].items()},
                  'gui_checks':{k:v['success'] for k,v in summary['gui_checks'].items()}},indent=2))
