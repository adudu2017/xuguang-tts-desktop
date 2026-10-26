import theme as T
from theme import brand_window
import ctypes
import os
from pathlib import Path
import queue
import shutil
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import winsound
import core
from voice_studio import VoiceStudio
from audio_player import AudioPlayer
import transcript_tools
from modern_ui import Button, ComboBox, TextBox, Slider
from video_dialog import VideoDialog
from export_names import next_name
from appearance_dialog import AppearanceDialog

BASE = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
core.ROOT = BASE
DATA = BASE / 'data'
DATA.mkdir(exist_ok=True)
SETTINGS = DATA / 'settings.json'
ENGINE = 'Ming 0.5B'
ENGINE_LABELS = {'Ming 0.5B': 'Ming 0.5B', 'Qwen3-TTS': 'Qwen Python'}

SAMPLE_TEXT = '小兔子在森林里发现了一颗小小的种子。它把种子埋进泥土，每天给它浇水。\n过了几天，泥土里冒出一片嫩绿的叶子。小兔子高兴地叫来小松鼠，一起守护这株小苗。\n春风轻轻吹过，小苗终于开出一朵黄色的小花。小松鼠说：“原来，耐心和关爱，真的能让美好的事情慢慢长大！”'

ENGLISH_SAMPLE = 'A little rabbit found a seed in the forest. Every morning, she gave it water. One day, a yellow flower opened in the sunshine.'

class App(tk.Tk):
    def __init__(self):
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('VoiceDesk.LocalTTS')
        super().__init__()
        self.title('叙光')
        brand_window(self, default=True)
        self.geometry('960x920')
        self.minsize(900, 880)
        self.configure(bg=T.BG)
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('Treeview', background=T.SURFACE, fieldbackground=T.SURFACE, foreground=T.INK, rowheight=30)
        style.map('Treeview', background=[('selected', T.PRIMARY)], foreground=[('selected', T.WHITE)])
        style.configure('Treeview.Heading', background=T.SECONDARY, foreground=T.INK)
        style.map('Treeview.Heading', background=[('active', T.SECONDARY_HOVER)])
        style.configure('TEntry', selectbackground=T.PRIMARY, selectforeground=T.WHITE)
        style.configure('Vertical.TScrollbar', background=T.SECONDARY, troughcolor=T.BG, arrowcolor=T.PRIMARY)
        self.option_add('*selectBackground', T.GOLD_LIGHT)
        self.option_add('*selectForeground', T.INK)
        self.option_add('*Font', ('Microsoft YaHei UI', 11))
        self.option_add('*TCombobox*Listbox.font', ('Microsoft YaHei UI', 11))
        style.configure('.', font=('Microsoft YaHei UI', 11), background=T.BG, foreground=T.INK)
        style.configure('TButton', padding=(14, 8), relief='flat', borderwidth=0, background=T.SECONDARY)
        style.map('TButton', background=[('active', T.SECONDARY_HOVER)])
        style.configure('Primary.TButton', background=T.PRIMARY, foreground=T.SURFACE, padding=(24, 12))
        style.map('Primary.TButton', background=[('disabled', T.DISABLED), ('active', T.PRIMARY_HOVER)])
        style.configure('TEntry', padding=8, fieldbackground=T.SURFACE, borderwidth=0)
        style.configure('TProgressbar', background=T.GOLD, troughcolor=T.TRACK, borderwidth=0)
        self.config_values = dict(ming_python='', ming_model='', ming_source='', device='cuda:0')
        if SETTINGS.exists():
            self.config_values.update(core.read_json(SETTINGS))
        saved_engine = self.config_values.get('default_engine', ENGINE)
        self.engine_choice = tk.StringVar(value=next((label for label, key in ENGINE_LABELS.items() if key == saved_engine), 'Ming 0.5B'))
        self.active_engine = ENGINE_LABELS[self.engine_choice.get()]
        self.events = queue.Queue()
        self.busy = False
        self.runner = None
        self.output = None
        self.output_text = ''
        self.output_cues = []
        self.logs = []
        self.reference = tk.StringVar(value=self.config_values.get('reference_wav', ''))
        self.language = tk.StringVar(value='英文' if self.config_values.get('output_language') == 'English' else '中文')
        self.subtitle_mode = tk.StringVar(value=self.config_values.get('chinese_subtitles', '仅中文字幕'))
        self.voice_choice = tk.StringVar(value='自定义录音')
        self.voice_window = None
        self.video_window = None
        self.appearance_window = None
        self.status = tk.StringVar(value='准备就绪')
        self.result_label = tk.StringVar(value='生成后，即可在这里试听与保存')
        self.count = tk.StringVar(value='0 字')
        shell = ttk.Frame(self, padding=(32, 22))
        shell.pack(fill='both', expand=True)
        header = ttk.Frame(shell)
        header.pack(fill='x', pady=(0, 20))
        ttk.Label(header, text='叙光', font=('Microsoft YaHei UI', 26, 'bold')).pack(side='left')
        ttk.Label(header, text='让文字，用你的声音说出来', foreground=T.MUTED).pack(side='left', padx=18)
        Button(header, text='设置', command=self.settings).pack(side='right')
        Button(header, text='历史', command=self.history).pack(side='right', padx=8)
        Button(header, text='换肤', command=self.appearance, width=90).pack(side='right')
        row = ttk.Frame(shell)
        row.pack(fill='x')
        ttk.Label(row, text='参考音色', font=('Microsoft YaHei UI', 12, 'bold')).pack(side='left')
        self.voice_combo = ComboBox(row, textvariable=self.voice_choice, state='readonly', width=14)
        self.voice_combo.pack(side='left', padx=10)
        self.voice_combo.bind('<<ComboboxSelected>>', self.select_voice)
        Button(row, text='制作音色', command=self.make_voice).pack(side='left')
        Button(row, text='管理音色', command=self.manage_voice).pack(side='right')
        ttk.Label(shell, text='录音对应文字', foreground=T.MUTED).pack(anchor='w')
        self.transcript = self.editor(shell, 3)
        self.transcript.pack(fill='x', pady=(8, 18))
        self.transcript.insert('1.0', self.config_values.get('reference_text', ''))
        self.refresh_voices(self.config_values.get('voice_id'))
        row = ttk.Frame(shell)
        row.pack(fill='x')
        ttk.Label(row, text='想说的话', font=('Microsoft YaHei UI', 12, 'bold')).pack(side='left')
        ttk.Label(row, textvariable=self.count, foreground=T.MUTED).pack(side='left', padx=8)
        ttk.Label(row, text='输出语言', foreground=T.MUTED).pack(side='left')
        ComboBox(row, textvariable=self.language, values=['中文','英文'], state='readonly', width=5).pack(side='left', padx=6)
        ttk.Label(row, text='模型', foreground=T.MUTED).pack(side='left', padx=(10,6))
        self.engine_combo = ComboBox(row, textvariable=self.engine_choice, values=list(ENGINE_LABELS), state='readonly', width=10)
        self.engine_combo.pack(side='left')
        Button(row, text='示例故事', command=self.sample).pack(side='right')
        Button(row, text='导入文字', command=self.import_text).pack(side='right', padx=8)
        self.subtitle_row = ttk.Frame(shell)
        self.subtitle_row.pack(fill='x', pady=(8, 0))
        ttk.Label(self.subtitle_row, text='中文字幕', foreground=T.MUTED).pack(side='left')
        self.subtitle_combo = ComboBox(self.subtitle_row, textvariable=self.subtitle_mode, values=['仅中文字幕', '中英双语字幕', '不生成字幕'], state='readonly', width=14)
        self.subtitle_combo.pack(side='left', padx=10)
        self.language.trace_add('write', lambda *_: self.subtitle_combo.configure(state='readonly' if self.language.get() == '中文' else 'disabled'))
        self.subtitle_combo.configure(state='readonly' if self.language.get() == '中文' else 'disabled')
        self.text = self.editor(shell, 4)
        self.text.pack(fill='both', expand=True, pady=(8, 16))
        self.text.bind('<<Modified>>', self.text_changed)
        row = ttk.Frame(shell)
        row.pack(fill='x')
        self.generate = Button(row, text='生成语音', style='Primary.TButton', command=self.start)
        self.generate.pack(side='left')
        self.cancel = Button(row, text='取消', command=self.stop, state='disabled')
        self.cancel.pack(side='left', padx=10)
        ttk.Label(row, textvariable=self.status, foreground=T.MUTED).pack(side='right')
        self.sentence_status = tk.StringVar(value='')
        self.sentence_label = ttk.Label(shell, textvariable=self.sentence_status, foreground=T.MUTED, wraplength=740)
        self.sentence_label.pack(fill='x', pady=(8, 0))
        shell.bind('<Configure>', lambda e: self.sentence_label.configure(wraplength=max(200, e.width-72)))
        self.active_folder = None
        self.progress = ttk.Progressbar(shell, mode='indeterminate', length=200)
        style.configure('Horizontal.TProgressbar', thickness=6, borderwidth=0, troughcolor=T.TRACK, background=T.GOLD, lightcolor=T.GOLD, darkcolor=T.GOLD, bordercolor=T.BG)
        style.layout('Horizontal.TProgressbar', [('Horizontal.Progressbar.trough', {'sticky': 'nswe', 'children': [('Horizontal.Progressbar.pbar', {'side': 'left', 'sticky': 'ns'})]})])
        self.progress.pack(fill='x', pady=(14, 20))
        result = ttk.Frame(shell)
        result.pack(fill='x')
        ttk.Label(result, textvariable=self.result_label, foreground=T.MUTED).pack(side='left')
        self.save_button = Button(result, text='保存音频与字幕', command=self.export, state='disabled')
        self.save_button.pack(side='right')
        self.video_button = Button(result, text='导出字幕视频', command=self.export_video, state='disabled', width=150)
        self.video_button.pack(side='right', padx=8)
        self.player = AudioPlayer(shell)
        self.player.pack(fill='both', expand=True, pady=(10,0))
        ttk.Label(shell, text='本地合成  ·  录音音色可在两个模型间共用', foreground=T.MUTED, font=('Microsoft YaHei UI', 9)).pack(anchor='w', pady=(24, 0))
        self.after(150, self.poll)
        self.protocol('WM_DELETE_WINDOW', self.close)

    def appearance(self):
        if self.appearance_window and self.appearance_window.winfo_exists():
            self.appearance_window.lift();return
        self.appearance_window=AppearanceDialog(self,BASE)

    def refresh_voices(self, selected=None):
        self.voices = {}
        for p in (BASE / 'voices').glob('*/voice.json'):
            try:
                v = core.read_json(p)
                label = v['name']
                if label in self.voices: label += ' · ' + p.parent.name[:6]
                self.voices[label] = (p.parent, v)
            except (OSError, ValueError, KeyError): pass
        self.voice_combo['values'] = [*self.voices, '自定义录音']
        for label, (folder, v) in self.voices.items():
            if folder.name == selected:
                self.voice_choice.set(label)
                self.select_voice()
                break

    def select_voice(self, event=None):
        pair = self.voices.get(self.voice_choice.get())
        if pair:
            folder, v = pair
            self.reference.set(str(folder / v['audio']))
            self.transcript.delete('1.0', 'end')
            self.transcript.insert('1.0', v['text'])

    def manage_voice(self):
        win=tk.Toplevel(self);brand_window(win);win.title('音色管理');win.geometry('460x320')
        frame=ttk.Frame(win,padding=24);frame.pack(fill='both',expand=True)
        ttk.Label(frame,textvariable=self.voice_choice,font=('Microsoft YaHei UI',14,'bold')).pack(anchor='w',pady=(0,16))
        Button(frame,text='试听参考录音',command=lambda:self.play(self.reference.get())).pack(fill='x',pady=4)
        Button(frame,text='导入参考录音',command=lambda:(self.choose_reference(),win.destroy())).pack(fill='x',pady=4)
        Button(frame,text='重命名当前音色',command=lambda:self.rename_voice(win)).pack(fill='x',pady=4)
        Button(frame,text='删除当前音色',command=lambda:self.delete_voice(win)).pack(fill='x',pady=4)

    def delete_voice(self, parent=None):
        parent=parent or self
        pair=self.voices.get(self.voice_choice.get())
        if not pair:
            messagebox.showinfo('删除音色','请先选择一个已保存的音色。外部导入的录音不会被删除。',parent=parent);return
        if self.busy:
            messagebox.showinfo('删除音色','请等待当前合成结束，或取消合成后再删除音色。',parent=parent);return
        folder,voice=pair
        root=(BASE/'voices').resolve()
        target=folder.resolve()
        if target.parent!=root or folder.is_symlink() or folder.is_junction():
            messagebox.showerror('删除失败','音色目录不在软件音色库中，无法删除。',parent=parent);return
        if not messagebox.askyesno('删除音色',f'确定永久删除音色“{voice["name"]}”及其参考录音吗？\n此操作无法撤销。已生成的音频、字幕和历史任务会保留。',parent=parent,default='no'):return
        try:
            winsound.PlaySound(None,0)
            shutil.rmtree(target)
        except OSError as error:
            messagebox.showerror('删除失败',str(error),parent=parent);return
        self.voice_choice.set('自定义录音');self.reference.set('');self.transcript.delete('1.0','end')
        self.refresh_voices()
        if self.voices:
            self.voice_choice.set(next(iter(self.voices)));self.select_voice()
        try:self.persist()
        except OSError as error:
            messagebox.showerror('设置保存失败',f'音色已删除，但无法保存新的默认音色：{error}',parent=parent)
        self.status.set(f'已删除音色：{voice["name"]}')

    def rename_voice(self, parent=None):
        pair=self.voices.get(self.voice_choice.get())
        if not pair:
            messagebox.showinfo('重命名','请先选择一个已保存的音色。',parent=parent or self);return
        folder,voice=pair
        name=simpledialog.askstring('重命名音色','音色名称',initialvalue=voice['name'],parent=parent or self)
        if name is None:return
        name=name.strip()
        if not name or name=='自定义录音' or any(v['name']==name and f!=folder for f,v in self.voices.values()):
            messagebox.showerror('名称不可用','请输入非空且不重复的音色名称。',parent=parent or self);return
        try:
            voice=dict(voice,name=name);core.write_json(folder/'voice.json',voice)
            self.refresh_voices(folder.name);self.persist()
        except OSError as error:messagebox.showerror('重命名失败',str(error),parent=parent or self)

    def make_voice(self):
        if self.voice_window and self.voice_window.winfo_exists():
            self.voice_window.deiconify()
            self.voice_window.lift()
            self.voice_window.focus_set()
            return
        self.voice_window = VoiceStudio(self, BASE / 'voices', self.refresh_voices)
        self.voice_window.transient(self)
        self.voice_window.update_idletasks()
        self.voice_window.geometry(f'+{self.winfo_rootx()+60}+{self.winfo_rooty()+60}')
        self.voice_window.lift()
        self.voice_window.focus_set()

    def editor(self, parent, height):
        return TextBox(parent, height=height, wrap='word', undo=True, font=('Microsoft YaHei UI', 11), bg=T.SURFACE, fg=T.INK, insertbackground=T.INK, relief='flat', padx=16, pady=12, spacing1=3, spacing3=5)

    def text_changed(self, event=None):
        self.count.set(f"{len(self.text.get('1.0', 'end').strip())} 字")
        self.text.edit_modified(False)

    def sample(self):
        self.text.delete('1.0', 'end')
        self.text.insert('1.0', ENGLISH_SAMPLE if self.language.get() == '英文' else SAMPLE_TEXT)

    def choose_reference(self):
        path = filedialog.askopenfilename(filetypes=[('WAV 录音', '*.wav')])
        if path:
            self.voice_choice.set('自定义录音')
            self.reference.set(path)
            self.transcript.delete('1.0', 'end')

    def import_text(self):
        path = filedialog.askopenfilename(filetypes=[('文本', '*.txt')])
        if path:
            try:
                content = Path(path).read_text(encoding='utf-8-sig')
                self.text.delete('1.0', 'end')
                self.text.insert('1.0', content)
            except Exception as e:
                messagebox.showerror('导入失败', str(e))

    def settings(self):
        win = tk.Toplevel(self)
        brand_window(win)
        win.title('设置')
        win.geometry('780x500')
        frame = ttk.Frame(win, padding=24)
        frame.pack(fill='both', expand=True)
        fields = [('ming_python', 'Ming 运行环境', False), ('ming_model', 'Ming 模型目录', True), ('ming_source', 'Ming 引擎目录', True), ('qwen_python', 'Qwen 运行环境', False), ('qwen_model', 'Qwen 模型目录', True)]
        variables = {}
        for i, (key, label, directory) in enumerate(fields):
            ttk.Label(frame, text=label).grid(row=i, column=0, pady=10)
            var = variables[key] = tk.StringVar(value=self.config_values.get(key, ''))
            ttk.Entry(frame, textvariable=var).grid(row=i, column=1, sticky='ew', padx=12)
            def browse(v=var, d=directory):
                p = filedialog.askdirectory(parent=win) if d else filedialog.askopenfilename(parent=win)
                if p: v.set(p)
            Button(frame, text='选择', command=browse).grid(row=i, column=2)
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text='使用本机 NVIDIA 显卡进行合成。', foreground=T.MUTED).grid(row=5, column=0, columnspan=3, sticky='w', pady=15)
        def save():
            self.config_values.update({k: v.get().strip() for k, v in variables.items()})
            self.persist()
            win.destroy()
        Button(frame, text='保存', command=save).grid(row=6, column=2)

    def persist(self):
        self.config_values.update(chinese_subtitles=self.subtitle_mode.get(), voice_id=self.voices[self.voice_choice.get()][0].name if self.voice_choice.get() in self.voices else None, output_language='English' if self.language.get() == '英文' else 'Chinese', default_engine=ENGINE_LABELS[self.engine_choice.get()], reference_wav=self.reference.get(), reference_text=self.transcript.get('1.0', 'end').strip())
        core.write_json(SETTINGS, self.config_values)

    def start(self):
        if self.busy: return
        try:
            self.persist()
            self.active_engine = ENGINE_LABELS[self.engine_choice.get()]
            self.runner = core.Runner(DATA / 'jobs', lambda text: self.events.put(('log', text)))
            folder = self.runner.create(self.text.get('1.0', 'end').strip(), self.reference.get(), self.transcript.get('1.0', 'end').strip(), [self.active_engine], self.config_values)
        except Exception as e:
            messagebox.showerror('无法生成', str(e))
            return
        self.launch_job(folder)

    def resume_job(self, folder):
        if self.busy:
            messagebox.showinfo("任务运行中", "请等待当前任务完成或取消后再续跑。", parent=self);return
        try:
            job=core.read_json(Path(folder)/"job.json")
            self.active_engine=job["engines"][0]
            self.runner=core.Runner(DATA / "jobs", lambda text:self.events.put(("log",text)))
            self.launch_job(Path(folder), resume=True)
        except Exception as e: messagebox.showerror("无法续跑", str(e), parent=self)

    def launch_job(self, folder, resume=False):
        self.active_folder = folder
        self.sentence_status.set('正在准备模型和参考音色…')
        self.busy = True
        self.engine_combo.configure(state='disabled')
        self.generate.configure(state='disabled')
        self.cancel.configure(state='normal')
        self.status.set('正在生成，请稍候…')
        self.progress.configure(mode='indeterminate')
        self.progress.start(15)
        def task():
            error = None
            try: self.runner.run(folder, resume=resume)
            except Exception as e: error = str(e)
            self.events.put(('done', (folder, error)))
        threading.Thread(target=task, daemon=True).start()

    def stop(self):
        if self.busy and self.runner:
            self.runner.stop()
            self.status.set('正在取消…')

    def poll(self):
        if self.busy and self.active_folder and not self.runner.cancel.is_set():
            try:
                p = core.read_json(self.active_folder / self.active_engine.replace(' ', '_') / 'progress.json')
                total, completed = p.get('total', 0), p.get('completed', 0)
                preview=' '.join(p.get('text', '').split())
                self.sentence_status.set(preview[:160]+('…' if len(preview)>160 else ''))
                if total:
                    self.progress.stop()
                    self.progress.configure(mode='determinate', maximum=total, value=completed)
                    if p['stage'] == 'generating':
                        unit='段' if self.active_engine=='Qwen Python' else '句'
                        detail=f" · {p['generated_steps']}步 / {p.get('elapsed_seconds',0):.0f}秒" if p.get('generated_steps') else ''
                        self.status.set(f'正在合成第 {min(completed+1,total)} / {total} {unit}'+detail)
                    elif p['stage'] == 'finalizing': self.status.set('正在保存音频…')
                    else: self.status.set(f'已完成 {completed} / {total} '+('段' if self.active_engine=='Qwen Python' else '句'))
                elif p['stage'] == 'loading':
                    self.status.set('正在准备模型…')
                    self.progress.configure(mode='indeterminate')
            except (OSError, ValueError): pass
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == 'log':
                    self.logs.append(value)
                    continue
                folder, error = value
                self.busy = False
                self.engine_combo.configure(state='readonly')
                self.progress.stop()
                self.progress['value'] = 0
                self.generate.configure(state='normal')
                self.cancel.configure(state='disabled')
                job = core.read_json(folder / 'job.json')
                result = job.get('results', {}).get(self.active_engine, {})
                if result.get('wav') and Path(result['wav']).exists():
                    self.set_result(result)
                    self.status.set('生成完成')
                    self.sentence_status.set('全部语句已完成')
                    self.progress.configure(mode='determinate', maximum=1, value=1)
                else:
                    self.status.set('已取消' if job.get('status') == '已中断' else '生成失败')
                    self.sentence_status.set('任务已停止；已完成句数不代表音频已全部保存。')
                    if job.get('status') != '已中断':
                        messagebox.showerror('生成失败', error or result.get('error') or '请查看任务文件夹中的日志。')
        except queue.Empty: pass
        self.after(150, self.poll)

    def set_result(self, result):
        self.output = result['wav']
        self.result_label.set(f"音频已就绪 · {result.get('audio_seconds', 0):.1f} 秒")
        try:
            self.output_text, self.output_cues = transcript_tools.load(self.output)
        except (OSError, ValueError, KeyError):
            self.output_text, self.output_cues = '', []
        self.player.load(self.output, self.output_text, self.output_cues)
        if result.get('subtitle_warning'):
            messagebox.showwarning('字幕未完成', '音频已生成，但双语字幕翻译失败，当前只提供原文字幕。可稍后重试。')
        self.save_button.configure(state='normal')
        self.video_button.configure(state='normal' if self.output_cues else 'disabled')

    def history(self):
        win = tk.Toplevel(self)
        brand_window(win)
        win.title('历史任务与音频')
        win.geometry('760x440')
        frame = ttk.Frame(win, padding=20)
        frame.pack(fill='both', expand=True)
        tree = ttk.Treeview(frame, columns=('time', 'text'), show='headings')
        tree.heading('time', text='时间'); tree.column('time', width=160, stretch=False)
        tree.heading('text', text='内容'); tree.column('text', width=480)
        tree.pack(fill='both', expand=True)
        results = {}
        tasks = {}
        for path in sorted((DATA / 'jobs').glob('*/job.json'), reverse=True):
            try:
                job = core.read_json(path)
                if job.get('status') != '完成':
                    item=tree.insert('', 'end', values=(job['created'], f"[{job.get('status','待生成')}] "+job['text'][:55]))
                    tasks[item]=path.parent
                for engine, result in job.get('results', {}).items():
                    if not result.get('wav') or not Path(result['wav']).exists(): continue
                    label = 'Qwen3-TTS' if engine == 'Qwen Python' else engine
                    item = tree.insert('', 'end', values=(job['created'], f'[{label}] '+job['text'][:55]))
                    results[item] = result
            except (OSError, ValueError, KeyError): continue
        def choose(event=None):
            if tree.selection():
                item=tree.selection()[0]
                if item in tasks:
                    if self.busy:
                        messagebox.showinfo('任务运行中','请先完成或取消当前任务。',parent=win);return
                    self.resume_job(tasks[item])
                else: self.set_result(results[item])
                win.destroy()
        tree.bind('<Double-1>', choose)
        Button(frame, text='续跑任务 / 使用所选音频', command=choose).pack(anchor='e', pady=(12, 0))

    def play(self, path):
        if not path: return
        try:
            core.wav_info(path)
            winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception as e: messagebox.showerror('无法播放', str(e))

    def export(self):
        if not self.output: return
        try:
            from subtitle_quality import validate_cues
            validate_cues(self.output_cues)
            suggested = next_name(BASE, '叙光音频', '.wav')
        except Exception as e:
            messagebox.showerror('无法生成文件名', str(e));return
        dest = filedialog.asksaveasfilename(defaultextension='.wav', initialfile=suggested, filetypes=[('WAV', '*.wav')])
        if dest:
            try:
                target = Path(dest)
                existing = [target.with_suffix(ext).name for ext in ('.txt','.srt','.cues.json') if target.with_suffix(ext).exists()]
                if existing and not messagebox.askyesno('覆盖附属文件', '将覆盖同名文字或字幕文件：\n'+'\n'.join(existing)): return
                if target.resolve() != Path(self.output).resolve(): shutil.copy2(self.output, target)
                transcript_tools.save_sidecars(target, self.output_text, self.output_cues)
            except Exception as e: messagebox.showerror('保存失败', str(e))

    def export_video(self):
        if not self.output:return
        if self.video_window and self.video_window.winfo_exists():
            self.video_window.lift();return
        if not self.output_cues:
            messagebox.showerror('没有字幕','当前音频缺少时间轴字幕，请先生成带字幕的音频。');return
        try:self.video_window=VideoDialog(self,BASE,self.output,self.output_cues)
        except Exception as e:messagebox.showerror('无法导出视频',str(e))

    def close(self):
        if self.video_window and self.video_window.winfo_exists():
            self.video_window.close()
            if self.video_window.winfo_exists():self.after(250,self.close);return
        if self.busy:
            self.stop()
            self.after(250, self.close)
            return
        if self.voice_window and self.voice_window.winfo_exists(): self.voice_window.close()
        self.player.close()
        core.RESIDENT.close()
        self.persist()
        winsound.PlaySound(None, 0)
        self.destroy()

if __name__ == '__main__':
    App().mainloop()

