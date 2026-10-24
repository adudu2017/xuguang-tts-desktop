"""Offline English -> Chinese subtitle translation; runs in Ming environment."""
import sys,json,re
from pathlib import Path
import torch
from transformers import MarianMTModel,MarianTokenizer
from transcript_tools import save_sidecars
p=Path(sys.argv[1]);model_dir=Path(__file__).parent/'models/opus-mt-en-zh'
tok=MarianTokenizer.from_pretrained(model_dir,local_files_only=True)
m=MarianMTModel.from_pretrained(model_dir,local_files_only=True).eval()
torch.set_num_threads(4)
cues=json.loads(p.with_suffix('.cues.json').read_text(encoding='utf-8'))
cache={}
for c in cues:
    if c.get('translation'):continue
    text=c['text']
    if text not in cache:
        # Keep each model input below its token limit, translating all chunks.
        ids=tok.encode(text,add_special_tokens=False);parts=[]
        for i in range(0,len(ids),350):
            inputs=tok(tok.decode(ids[i:i+350],skip_special_tokens=True),return_tensors='pt')
            with torch.inference_mode():out=m.generate(**inputs,max_new_tokens=450,num_beams=4)
            parts.append(tok.decode(out[0],skip_special_tokens=True))
        cache[text]=''.join(parts)
    c['translation']=cache[text]
save_sidecars(p,p.with_suffix('.txt').read_text(encoding='utf-8-sig'),cues)
print('Translated',len(cues),'cues',flush=True)
