import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from inference_diagnostics import Diagnostics, diagnosed_main


class DiagnosticTests(unittest.TestCase):
    def test_stages_failure_and_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch('inference_diagnostics.faulthandler.dump_traceback_later') as arm:
                with patch('inference_diagnostics.faulthandler.cancel_dump_traceback_later') as cancel:
                    d = Diagnostics(tmp)
                    self.assertEqual(d.wrap(lambda: 7, 'audio_decode')(), 7)
                    d.touch(123)
                    def fail():
                        raise RuntimeError('test failure')
                    with self.assertRaisesRegex(RuntimeError, 'test failure'):
                        d.wrap(fail, 'acoustic_tokens')()
                    self.assertEqual(d.stage, 'startup')
                    d.close()
                    self.assertFalse(d.thread.is_alive())
                    self.assertTrue(arm.called)
                    cancel.assert_called_once()
            rows = [json.loads(x) for x in (Path(tmp)/'diagnostics.jsonl').read_text().splitlines()]
            self.assertTrue(any(x['event']=='stage_end' and x['stage']=='audio_decode' for x in rows))
            self.assertTrue(any(x['event']=='stage_error' and x['steps']==123 for x in rows))
            self.assertEqual(rows[-1]['event'], 'worker_end')

    def test_worker_exception_and_ming_bypass(self):
        with tempfile.TemporaryDirectory() as tmp:
            req=Path(tmp)/'request.json'
            req.write_text(json.dumps(dict(engine='Qwen Python', output=tmp)))
            @diagnosed_main
            def fail(path, diagnostics=None):
                raise ValueError('intentional')
            with self.assertRaises(ValueError):
                fail(req)
            rows=[json.loads(x) for x in (Path(tmp)/'diagnostics.jsonl').read_text().splitlines()]
            self.assertEqual(rows[-2]['event'],'worker_error')
            self.assertEqual(rows[-1]['event'],'worker_end')
            req.write_text(json.dumps(dict(engine='Ming 0.5B')))
            @diagnosed_main
            def ming(path):
                return 'unchanged'
            self.assertEqual(ming(req),'unchanged')

if __name__=='__main__':
    unittest.main()
