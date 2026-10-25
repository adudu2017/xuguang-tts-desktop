"""Offline translation with source-language routing and bounded quality retry."""
import sys
import json
from pathlib import Path
from subtitle_quality import detect_language, translation_error
from transcript_tools import save_sidecars


def main():
    import torch
    from transformers import MarianMTModel, MarianTokenizer
    audio = Path(sys.argv[1])
    fallback = sys.argv[2] if len(sys.argv) > 2 else 'English'
    if fallback not in ('Chinese', 'English'): raise ValueError('Unsupported language')
    cues = json.loads(audio.with_suffix('.cues.json').read_text(encoding='utf-8'))
    models, cache, failures = {}, {}, []
    torch.set_num_threads(4)
    for index, cue in enumerate(cues, 1):
        text = cue['text']
        language = detect_language(text) or fallback
        if cue.get('translation') and not translation_error(cue['translation'], language):
            continue
        cue.pop('translation', None)
        try:
            if language not in models:
                name = 'opus-mt-zh-en' if language == 'Chinese' else 'opus-mt-en-zh'
                directory = Path(__file__).parent / 'models' / name
                if not directory.exists(): raise RuntimeError(f'缺少翻译模型 {name}')
                models[language] = (MarianTokenizer.from_pretrained(directory, local_files_only=True),
                                    MarianMTModel.from_pretrained(directory, local_files_only=True).eval())
            tok, model = models[language]
            key = (language, text)
            if key not in cache:
                ids = tok.encode(text, add_special_tokens=False)
                last_error = '没有可翻译内容'
                for attempt, chunk_size in enumerate((350, 120)):
                    parts = []
                    for start in range(0, len(ids), chunk_size):
                        # Use source token IDs directly: decode() defaults to target vocabulary.
                        inputs = tok.prepare_for_model(ids[start:start+chunk_size], return_tensors='pt', prepend_batch_axis=True)
                        options = dict(max_new_tokens=450, num_beams=4)
                        if attempt: options.update(no_repeat_ngram_size=4, repetition_penalty=1.1)
                        with torch.inference_mode(): result = model.generate(**inputs, **options)
                        if result.shape[-1] >= 451 or result[0, -1].item() != tok.eos_token_id:
                            last_error = '译文达到长度上限'; break
                        part = tok.decode(result[0], skip_special_tokens=True)
                        last_error = translation_error(part, language)
                        if last_error: break
                        parts.append(part)
                    else:
                        translated = (' ' if language == 'Chinese' else '').join(parts)
                        last_error = translation_error(translated, language)
                        if not last_error:
                            cache[key] = translated; break
                    print(f'第 {index} 段翻译异常，' + ('缩短分段重试' if not attempt else '保留原文') + f'：{last_error}', flush=True)
                if key not in cache: raise RuntimeError(last_error)
            cue['translation'] = cache[key]
        except Exception as error:
            failures.append(dict(segment=index, error=str(error)))
        print(f'字幕翻译 {index}/{len(cues)}', flush=True)
    # Invalid historical translations are removed, even when retry fails.
    save_sidecars(audio, audio.with_suffix('.txt').read_text(encoding='utf-8-sig'), cues)
    audio.with_suffix('.translation-report.json').write_text(json.dumps(dict(failures=failures, total=len(cues)), ensure_ascii=False, indent=2), encoding='utf-8')
    if failures: raise RuntimeError(f'{len(failures)} 段翻译失败，已保留原文；详见 translation-report.json')
    print('Translated', len(cues), 'cues', flush=True)


if __name__ == '__main__':
    main()
