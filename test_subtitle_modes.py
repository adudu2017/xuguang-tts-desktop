import json
import tempfile
import unittest
from pathlib import Path
from transcript_tools import collect, save_sidecars, load

class SubtitleModesTests(unittest.TestCase):
    def test_no_subtitles_does_not_reconstruct_history_or_leave_stale_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / 'engine'
            folder.mkdir()
            wav = folder / 'complete.wav'
            (root / 'job.json').write_text(json.dumps(dict(config=dict(output_language='Chinese', chinese_subtitles='不生成字幕'), text='你好', segments=['你好'])), encoding='utf-8')
            for ext in ('.srt', '.cues.json'):
                wav.with_suffix(ext).write_text('stale')
            text, cues = collect(wav)
            save_sidecars(wav, text, cues)
            self.assertEqual(load(wav), ('你好', []))
            self.assertFalse(wav.with_suffix('.srt').exists())
            self.assertFalse(wav.with_suffix('.cues.json').exists())

    def test_bilingual_export_keeps_both_languages(self):
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / 'complete.wav'
            cues = [dict(start=0, end=1, text='你好', translation='Hello.')]
            save_sidecars(wav, '你好', cues)
            self.assertEqual(load(wav), ('你好', cues))
            self.assertIn('你好\nHello.', wav.with_suffix('.srt').read_text(encoding='utf-8-sig'))

if __name__ == '__main__':
    unittest.main()
