"""Qwen sentence boundaries and conservative generation watchdog."""
import re,time

def split_sentences(text):
    if not text.strip():raise ValueError('请输入需要合成的文字。')
    # Preserve every non-whitespace character; punctuation and quotes stay attached.
    protected=re.sub(r'\b(?:Mr|Mrs|Ms|Dr|Prof|Sr|Jr|St|vs|etc)\.',lambda m:m.group().replace('.', '\ue000'),text,flags=re.I)
    protected=re.sub(r'(?<=\d)\.(?=\d)','\ue000',protected)
    protected=re.sub(r'\b[A-Z]\.(?=\s*[A-Z]\.)',lambda m:m.group().replace('.','\ue000'),protected)
    parts=re.split(r'(?<=[.!?。！？])([\"”’\']*)(?:\s+|(?=[\u4e00-\u9fff]))|\n+',protected)
    result=[]
    for part in parts:
        if not part:continue
        part=part.replace('\ue000','.').strip()
        if not part:continue
        if all(c in '\"”’\'' for c in part) and result:result[-1]+=part
        else:result.append(part)
    return result

def prepare_segments(text, limit=60):
    text=re.sub(r'(?m)^\s*(?:---+|___+|\*\*\*+)\s*$','',text)
    text=re.sub(r'(?m)^\s*#{1,6}\s+','',text)
    text=text.replace('**','').replace('*','')
    chunks=[];current=''
    sentences=split_sentences(text)
    def short(sentence):
        return bool(re.search(r'[.!?。！？][\"”’\']*$', sentence)) and len(re.sub(r'[^\w\u4e00-\u9fff]', '', sentence)) <= 6
    for index, sentence in enumerate(sentences):
        # Isolate clusters of very short utterances before normal paragraph packing.
        risk=short(sentence) and ((index > 0 and short(sentences[index-1])) or
                                  (index+1 < len(sentences) and short(sentences[index+1])))
        if risk:
            if current: chunks.append(current);current=''
            chunks.append(sentence)
            continue
        combined=current+' '+sentence
        units=len(combined.split())+len(re.findall(r'[\u4e00-\u9fff]',combined))
        if current and units>limit:
            chunks.append(current);current=''
        current=(current+' '+sentence).strip()
    if current:chunks.append(current)
    return chunks

class GenerationGuard:
    def __init__(self,text,emit=None,timeout=None,max_frames=None):
        words=len(re.findall(r"\b\w+\b",text))+len(re.findall(r'[\u4e00-\u9fff]',text));self.started=time.monotonic();self.last=0;self.steps=0;self.emit=emit
        self.timeout=timeout or max(120,words*5)
        self.max_frames=max_frames or max(500,words*35)
    def __call__(self,input_ids,scores,**kwargs):
        self.steps+=1;elapsed=time.monotonic()-self.started
        if self.steps>=self.max_frames or elapsed>self.timeout:
            raise RuntimeError(f'QWEN_GENERATION_GUARD: 本段生成异常过长（{self.steps}步，{elapsed:.1f}秒），已停止且不会保存为完整音频。请检查文案或拆分本段后重试。')
        if self.emit and elapsed-self.last>=1:
            self.last=elapsed;self.emit(self.steps,elapsed)
        return False


def generate_with_recovery(text, synthesize, emit=None):
    """Bounded sentence retry; never accept partial audio after watchdog failure."""
    try:
        audio, rate = synthesize(text)
        return audio, rate, [dict(start=0., end=len(audio)/rate, text=text)]
    except RuntimeError as error:
        if 'QWEN_GENERATION_GUARD:' not in str(error): raise
        if emit: emit('retry', str(error))
    parts = split_sentences(text)
    if len(parts) < 2:
        raise RuntimeError('QWEN_GENERATION_GUARD: 单句生成异常，无法按完整句子拆分。请缩短该句后重试；已完成的分段仍保留。')
    import numpy as np
    chunks, cues, offset, rate = [], [], 0., None
    for index, part in enumerate(parts):
        if emit: emit('sentence', f'{index+1}/{len(parts)}')
        audio, current_rate = synthesize(part)
        if rate is not None and current_rate != rate: raise RuntimeError('重试音频采样率不一致')
        rate = current_rate
        if len(audio) == 0 or not np.isfinite(audio).all(): raise RuntimeError('重试生成无效音频')
        seconds = len(audio)/rate
        cues.append(dict(start=offset, end=offset+seconds, text=part))
        chunks.append(audio); offset += seconds
    return np.concatenate(chunks), rate, cues
