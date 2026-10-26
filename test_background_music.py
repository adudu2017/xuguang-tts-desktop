import tempfile
import unittest
from pathlib import Path
from background_music import music_path, mix_filter, shift_cues

class BackgroundMusicTests(unittest.TestCase):
    def test_off_requires_no_asset(self):
        self.assertIsNone(music_path('.', '关闭背景音乐'))
    def test_missing_music_is_not_silently_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError): music_path(tmp, '背景音乐 1 · 1989154383')
            p=Path(tmp)/'assets/music/1989154383.mp3';p.parent.mkdir(parents=True);p.write_bytes(b'test')
            self.assertEqual(music_path(tmp,'背景音乐 1 · 1989154383'),p)
    def test_unknown_choice_rejected(self):
        with self.assertRaises(ValueError): music_path('.', '../other.mp3')
    def test_short_audio_fades_do_not_go_negative(self):
        graph=mix_filter(.5)
        self.assertIn('st=0.250000',graph)
        self.assertIn('sidechaincompress',graph)
        with self.assertRaises(ValueError):mix_filter(0)

    def test_intro_shifts_cues_without_mutating_original(self):
        cues=[dict(start=0,end=3,text='Hello')]
        shifted=shift_cues(cues,2)
        self.assertEqual((shifted[0]['start'],shifted[0]['end']),(2,5))
        self.assertEqual(cues[0]['start'],0)
        self.assertIn('adelay=2000:all=1',mix_filter(5))
