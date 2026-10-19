"""Verify the v074 mouth-mask repair changes exactly two lossless weight rows."""
import copy
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[4]
SKINS = ROOT / 'maya_tools/assets/Edward/skin_clusters'


class SkinRevisionTests(unittest.TestCase):
    def test_only_two_low_head_weight_rows_change(self):
        source = json.loads((SKINS / 'Edward_v073.skc').read_text())
        repaired = json.loads((SKINS / 'Edward_v074.skc').read_text())
        old = next(r for r in source['cabeza_low_Shape'] if r['name'] == 'skinCluster41')
        new = next(r for r in repaired['cabeza_low_Shape'] if r['name'] == 'skinCluster41')
        edited = new['sparse_weights']
        new['sparse_weights'] = copy.deepcopy(old['sparse_weights'])
        self.assertEqual(repaired, source)
        changed = set()
        totals = {vertex: [0., 0.] for vertex in (2942, 3080)}
        for name in set(old['sparse_weights']) | set(edited):
            before = old['sparse_weights'].get(name, {'ix': [], 'v': []})
            after = edited.get(name, {'ix': [], 'v': []})
            key = next(k for k in before if k != 'ix')
            a = dict(zip(before['ix'], before[key]))
            b = dict(zip(after['ix'], after[key]))
            for vertex in set(a) | set(b):
                x, y = a.get(vertex, 0.), b.get(vertex, 0.)
                if x != y:
                    changed.add(vertex)
                    self.assertIn(vertex, totals)
                    if x > 0:
                        self.assertGreater(y, 0)
                if vertex in totals:
                    totals[vertex][0] += x
                    totals[vertex][1] += y
        self.assertEqual(changed, {2942, 3080})
        for before, after in totals.values():
            self.assertAlmostEqual(before, after, places=14)


if __name__ == '__main__':
    unittest.main()
