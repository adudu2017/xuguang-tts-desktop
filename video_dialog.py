import theme as T
from theme import brand_window
"""Background selection and asynchronous MP4 export UI."""
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageOps, ImageTk
from modern_ui import Button, ComboBox
from video_export import export_mp4, ExportCancelled
from export_names import next_name
from background_music import TRACKS, music_path


class VideoDialog(tk.Toplevel):
    def __init__(self, parent, base, audio, cues):
        super().__init__(parent)
        brand_window(self)
        self.title('导出字幕视频（MP4）')
        x=max(0,parent.winfo_rootx()+(parent.winfo_width()-740)//2)
        y=max(20,parent.winfo_rooty()+(parent.winfo_height()-760)//2)
        self.geometry(f'740x840+{x}+{y}'); self.resizable(False, False)
        self.configure(bg=T.BG); self.transient(parent)
        self.owner=parent; self.base=Path(base); self.audio=audio; self.cues=[dict(c) for c in cues]
        self.theme_choice=tk.StringVar(value=parent.config_values.get('video_theme','暖金书页'))
        self.default=T.background_path(self.base,self.theme_choice.get())
        configured=parent.config_values.get('video_background', '')
        self.background=Path(configured) if configured and Path(configured).is_file() else self.default
        self.is_running=False; self.cancel=threading.Event(); self.events=queue.Queue(); self.closing=False
        frame=ttk.Frame(self,padding=24); frame.pack(fill='both',expand=True)
        ttk.Label(frame,text='把声音，变成可随身播放的视频',font=('Microsoft YaHei UI',17,'bold')).pack(anchor='w')
        ttk.Label(frame,text='1080p · 中英文字幕直接显示在画面中 · 无需外挂字幕',foreground=T.MUTED).pack(anchor='w',pady=(6,12))
        self.preview=ttk.Label(frame,anchor='center'); self.preview.pack(fill='x')
        self.background_name=tk.StringVar(); ttk.Label(frame,textvariable=self.background_name,foreground=T.MUTED).pack(anchor='w',pady=(8,8))
        row=ttk.Frame(frame); row.pack(fill='x')
        self.theme_combo=ComboBox(row,textvariable=self.theme_choice,values=list(T.VIDEO_THEMES),state='readonly',width=12)
        self.theme_combo.pack(side='left',padx=(0,10));self.theme_combo.bind('<<ComboboxSelected>>',self.set_theme)
        self.choose_button=Button(row,text='选择图片',command=self.choose); self.choose_button.pack(side='left')
        self.reset_button=Button(row,text='恢复默认背景',command=self.reset); self.reset_button.pack(side='left',padx=10)
        ttk.Label(frame,text='图片保持比例，空余区域补深色。字幕显示在下方，预览仅展示背景。',foreground=T.MUTED).pack(anchor='w',pady=(12,8))
        row=ttk.Frame(frame); row.pack(fill='x',pady=(8,8))
        ttk.Label(row,text='背景音乐').pack(side='left')
        saved_music=parent.config_values.get('video_music','关闭背景音乐')
        self.music_choice=tk.StringVar(value=saved_music if saved_music in TRACKS else '关闭背景音乐')
        self.music_combo=ComboBox(row,textvariable=self.music_choice,values=list(TRACKS),state='readonly',width=28)
        self.music_combo.pack(side='left',padx=10)
        ttk.Label(frame,text='人声优先 · 轻柔配乐 · 说话时自动降低音乐音量',foreground=T.MUTED).pack(anchor='w')
        self.status=tk.StringVar(value='选择保存位置，即可导出')
        ttk.Label(frame,textvariable=self.status,wraplength=680).pack(anchor='w',pady=(4,8))
        self.progress=ttk.Progressbar(frame,maximum=100); self.progress.pack(fill='x')
        row=ttk.Frame(frame);row.pack(fill='x',pady=(16,0))
        self.start_button=Button(row,text='导出 MP4',style='Primary.TButton',command=self.start);self.start_button.pack(side='right')
        self.cancel_button=Button(row,text='取消导出',state='disabled',command=self.cancel.set);self.cancel_button.pack(side='right',padx=10)
        try:self.refresh()
        except Exception:self.destroy();raise
        self.protocol('WM_DELETE_WINDOW',self.close);self.after(150,self.poll)

    def refresh(self):
        with Image.open(self.background) as src:
            picture=ImageOps.contain(ImageOps.exif_transpose(src).convert('RGB'),(640,360))
        self.photo=ImageTk.PhotoImage(picture);self.preview.configure(image=self.photo)
        self.background_name.set('叙光 · '+self.theme_choice.get() if self.background==self.default else '自定义 · '+self.background.name)

    def set_theme(self,event=None):
        if self.is_running:return
        try:
            self.default=T.background_path(self.base,self.theme_choice.get())
            self.select_background(self.default)
        except Exception as e:messagebox.showerror('主题不可用',str(e),parent=self)

    def select_background(self, path):
        with Image.open(path) as src: src.verify()
        old=self.background
        try:self.background=Path(path);self.refresh()
        except Exception:self.background=old;raise
        self.owner.config_values['video_background']='' if self.background==self.default else str(self.background)
        self.owner.config_values['video_theme']=self.theme_choice.get()
        self.owner.persist()

    def choose(self):
        path=filedialog.askopenfilename(parent=self,title='选择视频背景图片',filetypes=[('图片','*.png *.jpg *.jpeg *.webp *.bmp')])
        if path:
            try:self.select_background(path)
            except Exception as e:messagebox.showerror('无法读取图片',str(e),parent=self)

    def reset(self):
        try:self.select_background(self.default)
        except Exception as e:messagebox.showerror('默认背景不可用',str(e),parent=self)

    def start(self):
        if self.is_running:return
        try:
            music_choice=self.music_choice.get()
            music_path(self.base,music_choice)
            self.owner.config_values['video_music']=music_choice
            self.owner.persist()
        except Exception as e:
            messagebox.showerror('背景音乐不可用',str(e),parent=self);return
        try:suggested=next_name(self.base,'叙光字幕视频','.mp4')
        except Exception as e:
            messagebox.showerror('无法生成文件名',str(e),parent=self);return
        dest=filedialog.asksaveasfilename(parent=self,title='保存字幕视频',defaultextension='.mp4',initialfile=suggested,filetypes=[('MP4 视频','*.mp4')])
        if not dest:return
        if Path(dest).suffix.lower()!='.mp4':
            messagebox.showerror('文件格式','请使用 .mp4 文件扩展名。',parent=self);return
        self.is_running=True;self.cancel.clear();self.progress['value']=0;self.status.set('正在导出，随时可以取消…')
        for button in (self.choose_button,self.reset_button,self.start_button):button.configure(state='disabled')
        self.cancel_button.configure(state='normal')
        self.theme_combo.configure(state='disabled')
        self.music_combo.configure(state='disabled')
        background=self.background
        def work():
            try:
                export_mp4(self.audio,self.cues,background,dest,self.base,self.cancel,lambda value:self.events.put(('progress',value)),music_choice=music_choice)
                self.events.put(('done',dest))
            except ExportCancelled as e:self.events.put(('cancelled',str(e)))
            except Exception as e:self.events.put(('error',str(e)))
        threading.Thread(target=work,daemon=True).start()

    def poll(self):
        try:
            while True:
                kind,value=self.events.get_nowait()
                if kind=='progress':
                    self.progress['value']=value*100;self.status.set(f'正在导出 · {value:.0%}');continue
                self.is_running=False;self.cancel_button.configure(state='disabled')
                self.theme_combo.configure(state='readonly')
                self.music_combo.configure(state='readonly')
                for button in (self.choose_button,self.reset_button,self.start_button):button.configure(state='normal')
                if kind=='done':self.status.set('已保存：'+value)
                elif kind=='cancelled':self.status.set(value)
                else:
                    self.status.set('导出失败')
                    if not self.closing:messagebox.showerror('导出失败',value,parent=self)
        except queue.Empty:pass
        if self.closing and not self.is_running:self.destroy();return
        self.after(150,self.poll)

    def close(self):
        if self.is_running:self.closing=True;self.cancel.set();self.status.set('正在取消导出…')
        else:self.destroy()
