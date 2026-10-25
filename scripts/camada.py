"""Janela do Windows com transparência real por pixel (bordas suaves e sombras)."""
import ctypes
from ctypes import wintypes

from PIL import Image, ImageChops

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32


# ---------- janela com transparência real (Windows) ----------

class _BIH(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


class _BLEND(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]


user32.GetDC.restype = wintypes.HDC
user32.GetDC.argtypes = [wintypes.HWND]
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
user32.UpdateLayeredWindow.argtypes = [wintypes.HWND, wintypes.HDC, ctypes.POINTER(wintypes.POINT),
                                       ctypes.POINTER(wintypes.SIZE), wintypes.HDC, ctypes.POINTER(wintypes.POINT),
                                       wintypes.COLORREF, ctypes.POINTER(_BLEND), wintypes.DWORD]
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateDIBSection.restype = wintypes.HBITMAP
gdi32.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.c_void_p, wintypes.UINT,
                                   ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD]
gdi32.SelectObject.restype = wintypes.HGDIOBJ
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wintypes.HDC]


class Camada:
    """Mostra uma imagem RGBA como janela, com cada pixel na sua transparência."""

    def __init__(self, root):
        root.update_idletasks()
        self.hwnd = int(root.wm_frame(), 16)
        ex = user32.GetWindowLongW(self.hwnd, -20)
        user32.SetWindowLongW(self.hwnd, -20, ex | 0x80000)  # WS_EX_LAYERED

    def mostrar(self, img, x, y):
        w, h = img.size
        a = img.getchannel("A")
        r, g, b = (ImageChops.multiply(c, a) for c in img.split()[:3])
        dados = Image.merge("RGBA", (b, g, r, a)).tobytes()
        tela = user32.GetDC(None)
        mdc = gdi32.CreateCompatibleDC(tela)
        bih = _BIH(ctypes.sizeof(_BIH), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
        bits = ctypes.c_void_p()
        bmp = gdi32.CreateDIBSection(mdc, ctypes.byref(bih), 0, ctypes.byref(bits), None, 0)
        ctypes.memmove(bits, dados, len(dados))
        antigo = gdi32.SelectObject(mdc, bmp)
        args = (self.hwnd, tela, ctypes.byref(wintypes.POINT(x, y)), ctypes.byref(wintypes.SIZE(w, h)), mdc,
                ctypes.byref(wintypes.POINT(0, 0)), 0, ctypes.byref(_BLEND(0, 0, 255, 1)), 2)
        if not user32.UpdateLayeredWindow(*args):
            # o Tk troca o modo de transparência ao reabrir a janela: religa e tenta de novo
            ex = user32.GetWindowLongW(self.hwnd, -20)
            user32.SetWindowLongW(self.hwnd, -20, ex & ~0x80000)
            user32.SetWindowLongW(self.hwnd, -20, ex | 0x80000)
            user32.UpdateLayeredWindow(*args)
        gdi32.SelectObject(mdc, antigo)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(mdc)
        user32.ReleaseDC(None, tela)
