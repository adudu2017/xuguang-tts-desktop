import tempfile
import unittest
import wave
import sys
import time
import threading
from pathlib import Path
from unittest.mock import patch
import core


def make_wav(path, value=1):
    with wave.open(str(path), 'wb') as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(24000)
        f.writeframes(bytes([value, 0]) * 2400)


class CoreTests(unittest.TestCase):
    def test_split_preserves_text(self):
        for s in ['你好！真的吗？当然。', '十月二十三日，三十九元五角。'*31, 'x'*401, '\n甲\n\n乙。']:
            parts = core.split_text(s)
            self.assertTrue(all(len(p) <= 100 for p in parts))
            self.assertEqual(''.join(''.join(parts).split()), ''.join(s.split()))

    def test_empty(self):
        with self.assertRaises(ValueError): core.split_text('  \n')

    def test_merge(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); make_wav(p/'a.wav'); make_wav(p/'b.wav')
            core.merge_wavs([p/'a.wav', p/'b.wav'], p/'all.wav')
            self.assertAlmostEqual(core.wav_info(p/'all.wav')[0], .2)

    def test_failed_segment_and_corrupted_cache_recover(self):
        with tempfile.TemporaryDirectory() as d, patch('core.check_config'):
            p = Path(d); make_wav(p/'ref.wav')
            runner = core.Runner(p/'jobs')
            folder = runner.create('甲。'*80, p/'ref.wav', '参考', ['Qwen C++'], {})
            calls = []
            def fake(request, dest):
                saved = core.read_json(dest/'segments.json')
                for i, text in enumerate(request['segments']):
                    if str(i) in request['skip']: continue
                    calls.append(i)
                    make_wav(dest/f'{i:04}.wav')
                    saved[str(i)] = {'sha256':core.digest(dest/f'{i:04}.wav')}
                    core.write_json(dest/'segments.json', saved)
            runner.run_cpp = fake
            with patch.object(core.GPUMonitor, 'poll', lambda self: None):
                runner.run(folder)
                self.assertEqual(calls, [0,1]); calls.clear()
                (folder/'Qwen_Cpp'/'0001.wav').write_bytes(b'corrupt')
                runner.run(folder, True)
                self.assertEqual(calls, [1])
                self.assertEqual(core.read_json(folder/'job.json')['status'], '完成')

    def test_graph_failure_falls_back_once(self):
        with tempfile.TemporaryDirectory() as d, patch('core.check_config'):
            p=Path(d);make_wav(p/'ref.wav');runner=core.Runner(p/'jobs')
            folder=runner.create('测试。',p/'ref.wav','参考',['Ming 0.5B'],{})
            calls=[]
            def fake(request,dest,cancel):
                calls.append(request['config'].get('ming_cuda_graph',True))
                if len(calls)==1:raise RuntimeError('CUDA_GRAPH_FAILED: injected failure')
                make_wav(dest/'0000.wav')
                core.write_json(dest/'metrics.json',{'cuda_graph_enabled':False})
            with patch.object(core.RESIDENT,'run',side_effect=fake), patch.object(core.GPUMonitor,'poll',lambda self:None):
                result=runner.run(folder)
            self.assertEqual(calls,[True,False])
            self.assertEqual(result['status'],'完成')
            self.assertFalse(result['results']['Ming 0.5B']['cuda_graph_enabled'])

    def test_engine_failure_not_success(self):
        with tempfile.TemporaryDirectory() as d, patch('core.check_config'):
            p = Path(d); make_wav(p/'ref.wav'); runner = core.Runner(p/'jobs')
            folder = runner.create('测试。', p/'ref.wav', '参考', ['Qwen C++'], {})
            def fail(*args): raise RuntimeError('synthetic engine failure')
            runner.run_cpp = fail
            with patch.object(core.GPUMonitor, 'poll', lambda self: None): runner.run(folder)
            result = core.read_json(folder/'job.json')
            self.assertEqual(result['status'], '部分失败')
            self.assertNotIn('wav', result['results']['Qwen C++'])

    def test_cancel_terminates_worker(self):
        with tempfile.TemporaryDirectory() as d:
            runner = core.Runner(d)
            timer = threading.Timer(.3, runner.stop)
            timer.start(); start = time.perf_counter()
            with self.assertRaises(core.Cancelled):
                runner.run_process([sys.executable, '-c', 'import time;time.sleep(30)'], Path(d))
            timer.join()
            self.assertLess(time.perf_counter()-start, 5)

    def test_reference_change_rejected(self):
        with tempfile.TemporaryDirectory() as d, patch('core.check_config'):
            p=Path(d);make_wav(p/'ref.wav');runner=core.Runner(p/'jobs')
            folder=runner.create('测试',p/'ref.wav','参考',['Qwen C++'],{})
            make_wav(folder/'reference.wav',2)
            with self.assertRaises(ValueError): runner.run(folder,True)


if __name__ == '__main__': unittest.main()
