from pathlib import Path
import hashlib
import importlib.util
import json
import sys

root = Path('C:/proyectos/auto-rig')
live = root / 'autorig_tools'
sys.path.insert(0, str(root / 'tmp/skill_validation'))
spec = importlib.util.spec_from_file_location('skill_validator', 'C:/Users/LaiaPeris/.codex/skills/.system/skill-creator/scripts/quick_validate.py')
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)
skills = ('rig-change-impact', 'rig-performance-audit', 'rig-deformation-equivalence')
for name in skills:
    for checkout in (root, live):
        path = checkout / '.agents/skills' / name
        ok, message = validator.validate_skill(path)
        assert ok, (path, message)
        assert path.joinpath('SKILL.md').read_text(encoding='utf-8').isascii()
        print(name, checkout.name, message)

docs = ['rig_performance_criteria.md', 'rig_optimization_roadmap_20261015.md']
for filename in docs:
    assert (root / 'maya_tools/docs' / filename).read_bytes() == (live / 'maya_tools/docs' / filename).read_bytes()
    assert (live / 'maya_tools/docs' / filename).read_text(encoding='utf-8').isascii()

data_path = root / 'maya_tools/assets/Edward/experiments/full_audit_20261015_v001/report_data.json'
data = json.loads(data_path.read_text(encoding='utf-8'))
summary = {key: data[key] for key in ('scene_bytes', 'node_count', 'modules', 'layers', 'state_tests', 'quality_resolution', 'gpu_quality', 'decision')}
summary['source_report_data_sha256'] = hashlib.sha256(data_path.read_bytes()).hexdigest()
summary['scope'] = '2026-10-15 artist snapshot; distinct from regional v002. Full raw evidence retained in outer workspace.'
for checkout in (root, live):
    target = checkout / 'maya_tools/docs/validation/edward_audit_20261015/summary.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(summary, indent=2, ensure_ascii=True), encoding='utf-8')
print('PASS skill schemas, mirrored ASCII criteria/roadmap, portable evidence summary')
