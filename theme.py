"""Xuguang brand palette: warm paper, plum ink and amber light."""
from pathlib import Path
import sys
import json
BG = '#FFF8F0'
SURFACE = '#FFFEFA'
INK = '#3C203A'
MUTED = '#826477'
PRIMARY = '#A63878'
PRIMARY_HOVER = '#89275F'
SECONDARY = '#FBE2ED'
SECONDARY_HOVER = '#F5C9DF'
BORDER = '#EAD3D9'
DISABLED = '#B39AA7'
TRACK = '#F2E1D6'
GOLD = '#E7A021'
GOLD_LIGHT = '#FFE6A3'
WHITE = '#FFFCF5'

KEYS = 'BG SURFACE INK MUTED PRIMARY PRIMARY_HOVER SECONDARY SECONDARY_HOVER BORDER DISABLED TRACK GOLD GOLD_LIGHT WHITE'.split()
PALETTES = {'暖金书页': {key:globals()[key] for key in KEYS}}
PALETTES['星海蓝'] = dict(zip(KEYS, ['#F0F7FF','#FCFEFF','#183651','#60778B','#2369A7','#174F85','#DEEDFC','#C8E0F9','#CCDFEF','#95AABD','#DEEAF5','#22A8CF','#CDEFFB','#FFFFFF']))
PALETTES['翡翠林语'] = dict(zip(KEYS, ['#F0FAF4','#FCFFFC','#1D4034','#617D70','#217650','#145C3C','#DEF2E5','#C5E9D2','#CDE5D6','#98B2A3','#DEEEE4','#C7992D','#F7E9B4','#FFFFFF']))
PALETTES['暮紫花境'] = dict(zip(KEYS, ['#F7F2FF','#FFFCFF','#39254E','#7B678B','#7C45B1','#60318E','#EDE1FA','#DFC9F3','#DFD1ED','#AF9FBC','#E9DFF3','#B267CE','#EDD7FA','#FFFFFF']))
VIDEO_THEMES = dict(zip(PALETTES, ['gold.png','ocean.png','forest.png','violet.png']))
CURRENT = '暖金书页'

def base_path():
    return Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent

def background_path(base, name):
    return Path(base)/'assets/themes'/VIDEO_THEMES.get(name,'gold.png')

def select(name):
    global CURRENT
    if name not in PALETTES: name='暖金书页'
    CURRENT=name
    globals().update(PALETTES[name])

try:
    select(json.loads((base_path()/'data/settings.json').read_text(encoding='utf-8')).get('skin','暖金书页'))
except (OSError,ValueError):pass

def apply(root, name):
    """Recolor live widgets without rebuilding them or touching user content."""
    from tkinter import ttk
    import tkinter as tk
    import customtkinter as ctk
    old={key:globals()[key] for key in KEYS}
    select(name)
    mapping={old[key].lower():globals()[key] for key in KEYS}
    options=('bg_color','fg_color','border_color','text_color','text_color_disabled','hover_color',
             'button_color','button_hover_color','dropdown_fg_color','dropdown_hover_color','dropdown_text_color',
             'scrollbar_button_color','scrollbar_button_hover_color','progress_color',
             'background','foreground','selectbackground','selectforeground','insertbackground',
             'activebackground','activeforeground','disabledforeground','highlightbackground','highlightcolor')
    def visit(widget):
        for option in options:
            try:
                value=widget.cget(option)
                if isinstance(value,str) and value.lower() in mapping:widget.configure(**{option:mapping[value.lower()]})
            except (tk.TclError,ValueError,AttributeError):pass
        if isinstance(widget,tk.Text):
            for tag in widget.tag_names():
                for option in ('background','foreground'):
                    value=widget.tag_cget(tag,option)
                    if value.lower() in mapping:widget.tag_configure(tag,**{option:mapping[value.lower()]})
        # CTk owns the internal canvases/entries; configure its public palette,
        # and only touch the entry/text selection properties explicitly.
        if isinstance(widget,ctk.CTkBaseClass):
            for attr in ('_entry','_textbox'):
                internal=getattr(widget,attr,None)
                if internal is not None:
                    internal.configure(selectbackground=GOLD_LIGHT,selectforeground=INK,insertbackground=PRIMARY)
                    if isinstance(internal,tk.Text):
                        for tag in internal.tag_names():
                            for option in ('background','foreground'):
                                value=internal.tag_cget(tag,option)
                                if value.lower() in mapping:internal.tag_configure(tag,**{option:mapping[value.lower()]})
            return
        for child in widget.winfo_children():visit(child)
    visit(root)
    style=ttk.Style(root)
    style.configure('.',background=BG,foreground=INK)
    style.configure('TEntry',fieldbackground=SURFACE,selectbackground=PRIMARY,selectforeground=WHITE)
    style.configure('Treeview',background=SURFACE,fieldbackground=SURFACE,foreground=INK)
    style.map('Treeview',background=[('selected',PRIMARY)],foreground=[('selected',WHITE)])
    style.configure('Treeview.Heading',background=SECONDARY,foreground=INK)
    style.map('Treeview.Heading',background=[('active',SECONDARY_HOVER)])
    style.configure('TButton',background=SECONDARY)
    style.map('TButton',background=[('active',SECONDARY_HOVER)])
    style.configure('Primary.TButton',background=PRIMARY,foreground=WHITE)
    style.map('Primary.TButton',background=[('disabled',DISABLED),('active',PRIMARY_HOVER)])
    style.configure('Vertical.TScrollbar',background=SECONDARY,troughcolor=BG,arrowcolor=PRIMARY)
    for name in ('TProgressbar','Horizontal.TProgressbar'):
        style.configure(name,background=GOLD,troughcolor=TRACK,lightcolor=GOLD,darkcolor=GOLD,bordercolor=BG)
    root.option_add('*selectBackground',GOLD_LIGHT);root.option_add('*selectForeground',INK)

def brand_window(window, default=False):
    base = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
    window.configure(bg=BG)
    icon = base / 'assets/xuguang.ico'
    if icon.exists():
        if default: window.iconbitmap(default=str(icon))
        window.iconbitmap(str(icon))
