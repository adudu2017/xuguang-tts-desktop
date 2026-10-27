"""Theme-aware modal confirmation with cancellation as the default."""
import tkinter as tk
from tkinter import ttk
import theme as T
from theme import brand_window
from modern_ui import Button

class ConfirmDialog(tk.Toplevel):
    def __init__(self, parent, title, message, confirm_text='确认删除'):
        super().__init__(parent)
        brand_window(self)
        self.result=False
        self.previous_grab=self.grab_current()
        self.title(title);self.transient(parent);self.resizable(False,False)
        frame=ttk.Frame(self,padding=24);frame.pack(fill='both',expand=True)
        ttk.Label(frame,text=title,font=('Microsoft YaHei UI',18,'bold')).pack(anchor='w')
        ttk.Label(frame,text=message,foreground=T.INK,wraplength=410,justify='left').pack(fill='x',pady=(16,24))
        row=ttk.Frame(frame);row.pack(fill='x')
        self.confirm_button=Button(row,text=confirm_text,command=lambda:self.finish(True))
        self.confirm_button.pack(side='right')
        self.cancel_button=Button(row,text='取消',style='Primary.TButton',command=self.finish)
        self.cancel_button.pack(side='right',padx=(0,10))
        self.update_idletasks()
        width=460;height=max(240,self.winfo_reqheight())
        x=max(0,min(self.winfo_screenwidth()-width,parent.winfo_rootx()+(parent.winfo_width()-width)//2))
        y=max(0,min(self.winfo_screenheight()-height,parent.winfo_rooty()+(parent.winfo_height()-height)//2))
        self.geometry(f'{width}x{height}+{x}+{y}')
        self.protocol('WM_DELETE_WINDOW',self.finish)
        self.bind('<Escape>',lambda _:self.finish())
        self.bind('<Return>',lambda _:self.finish())
        self.grab_set();self.cancel_button.focus_set()
    def finish(self, confirmed=False):
        self.result=confirmed
        self.grab_release();self.destroy()
        if self.previous_grab and self.previous_grab.winfo_exists():self.previous_grab.grab_set()

def confirm_delete(parent, name):
    dialog=ConfirmDialog(parent,'删除音色',f'确定删除音色“{name}”及其参考录音吗？\n\n删除后无法恢复。已生成的音频、字幕和历史任务会保留。')
    parent.wait_window(dialog)
    return dialog.result
