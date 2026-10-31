import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'scripts'))
from analyze import rank


class RankingTests(unittest.TestCase):
    def test_sibling_before_distant_file(self):
        rows = rank(['a/seed.py', 'z/other.py', 'a/sibling.py'], 'a/seed.py')
        self.assertEqual([r['path'] for r in rows], ['a/sibling.py', 'z/other.py'])

    def test_unknown_seed_rejected(self):
        with self.assertRaises(ValueError):
            rank(['a.py'], 'missing.py')

    def test_order_and_duplicates_do_not_change_result(self):
        self.assertEqual(rank(['a.py', 'b.py', 'c.py'], 'a.py'),
                         rank(['c.py', 'b.py', 'a.py', 'b.py'], 'a.py'))
