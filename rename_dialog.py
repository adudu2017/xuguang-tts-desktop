"""Theme-aware voice rename dialog with inline validation."""
import tkinter as tk
from tkinter import ttk
import theme as T
from theme import brand_window
from modern_ui import Entry, Button

class RenameDialog(tk.Toplevel):
    def __init__(self, parent, initial_name, save):
        super().__init__(parent)
        brand_window(self)
        self.title('重命名音色');self.transient(parent);self.resizable(False,False)
        self.save_name=save;self.previous_grab=self.grab_current()
        frame=ttk.Frame(self,padding=24);frame.pack(fill='both',expand=True)
        ttk.Label(frame,text='重命名音色',font=('Microsoft YaHei UI',18,'bold')).pack(anchor='w')
        ttk.Label(frame,text='为这个声音取一个容易辨认的名字',foreground=T.MUTED).pack(anchor='w',pady=(8,18))
        self.name=tk.StringVar(value=initial_name)
        self.entry=Entry(frame,textvariable=self.name);self.entry.pack(fill='x')
        self.error=tk.StringVar()
        ttk.Label(frame,textvariable=self.error,foreground=T.PRIMARY,wraplength=400).pack(fill='x',pady=(8,12))
        row=ttk.Frame(frame);row.pack(fill='x')
        Button(row,text='保存名称',style='Primary.TButton',command=self.submit).pack(side='right')
        Button(row,text='取消',command=self.close).pack(side='right',padx=(0,10))
        self.update_idletasks()
        width=460;height=max(260,self.winfo_reqheight())
        x=max(0,min(self.winfo_screenwidth()-width,parent.winfo_rootx()+(parent.winfo_width()-width)//2))
        y=max(0,min(self.winfo_screenheight()-height,parent.winfo_rooty()+(parent.winfo_height()-height)//2))
        self.geometry(f'{width}x{height}+{x}+{y}')
        self.protocol('WM_DELETE_WINDOW',self.close)
        self.bind('<Return>',lambda _:self.submit());self.bind('<Escape>',lambda _:self.close())
        self.grab_set();self.entry.focus_set();self.entry.select_range(0,'end')
    def submit(self):
        try:self.save_name(self.name.get().strip())
        except (ValueError,OSError) as error:
            self.error.set(str(error));return
        self.close()
    def close(self):
        self.grab_release();self.destroy()
        if self.previous_grab and self.previous_grab.winfo_exists():self.previous_grab.grab_set()
