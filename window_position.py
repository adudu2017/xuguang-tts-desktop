"""Place owned windows on the owner's monitor, including negative coordinates."""
import ctypes
from ctypes import wintypes

def centered_rect(owner, size, work):
    left,top,right,bottom=work
    width,height=size
    x=round((owner[0]+owner[2]-width)/2)
    y=round((owner[1]+owner[3]-height)/2)
    return max(left,min(x,right-width)),max(top,min(y,bottom-height))

def center_window(window):
    if not window.winfo_exists():return
    parent=window.master
    if parent is None:return
    parent=parent.winfo_toplevel()
    window.transient(parent)
    window.update_idletasks()
    try:
        user=ctypes.windll.user32
        user.GetAncestor.argtypes=[wintypes.HWND,wintypes.UINT];user.GetAncestor.restype=wintypes.HWND
        user.MonitorFromWindow.argtypes=[wintypes.HWND,wintypes.DWORD];user.MonitorFromWindow.restype=wintypes.HANDLE
        user.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
        user.SetWindowPos.argtypes=[wintypes.HWND,wintypes.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wintypes.UINT]
        class MonitorInfo(ctypes.Structure):
            _fields_=[('cbSize',wintypes.DWORD),('monitor',wintypes.RECT),('work',wintypes.RECT),('flags',wintypes.DWORD)]
        user.GetMonitorInfoW.argtypes=[wintypes.HANDLE,ctypes.POINTER(MonitorInfo)]
        owner=user.GetAncestor(parent.winfo_id(),2);handle=user.GetAncestor(window.winfo_id(),2)
        owner_rect=wintypes.RECT();rect=wintypes.RECT()
        if not user.GetWindowRect(owner,ctypes.byref(owner_rect)):raise OSError('Owner geometry unavailable')
        if not user.GetWindowRect(handle,ctypes.byref(rect)):raise OSError('Window geometry unavailable')
        info=MonitorInfo();info.cbSize=ctypes.sizeof(info)
        if not user.GetMonitorInfoW(user.MonitorFromWindow(owner,2),ctypes.byref(info)):raise OSError('Monitor unavailable')
        bounds=lambda r:(r.left,r.top,r.right,r.bottom)
        x,y=centered_rect(bounds(owner_rect),(rect.right-rect.left,rect.bottom-rect.top),bounds(info.work))
        user.SetWindowPos(handle,None,x,y,0,0,0x0001|0x0004|0x0010)
    except (AttributeError,OSError):
        x,y=centered_rect((parent.winfo_rootx(),parent.winfo_rooty(),parent.winfo_rootx()+parent.winfo_width(),parent.winfo_rooty()+parent.winfo_height()),(window.winfo_width(),window.winfo_height()),(0,0,window.winfo_screenwidth(),window.winfo_screenheight()))
        window.geometry(f'+{x}+{y}')


def show_centered(window):
    """Complete geometry while withdrawn, then map only once."""
    if not window.winfo_exists():return
    center_window(window)
    window.update_idletasks()
    window.deiconify()
    if hasattr(window, 'entry'):window.entry.focus_set()
    elif hasattr(window, 'cancel_button'):window.cancel_button.focus_set()
