import theme as T
from theme import brand_window
"""Shared rounded controls for the desktop UI."""
import customtkinter as ctk
ctk.set_appearance_mode('light')
ctk.set_widget_scaling(1.0)

FONT=('Microsoft YaHei UI',14)

class Entry(ctk.CTkEntry):
    def __init__(self,master,**kwargs):
        super().__init__(master,height=40,corner_radius=10,border_width=1,
            border_color=T.BORDER,bg_color=T.BG,fg_color=T.SURFACE,
            text_color=T.INK,font=FONT,**kwargs)
        self._entry.configure(selectbackground=T.GOLD_LIGHT,selectforeground=T.INK,insertbackground=T.PRIMARY)

class Button(ctk.CTkButton):
    def __init__(self,master,**kwargs):
        primary=kwargs.pop('style','')=='Primary.TButton'
        super().__init__(master,width=kwargs.pop('width',120),height=40,corner_radius=10,
            font=FONT,bg_color=T.BG,fg_color=T.PRIMARY if primary else T.SECONDARY,
            hover_color=T.PRIMARY_HOVER if primary else T.SECONDARY_HOVER,text_color=T.WHITE if primary else T.INK,
            text_color_disabled=T.DISABLED,border_width=0,**kwargs)

class ComboBox(ctk.CTkComboBox):
    def __init__(self,master,**kwargs):
        variable=kwargs.pop('textvariable',None)
        width=kwargs.pop('width',20)
        self.selection_callback=None
        super().__init__(master,variable=variable,width=max(100,width*10+40),height=40,
            corner_radius=10,border_width=1,border_color=T.BORDER,bg_color=T.BG,fg_color=T.SURFACE,
            button_color=T.SECONDARY,button_hover_color=T.SECONDARY_HOVER,text_color=T.INK,
            dropdown_fg_color=T.SURFACE,dropdown_hover_color=T.GOLD_LIGHT,dropdown_text_color=T.INK,
            font=FONT,dropdown_font=FONT,command=self.selected,**kwargs)
        self._entry.configure(selectbackground=T.GOLD_LIGHT,selectforeground=T.INK,insertbackground=T.PRIMARY)
    def selected(self,value):
        if self.selection_callback:self.selection_callback(None)
    def bind(self,sequence=None,command=None,add=True):
        if sequence=='<<ComboboxSelected>>':self.selection_callback=command
        else:return super().bind(sequence,command,add=add)
    def __setitem__(self,key,value):self.configure(**{key:value})

class TextBox(ctk.CTkTextbox):
    def __init__(self,master,**kwargs):
        lines=kwargs.pop('height',4)
        for key in ('relief','padx','pady','bg','fg','insertbackground','font'):
            kwargs.pop(key,None)
        super().__init__(master,height=lines*24+28,corner_radius=12,border_width=1,
            border_color=T.BORDER,bg_color=T.BG,fg_color=T.SURFACE,text_color=T.INK,font=FONT,
            scrollbar_button_color=T.SECONDARY,scrollbar_button_hover_color=T.GOLD,**kwargs)
        self._textbox.configure(selectbackground=T.GOLD_LIGHT,selectforeground=T.INK,insertbackground=T.PRIMARY)
    def tag_configure(self,*args,**kwargs):return self.tag_config(*args,**kwargs)

class Slider(ctk.CTkSlider):
    def __init__(self,master,**kwargs):
        super().__init__(master,height=18,corner_radius=8,bg_color=T.BG,fg_color=T.TRACK,
            progress_color=T.GOLD,button_color=T.PRIMARY,button_hover_color=T.PRIMARY_HOVER,
            button_length=14,**kwargs)
