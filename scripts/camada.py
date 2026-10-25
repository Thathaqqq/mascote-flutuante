"""Janela com transparência real por pixel (bordas suaves e sombras).

Windows: janela "em camadas" atualizada direto pelo sistema.
Mac: janela transparente do próprio Tk, com a imagem (com transparência) num canvas.
"""
import ctypes
import sys

from PIL import Image, ImageChops

if sys.platform != "win32":
    from PIL import ImageTk

    class Camada:
        def __init__(self, root, canvas=None):
            self.root = root
            root.attributes("-transparent", True)
            root.config(bg="systemTransparent")
            self.canvas = canvas or __import__("tkinter").Canvas(root, highlightthickness=0)
            self.canvas.config(bg="systemTransparent", highlightthickness=0)
            if not canvas:
                self.canvas.pack(fill="both", expand=True)
            self.item = None
            self.foto = None
            self.pos = None

        def mostrar(self, img, x, y):
            self.foto = ImageTk.PhotoImage(img)
            if (int(self.canvas["width"]), int(self.canvas["height"])) != img.size:
                self.canvas.config(width=img.width, height=img.height)
            if self.item is None:
                self.item = self.canvas.create_image(0, 0, image=self.foto, anchor="nw")
            else:
                self.canvas.itemconfig(self.item, image=self.foto)
                self.canvas.tag_lower(self.item)
            if self.pos != (x, y):
                self.pos = (x, y)
                self.root.geometry(f"+{x}+{y}")

else:
    from ctypes import wintypes

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

        def __init__(self, root, canvas=None):
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
