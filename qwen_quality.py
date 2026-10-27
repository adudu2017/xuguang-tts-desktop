"""Qwen sentence boundaries and conservative generation watchdog."""
import re,time

def split_sentences(text):
    if not text.strip():raise ValueError('请输入需要合成的文字。')
    # Preserve every non-whitespace character; punctuation and quotes stay attached.
    protected=re.sub(r'\b(?:Mr|Mrs|Ms|Dr|Prof|Sr|Jr|St|vs|etc)\.',lambda m:m.group().replace('.', '\ue000'),text,flags=re.I)
    protected=re.sub(r'(?<=\d)\.(?=\d)','\ue000',protected)
    protected=re.sub(r'\b[A-Z]\.(?=\s*[A-Z]\.)',lambda m:m.group().replace('.','\ue000'),protected)
    # Quotes are indivisible units. Apostrophes inside English words are not quotes.
    pairs={'“':'”','‘':'’','「':'」','『':'』'}
    result=[];buffer='';stack=[]
    for index,char in enumerate(protected):
        buffer+=char
        if char in pairs:stack.append(pairs[char])
        elif stack and char==stack[-1]:stack.pop()
        elif char=='"':stack.append('"')
        next_char=protected[index+1:index+2]
        boundary=char in '。！？!?\n' or (char=='.' and (not next_char or next_char.isspace()))
        closed=char in '”’」』"' and bool(re.search(r'[.!?。！？][”’」』"]*$',buffer))
        if not stack and (boundary or closed):
            if buffer.strip():result.append(buffer.replace('\ue000','.').strip())
            buffer=''
    if buffer.strip():result.append(buffer.replace('\ue000','.').strip())
    return result


def text_units(text):
    return len(re.findall(r'[\u3400-\u9fff]|[A-Za-z0-9]+',text))


def pack_sentences(sentences, limit=60):
    """Soft length limit: do not create tiny isolated utterances or split quotes."""
    chunks=[];current=''
    for sentence in sentences:
        combined=(current+' '+sentence).strip()
        if current and text_units(combined)>limit and text_units(current)>=8:
            chunks.append(current);current=''
        current=(current+' '+sentence).strip()
    if current:
        if chunks and text_units(current)<8:chunks[-1]+=' '+current
        else:chunks.append(current)
    return chunks


def prepare_segments(text, limit=60):
    text=re.sub(r'(?m)^\s*(?:---+|___+|\*\*\*+)\s*$','',text)
    text=re.sub(r'(?m)^\s*#{1,6}\s+','',text)
    text=text.replace('**','').replace('*','')
    return pack_sentences(split_sentences(text),limit)

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
    # One bounded retry even for an indivisible quote/single sentence.
    # The model's RNG advances naturally; do not reset the seed and replay the failure.
    parts = pack_sentences(split_sentences(text),limit=20)
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
