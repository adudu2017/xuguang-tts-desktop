import theme as T
from theme import brand_window
import wave,threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk,messagebox
import sounddevice as sd
from modern_ui import Button, ComboBox, TextBox, Slider

class AudioPlayer(ttk.Frame):
    def __init__(self,parent):
        super().__init__(parent)
        self.reader=None;self.stream=None;self.position=0;self.total=0;self.rate=1;self.playing=False;self.dragging=False;self.lock=threading.Lock();self.cues=[];self.ranges=[]
        row=ttk.Frame(self);row.pack(fill='x')
        self.button=Button(row,text='播放',command=self.toggle,state='disabled');self.button.pack(side='left')
        self.clock=tk.StringVar(value='00:00 / 00:00');ttk.Label(row,textvariable=self.clock).pack(side='right')
        self.scale=Slider(row,from_=0,to=1,command=self.scrub);self.scale.pack(side='left',fill='x',expand=True,padx=12)
        self.scale.bind('<ButtonPress-1>',self.drag_start);self.scale.bind('<ButtonRelease-1>',self.drag_end)
        self.text=TextBox(self,height=4,wrap='word',font=('Microsoft YaHei UI',11),relief='flat',padx=12,pady=8,bg=T.SURFACE,spacing3=5)
        self.text.pack(fill='both',expand=True,pady=(8,0));self.text.tag_configure('current',background=T.GOLD_LIGHT,foreground=T.INK);self.text.configure(state='disabled')
        self.after(100,self.tick)
        self.active_cue=None

    def load(self,path,text,cues):
        self.stop_stream()
        self.active_cue=None
        if self.reader:self.reader.close()
        self.reader=wave.open(str(path),'rb');self.total=self.reader.getnframes();self.rate=self.reader.getframerate();self.position=0;self.cues=cues;self.ranges=[]
        self.scale.configure(to=max(.01,self.total/self.rate));self.scale.set(0);self.button.configure(state='normal',text='播放')
        self.text.configure(state='normal');self.text.delete('1.0','end')
        if cues:
            for c in cues:
                start=self.text.index('end-1c');self.text.insert('end',c['text']+ ('\n'+c['translation'] if c.get('translation') else '')+'\n\n');end=self.text.index('end-1c');self.ranges.append((start,end))
        else:self.text.insert('1.0',text or '未找到对应文字。')
        self.text.configure(state='disabled')

    def stop_stream(self):
        self.playing=False
        if self.stream:
            self.stream.stop();self.stream.close();self.stream=None

    def toggle(self):
        if not self.reader:return
        if self.playing:
            self.stop_stream();self.button.configure(text='播放');return
        if self.position>=self.total:self.position=0
        width=self.reader.getsampwidth();dtype={1:'uint8',2:'int16',3:'int24',4:'int32'}.get(width)
        def callback(out,frames,timing,status):
            with self.lock:
                self.reader.setpos(min(self.position,self.total));data=self.reader.readframes(frames);self.position+=len(data)//(width*self.reader.getnchannels())
            silence=b'\x80' if width==1 else b'\0'
            out[:]=data+silence*(len(out)-len(data))
            if self.position>=self.total:self.playing=False;raise sd.CallbackStop
        try:
            if self.stream:self.stop_stream()
            self.stream=sd.RawOutputStream(samplerate=self.rate,channels=self.reader.getnchannels(),dtype=dtype,callback=callback,blocksize=1024)
            self.playing=True;self.stream.start();self.button.configure(text='暂停')
        except Exception as e:self.stop_stream();messagebox.showerror('无法播放',str(e),parent=self)

    def drag_start(self,event):self.dragging=True
    def scrub(self,value):
        if self.dragging:
            with self.lock:self.position=min(self.total,max(0,int(float(value)*self.rate)))
            self.highlight(float(value))
    def drag_end(self,event):
        self.scrub(self.scale.get());self.dragging=False
    def highlight(self,seconds):
        active=next((i for i,c in enumerate(self.cues) if c['start']<=seconds<c['end']),None)
        if active==self.active_cue:return
        self.active_cue=active
        self.text.tag_remove('current','1.0','end')
        if active is not None:
            self.text.tag_add('current',*self.ranges[active]);self.text.see(self.ranges[active][0])
    def tick(self):
        seconds=self.position/self.rate;duration=self.total/self.rate
        self.clock.set(f'{int(seconds)//60:02}:{int(seconds)%60:02} / {int(duration)//60:02}:{int(duration)%60:02}')
        if not self.dragging:self.scale.set(seconds);self.highlight(seconds)
        if not self.playing:self.button.configure(text='播放')
        self.after(100,self.tick)
    def close(self):
        self.stop_stream()
        if self.reader:self.reader.close();self.reader=None
