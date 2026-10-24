"""Local append-only inference diagnostics; no token copies or CUDA synchronization."""
import json,time,os,threading,faulthandler
from pathlib import Path
from functools import wraps

class Diagnostics:
    def __init__(self,folder):
        self.folder=Path(folder);self.folder.mkdir(parents=True,exist_ok=True)
        self.started=time.monotonic();self.last_progress=self.started;self.last_log=0
        self.stage='startup';self.segment=None;self.steps=0;self.done=threading.Event();self.lock=threading.Lock()
        self.file=open(self.folder/'diagnostics.jsonl','a',encoding='utf-8',buffering=1)
        self.stack=open(self.folder/'stacks.log','a',encoding='utf-8',buffering=1)
        faulthandler.dump_traceback_later(90,repeat=True,file=self.stack)
        self.thread=threading.Thread(target=self.monitor,daemon=True);self.thread.start();self.event('worker_start',pid=os.getpid())
    def event(self,event,**fields):
        row=dict(timestamp=time.strftime('%Y-%m-%dT%H:%M:%S'),elapsed_seconds=round(time.monotonic()-self.started,3),event=event,stage=self.stage,segment=self.segment,steps=self.steps,**fields)
        try:
            with self.lock:self.file.write(json.dumps(row,ensure_ascii=False)+'\n')
        except OSError:pass
    def touch(self,steps=None):
        self.last_progress=time.monotonic()
        if steps is not None:self.steps=steps
        faulthandler.dump_traceback_later(90,repeat=True,file=self.stack)
        if self.last_progress-self.last_log>=5:
            self.last_log=self.last_progress;self.event('generation_progress')
    def monitor(self):
        while not self.done.wait(10):
            self.event('heartbeat',progress_age_seconds=round(time.monotonic()-self.last_progress,2))
    def wrap(self,fn,stage):
        @wraps(fn)
        def call(*a,**kw):
            prior=self.stage;self.stage=stage;self.touch();start=time.monotonic();self.event('stage_start')
            try:
                result=fn(*a,**kw);self.event('stage_end',wall_seconds=round(time.monotonic()-start,3));return result
            except BaseException as e:
                self.event('stage_error',error=repr(e));raise
            finally:self.stage=prior;self.touch()
        return call
    def close(self):
        self.done.set();self.thread.join(timeout=2);faulthandler.cancel_dump_traceback_later();self.event('worker_end');self.file.close();self.stack.close()

def diagnosed_main(fn):
    @wraps(fn)
    def call(request_path):
        r=json.loads(Path(request_path).read_text(encoding='utf-8'))
        if r['engine']!='Qwen Python':return fn(request_path)
        d=Diagnostics(r['output'])
        try:return fn(request_path,diagnostics=d)
        except BaseException as e:d.event('worker_error',error=repr(e));raise
        finally:d.close()
    return call
