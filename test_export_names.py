import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from export_names import next_name


class NamingTests(unittest.TestCase):
    def test_daily_sequence_persists_and_resets(self):
        with tempfile.TemporaryDirectory() as base:
            self.assertEqual(next_name(base,'叙光字幕视频','.mp4','20261024'),'叙光字幕视频20261024001.mp4')
            self.assertEqual(next_name(base,'叙光音频','.wav','20261024'),'叙光音频20261024002.wav')
            self.assertEqual(next_name(base,'叙光音色',day='20261025'),'叙光音色20261025001')
            self.assertEqual(next_name(base,'叙光音频','.wav','20261024'),'叙光音频20261024003.wav')

    def test_concurrent_reservations_are_unique(self):
        with tempfile.TemporaryDirectory() as base:
            with ThreadPoolExecutor(max_workers=4) as pool:
                names=list(pool.map(lambda _:next_name(base,'叙光字幕视频','.mp4','20261024'),range(12)))
            self.assertEqual(len(set(names)),12)
            self.assertEqual(sorted(names)[-1],'叙光字幕视频20261024012.mp4')
