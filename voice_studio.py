import theme as T
from theme import brand_window
"""Local microphone recording and reusable reference voice profiles."""
import array
import json
from pathlib import Path
import shutil
import tempfile
import time
import uuid
import wave
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import winsound
import sounddevice as sd
from modern_ui import Button, ComboBox, TextBox, Slider, Entry
from export_names import next_name

SCRIPTS = {
    '中文': '今天的天气很好，阳光透过窗户，轻轻落在桌面上。我用自然的声音，记录这一刻的心情。',
    '英文': 'The morning sun shines through my window. I take a quiet breath and smile. Today is a good day to share a little story with a friend.',
}

class VoiceStudio(tk.Toplevel):
    def __init__(self, parent, root, on_save):
        super().__init__(parent)
        brand_window(self)
        self.title('制作音色'); self.geometry('720x560'); self.minsize(680,540)
        self.root=Path(root);self.on_save=on_save;self.stream=None;self.chunks=[];self.temp=tempfile.TemporaryDirectory(prefix='voicedesk-voice-');self.wav=Path(self.temp.name)/'reference.wav';self.recorded_text=None;self.recorded_language=None;self.rate=48000;self.frames=0;self.overflows=0
        f=ttk.Frame(self,padding=24);f.pack(fill='both',expand=True)
        row=ttk.Frame(f);row.pack(fill='x')
        ttk.Label(row,text='为你的声音留一份参考',font=('Microsoft YaHei UI',18,'bold')).pack(side='left')
        self.language=tk.StringVar(value='中文')
        self.lang=ComboBox(row,textvariable=self.language,values=list(SCRIPTS),state='readonly',width=7);self.lang.pack(side='right');self.lang.bind('<<ComboboxSelected>>',self.script)
        ttk.Label(f,text='安静环境、自然语速，按下录音后朗读下方文字。建议约 6–20 秒，最长 30 秒。',wraplength=640).pack(anchor='w',pady=(16,8))
        self.text=TextBox(f,height=5,wrap='word',font=('Microsoft YaHei UI',11),padx=12,pady=12,relief='flat');self.text.pack(fill='both',expand=True);self.script()
        row=ttk.Frame(f);row.pack(fill='x',pady=12)
        ttk.Label(row,text='麦克风').pack(side='left')
        self.devices={};self.device=tk.StringVar()
        try:
            for i,d in enumerate(sd.query_devices()):
                if d['max_input_channels']>0:self.devices[f'{i} · {d["name"]}']=i
            default=sd.default.device[0]
            self.device.set(next((k for k,v in self.devices.items() if v==default),next(iter(self.devices),'')))
        except Exception:pass
        self.mic=ComboBox(row,textvariable=self.device,values=list(self.devices),state='readonly');self.mic.pack(side='left',fill='x',expand=True,padx=10)
        row=ttk.Frame(f);row.pack(fill='x')
        self.record=Button(row,text='开始录音',command=self.start);self.record.pack(side='left')
        self.stop_button=Button(row,text='结束录音',command=self.stop,state='disabled');self.stop_button.pack(side='left',padx=8)
        self.listen=Button(row,text='试听',command=self.play,state='disabled');self.listen.pack(side='left')
        self.import_button=Button(row,text='导入 WAV',command=self.import_wav);self.import_button.pack(side='right')
        self.status=tk.StringVar(value='尚未录音 · 录音只保存在本机')
        ttk.Label(f,textvariable=self.status,wraplength=640).pack(anchor='w',pady=12)
        row=ttk.Frame(f);row.pack(fill='x')
        ttk.Label(row,text='音色名称').pack(side='left')
        self.name=tk.StringVar(value=next_name(self.root.parent,'叙光音色'));Entry(row,textvariable=self.name).pack(side='left',fill='x',expand=True,padx=10)
        self.save_button=Button(row,text='保存音色',command=self.save,state='disabled');self.save_button.pack(side='right')
        self.protocol('WM_DELETE_WINDOW',self.close)

    def script(self,event=None):
        self.text.delete('1.0','end');self.text.insert('1.0',SCRIPTS[self.language.get()])

    def start(self):
        if self.stream:return
        text=self.text.get('1.0','end').strip()
        if not text:return messagebox.showerror('录音','请先填写要朗读的文字。',parent=self)
        if not self.devices:return messagebox.showerror('录音','未找到麦克风，请连接后重新打开制作音色。',parent=self)
        winsound.PlaySound(None,0);self.chunks=[];self.frames=0;self.overflows=0
        def callback(data,frames,timing,status):
            if status:self.overflows+=1
            if self.frames < self.rate*30:self.chunks.append(bytes(data));self.frames+=frames
        try:
            device=self.devices[self.device.get()];self.rate=int(sd.query_devices(device)['default_samplerate'])
            self.stream=sd.RawInputStream(device=device,samplerate=self.rate,channels=1,dtype='int16',callback=callback)
            self.stream.start()
        except Exception as e:
            if self.stream:self.stream.close();self.stream=None
            return messagebox.showerror('无法录音',str(e),parent=self)
        self.recorded_text=text;self.recorded_language=self.language.get();self.started=time.monotonic()
        for w in (self.record,self.listen,self.save_button,self.import_button):w.configure(state='disabled')
        self.lang.configure(state='disabled');self.mic.configure(state='disabled');self.text.configure(state='disabled');self.stop_button.configure(state='normal');self.tick()

    def tick(self):
        if not self.stream:return
        elapsed=time.monotonic()-self.started;self.status.set(f'正在录音 · {elapsed:.1f} 秒 / 30 秒')
        if elapsed>=30:self.stop()
        else:self.after(100,self.tick)

    def stop(self):
        if not self.stream:return
        self.stream.stop();self.stream.close();self.stream=None
        self.lang.configure(state='readonly');self.mic.configure(state='readonly');self.text.configure(state='normal');self.record.configure(state='normal');self.import_button.configure(state='normal');self.stop_button.configure(state='disabled')
        data=b''.join(self.chunks)
        with wave.open(str(self.wav),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(self.rate);f.writeframes(data)
        seconds=len(data)/2/self.rate;samples=array.array('h',data);peak=max(map(abs,samples),default=0)
        good=seconds>=3 and peak>=100 and not self.overflows
        clipped=sum(abs(v)>=32767 for v in samples)
        self.status.set(f'已录制 {seconds:.1f} 秒。'+('请试听后保存。' if good else '录音过短、过轻或有丢帧，请重新录制。')+(' 检测到削波，建议降低麦克风音量重录。' if clipped else ''))
        self.listen.configure(state='normal');self.save_button.configure(state='normal' if good else 'disabled')

    def import_wav(self):
        path=filedialog.askopenfilename(parent=self,filetypes=[('PCM WAV','*.wav')])
        if not path:return
        try:
            with wave.open(path,'rb') as f:
                if f.getcomptype()!='NONE' or f.getnframes()==0:raise ValueError('需要非空 PCM WAV')
            shutil.copy2(path,self.wav)
            self.recorded_text=None;self.recorded_language=None
            self.text.delete('1.0','end');self.status.set('已导入。请填写这段录音实际朗读的原文，再保存。')
            self.listen.configure(state='normal');self.save_button.configure(state='normal')
        except Exception as e:messagebox.showerror('导入失败',str(e),parent=self)

    def play(self):
        if self.wav.exists():winsound.PlaySound(str(self.wav),winsound.SND_FILENAME|winsound.SND_ASYNC)

    def save(self):
        name=self.name.get().strip();text=self.text.get('1.0','end').strip()
        if not name or not text or not self.wav.exists():return messagebox.showerror('无法保存','请填写音色名称、录音原文，并完成录音或导入。',parent=self)
        if self.recorded_text is not None and (text!=self.recorded_text or self.language.get()!=self.recorded_language):return messagebox.showerror('文案已改变','请恢复录音时的文案与语言，或重新录制。',parent=self)
        folder=self.root/uuid.uuid4().hex;folder.mkdir(parents=True)
        try:
            shutil.copy2(self.wav,folder/'reference.wav')
            (folder/'voice.json').write_text(json.dumps(dict(name=name,audio='reference.wav',text=text,language=self.language.get()),ensure_ascii=False,indent=2),encoding='utf-8')
        except Exception as e:return messagebox.showerror('保存失败',str(e),parent=self)
        self.on_save(folder.name);self.close()

    def close(self):
        if self.stream:self.stream.stop();self.stream.close();self.stream=None
        winsound.PlaySound(None,0);self.temp.cleanup();self.destroy()
