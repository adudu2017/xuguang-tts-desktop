"""Persistent jobs and isolated inference. No ML dependency in the desktop UI."""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
import wave
import csv

ROOT = Path(__file__).resolve().parent
CREATE_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
ENGINES = ('Qwen Python', 'Ming 0.5B', 'Qwen C++')


def write_json(path, value):
    path = Path(path)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def split_text(text, limit=100):
    """Keep punctuation, numbers and all non-whitespace text; bound each segment."""
    if not text.strip():
        raise ValueError('请输入需要合成的文字。')
    parts, current = [], ''
    for piece in re.findall(r'[^。！？!?\n]+[。！？!?\n]*|[。！？!?\n]+', text):
        while len(piece) > limit:
            if current.strip():
                parts.append(current.strip())
                current = ''
            parts.append(piece[:limit].strip())
            piece = piece[limit:]
        if len(current) + len(piece) > limit and current.strip():
            parts.append(current.strip())
            current = ''
        current += piece
    if current.strip():
        parts.append(current.strip())
    return [p for p in parts if p]


def split_english(text, limit=100):
    if not text.strip(): raise ValueError('请输入需要合成的文字。')
    tokens = list(re.finditer(r'\S+', text))
    return [text[tokens[i].start():tokens[min(i+limit,len(tokens))-1].end()] for i in range(0,len(tokens),limit)]


def wav_info(path):
    with wave.open(str(path), 'rb') as f:
        if f.getnframes() == 0 or f.getcomptype() != 'NONE':
            raise ValueError('音频为空或不是 PCM WAV')
        frames = f.readframes(f.getnframes())
        if len(frames) != f.getnframes() * f.getnchannels() * f.getsampwidth():
            raise ValueError('WAV 文件不完整')
        return f.getnframes() / f.getframerate(), (f.getnchannels(), f.getsampwidth(), f.getframerate())


def merge_wavs(files, output):
    fmt = wav_info(files[0])[1]
    tmp = Path(output).with_suffix('.partial.wav')
    with wave.open(str(tmp), 'wb') as dest:
        dest.setnchannels(fmt[0]); dest.setsampwidth(fmt[1]); dest.setframerate(fmt[2])
        for path in files:
            if wav_info(path)[1] != fmt:
                raise ValueError('各分段采样格式不一致，无法合并')
            with wave.open(str(path), 'rb') as src:
                while data := src.readframes(65536):
                    dest.writeframesraw(data)
    tmp.replace(output)


def check_config(engine, config):
    keys = ['cpp_exe', 'cpp_models'] if engine == 'Qwen C++' else ['qwen_python', 'qwen_model'] if engine == 'Qwen Python' else ['ming_python', 'ming_model', 'ming_source']
    for key in keys:
        if not config.get(key) or not Path(config[key]).exists():
            raise ValueError(f'{engine} 尚未配置有效路径：{key}。请打开“引擎设置”。')
    if engine == 'Qwen C++':
        for key in ('cpp_talker', 'cpp_codec'):
            if not config.get(key) or not (Path(config['cpp_models']) / config[key]).is_file():
                raise ValueError(f'缺少 GGUF 文件：{key}')
    else:
        model = Path(config['qwen_model' if engine == 'Qwen Python' else 'ming_model'])
        for filename in ('config.json', 'model.safetensors'):
            if not (model / filename).is_file():
                raise ValueError(f'模型未完整下载，缺少：{model / filename}')
        if engine == 'Ming 0.5B' and config.get('device', 'cuda:0') == 'cpu':
            raise ValueError('Ming 当前需要 CUDA，请在设置中选择 cuda:0。')


def engine_identity(engine, config):
    keys = ['cpp_exe', 'cpp_models'] if engine == 'Qwen C++' else ['qwen_python', 'qwen_model'] if engine == 'Qwen Python' else ['ming_python', 'ming_model', 'ming_source']
    files = {}
    for key in keys:
        if not config.get(key): continue
        path = Path(config[key])
        candidates = [path] if path.is_file() else [f for f in path.rglob('*') if f.suffix in ('.json', '.safetensors', '.gguf', '.onnx', '.py') and '.git' not in f.parts]
        for f in candidates:
            stat = f.stat()
            files[str(f)] = [stat.st_size, stat.st_mtime_ns]
    return files


def export_csv(folder, job):
    with open(Path(folder) / 'comparison.csv', 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['engine','status','load_and_prompt_seconds','generation_seconds','wall_seconds','audio_seconds','wall_rtf','cuda_peak_allocated_mib','cuda_peak_reserved_mib','gpu_total_peak_mib','resumed','omissions','repetitions','similarity'])
        for engine, r in job['results'].items():
            writer.writerow([engine, r.get('error', '完成'), *[r.get(k, '') for k in ('load_and_prompt_seconds','generation_seconds','wall_seconds','audio_seconds','wall_rtf','cuda_peak_allocated_mib','cuda_peak_reserved_mib')],r.get('gpu_total',{}).get('peak_mib',''),r.get('resumed',False),*[r.get('review',{}).get(k,'未评估') for k in ('omissions','repetitions','similarity')]])


class Cancelled(Exception):
    pass


class ResidentWorker:
    def __init__(self):
        self.process = None
        self.key = None
        self.logfile = None
        self.lock = threading.Lock()

    def close(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.kill()
            self.process.wait()
            if self.process.stdin:
                self.process.stdin.close()
            self.process = None
        if self.logfile:
            self.logfile.close()
            self.logfile = None
        self.key = None

    def run(self, request, dest, cancel):
        with self.lock:
            cfg = request['config']
            key = json.dumps([request.get('identity'), {k: cfg.get(k) for k in
                ('ming_python', 'ming_model', 'ming_source', 'device', 'ming_cuda_graph')}], sort_keys=True)
            if self.process is None or self.process.poll() is not None or key != self.key:
                self.close()
                log = ROOT / 'data' / 'resident-ming.log'
                log.parent.mkdir(exist_ok=True)
                self.logfile = open(log, 'a', encoding='utf-8')
                self.process = subprocess.Popen([cfg['ming_python'], str(ROOT / 'worker.py'), '--serve'],
                    stdin=subprocess.PIPE, stdout=self.logfile, stderr=subprocess.STDOUT,
                    text=True, encoding='utf-8', creationflags=CREATE_NO_WINDOW,
                    env=dict(os.environ, PYTHONUTF8='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1'))
                self.key = key
            response = dest / 'response.json'
            response.unlink(missing_ok=True)
            try:
                self.process.stdin.write(str((dest / 'request.json').resolve()) + '\n')
                self.process.stdin.flush()
                while not response.exists():
                    if cancel.wait(.1):
                        raise Cancelled('已取消；下次生成会重新加载模型。')
                    if self.process.poll() is not None:
                        raise RuntimeError('Ming 后台退出，请查看 data/resident-ming.log。')
                result = read_json(response)
                if not result['ok']:
                    raise RuntimeError(result['error'])
            except BaseException:
                self.close()
                raise

RESIDENT = ResidentWorker()
import atexit
atexit.register(RESIDENT.close)


class Runner:
    def __init__(self, data, log=lambda text: None):
        self.data = Path(data)
        self.data.mkdir(parents=True, exist_ok=True)
        self.log = log
        self.cancel = threading.Event()

    def stop(self):
        self.cancel.set()

    def create(self, text, reference, transcript, engines, config):
        for engine in engines:
            check_config(engine, config)
        if not Path(reference).is_file() or not transcript.strip():
            raise ValueError('请提供参考 WAV 和与录音一致的参考文字。')
        wav_info(reference)
        language = config.get('output_language', 'Chinese')
        if language not in ('Chinese', 'English'): raise ValueError('请选择中文或英文。')
        from subtitle_quality import validate_language
        validate_language(text, language)
        if engines == ['Qwen Python']:
            from qwen_quality import prepare_segments
            segments = prepare_segments(text)
        else:
            segments = split_english(text) if language == 'English' else split_text(text)
        folder = self.data / (time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6])
        folder.mkdir()
        shutil.copy2(reference, folder / 'reference.wav')
        job = dict(id=folder.name, text=text, transcript=transcript.strip(), segments=segments,
                   reference_sha256=digest(folder / 'reference.wav'), engines=engines,
                   config=dict(config), results={}, status='待生成', created=time.strftime('%Y-%m-%d %H:%M:%S'),
                   engine_identity={e: engine_identity(e, config) for e in engines},
                   measurement='Ming 常驻进程；记录模型及音色缓存命中；整卡 GPU 采样包含其他程序')
        write_json(folder / 'job.json', job)
        return folder

    def run_process(self, command, folder, env=None):
        with open(folder / 'engine.log', 'a', encoding='utf-8') as out:
            p = subprocess.Popen(command, stdout=out, stderr=subprocess.STDOUT, env=env,
                                 creationflags=CREATE_NO_WINDOW)
            reported = -1
            try:
                while p.poll() is None:
                    if self.cancel.wait(.15):
                        raise Cancelled('已停止；已完成分段保留，可从历史恢复。')
                    try:
                        count = len(read_json(folder / 'segments.json'))
                        if count != reported:
                            self.log(f'已保存 {count} 个分段；推理日志：{folder / "engine.log"}')
                            reported = count
                    except (OSError, ValueError):
                        pass
                if p.returncode:
                    tail = (folder / 'engine.log').read_text(encoding='utf-8', errors='replace')[-1800:]
                    raise RuntimeError(f'引擎退出码 {p.returncode}\n{tail}')
            finally:
                if p.poll() is None:
                    p.kill()
                    p.wait()

    def run(self, folder, resume=False):
        folder = Path(folder)
        job = read_json(folder / 'job.json')
        self.cancel.clear()
        if digest(folder / 'reference.wav') != job['reference_sha256']:
            raise ValueError('参考音频已改变；请创建新任务。')
        if resume:
            for e in job['engines']:
                if job.get('engine_identity', {}).get(e) != engine_identity(e, job['config']):
                    raise ValueError('引擎源码或模型文件已改变，请创建新任务，避免混合不同版本的分段。')
        job['status'] = '生成中'
        write_json(folder / 'job.json', job)
        try:
            for engine in job['engines']:
                if self.cancel.is_set():
                    raise Cancelled('已停止')
                check_config(engine, job['config'])
                self.log(f'{engine}：准备生成 {len(job["segments"])} 段')
                dest = folder / engine.replace(' ', '_').replace('+', 'p')
                dest.mkdir(exist_ok=True)
                # Recovery only trusts WAVs whose content checksum was committed.
                valid = {}
                if resume and (dest / 'segments.json').exists():
                    for key, value in read_json(dest / 'segments.json').items():
                        path = dest / f'{int(key):04}.wav'
                        try:
                            if digest(path) == value['sha256']:
                                wav_info(path); valid[key] = value
                        except (OSError, ValueError, wave.Error):
                            pass
                if resume: self.log(f'{engine}：校验通过 {len(valid)} 段，将复用；待生成 {len(job["segments"])-len(valid)} 段')
                write_json(dest / 'segments.json', valid)
                request = dict(engine=engine, config=job['config'], segments=job['segments'],
                               reference=str(folder / 'reference.wav'), transcript=job['transcript'],
                               output=str(dest), skip=list(valid), identity=job['engine_identity'].get(engine))
                write_json(dest / 'request.json', request)
                monitor = GPUMonitor(); monitor.start()
                start = time.perf_counter()
                try:
                    if engine == 'Qwen C++':
                        self.run_cpp(request, dest)
                    elif engine == 'Ming 0.5B':
                        try:
                            RESIDENT.run(request, dest, self.cancel)
                        except RuntimeError as error:
                            if 'CUDA_GRAPH_FAILED:' not in str(error): raise
                            self.log('加速失败，重新加载并使用标准推理。')
                            request['config'] = dict(request['config'], ming_cuda_graph=False)
                            write_json(dest / 'request.json', request)
                            RESIDENT.run(request, dest, self.cancel)
                    else:
                        # Release Ming's resident model before loading a different engine.
                        RESIDENT.close()
                        python = job['config']['qwen_python' if engine == 'Qwen Python' else 'ming_python']
                        env = dict(os.environ, PYTHONUTF8='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
                        self.run_process([python, str(ROOT / 'worker.py'), str(dest / 'request.json')], dest, env)
                    monitor.stop()
                    files = [dest / f'{i:04}.wav' for i in range(len(job['segments']))]
                    merge_wavs(files, dest / 'complete.wav')
                    from transcript_tools import collect, save_sidecars
                    text, cues = collect(dest / 'complete.wav')
                    save_sidecars(dest / 'complete.wav', text, cues)
                    subtitle_warning = None
                    if job['config'].get('output_language') == 'English' or job['config'].get('chinese_subtitles') == '中英双语字幕':
                        self.log('正在生成中英文字幕…')
                        write_json(dest / 'progress.json', dict(stage='finalizing',total=0,completed=0,text='正在生成中英文字幕…'))
                        try:
                            self.run_process([job['config']['ming_python'], str(ROOT / 'translate_subtitles.py'), str(dest / 'complete.wav'), job['config'].get('output_language', 'Chinese')],dest,
                                dict(os.environ,PYTHONUTF8='1',HF_HUB_OFFLINE='1'))
                        except Cancelled: raise
                        except Exception as error:
                            subtitle_warning = str(error)
                            self.log('音频已保存，双语字幕未完成：' + str(error))
                    metrics = read_json(dest / 'metrics.json') if (dest / 'metrics.json').exists() else {}
                    seconds = sum(wav_info(f)[0] for f in files)
                    metrics.update(subtitle_warning=subtitle_warning, audio_seconds=seconds, wall_seconds=time.perf_counter() - start,
                                   resumed=bool(valid), gpu_total=monitor.snapshot(),
                                   wav=str(dest / 'complete.wav'), review={})
                    metrics['wall_rtf'] = metrics['wall_seconds'] / seconds
                    job['results'][engine] = metrics
                    self.log(f'{engine}：完成，音频 {seconds:.1f} 秒')
                except Exception as error:
                    job['results'][engine] = dict(error=str(error))
                    self.log(f'{engine}：{error}')
                    if isinstance(error, Cancelled):
                        raise
                finally:
                    monitor.stop()
                    monitor.save(dest / 'gpu.csv')
                    write_json(folder / 'job.json', job)
            job['status'] = '完成' if all('wav' in v for v in job['results'].values()) else '部分失败'
        except Exception:
            job['status'] = '已中断'
            raise
        finally:
            write_json(folder / 'job.json', job)
            export_csv(folder, job)
        return job

    def run_cpp(self, request, dest):
        cfg = request['config']
        saved = read_json(dest / 'segments.json')
        for i, text in enumerate(request['segments']):
            if str(i) in request['skip']:
                continue
            if self.cancel.is_set():
                raise Cancelled('已停止')
            output = dest / f'{i:04}.wav'
            if output.exists():
                output.unlink()
            command = [cfg['cpp_exe'], '-m', cfg['cpp_models'], '--model-name', cfg['cpp_talker'],
                       '--codec-model', str(Path(cfg['cpp_models']) / cfg['cpp_codec']), '-t', text,
                       '-r', request['reference'], '--reference-text', request['transcript'],
                       '-l', 'zh', '--seed', '42', '-o', str(output)]
            self.log(f'Qwen C++：第 {i + 1} 段（每段重新加载模型）')
            self.run_process(command, dest)
            wav_info(output)
            saved[str(i)] = dict(sha256=digest(output))
            write_json(dest / 'segments.json', saved)


class GPUMonitor:
    """Whole-board memory, explicitly NOT process-only VRAM on WDDM."""
    def __init__(self):
        self.done = threading.Event()
        self.values = []
        self.rows = []
        self.started = time.perf_counter()

    def start(self):
        self.thread = threading.Thread(target=self.poll, daemon=True)
        self.thread.start()

    def poll(self):
        while not self.done.is_set():
            try:
                result = subprocess.check_output(['nvidia-smi', '--id=0', '--query-gpu=memory.used,utilization.gpu,utilization.memory,power.draw',
                                                  '--format=csv,noheader,nounits'], timeout=3,
                                                 creationflags=CREATE_NO_WINDOW)
                parts = result.decode().strip().split(',')
                values = []
                for item in parts:
                    try: values.append(float(item.strip()))
                    except ValueError: values.append(None)
                self.rows.append([time.perf_counter() - self.started, *values])
                if values[0] is not None: self.values.append(values[0])
            except (OSError, ValueError, subprocess.SubprocessError):
                pass
            self.done.wait(.5)

    def snapshot(self):
        return dict(baseline_mib=self.values[0] if self.values else None,
                    peak_mib=max(self.values) if self.values else None,
                    samples=len(self.rows),
                    utilization_mean=sum(r[2] for r in self.rows if r[2] is not None) / max(1, sum(r[2] is not None for r in self.rows)),
                    utilization_peak=max((r[2] for r in self.rows if r[2] is not None), default=None),
                    power_peak_w=max((r[4] for r in self.rows if r[4] is not None), default=None),
                    scope='GPU 0 整卡，含其他程序；每次查询后等待 0.5 秒，实际时间见 CSV')

    def save(self, path):
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['elapsed_seconds', 'memory_mib', 'gpu_util_percent', 'memory_util_percent', 'power_w'])
            writer.writerows(self.rows)

    def stop(self):
        self.done.set()
        self.thread.join(timeout=4)
