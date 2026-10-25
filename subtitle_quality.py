"""Conservative language and subtitle checks; no model dependencies."""
import re

def detect_language(text):
    chinese = len(re.findall(r'[\u3400-\u9fff]', text))
    latin = len(re.findall(r'[A-Za-z]', text))
    if chinese >= 4 and chinese >= latin: return 'Chinese'
    if latin >= 8 and latin >= chinese * 5: return 'English'
    return None

def validate_language(text, selected):
    detected = detect_language(text)
    if detected and detected != selected:
        label = '中文' if detected == 'Chinese' else '英文'
        raise ValueError(f'稿件主要是{label}，请将输出语言改为{label}，或先翻译稿件。输出语言选项不会自动翻译朗读内容。')

def translation_error(text, source_language=None):
    text = str(text).strip()
    letters = re.findall(r'[A-Za-z\u3400-\u9fff]', text)
    if not letters: return '译文为空或只有标点'
    if re.search(r'([^\w\s])\1{7,}', text): return '译文含大量重复标点'
    if re.search(r'\b([A-Za-z]+)(?:\s+\1){5,}\b', text, re.I): return '译文含异常重复词语'
    if len(text) > 30 and len(letters) / len(text) < .15: return '译文标点比例异常'
    if source_language == 'Chinese' and not re.search(r'[A-Za-z]', text): return '译文缺少英文内容'
    if source_language == 'English' and not re.search(r'[\u3400-\u9fff]', text): return '译文缺少中文内容'
    return None

def validate_cues(cues):
    for index, cue in enumerate(cues, 1):
        if 'translation' in cue:
            error = translation_error(cue['translation'], detect_language(cue.get('text', '')))
            if error: raise ValueError(f'第 {index} 段字幕异常：{error}。请重新翻译后再导出。')
