from tkinter import Toplevel, StringVar, ttk
from PIL import Image, ImageOps, ImageTk
import theme as T
from modern_ui import ComboBox, Button


class AppearanceDialog(Toplevel):
    def __init__(self,owner,base):
        super().__init__(owner);self.owner=owner;self.base=base
        self.title('皮肤与视频主题');self.geometry('740x650');self.resizable(False,False)
        T.brand_window(self);self.transient(owner)
        frame=ttk.Frame(self,padding=24);frame.pack(fill='both',expand=True)
        ttk.Label(frame,text='叙光 · 随心换装',font=('Microsoft YaHei UI',20,'bold')).pack(anchor='w')
        ttk.Label(frame,text='界面皮肤与视频背景独立选择，立即生效并自动保存。',foreground=T.MUTED).pack(anchor='w',pady=(6,18))
        row=ttk.Frame(frame);row.pack(fill='x')
        ttk.Label(row,text='界面皮肤').pack(side='left')
        self.skin=StringVar(value=T.CURRENT)
        skin=ComboBox(row,textvariable=self.skin,values=list(T.PALETTES),state='readonly',width=13)
        skin.pack(side='left',padx=10);skin.bind('<<ComboboxSelected>>',self.change_skin)
        ttk.Label(row,text='视频主题').pack(side='left',padx=(18,0))
        self.video=StringVar(value=owner.config_values.get('video_theme','暖金书页'))
        video=ComboBox(row,textvariable=self.video,values=list(T.VIDEO_THEMES),state='readonly',width=13)
        video.pack(side='left',padx=10);video.bind('<<ComboboxSelected>>',self.change_video)
        self.preview=ttk.Label(frame,anchor='center');self.preview.pack(fill='x',pady=(20,10))
        self.note=StringVar();ttk.Label(frame,textvariable=self.note,foreground=T.MUTED,wraplength=680).pack(anchor='w')
        row=ttk.Frame(frame);row.pack(fill='x',pady=(20,0))
        Button(row,text='使用同款视频主题',width=180,command=self.match).pack(side='left')
        Button(row,text='完成',command=self.destroy,style='Primary.TButton').pack(side='right')
        self.refresh()

    def refresh(self):
        with Image.open(T.background_path(self.base,self.video.get())) as im:
            self.photo=ImageTk.PhotoImage(ImageOps.contain(im.convert('RGB'),(640,360)))
        self.preview.configure(image=self.photo)
        custom=self.owner.config_values.get('video_background')
        self.note.set('当前导出使用自定义背景；选择上方视频主题可切回内置背景。' if custom else '视频背景：'+self.video.get()+' · 品牌名始终为“叙光”')

    def change_skin(self,event=None):
        T.apply(self.owner,self.skin.get())
        self.owner.config_values['skin']=self.skin.get();self.owner.persist()

    def change_video(self,event=None):
        self.owner.config_values.update(video_theme=self.video.get(),video_background='')
        self.owner.persist();self.refresh()
        window=self.owner.video_window
        if window and window.winfo_exists() and not window.is_running:
            window.theme_choice.set(self.video.get());window.set_theme()

    def match(self):
        self.video.set(self.skin.get());self.change_video()
