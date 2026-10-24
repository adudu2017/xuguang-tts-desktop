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
    for sentence in split_sentences(text):
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
