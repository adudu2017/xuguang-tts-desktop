"""Transcript, real segment timing and SRT sidecars (no guessed word alignment)."""
import json
from pathlib import Path
import wave

def duration(p):
    with wave.open(str(p),'rb') as f:return f.getnframes()/f.getframerate()

def collect(wav):
    wav=Path(wav);folder=wav.parent
    job=json.loads((folder.parent/'job.json').read_text(encoding='utf-8'))
    if job.get('config', {}).get('output_language', 'Chinese') == 'Chinese' and job.get('config', {}).get('chinese_subtitles') == '不生成字幕':
        return job['text'], []
    cues=[];offset=0
    for i,text in enumerate(job['segments']):
        part=folder/f'{i:04}.wav'
        if not part.exists():return job['text'],[]
        seconds=duration(part);cp=folder/f'{i:04}.cues.json'
        if cp.exists():
            for c in json.loads(cp.read_text(encoding='utf-8')):
                cues.append(dict(start=offset+c['start'],end=offset+c['end'],text=c['text']))
        else:cues.append(dict(start=offset,end=offset+seconds,text=text))
        offset+=seconds
    return job['text'],cues

def timestamp(t):
    ms=round(t*1000);s,ms=divmod(ms,1000);m,s=divmod(s,60);h,m=divmod(m,60)
    return f'{h:02}:{m:02}:{s:02},{ms:03}'

def save_sidecars(wav,text,cues):
    p=Path(wav);p.with_suffix('.txt').write_text(text,encoding='utf-8-sig')
    if not cues:
        for ext in ('.cues.json', '.srt'):
            p.with_suffix(ext).unlink(missing_ok=True)
        return
    p.with_suffix('.cues.json').write_text(json.dumps(cues,ensure_ascii=False,indent=2),encoding='utf-8')
    blocks=[]
    for i,c in enumerate(cues,1):
        body=c['text']+ ('\n'+c['translation'] if c.get('translation') else '')
        blocks.append(f"{i}\n{timestamp(c['start'])} --> {timestamp(c['end'])}\n{body}\n")
    p.with_suffix('.srt').write_text('\n'.join(blocks),encoding='utf-8-sig')

def load(wav):
    p=Path(wav)
    text,cues='',[]
    if (p.parent.parent/'job.json').exists():text,cues=collect(p)
    if p.with_suffix('.txt').exists():text=p.with_suffix('.txt').read_text(encoding='utf-8-sig')
    if p.with_suffix('.cues.json').exists():cues=json.loads(p.with_suffix('.cues.json').read_text(encoding='utf-8'))
    return text,cues
