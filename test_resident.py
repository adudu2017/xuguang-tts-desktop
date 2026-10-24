import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import core

SERVICE = '''import sys,json,time,os
from pathlib import Path
for line in sys.stdin:
 p=Path(line.strip()); r=json.loads(p.read_text())
 if r.get('crash'): sys.exit(7)
 if r.get('slow'): time.sleep(20)
 (p.parent/'pid.txt').write_text(str(os.getpid()))
 out=p.parent/'response.json'; tmp=out.with_suffix('.tmp')
 tmp.write_text(json.dumps({'ok':True}));tmp.replace(out)
'''

class ResidentTests(unittest.TestCase):
    def test_reuse_invalidation_and_close(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'worker.py').write_text(SERVICE)
            worker=core.ResidentWorker()
            req={'config':{'ming_python':sys.executable},'identity':'a'}
            try:
                with patch.object(core,'ROOT',root):
                    for i in range(3):
                        dest=root/str(i);dest.mkdir()
                        if i==2: req['identity']='b'
                        core.write_json(dest/'request.json',req)
                        worker.run(req,dest,threading.Event())
                        if i==0: first=worker.process
                        if i==1: self.assertIs(first,worker.process)
                        if i==2:
                            self.assertIsNot(first,worker.process)
                            self.assertIsNotNone(first.poll())
                    final=worker.process
            finally: worker.close()
            self.assertIsNotNone(final.poll())

    def test_crash_then_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'worker.py').write_text(SERVICE)
            dest=root/'job';dest.mkdir()
            req={'config':{'ming_python':sys.executable},'crash':True}
            worker=core.ResidentWorker()
            try:
                with patch.object(core,'ROOT',root):
                    core.write_json(dest/'request.json',req)
                    with self.assertRaises(RuntimeError):worker.run(req,dest,threading.Event())
                    self.assertIsNone(worker.process)
                    req.pop('crash');core.write_json(dest/'request.json',req)
                    worker.run(req,dest,threading.Event())
                    self.assertTrue(core.read_json(dest/'response.json')['ok'])
            finally:worker.close()

    def test_cancel_releases_process(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'worker.py').write_text(SERVICE)
            dest=root/'job';dest.mkdir()
            req={'config':{'ming_python':sys.executable},'slow':True}
            core.write_json(dest/'request.json',req)
            worker=core.ResidentWorker();cancel=threading.Event();cancel.set()
            try:
                with patch.object(core,'ROOT',root):
                    with self.assertRaises(core.Cancelled):worker.run(req,dest,cancel)
                self.assertIsNone(worker.process)
            finally:worker.close()

if __name__=='__main__':unittest.main()
