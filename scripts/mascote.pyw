"""Mascote do Claude: bonequinho flutuante que mostra o que o Claude está fazendo.

- Fica por cima das outras janelas e pode ser arrastado.
- Mostra: trabalhando, precisa de você, pronto para revisar, travou.
- Olha para o cursor, reage a cliques e pode andar atrás do cursor.
- Clique: abre o Claude.  Clique no número: lista de conversas.
- Botão direito: chat rápido, modo mini, seguir o cursor, personagem, sair.

Com o Pillow instalado, a janela tem transparência real (bordas suaves) e
aceita personagens em 3D. Sem ele, desenha só os personagens de quadradinhos.
"""
import ctypes
import json
import math
import os
import socket
import subprocess
import threading
import time
import tkinter as tk
from ctypes import wintypes
from pathlib import Path

try:
    from PIL import Image, ImageChops, ImageDraw, ImageFont
    import borboleta3d
    TEM_PIL = True
except Exception:
    TEM_PIL = False

AQUI = Path(__file__).resolve().parent
BASE = Path.home() / ".claude" / "mascote"
PASTA_ESTADO = BASE / "estado"
PASTA_PERSONAGENS = BASE / "personagens"
PERSONAGENS_PRONTOS = AQUI.parent / "personagens"
CONFIG = BASE / "config.json"
PORTA = 47653
TICK = 45  # ms entre quadros

TRANSPARENTE = "#010203"
COR_ESTADO = {
    "trabalhando": "#3B82F6",
    "esperando": "#F59E0B",
    "pronto": "#22A35A",
    "bloqueado": "#DC2626",
    "ocioso": "#9CA3AF",
}
TEXTO_ESTADO = {
    "trabalhando": "Trabalhando",
    "esperando": "Precisa de você",
    "pronto": "Pronto para revisar",
    "bloqueado": "Algo travou",
    "ocioso": "",
}
PRIORIDADE = ["esperando", "bloqueado", "pronto", "trabalhando"]
RESERVA = {"nome": "Clawd", "cores": {"X": "#D97757", "E": "#1F1F1F"}, "mapa": [
    "..XXXXXXXX..", "..XXXXXXXX..", "..XEXXXXEX..", "..XEXXXXEX..", "XXXXXXXXXXXX",
    "XXXXXXXXXXXX", "..XXXXXXXX..", "..X.X..X.X..", "..X.X..X.X.."]}

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass


# ---------- utilidades ----------

def ler_json(caminho, padrao):
    try:
        return json.loads(Path(caminho).read_text(encoding="utf-8"))
    except Exception:
        return padrao


def salvar_config(cfg):
    BASE.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")


def eh_3d(p):
    return p.get("tipo") == "borboleta3d"


def carregar_personagens():
    """Personagens prontos do plugin + personalizados da pessoa (estes ganham no mesmo nome)."""
    todos = {}
    for pasta in (PERSONAGENS_PRONTOS, PASTA_PERSONAGENS):
        if not pasta.exists():
            continue
        for arq in sorted(pasta.glob("*.json")):
            p = ler_json(arq, None)
            if not p:
                continue
            if eh_3d(p):
                if not TEM_PIL or not (arq.parent / p.get("imagem", "")).is_file():
                    continue
                p["_imagem"] = str(arq.parent / p["imagem"])
            elif not (p.get("mapa") and p.get("cores")):
                continue
            todos[p.get("nome") or arq.stem] = p
    return todos or {"Clawd": RESERVA}


def posicao_cursor():
    pt = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def clicou_agora():
    return bool(user32.GetAsyncKeyState(0x01) & 0x8001)


def focar_claude():
    """Traz a janela do Claude para a frente. Devolve False se não achou."""
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


def ha_quanto(ts):
    s = max(0, int(time.time() - ts))
    if s < 60:
        return "agora"
    if s < 3600:
        return f"há {s // 60} min"
    return f"há {s // 3600} h"


def ler_sessoes():
    """Lê os estados gravados pelo gancho. Ignora sessões paradas há mais de 12 h."""
    sessoes = []
    if not PASTA_ESTADO.exists():
        return sessoes
    agora = time.time()
    for arq in PASTA_ESTADO.glob("*.json"):
        r = ler_json(arq, None)
        if r and agora - r.get("quando", 0) <= 12 * 3600:
            sessoes.append(r)
    sessoes.sort(key=lambda r: r.get("quando", 0), reverse=True)
    return sessoes


def cor_rgb(hexa):
    return tuple(int(hexa[i:i + 2], 16) for i in (1, 3, 5))


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
        user32.UpdateLayeredWindow(self.hwnd, tela, ctypes.byref(wintypes.POINT(x, y)),
                                   ctypes.byref(wintypes.SIZE(w, h)), mdc, ctypes.byref(wintypes.POINT(0, 0)),
                                   0, ctypes.byref(_BLEND(0, 0, 255, 1)), 2)
        gdi32.SelectObject(mdc, antigo)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(mdc)
        user32.ReleaseDC(None, tela)


# ---------- janela principal ----------

class Mascote:
    def __init__(self, servidor):
        self.servidor = servidor
        self.cfg = ler_json(CONFIG, {})
        self.personagens = carregar_personagens()
        self.vistos = {}  # sessao -> quando já visto (pronto/bloqueado)
        self.sessoes = []
        self.estado = "ocioso"
        self.quadro = 0
        self.piscar_ate = 0
        self.pulo_extra_ate = 0
        self.olhar_clique = None
        self.andando = False
        self.virado = 1
        self.cursor_dentro = False
        self.dir_olhar = (0, 0)
        self.rel_cursor = (0, 0)
        self.ultimo_cursor = None
        self.ultimo_t = time.time()
        self.dica_ate = time.time() + 5
        self.arraste = None
        self.area_numero = None
        self.bandeja = None
        self.chat = None
        self.chat_rodando = False
        self.borboletas = {}
        self.voo = borboleta3d.Voo() if TEM_PIL else None
        self.cache_img = {}

        self.root = tk.Tk()
        self.root.title("Mascote do Claude")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.config(bg=TRANSPARENTE)
        if not TEM_PIL:
            self.root.wm_attributes("-transparentcolor", TRANSPARENTE)

        self.canvas = tk.Canvas(self.root, bg=TRANSPARENTE, highlightthickness=0, cursor="hand2")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self.ao_apertar)
        self.canvas.bind("<B1-Motion>", self.ao_arrastar)
        self.canvas.bind("<ButtonRelease-1>", self.ao_soltar)
        self.canvas.bind("<Button-3>", self.abrir_menu)

        self.aplicar_tamanho()
        x = self.cfg.get("x", self.root.winfo_screenwidth() - self.largura - 40)
        y = self.cfg.get("y", self.root.winfo_screenheight() - self.altura - 80)
        self.root.geometry(f"+{x}+{y}")
        self.camada = Camada(self.root) if TEM_PIL else None
        if TEM_PIL:
            dpi = self.root.winfo_fpixels("1i")
            self.fonte = self.carregar_fonte(["segoeuib.ttf", "arialbd.ttf"], round(10 * dpi / 72))
            self.fonte_mini = self.carregar_fonte(["segoeuib.ttf", "arialbd.ttf"], round(8.5 * dpi / 72))

        threading.Thread(target=self.escutar, daemon=True).start()
        self.atualizar_estado()
        self.animar()

    @staticmethod
    def carregar_fonte(nomes, tam):
        for n in nomes:
            try:
                return ImageFont.truetype(str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / n), tam)
            except OSError:
                continue
        return ImageFont.load_default()

    def personagem(self):
        nome = self.cfg.get("personagem")
        return self.personagens.get(nome) or self.personagens.get("Clawd") or next(iter(self.personagens.values()))

    def borboleta(self, p):
        mini = bool(self.cfg.get("mini"))
        chave = (p["_imagem"], mini)
        if chave not in self.borboletas:
            self.borboletas[chave] = borboleta3d.Borboleta3D(p["_imagem"], p.get("centro", 0.5),
                                                             58 if mini else 150)
        return self.borboletas[chave]

    # --- comandos de fora (iniciar.py) ---
    def escutar(self):
        while True:
            try:
                conn, _ = self.servidor.accept()
                with conn:
                    cmd = conn.recv(64).decode(errors="ignore").strip()
                self.root.after(0, lambda c=cmd: self.comando(c))
            except OSError:
                return

    def comando(self, cmd):
        if cmd == "sair":
            self.root.destroy()
        elif cmd == "recarregar":
            self.cfg = ler_json(CONFIG, {})
            self.personagens = carregar_personagens()
            self.aplicar_tamanho()

    # --- tamanho ---
    def aplicar_tamanho(self):
        mini = self.cfg.get("mini")
        if eh_3d(self.personagem()):
            self.px = 0
            self.largura, self.altura = (110, 110) if mini else (260, 270)
        elif mini:
            self.px, self.largura, self.altura = 4, 80, 64
        else:
            self.px, self.largura, self.altura = 9, 240, 190
        self.canvas.config(width=self.largura, height=self.altura)
        self.root.geometry(f"{self.largura}x{self.altura}")

    # --- estado ---
    def atualizar_estado(self):
        self.sessoes = ler_sessoes()
        estados = set()
        for s in self.sessoes:
            e = s.get("estado")
            if e in ("pronto", "bloqueado") and self.vistos.get(s["sessao"]) == s.get("quando"):
                continue
            estados.add(e)
        if self.chat_rodando:
            estados.add("trabalhando")
        self.estado = next((e for e in PRIORIDADE if e in estados), "ocioso")
        if self.bandeja:
            self.preencher_bandeja()
        self.root.after(1000, self.atualizar_estado)

    def marcar_vistos(self):
        for s in self.sessoes:
            if s.get("estado") in ("pronto", "bloqueado"):
                self.vistos[s["sessao"]] = s.get("quando")

    def ativas(self):
        return [s for s in self.sessoes if s.get("estado") not in ("pronto", "bloqueado")
                or self.vistos.get(s["sessao"]) != s.get("quando")]

    # --- cursor ---
    def acompanhar_cursor(self, dt):
        cx, cy = posicao_cursor()
        wx, wy = self.root.winfo_x(), self.root.winfo_y()
        meio_x, meio_y = wx + self.largura / 2, wy + self.altura * 0.65
        self.cursor_dentro = wx <= cx <= wx + self.largura and wy <= cy <= wy + self.altura
        self.rel_cursor = (cx - meio_x, cy - meio_y)
        self.dir_olhar = (max(-1, min(1, round((cx - meio_x) / 150))),
                          max(-1, min(1, round((cy - meio_y) / 150))))

        # cursor chegando rápido perto: susto
        if self.ultimo_cursor and dt > 0 and self.voo:
            vel = math.hypot(cx - self.ultimo_cursor[0], cy - self.ultimo_cursor[1]) / dt
            antes = math.hypot(self.ultimo_cursor[0] - meio_x, self.ultimo_cursor[1] - meio_y)
            agora = math.hypot(*self.rel_cursor)
            if vel > 1800 and agora < 230 and agora < antes and not self.cursor_dentro:
                self.voo.susto()
        self.ultimo_cursor = (cx, cy)

        if clicou_agora() and not self.cursor_dentro:
            self.pulo_extra_ate = self.quadro + 8
            self.olhar_clique = (self.quadro + 30, self.dir_olhar)
            if self.voo:
                self.voo.agito()

        self.andando = False
        if self.cfg.get("seguir") and not self.arraste:
            # fica um pouco abaixo e à direita do cursor, sem cobrir o que a pessoa clica
            alvo_x = cx + 30 - self.largura * 0.2
            alvo_y = cy + 30
            dx, dy = alvo_x - wx, alvo_y - wy
            dist = math.hypot(dx, dy)
            if dist > 50:
                passo = min(dist * 0.09, 14)
                nx = int(wx + dx / dist * passo)
                ny = int(wy + dy / dist * passo)
                nx = max(0, min(nx, self.root.winfo_screenwidth() - self.largura))
                ny = max(0, min(ny, self.root.winfo_screenheight() - self.altura))
                self.root.geometry(f"+{nx}+{ny}")
                self.andando = True
                self.virado = 1 if dx > 0 else -1
                self.posicionar_janelas()

    # --- desenho ---
    def animar(self):
        agora = time.time()
        dt = min(0.2, agora - self.ultimo_t)
        self.ultimo_t = agora
        self.quadro += 1
        if self.quadro % 80 == 0:
            self.piscar_ate = self.quadro + 4
        try:
            self.acompanhar_cursor(dt)
        except Exception:
            self.cursor_dentro, self.dir_olhar = False, (0, 0)
        if TEM_PIL:
            self.desenhar_imagem(dt)
        else:
            self.desenhar_canvas()
        self.root.after(TICK, self.animar)

    def pose_pixel(self):
        """Pulo, olhar e aperto do personagem de quadradinhos neste quadro."""
        f = self.quadro // 2  # o ritmo foi pensado para 90 ms por quadro
        e = self.estado
        olhar_x, olhar_y = self.dir_olhar
        if self.olhar_clique and self.quadro < self.olhar_clique[0]:
            olhar_x, olhar_y = self.olhar_clique[1]
        pulo, aperto = 0, 1.0
        if e == "ocioso":
            pulo = [0, 0, 1, 1, 1, 0][f // 4 % 6]
        elif e == "trabalhando":
            pulo = [0, 1][f // 3 % 2]
            if not self.cursor_dentro:
                olhar_x = [-1, 0, 1, 0][f // 5 % 4]
                olhar_y = 0
            aperto = 1.0 if f // 3 % 2 else 0.88
        elif e == "esperando":
            pulo = [0, 2, 4, 2, 0, 0, 0, 0][f % 8]
        elif e == "pronto":
            pulo = [0, 3, 0, 0, 0, 0, 0, 0, 0, 0][f % 10]
        elif e == "bloqueado" and f % 20 < 6:
            olhar_x = [-1, 1][f // 2 % 2]
        if self.cursor_dentro:
            pulo = max(pulo, [0, 2, 3, 2][f % 4])
        if self.quadro < self.pulo_extra_ate:
            pulo = max(pulo, [3, 4, 3, 1][(self.pulo_extra_ate - self.quadro) // 2 % 4])
        if self.andando:
            pulo = [0, 2][f % 2]
            olhar_x, olhar_y = self.virado, 0
        return pulo * max(1, self.px // 3), olhar_x, olhar_y, aperto

    def texto_balao(self):
        e, f = self.estado, self.quadro // 2
        texto = TEXTO_ESTADO[e]
        if e == "trabalhando":
            qtd = sum(1 for s in self.sessoes if s.get("estado") == "trabalhando") + (1 if self.chat_rodando else 0)
            texto = (f"Trabalhando em {qtd}" if qtd > 1 else texto) + "." * (f // 4 % 4)
        elif not texto and time.time() < self.dica_ate:
            texto = "Clique para abrir o Claude"
        elif not texto and self.cursor_dentro:
            texto = "Oi!"
        return "" if self.cfg.get("mini") else texto

    # quadradinhos (com Pillow)
    def desenhar_pixel(self, tela):
        p = self.personagem()
        mapa, cores = p["mapa"], p["cores"]
        mini = self.cfg.get("mini")
        px = self.px
        linhas, colunas = len(mapa), max(len(l) for l in mapa)
        pulo, olhar_x, olhar_y, aperto = self.pose_pixel()
        base_y = self.altura - (8 if mini else 14)
        topo = base_y - linhas * px - pulo
        meio = self.largura / 2
        centro_col = (colunas - 1) / 2
        larg_sombra = int(colunas * px / 1.2)
        sombra = self.imagem_cache(("sombra", larg_sombra), lambda: self.sombra_oval(larg_sombra, 7))
        tela.alpha_composite(sombra, (int(meio - sombra.width / 2), int(base_y - sombra.height / 2)))
        d = ImageDraw.Draw(tela)
        piscando = self.quadro < self.piscar_ate
        for li, linha in enumerate(mapa):
            for co, ch in enumerate(linha):
                cor = cores.get(ch) if ch != "." else None
                if not cor:
                    continue
                dx = dy = 0
                if ch == "E":
                    dx, dy = olhar_x * px // 3, olhar_y * px // 3
                    if piscando:
                        cor = cores.get("X", cor)
                x0 = round(meio + (co - centro_col - 0.5) * px * (aperto if ch != "B" else 1.0) + dx)
                y0 = round(topo + li * px + dy)
                d.rectangle((x0, y0, x0 + px - 1, y0 + px - 1), fill=cor)
        return topo, meio + colunas * px / 2

    # borboleta 3D
    def desenhar_borboleta(self, tela, dt):
        p = self.personagem()
        mini = self.cfg.get("mini")
        b = self.borboleta(p)
        rel = self.rel_cursor
        batida, yaw, pitch, roll, brilho, alt = self.voo.passo(dt, self.estado, rel, self.cursor_dentro,
                                                                self.andando, self.virado)
        if mini:
            alt *= 0.4
        sprite, (cx, cy) = b.desenhar(batida, yaw, pitch, roll, brilho, rel)
        chao = self.altura - (10 if mini else 18)
        meio = self.largura / 2
        corpo_y = chao - (26 if mini else 58) - alt
        sombra = borboleta3d.sombra_de(sprite.crop(sprite.getbbox() or (0, 0, 1, 1)), alt)
        tela.alpha_composite(sombra, (int(meio - sombra.width / 2), int(chao - sombra.height / 2)))
        x0, y0 = int(meio - cx), int(corpo_y - cy)
        tela.alpha_composite(sprite, (max(0, x0), max(0, y0)), (max(0, -x0), max(0, -y0)))
        caixa = sprite.getbbox() or (0, 0, sprite.width, sprite.height)
        return y0 + caixa[1], x0 + caixa[2] - (10 if mini else 26)

    def desenhar_imagem(self, dt):
        tela = Image.new("RGBA", (self.largura, self.altura), (0, 0, 0, 0))
        e = self.estado
        mini = self.cfg.get("mini")
        if eh_3d(self.personagem()):
            topo, direita = self.desenhar_borboleta(tela, dt)
        else:
            topo, direita = self.desenhar_pixel(tela)

        # número de conversas (clicável)
        n = len(self.ativas())
        self.area_numero = None
        if n:
            num = self.imagem_cache(("num", n, e, mini), lambda: self.img_numero(n, COR_ESTADO[e], bool(mini)))
            r = num.width / 2
            bx = min(direita + (2 if mini else 6), self.largura - r - 2)
            by = max(topo + 2, r + 2)
            tela.alpha_composite(num, (int(bx - r), int(by - r)))
            self.area_numero = (bx - r, by - r, bx + r, by + r)

        texto = self.texto_balao()
        if texto:
            balao = self.imagem_cache(("balao", texto, e), lambda: self.img_balao(texto, COR_ESTADO[e]))
            bx = int(self.largura / 2 - balao.width / 2)
            by = int(max(2, topo - balao.height - 4))
            tela.alpha_composite(balao, (max(0, bx), by))

        self.camada.mostrar(tela, self.root.winfo_x(), self.root.winfo_y())

    def imagem_cache(self, chave, fazer):
        if chave not in self.cache_img:
            if len(self.cache_img) > 80:
                self.cache_img.clear()
            self.cache_img[chave] = fazer()
        return self.cache_img[chave]

    @staticmethod
    def sombra_oval(largura, altura):
        from PIL import ImageFilter
        m = Image.new("L", (largura + 16, altura + 16), 0)
        ImageDraw.Draw(m).ellipse((8, 8, 8 + largura, 8 + altura), fill=150)
        m = m.filter(ImageFilter.GaussianBlur(3))
        s = Image.new("RGBA", m.size, (40, 40, 40, 0))
        s.putalpha(m)
        return s

    def img_numero(self, n, cor, mini):
        r = 8 if mini else 11
        k = 3
        img = Image.new("RGBA", (2 * r * k, 2 * r * k), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse((0, 0, 2 * r * k - 1, 2 * r * k - 1), fill="white")
        d.ellipse((2 * k, 2 * k, 2 * r * k - 1 - 2 * k, 2 * r * k - 1 - 2 * k), fill=cor)
        img = img.resize((2 * r, 2 * r), Image.LANCZOS)
        d = ImageDraw.Draw(img)
        d.text((r, r), str(n), fill="white", font=self.fonte_mini, anchor="mm")
        return img

    def img_balao(self, texto, cor):
        f = self.fonte
        x0, y0, x1, y1 = f.getbbox(texto)
        pw, ph = 12, 7
        w, h = (x1 - x0) + 2 * pw, (y1 - y0) + 2 * ph
        bico = 7
        k = 3
        img = Image.new("RGBA", ((w + 4) * k, (h + bico + 4) * k), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        caixa = (2 * k, 2 * k, (w + 2) * k, (h + 2) * k)
        meio = (w / 2 + 2) * k
        d.rounded_rectangle(caixa, radius=10 * k, fill=cor)
        d.polygon([(meio - 7 * k, (h + 1) * k), (meio + 7 * k, (h + 1) * k), (meio, (h + 2 + bico) * k)], fill=cor)
        d.rounded_rectangle((caixa[0] + 2 * k, caixa[1] + 2 * k, caixa[2] - 2 * k, caixa[3] - 2 * k),
                            radius=8 * k, fill="white")
        d.polygon([(meio - 5 * k, (h - 1) * k), (meio + 5 * k, (h - 1) * k), (meio, (h + bico - 1) * k)],
                  fill="white")
        img = img.resize((w + 4, h + bico + 4), Image.LANCZOS)
        ImageDraw.Draw(img).text((2 + pw - x0, 2 + ph - y0), texto, fill="#1F1F1F", font=f)
        return img

    # sem Pillow: desenho simples no canvas
    def desenhar_canvas(self):
        c = self.canvas
        c.delete("all")
        p = self.personagem()
        mapa, cores = p["mapa"], p["cores"]
        mini = self.cfg.get("mini")
        px = self.px
        linhas, colunas = len(mapa), max(len(l) for l in mapa)
        pulo, olhar_x, olhar_y, aperto = self.pose_pixel()
        e = self.estado
        base_y = self.altura - (8 if mini else 14)
        topo = base_y - linhas * px - pulo
        meio = self.largura / 2
        centro_col = (colunas - 1) / 2
        c.create_oval(meio - colunas * px / 2.4, base_y - 3, meio + colunas * px / 2.4, base_y + 4,
                      fill="#5A5A5A", outline="")
        piscando = self.quadro < self.piscar_ate
        for li, linha in enumerate(mapa):
            for co, ch in enumerate(linha):
                cor = cores.get(ch) if ch != "." else None
                if not cor:
                    continue
                dx = dy = 0
                if ch == "E":
                    dx, dy = olhar_x * px // 3, olhar_y * px // 3
                    if piscando:
                        cor = cores.get("X", cor)
                x0 = meio + (co - centro_col - 0.5) * px * (aperto if ch != "B" else 1.0) + dx
                y0 = topo + li * px + dy
                c.create_rectangle(x0, y0, x0 + px, y0 + px, fill=cor, outline="")
        n = len(self.ativas())
        self.area_numero = None
        if n:
            r = 8 if mini else 11
            bx = min(meio + colunas * px / 2 + (2 if mini else 6), self.largura - r - 2)
            by = max(topo + 2, r + 2)
            c.create_oval(bx - r, by - r, bx + r, by + r, fill=COR_ESTADO[e], outline="white", width=2)
            c.create_text(bx, by, text=str(n), fill="white", font=("Segoe UI", 8 if mini else 9, "bold"))
            self.area_numero = (bx - r, by - r, bx + r, by + r)
        texto = self.texto_balao()
        if texto:
            t = c.create_text(meio, topo - 30, text=texto, font=("Segoe UI", 10, "bold"), fill="#1F1F1F")
            x0, y0, x1, y1 = c.bbox(t)
            c.create_rectangle(x0 - 10, y0 - 5, x1 + 10, y1 + 5, fill="white", outline=COR_ESTADO[e], width=2)
            c.tag_raise(t)

    # --- mouse no mascote ---
    def ao_apertar(self, ev):
        self.arraste = (ev.x_root, ev.y_root, self.root.winfo_x(), self.root.winfo_y(), False)

    def ao_arrastar(self, ev):
        if not self.arraste:
            return
        x0, y0, wx, wy, _ = self.arraste
        dx, dy = ev.x_root - x0, ev.y_root - y0
        if abs(dx) + abs(dy) > 4:
            self.arraste = (x0, y0, wx, wy, True)
            self.root.geometry(f"+{wx + dx}+{wy + dy}")
            self.posicionar_janelas()

    def ao_soltar(self, ev):
        moveu = self.arraste and self.arraste[4]
        self.arraste = None
        if moveu:
            self.cfg["x"], self.cfg["y"] = self.root.winfo_x(), self.root.winfo_y()
            salvar_config(self.cfg)
            return
        a = self.area_numero
        if a and a[0] - 3 <= ev.x <= a[2] + 3 and a[1] - 3 <= ev.y <= a[3] + 3:
            self.alternar_bandeja()
            return
        self.abrir_claude()

    def abrir_claude(self):
        self.marcar_vistos()
        if not focar_claude():
            self.aviso("Não achei a janela do Claude aberta.")

    def abrir_menu(self, ev):
        m = tk.Menu(self.root, tearoff=0)
        m.add_command(label="Abrir o Claude", command=self.abrir_claude)
        m.add_command(label="Conversas", command=self.alternar_bandeja)
        m.add_command(label="Chat rápido", command=self.alternar_chat)
        m.add_separator()
        self._v_mini = tk.BooleanVar(value=bool(self.cfg.get("mini")))
        self._v_seguir = tk.BooleanVar(value=bool(self.cfg.get("seguir")))
        self._v_auto = tk.BooleanVar(value=bool(self.cfg.get("automatico", True)))
        self._v_pers = tk.StringVar(value=self.personagem().get("nome", ""))
        m.add_checkbutton(label="Modo mini", variable=self._v_mini, command=self.alternar_mini)
        m.add_checkbutton(label="Seguir o cursor", variable=self._v_seguir,
                          command=lambda: self.alternar("seguir", False))
        m.add_checkbutton(label="Abrir junto com o Claude", variable=self._v_auto,
                          command=lambda: self.alternar("automatico", True))
        sub = tk.Menu(m, tearoff=0)
        for nome in self.personagens:
            sub.add_radiobutton(label=nome, value=nome, variable=self._v_pers,
                                command=lambda n=nome: self.trocar_personagem(n))
        sub.add_separator()
        sub.add_command(label="Abrir pasta de personagens", command=self.abrir_pasta_personagens)
        sub.add_command(label="Recarregar personagens", command=lambda: self.comando("recarregar"))
        m.add_cascade(label="Personagem", menu=sub)
        m.add_separator()
        m.add_command(label="Sair", command=self.root.destroy)
        m.tk_popup(ev.x_root, ev.y_root)

    def alternar(self, chave, padrao):
        self.cfg[chave] = not self.cfg.get(chave, padrao)
        if chave == "seguir" and not self.cfg[chave]:
            self.cfg["x"], self.cfg["y"] = self.root.winfo_x(), self.root.winfo_y()
        salvar_config(self.cfg)

    def alternar_mini(self):
        self.alternar("mini", False)
        self.aplicar_tamanho()
        self.posicionar_janelas()

    def trocar_personagem(self, nome):
        self.cfg["personagem"] = nome
        salvar_config(self.cfg)
        self.aplicar_tamanho()

    def abrir_pasta_personagens(self):
        PASTA_PERSONAGENS.mkdir(parents=True, exist_ok=True)
        exemplo = PASTA_PERSONAGENS / "exemplo.json.txt"
        if not exemplo.exists():
            exemplo.write_text(json.dumps({**RESERVA, "nome": "Meu personagem"}, ensure_ascii=False, indent=2),
                               encoding="utf-8")
        os.startfile(PASTA_PERSONAGENS)

    # --- janelas auxiliares ---
    def posicionar_janelas(self):
        x, y = self.root.winfo_x(), self.root.winfo_y()
        for jan in (self.bandeja, self.chat):
            if jan:
                w, h = jan.winfo_reqwidth(), jan.winfo_reqheight()
                jx = min(max(0, x + self.largura - w), self.root.winfo_screenwidth() - w)
                acima = y - h - 4 > 0
                if jan is self.chat and self.bandeja:
                    acima = not acima
                jy = y - h - 4 if acima else y + self.altura + 4
                jan.geometry(f"+{int(jx)}+{int(jy)}")

    def nova_janela(self):
        j = tk.Toplevel(self.root)
        j.overrideredirect(True)
        j.attributes("-topmost", True)
        j.config(bg="#D9D9D9")
        return j

    def cabecalho(self, caixa, titulo, fechar):
        topo = tk.Frame(caixa, bg="white")
        topo.pack(fill="x")
        tk.Label(topo, text=titulo, bg="white", font=("Segoe UI", 11, "bold")).pack(side="left")
        x = tk.Label(topo, text="Fechar", bg="white", fg="#6B7280", cursor="hand2", font=("Segoe UI", 9))
        x.pack(side="right")
        x.bind("<Button-1>", lambda _: fechar())

    def alternar_bandeja(self):
        if self.bandeja:
            self.bandeja.destroy()
            self.bandeja = None
            return
        self.bandeja = self.nova_janela()
        self.preencher_bandeja()

    def preencher_bandeja(self):
        b = self.bandeja
        for w in b.winfo_children():
            w.destroy()
        caixa = tk.Frame(b, bg="white", padx=12, pady=10)
        caixa.pack(padx=1, pady=1)
        self.cabecalho(caixa, "Conversas", self.alternar_bandeja)
        if not self.sessoes:
            tk.Label(caixa, text="Nenhuma conversa nas últimas 12 horas.", bg="white", fg="#6B7280",
                     font=("Segoe UI", 9)).pack(anchor="w", pady=(8, 0))
        for s in self.sessoes[:8]:
            e = s.get("estado", "ocioso")
            visto = e in ("pronto", "bloqueado") and self.vistos.get(s["sessao"]) == s.get("quando")
            linha = tk.Frame(caixa, bg="white", cursor="hand2", pady=6)
            linha.pack(fill="x")
            tk.Label(linha, text="\u25CF", fg=COR_ESTADO["ocioso" if visto else e], bg="white",
                     font=("Segoe UI", 11)).pack(side="left", anchor="n")
            txt = tk.Frame(linha, bg="white")
            txt.pack(side="left", fill="x", padx=(6, 0))
            nome = Path(s.get("pasta") or "").name or "Conversa"
            tk.Label(txt, text=nome, bg="white", font=("Segoe UI", 9, "bold"), anchor="w").pack(fill="x")
            pedido = s.get("aviso") if e == "esperando" and s.get("aviso") else s.get("pedido")
            if pedido:
                tk.Label(txt, text=pedido[:60] + ("..." if len(pedido) > 60 else ""), bg="white",
                         fg="#374151", font=("Segoe UI", 9), anchor="w", justify="left").pack(fill="x")
            tk.Label(txt, text=f"{TEXTO_ESTADO.get(e) or 'Parada'} · {ha_quanto(s.get('quando', 0))}",
                     bg="white", fg="#6B7280", font=("Segoe UI", 8), anchor="w").pack(fill="x")
            for w in [linha] + list(linha.winfo_children()) + list(txt.winfo_children()):
                w.bind("<Button-1>", lambda _: self.abrir_claude())
        b.update_idletasks()
        self.posicionar_janelas()

    # --- chat rápido ---
    def alternar_chat(self):
        if self.chat:
            self.chat.destroy()
            self.chat = None
            return
        self.chat = self.nova_janela()
        caixa = tk.Frame(self.chat, bg="white", padx=10, pady=10)
        caixa.pack(padx=1, pady=1)
        self.cabecalho(caixa, "Chat rápido", self.alternar_chat)
        self.entrada = tk.Entry(caixa, width=42, font=("Segoe UI", 10), relief="solid", bd=1)
        self.entrada.pack(fill="x", pady=(8, 6), ipady=4)
        self.entrada.bind("<Return>", self.enviar_chat)
        self.resposta = tk.Text(caixa, width=42, height=8, wrap="word", font=("Segoe UI", 9),
                                relief="flat", bg="#F7F7F7")
        self.resposta.pack(fill="both")
        self.resposta.insert("1.0", "Escreva e aperte Enter.")
        self.resposta.config(state="disabled")
        copiar = tk.Label(caixa, text="Copiar resposta", bg="white", fg="#3B6FD9", cursor="hand2",
                          font=("Segoe UI", 9))
        copiar.pack(anchor="e", pady=(6, 0))
        copiar.bind("<Button-1>", lambda _: self.copiar_resposta())
        self.chat.update_idletasks()
        self.posicionar_janelas()
        self.chat.after(50, lambda: self.chat and (self.chat.focus_force(), self.entrada.focus_set()))

    def escrever_resposta(self, texto):
        if not self.chat:
            return
        self.resposta.config(state="normal")
        self.resposta.delete("1.0", "end")
        self.resposta.insert("1.0", texto)
        self.resposta.config(state="disabled")

    def copiar_resposta(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.resposta.get("1.0", "end").strip())

    def enviar_chat(self, _=None):
        pergunta = self.entrada.get().strip()
        if not pergunta or self.chat_rodando:
            return
        self.chat_rodando = True
        self.escrever_resposta("Pensando...")

        def rodar():
            env = dict(os.environ, MASCOTE_INTERNO="1")
            try:
                r = subprocess.run(["claude", "-p", pergunta, "--output-format", "text"],
                                   cwd=str(Path.home()), env=env, capture_output=True, text=True,
                                   encoding="utf-8", timeout=300, creationflags=0x08000000)
                saida = (r.stdout or r.stderr or "Sem resposta.").strip()
            except FileNotFoundError:
                saida = "Não achei o Claude Code instalado (comando claude)."
            except subprocess.TimeoutExpired:
                saida = "Demorou demais. Tente pelo Claude."
            self.root.after(0, lambda: self.fim_chat(saida))

        threading.Thread(target=rodar, daemon=True).start()

    def fim_chat(self, saida):
        self.chat_rodando = False
        self.escrever_resposta(saida)
        if self.chat:
            self.entrada.delete(0, "end")

    def aviso(self, texto):
        j = self.nova_janela()
        tk.Label(j, text=texto, bg="white", padx=12, pady=8, font=("Segoe UI", 9)).pack(padx=1, pady=1)
        j.update_idletasks()
        j.geometry(f"+{self.root.winfo_x()}+{max(0, self.root.winfo_y() - j.winfo_reqheight() - 4)}")
        j.after(2500, j.destroy)

    def rodar(self):
        self.root.mainloop()


if __name__ == "__main__":
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        servidor.bind(("127.0.0.1", PORTA))  # só um mascote por vez
    except OSError:
        raise SystemExit(0)
    servidor.listen(4)
    Mascote(servidor).rodar()
