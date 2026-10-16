"""Mirror only this task's guidance; retain the distinct runtime checkouts."""
from pathlib import Path
import shutil

root = Path('C:/proyectos/auto-rig')
live = root / 'autorig_tools'
files = [
    'maya_tools/docs/rig_performance_criteria.md',
    'maya_tools/docs/rig_optimization_roadmap_20261015.md',
    '.cursor/rules/rig-performance-measurement.mdc',
    '.cursor/rules/rig-evaluation-architecture.mdc',
    '.cursor/rules/rig-wrinkles-and-detail.mdc',
    '.cursor/skills/how_it_works.md',
    'AGENTS.md',
] + ['.agents/skills/' + name + '/SKILL.md' for name in (
    'rig-change-impact', 'rig-performance-audit', 'rig-deformation-equivalence')]
for relative in files:
    source, target = live / relative, root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
print('Mirrored %d guidance files; existing runtime files were not replaced.' % len(files))
