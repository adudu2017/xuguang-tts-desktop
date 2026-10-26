"""Run with the selected engine's Python interpreter, never the UI interpreter."""
import json
import sys
import time
from pathlib import Path
from core import digest, read_json, write_json, wav_info
from inference_diagnostics import diagnosed_main


RESIDENT_MODEL = None
PROMPTS = {}

def write_progress(out, state):
    # Windows may briefly hold the destination while the UI reads it.
    # Telemetry must never fail an otherwise successful synthesis.
    for attempt in range(5):
        try:
            write_json(out / 'progress.json', state)
            return
        except PermissionError:
            time.sleep(.01)


@diagnosed_main
def main(request_path, diagnostics=None):
    global RESIDENT_MODEL
    r = read_json(request_path)
    cfg = r['config']; out = Path(r['output'])
    language = cfg.get('output_language', 'Chinese')
    write_progress(out, dict(stage='loading', completed=0, total=0, text='正在准备模型和参考音色…'))
    import torch
    import soundfile as sf
    import numpy as np
    torch.manual_seed(42)
    device = cfg.get('device', 'cuda:0')
    cuda = device.startswith('cuda')
    if cuda and not torch.cuda.is_available():
        raise RuntimeError('当前引擎环境的 PyTorch 无法使用 CUDA；请安装 CUDA 版或在设置中选择 cpu。')
    if cuda:
        torch.cuda.set_device(device)
        torch.cuda.reset_peak_memory_stats()
    start = time.perf_counter()
    model_reused = False
    prompt_reused = False
    if r['engine'] == 'Qwen Python':
        from qwen_tts import Qwen3TTSModel
        import transformers.integrations.sdpa_attention as sdpa_attention
        from qwen_runtime import attention_mode
        expanded_kv = attention_mode(r)
        if expanded_kv:
            # Explicit KV expansion selects the tested SDPA path on this runtime.
            sdpa_attention.use_gqa_in_sdpa = lambda *args, **kwargs: False
        model = diagnostics.wrap(Qwen3TTSModel.from_pretrained,'model_load')(cfg['qwen_model'], device_map=device,
                    dtype=torch.bfloat16 if cuda else torch.float32, attn_implementation='sdpa')
        prompt = diagnostics.wrap(model.create_voice_clone_prompt,'reference_encode')(ref_audio=r['reference'], ref_text=r['transcript'], x_vector_only_mode=False)
        model.model.generate=diagnostics.wrap(model.model.generate,'acoustic_tokens')
        model.model.speech_tokenizer.decode=diagnostics.wrap(model.model.speech_tokenizer.decode,'audio_decode')
        diagnostics.event('configuration',torch_version=torch.__version__,device=device,language=language,
            generation_defaults=model.generate_defaults,reference_sha256=digest(r['reference']),
            attention_implementation='sdpa',expanded_kv=expanded_kv,segment_count=len(r['segments']))
    else:
        if not cuda:
            raise RuntimeError('Ming 官方实现包含 CUDA 专用计算路径；此客户端目前只支持 Ming CUDA 推理。')
        sys.path.insert(0, cfg['ming_source'])
        from ming_tts import MingTTS
        model_reused = RESIDENT_MODEL is not None
        if RESIDENT_MODEL is None:
            RESIDENT_MODEL = MingTTS(cfg['ming_model'], device=device, text_normalization=False)
        model = RESIDENT_MODEL
        if cfg.get('ming_cuda_graph', True) and not hasattr(model, '_flow_graph'):
            from flow_graph import FlowGraph
            model._flow_graph = FlowGraph(model.model.flowloss.cfm)
        if hasattr(model, '_flow_graph'):
            model._flow_graph.enabled = cfg.get('ming_cuda_graph', True)
        key = digest(r['reference'])
        prompt_reused = key in PROMPTS
        model._prompt_cache.clear()
        if prompt_reused:
            model._prompt_cache[r['reference']] = PROMPTS.pop(key)
        model.prepare_prompt(r['reference'], True)
        PROMPTS[key] = model._prompt_cache[r['reference']]
        while len(PROMPTS) > 4:
            del PROMPTS[next(iter(PROMPTS))]
    if cuda:
        torch.cuda.synchronize()
    load_seconds = time.perf_counter() - start
    if r['engine'] == 'Ming 0.5B':
        fragments = [([text] if cfg.get('ming_raw_text', False) else model.prepare_text(text, 'TTS', language, 24)) for text in r['segments']]
        progress_state = dict(stage='generating', completed=sum(len(fragments[i]) for i in range(len(fragments)) if str(i) in r['skip']), total=sum(map(len, fragments)), text='')
        if not hasattr(model, '_progress_original_generate'):
            model._progress_original_generate = model.model.generate
        def generate_with_progress(*args, **kwargs):
            progress_state.update(stage='generating', text=kwargs.get('text', ''))
            write_progress(out, progress_state)
            audio = model._progress_original_generate(*args, **kwargs)
            progress_state['completed'] += 1
            progress_state['stage'] = 'fragment_done'
            write_progress(out, progress_state)
            return audio
        model.model.generate = generate_with_progress
        import ming_tts as ming_module
        if not hasattr(ming_module, '_original_trim_for_cues'):
            ming_module._original_trim_for_cues = ming_module.trim_trailing_silence
        cue_state = {'rows': [], 'offset': 0.0}
        def trim_with_cues(*args, **kwargs):
            result = ming_module._original_trim_for_cues(*args, **kwargs)
            seconds = result.shape[-1] / model.sample_rate
            cue_state['rows'].append(dict(start=cue_state['offset'], end=cue_state['offset']+seconds, text=progress_state['text']))
            cue_state['offset'] += seconds
            return result
        ming_module.trim_trailing_silence = trim_with_cues
    saved = read_json(out / 'segments.json')
    generation_seconds = 0
    for i, text in enumerate(r['segments']):
        if str(i) in r['skip']:
            continue
        if r['engine'] == 'Ming 0.5B':
            cue_state.update(rows=[], offset=0.0)
        print(f'Segment {i+1}/{len(r["segments"])}', flush=True)
        torch.manual_seed(42 + i)
        start = time.perf_counter()
        if r['engine'] == 'Qwen Python':
            diagnostics.segment=i+1;diagnostics.steps=0
            diagnostics.event('segment_start',seed=42+i,text_characters=len(text))
            write_progress(out, dict(stage='generating', completed=i, total=len(r['segments']), text=text))
            from qwen_quality import GenerationGuard
            from transformers import StoppingCriteriaList
            def heartbeat(steps, seconds):
                diagnostics.touch(steps)
                write_progress(out, dict(stage='generating', completed=i, total=len(r['segments']), text=text,
                    generated_steps=steps, elapsed_seconds=seconds))
            from qwen_quality import generate_with_recovery
            def synthesize_qwen(part):
                guard=GenerationGuard(part,heartbeat)
                diagnostics.event('guard_limits',timeout_seconds=guard.timeout,max_frames=guard.max_frames)
                original_talker_generate=model.model.talker.generate
                def guarded_generate(*args, **kwargs):
                    kwargs['stopping_criteria']=StoppingCriteriaList([guard])
                    return original_talker_generate(*args, **kwargs)
                model.model.talker.generate=guarded_generate
                try:
                    waves, rate = model.generate_voice_clone(text=part, language=language, voice_clone_prompt=prompt)
                    return waves[0], rate
                finally:
                    model.model.talker.generate=original_talker_generate
            def recovery_event(kind, detail):
                diagnostics.event('generation_recovery',kind=kind,detail=detail)
                print(f'Qwen recovery {kind}: {detail}', flush=True)
                write_progress(out, dict(stage='generating', completed=i, total=len(r['segments']),
                    text=text, recovery=kind, recovery_detail=detail))
            audio, sr, qwen_cues = generate_with_recovery(text, synthesize_qwen, recovery_event)
        else:
            audio = model.synthesize(task='TTS', text=text, language_id=language,
                        prompt_wav_path=r['reference'], prompt_text=r['transcript'],
                        use_spk_emb=True, raw_text=cfg.get('ming_raw_text', False), max_length=24)
            audio = audio.detach().float().cpu().numpy().reshape(-1)
            sr = model.sample_rate
        if cuda:
            if diagnostics:diagnostics.wrap(torch.cuda.synchronize,'cuda_sync')()
            else:torch.cuda.synchronize()
        elapsed = time.perf_counter() - start
        generation_seconds += elapsed
        audio = np.asarray(audio, dtype=np.float32)
        if not np.isfinite(audio).all():
            raise RuntimeError('模型输出含无效数值，拒绝保存音频。')
        peak = float(np.max(np.abs(audio)))
        gain = min(1.0, 0.95 / peak) if peak > 0 else 1.0
        audio = audio * gain
        path = out / f'{i:04}.wav'
        if diagnostics:diagnostics.wrap(sf.write,'wav_write')(str(path), audio, sr, subtype='PCM_16')
        else:sf.write(str(path), audio, sr, subtype='PCM_16')
        wav_info(path)
        if r['engine'] == 'Ming 0.5B':
            write_json(out / f'{i:04}.cues.json', cue_state['rows'])
        if r['engine'] == 'Qwen Python':
            write_json(out / f'{i:04}.cues.json', qwen_cues)
        saved[str(i)] = dict(sha256=digest(path), generation_seconds=elapsed, raw_peak=peak, pcm_gain=gain)
        write_json(out / 'segments.json', saved)
        if diagnostics:
            diagnostics.event('segment_saved',audio_seconds=len(audio)/sr,generation_seconds=elapsed,
                allocated_mib=torch.cuda.memory_allocated()/1048576 if cuda else None,
                reserved_mib=torch.cuda.memory_reserved()/1048576 if cuda else None)
            diagnostics.touch()
        if r['engine'] == 'Qwen Python':
            write_progress(out, dict(stage='fragment_done', completed=i+1, total=len(r['segments']), text=text))
    if r['engine'] == 'Ming 0.5B':
        model.model.generate = model._progress_original_generate
        ming_module.trim_trailing_silence = ming_module._original_trim_for_cues
        progress_state.update(stage='finalizing', text='正在保存音频…')
        write_progress(out, progress_state)
    write_json(out / 'metrics.json', dict(load_and_prompt_seconds=load_seconds,
        generation_seconds=generation_seconds, model_reused=model_reused, prompt_reused=prompt_reused, worker_pid=__import__("os").getpid(), torch_version=torch.__version__,
        cuda_peak_allocated_mib=torch.cuda.max_memory_allocated()/1048576 if cuda else None,
        cuda_peak_reserved_mib=torch.cuda.max_memory_reserved()/1048576 if cuda else None,
        output_language=language, qwen_expanded_kv=r['engine']=='Qwen Python' and expanded_kv, cuda_graph_enabled=r['engine']=='Ming 0.5B' and cfg.get('ming_cuda_graph', True), cuda_graph_hits=getattr(getattr(model, '_flow_graph', None), 'hits', 0), device=device, normalization='不启用 Ming FST；同文分段，保留各引擎内部文本处理', seed=42))


if __name__ == '__main__':
    if sys.argv[1] == '--serve':
        import traceback
        for line in sys.stdin:
            request_path = line.strip()
            if not request_path: continue
            response = Path(request_path).parent / 'response.json'
            try:
                main(request_path)
                write_json(response, {'ok': True})
            except Exception:
                write_json(response, {'ok': False, 'error': traceback.format_exc()})
                break
    else:
        main(sys.argv[1])
