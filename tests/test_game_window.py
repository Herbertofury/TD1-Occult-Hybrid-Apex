from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from game_window import select_window


class GameWindowTests(unittest.TestCase):
    def row(self, pid=42, hwnd=7, **changes):
        return dict({'pid': pid, 'hwnd': hwnd, 'class': 'Canvas-ABC', 'visible': True,
                     'width': 1280, 'height': 720}, **changes)

    def test_window_identity_and_ambiguity(self):
        correct = self.row()
        self.assertEqual(select_window([self.row(pid=43), correct], 42), correct)
        with self.assertRaises(ValueError):
            select_window([correct, self.row(hwnd=8)], 42)
        for changes in ({'visible': False}, {'class': 'EADesktop'}, {'width': 0}):
            with self.assertRaises(ValueError):
                select_window([self.row(**changes)], 42)


if __name__ == '__main__':
    unittest.main()
