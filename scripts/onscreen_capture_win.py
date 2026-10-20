"""Photographing real windows on WINDOWS, for on-screen drivers (#205).

The macOS helper (``onscreen_capture.capture_window``) photographs a window by
its window id, behind other windows, and never brings anything to the front so
that Basti's typing stays where it is. This is the Windows counterpart, with
the same rules:

* ``capture_hwnd`` asks the window itself for its picture (``PrintWindow`` with
  ``PW_RENDERFULLCONTENT``), which works when the window is covered and does
  not raise or activate it. A screen rectangle (``ImageGrab``) is the fallback
  only when the window answered with nothing, and is reported as such.
* The size is the window's frame as DWM draws it
  (``DWMWA_EXTENDED_FRAME_BOUNDS``), in device pixels; the calling process must
  be DPI-aware (Qt makes its process per-monitor aware), or at 200 % scale the
  rectangle is the top-left quarter (memory: windows-dev-machine).
* Native windows of this process (the Windows print dialog, which Qt shows as
  ``PrintDlgEx``) are found with ``own_dialogs`` and can be read
  (``list_view_selection``) and answered (``press``) from another thread while
  ``exec()`` blocks.
"""
from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes as W
from pathlib import Path

if sys.platform != "win32":                               # pragma: no cover
    raise ImportError("onscreen_capture_win is for Windows")

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi")

PW_RENDERFULLCONTENT = 0x00000002
DWMWA_EXTENDED_FRAME_BOUNDS = 9
WM_COMMAND = 0x0111
IDOK, IDCANCEL = 1, 2
LVM_GETNEXTITEM = 0x100C
LVM_GETITEMTEXTW = 0x1073
LVNI_SELECTED = 0x0002

EnumWindowsProc = ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
user32.EnumWindows.argtypes = (EnumWindowsProc, W.LPARAM)
user32.EnumChildWindows.argtypes = (W.HWND, EnumWindowsProc, W.LPARAM)
user32.GetWindowThreadProcessId.argtypes = (W.HWND, ctypes.POINTER(W.DWORD))
user32.GetClassNameW.argtypes = (W.HWND, W.LPWSTR, ctypes.c_int)
user32.GetWindowTextW.argtypes = (W.HWND, W.LPWSTR, ctypes.c_int)
user32.IsWindowVisible.argtypes = (W.HWND,)
user32.PrintWindow.argtypes = (W.HWND, W.HDC, W.UINT)
user32.GetWindowDC.argtypes = (W.HWND,)
user32.GetWindowDC.restype = W.HDC
user32.ReleaseDC.argtypes = (W.HWND, W.HDC)
user32.PostMessageW.argtypes = (W.HWND, W.UINT, W.WPARAM, W.LPARAM)
user32.SendMessageW.argtypes = (W.HWND, W.UINT, W.WPARAM, W.LPARAM)
user32.SendMessageW.restype = ctypes.c_ssize_t
user32.GetWindowRect.argtypes = (W.HWND, ctypes.POINTER(W.RECT))
user32.GetDlgCtrlID.argtypes = (W.HWND,)
gdi32.CreateCompatibleDC.argtypes = (W.HDC,)
gdi32.CreateCompatibleDC.restype = W.HDC
gdi32.CreateCompatibleBitmap.argtypes = (W.HDC, ctypes.c_int, ctypes.c_int)
gdi32.CreateCompatibleBitmap.restype = W.HBITMAP
gdi32.SelectObject.argtypes = (W.HDC, W.HGDIOBJ)
gdi32.SelectObject.restype = W.HGDIOBJ
gdi32.DeleteObject.argtypes = (W.HGDIOBJ,)
gdi32.DeleteDC.argtypes = (W.HDC,)
gdi32.GetDIBits.argtypes = (W.HDC, W.HBITMAP, W.UINT, W.UINT, ctypes.c_void_p,
                            ctypes.c_void_p, W.UINT)


def frame_rect(hwnd: int) -> "tuple[int, int, int, int]":
    r = W.RECT()
    if dwmapi.DwmGetWindowAttribute(W.HWND(hwnd), DWMWA_EXTENDED_FRAME_BOUNDS,
                                    ctypes.byref(r), ctypes.sizeof(r)) != 0:
        user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def _print_window(hwnd: int):
    from PIL import Image
    wr = W.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(wr))
    w, h = wr.right - wr.left, wr.bottom - wr.top
    if w <= 0 or h <= 0:
        return None
    hdc = user32.GetWindowDC(hwnd)
    mem = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    old = gdi32.SelectObject(mem, bmp)
    try:
        if not user32.PrintWindow(hwnd, mem, PW_RENDERFULLCONTENT):
            return None

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [("biSize", W.DWORD), ("biWidth", W.LONG), ("biHeight", W.LONG),
                        ("biPlanes", W.WORD), ("biBitCount", W.WORD),
                        ("biCompression", W.DWORD), ("biSizeImage", W.DWORD),
                        ("biXPelsPerMeter", W.LONG), ("biYPelsPerMeter", W.LONG),
                        ("biClrUsed", W.DWORD), ("biClrImportant", W.DWORD)]
        bih = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
        buf = ctypes.create_string_buffer(w * h * 4)
        gdi32.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(bih), 0)
        img = Image.frombuffer("RGB", (w, h), buf.raw, "raw", "BGRX", 0, 1)
    finally:
        gdi32.SelectObject(mem, old)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(mem)
        user32.ReleaseDC(hwnd, hdc)
    # crop the invisible resize borders down to the frame DWM draws
    fl, ft, fr, fb = frame_rect(hwnd)
    box = (fl - wr.left, ft - wr.top, fr - wr.left, fb - wr.top)
    if 0 <= box[0] < box[2] <= w and 0 <= box[1] < box[3] <= h:
        img = img.crop(box)
    return img


def _one_colour(img) -> bool:
    lo, hi = img.convert("L").getextrema()
    return hi - lo < 3


def capture_hwnd(hwnd: int, path: Path) -> str:
    """Save a picture of the window *hwnd* to *path*; how it was taken
    ("window" or "screen-rect"), or "" when nothing usable came back."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    img = _print_window(hwnd)
    if img is not None and not _one_colour(img):
        img.save(path)
        return "window"
    from PIL import ImageGrab
    l, t, r, b = frame_rect(hwnd)
    if r - l <= 0 or b - t <= 0:
        return ""
    img = ImageGrab.grab(bbox=(l, t, r, b), all_screens=True)
    if _one_colour(img):
        return ""
    img.save(path)
    return "screen-rect"


def capture_widget(widget, path: Path) -> str:
    """The top-level window of a Qt *widget*, as the window server shows it."""
    return capture_hwnd(int(widget.window().winId()), path)


def _class(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def _text(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, buf, 512)
    return buf.value


def own_dialogs(class_name: str = "#32770") -> "list[tuple[int, str]]":
    """Visible top-level windows of THIS process of *class_name*."""
    pid = os.getpid()
    found = []

    def cb(hwnd, _l):
        p = W.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value == pid and user32.IsWindowVisible(hwnd) and _class(hwnd) == class_name:
            found.append((int(hwnd), _text(hwnd)))
        return True
    user32.EnumWindows(EnumWindowsProc(cb), 0)
    return found


def children(hwnd: int) -> "list[tuple[int, str, str, int]]":
    """(hwnd, class, text, control id) of every descendant window."""
    out = []

    def cb(h, _l):
        out.append((int(h), _class(h), _text(h), int(user32.GetDlgCtrlID(h))))
        return True
    user32.EnumChildWindows(hwnd, EnumWindowsProc(cb), 0)
    return out


class LVITEMW(ctypes.Structure):
    _fields_ = [("mask", W.UINT), ("iItem", ctypes.c_int), ("iSubItem", ctypes.c_int),
                ("state", W.UINT), ("stateMask", W.UINT), ("pszText", W.LPWSTR),
                ("cchTextMax", ctypes.c_int), ("iImage", ctypes.c_int),
                ("lParam", W.LPARAM), ("iIndent", ctypes.c_int),
                ("iGroupId", ctypes.c_int), ("cColumns", W.UINT),
                ("puColumns", ctypes.c_void_p), ("piColFmt", ctypes.c_void_p),
                ("iGroup", ctypes.c_int)]


def list_view_selection(dialog: int) -> "list[str]":
    """The selected item of every list view in *dialog* (same process, so the
    text buffer is ours): in the print dialog, the chosen printer."""
    out = []
    for h, cls, _t, _id in children(dialog):
        if cls != "SysListView32":
            continue
        idx = user32.SendMessageW(h, LVM_GETNEXTITEM, ctypes.c_size_t(-1).value, LVNI_SELECTED)
        if idx < 0:
            continue
        buf = ctypes.create_unicode_buffer(512)
        item = LVITEMW()
        item.iSubItem, item.pszText, item.cchTextMax = 0, ctypes.cast(buf, W.LPWSTR), 512
        user32.SendMessageW(h, LVM_GETITEMTEXTW, idx, ctypes.addressof(item))
        out.append(buf.value)
    return out


def press(dialog: int, control_id: int) -> None:
    """Press the dialog button *control_id* (IDOK = Print, IDCANCEL)."""
    user32.PostMessageW(dialog, WM_COMMAND, control_id, 0)
