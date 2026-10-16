"""Persist the observed verification without changing artist/model files."""
import ast
import hashlib
import json
from pathlib import Path
import shutil

root = Path('C:/proyectos/auto-rig')
live = root / 'autorig_tools'
receipt = json.loads((root / 'tmp/scene_evaluation_live_receipt_v001.json').read_text(encoding='utf-8'))
assert receipt['success'] and receipt['result']['artist_state_unchanged']
observed = receipt['result']
assert all(row['mode'] == 'parallel' and not any(row['evaluators'].values()) for row in observed['configuration_samples'])
source_paths = [
    'maya_tools/scripts/utils/scene_evaluation.py',
    'maya_tools/scripts/utils/create_rig.py',
    'maya_tools/scripts/userSetup.py',
    'maya_tools/scripts/tools/tests/test_scene_evaluation.py',
    'maya_tools/scripts/tools/tests/test_build_pipeline.py',
]
for relative in source_paths:
    ast.parse((live / relative).read_text(encoding='utf-8'))
summary = {
    'date': '2026-10-15',
    'maya': '2026 / API 20260303',
    'native_tests': {'scene_evaluation': {'tests': 8, 'passed': 8}, 'build_pipeline': {'tests': 11, 'passed': 11}},
    'standalone_fixture': {
        'deformer_evaluator_loaded': True,
        'registration_and_apply_seconds': 0.0012088000003132038,
        'settings_only_apply_seconds': 0.00015679999341955408,
        'reopen_seconds_including_file_io': [0.03687489999720128, 0.023786699995980598],
        'characters': ['FirstCharacter', 'OtherCharacter:Root'],
        'no_viewport_or_gpu_partition_query': True,
    },
    'live_artist_scene': observed,
    'skill_validation': '3 skills passed official quick_validate in both project checkouts',
    'canvas_typescript': 'tsc --noEmit passed',
    'source_sha256': {relative: hashlib.sha256((live / relative).read_bytes()).hexdigest() for relative in source_paths},
    'limits': [
        'Settings overhead excludes graph evaluation, final draw and a full rig rebuild.',
        'Two generic reopen fixtures are not performance certification of every character.',
        'Legacy unmarked scenes are opt-in. No source model or current artist scene was saved.',
        'Automatic reopen needs AutoRig Tools installed; no executable scene scripts are embedded.',
    ],
}
validation = live / 'maya_tools/docs/validation/scene_evaluation_20261015'
validation.mkdir(parents=True, exist_ok=True)
(validation / 'summary.json').write_text(json.dumps(summary, indent=2, ensure_ascii=True), encoding='utf-8')
(validation / 'live_artist_scene.json').write_text(json.dumps(receipt, indent=2, ensure_ascii=True), encoding='utf-8')
for relative in ('maya_tools/docs/rig_performance_criteria.md',):
    shutil.copyfile(live / relative, root / relative)
for filename in ('summary.json', 'live_artist_scene.json', 'build_pipeline.log'):
    target = root / 'maya_tools/docs/validation/scene_evaluation_20261015' / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(validation / filename, target)
print(json.dumps({'tests_passed': 19, 'live_apply_ms': [r['seconds'] * 1000 for r in observed['configuration_samples']], 'artist_state_unchanged': True}, indent=2))
