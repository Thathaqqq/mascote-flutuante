"""O que muda entre Windows e Mac: cursor, cliques, atalho, foco no Claude, som,
fontes e onde o aplicativo do Claude guarda as sessões. O resto do mascote é igual."""
import ctypes
import json
import os
import subprocess
import sys
import time
from pathlib import Path

WIN = sys.platform == "win32"
MAC = sys.platform == "darwin"

FONTE_UI = "Segoe UI" if WIN else "Helvetica Neue"
FONTE_UI_FORTE = "Segoe UI Semibold" if WIN else "Helvetica Neue Medium"
ATALHO_TEXTO = "Ctrl+Alt+Espaço" if WIN else "Control+Option+Espaço"

if WIN:
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
elif MAC:
    class _CGPoint(ctypes.Structure):
        _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]
    try:
        _qz = ctypes.cdll.LoadLibrary(
            "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")
        _qz.CGEventCreate.restype = ctypes.c_void_p
        _qz.CGEventCreate.argtypes = [ctypes.c_void_p]
        _qz.CGEventGetLocation.restype = _CGPoint
        _qz.CGEventGetLocation.argtypes = [ctypes.c_void_p]
        _qz.CFRelease.argtypes = [ctypes.c_void_p]
        _qz.CGEventSourceButtonState.restype = ctypes.c_bool
        _qz.CGEventSourceButtonState.argtypes = [ctypes.c_int32, ctypes.c_uint32]
        _qz.CGEventSourceKeyState.restype = ctypes.c_bool
        _qz.CGEventSourceKeyState.argtypes = [ctypes.c_int32, ctypes.c_uint16]
    except OSError:
        _qz = None

_tk_root = None  # reserva: posição do cursor pelo próprio Tk


def registrar_root(root):
    global _tk_root
    _tk_root = root


def escala(root):
    """Quanto aumentar medidas em pixels (telas com zoom no Windows). No Mac o Tk já trabalha em pontos."""
    return root.winfo_fpixels("1i") / 96 if WIN else 1.0


def posicao_cursor():
    if WIN:
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y
    if MAC and _qz:
        ev = _qz.CGEventCreate(None)
        p = _qz.CGEventGetLocation(ev)
        _qz.CFRelease(ev)
        return int(p.x), int(p.y)
    return _tk_root.winfo_pointerxy() if _tk_root else (0, 0)


_clique_antes = False


def clicou_agora():
    """Clique do botão esquerdo em qualquer lugar da tela (desde a última olhada)."""
    global _clique_antes
    if WIN:
        return bool(user32.GetAsyncKeyState(0x01) & 0x8001)
    if MAC and _qz:
        apertado = _qz.CGEventSourceButtonState(0, 0)
        novo = apertado and not _clique_antes
        _clique_antes = apertado
        return novo
    return False


def atalho_apertado():
    """Ctrl+Alt+Espaço (Windows) ou Control+Option+Espaço (Mac)."""
    if WIN:
        return all(user32.GetAsyncKeyState(k) & 0x8000 for k in (0x11, 0x12, 0x20))
    if MAC and _qz:
        k = _qz.CGEventSourceKeyState
        return (k(0, 59) or k(0, 62)) and (k(0, 58) or k(0, 61)) and k(0, 49)
    return False


def focar_claude():
    """Traz o aplicativo do Claude para a frente. Devolve False se não achou."""
    if MAC:
        return subprocess.run(["open", "-a", "Claude"], capture_output=True).returncode == 0
    if not WIN:
        return False
    achadas = []
    PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            if buf.value == "Claude":
                achadas.append(hwnd)
        return True

    user32.EnumWindows(PROC(cb), 0)
    if not achadas:
        return False
    hwnd = achadas[0]
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)
    user32.keybd_event(0x12, 0, 0, 0)  # Alt: libera o Windows a trocar o foco
    user32.keybd_event(0x12, 0, 2, 0)
    user32.SetForegroundWindow(hwnd)
    return True


def abrir(alvo):
    """Abre um endereço (link) ou uma pasta com o programa padrão do sistema."""
    alvo = str(alvo)
    if WIN:
        os.startfile(alvo)
    elif MAC:
        subprocess.Popen(["open", alvo])
    else:
        subprocess.Popen(["xdg-open", alvo])


def tocar_som(tipo):
    """Som discreto do sistema: 'esperando' ou 'pronto'."""
    try:
        if WIN:
            import winsound
            winsound.MessageBeep(0x40 if tipo == "esperando" else 0)
        elif MAC:
            som = "Ping" if tipo == "esperando" else "Glass"
            subprocess.Popen(["afplay", f"/System/Library/Sounds/{som}.aiff"])
    except Exception:
        pass


def janela_ativa():
    """Retângulo (esq, topo, dir) da janela em uso, ou None se não der para pousar
    (área de trabalho, janela maximizada ou minimizada, janela do próprio mascote).
    No Mac ainda não há: devolve None."""
    if not WIN:
        return None
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if pid.value == os.getpid():
        return "proprio"
    nome = ctypes.create_unicode_buffer(64)
    user32.GetClassNameW(hwnd, nome, 64)
    if nome.value in ("Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"):
        return None
    if user32.IsZoomed(hwnd) or user32.IsIconic(hwnd):
        return None
    r = wintypes.RECT()
    if ctypes.windll.dwmapi.DwmGetWindowAttribute(wintypes.HWND(hwnd), 9, ctypes.byref(r), ctypes.sizeof(r)):
        user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right


POUSO_DISPONIVEL = WIN


def fontes_pil(forte=True):
    """Arquivos de fonte para o Pillow, do melhor para o reserva."""
    if WIN:
        pasta = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        nomes = ["segoeuib.ttf", "arialbd.ttf"] if forte else ["segoeui.ttf", "arial.ttf"]
        return [str(pasta / n) for n in nomes]
    if MAC:
        return ["/System/Library/Fonts/SFNS.ttf", "/System/Library/Fonts/HelveticaNeue.ttc",
                "/System/Library/Fonts/Helvetica.ttc", "/Library/Fonts/Arial.ttf"]
    return ["DejaVuSans-Bold.ttf" if forte else "DejaVuSans.ttf"]


def sem_janela():
    """Argumentos para rodar um comando sem abrir janela preta no Windows."""
    return {"creationflags": 0x08000000} if WIN else {}


def pasta_sessoes_do_app():
    if WIN:
        return Path(os.environ.get("APPDATA", "")) / "Claude" / "claude-code-sessions"
    if MAC:
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude-code-sessions"
    return Path.home() / ".config" / "Claude" / "claude-code-sessions"


_cache_app = {"quando": 0.0, "mapa": {}}


def sessoes_do_app():
    """Relaciona o número da sessão do Claude Code ao número interno e ao título no aplicativo."""
    agora = time.time()
    if agora - _cache_app["quando"] < 10:
        return _cache_app["mapa"]
    mapa = {}
    pasta = pasta_sessoes_do_app()
    if pasta.exists():
        for arq in pasta.glob("*/*/local_*.json"):
            try:
                d = json.loads(arq.read_text(encoding="utf-8"))
            except Exception:
                continue
            if d.get("cliSessionId") and d.get("sessionId"):
                mapa[d["cliSessionId"]] = {"id": d["sessionId"], "titulo": d.get("title") or "",
                                           "arquivada": bool(d.get("isArchived"))}
    _cache_app.update(quando=agora, mapa=mapa)
    return mapa


def abrir_sessao(cli_id):
    """Abre a conversa exata no aplicativo do Claude. Devolve False se não for uma conversa do aplicativo.
    Usa o link claude://code/continue?session=..., que o aplicativo aceita mas ainda não está documentado."""
    info = sessoes_do_app().get(cli_id)
    if not info:
        return False
    try:
        abrir(f"claude://code/continue?session={info['id']}")
        return True
    except Exception:
        return False
