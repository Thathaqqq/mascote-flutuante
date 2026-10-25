"""Chat rápido do mascote, no estilo "barra embaixo do personagem".

- Barra branca arredondada logo abaixo do mascote: "+" (nova conversa), campo
  "Iniciar novo chat" e botão de enviar. Aparece ao passar o mouse no mascote
  ou pelo atalho, e some sozinha se não estiver em uso.
- As respostas aparecem num cartão acima do mascote, em balões; a conversa
  continua entre uma pergunta e outra (o Claude lembra o que foi dito).
- Enter envia, Esc fecha. Usa o comando `claude` com a conta da própria pessoa.
"""
import json
import os
import re
import subprocess
import threading
import tkinter as tk
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFilter
    from camada import Camada
    TEM_PIL = True
except Exception:
    TEM_PIL = False

CHAVE = "#010203"  # cor que vira transparente nos cantos do cartão
COR = {
    "cartao": "#FFFFFF",
    "borda": "#E3E6EA",
    "sombra": "#D5D9DF",
    "titulo": "#1F2328",
    "apoio": "#6B7280",
    "dica": "#9AA0A6",
    "eu": "#2F6FED",
    "eu_texto": "#FFFFFF",
    "claude": "#F1F3F5",
    "claude_texto": "#1F2328",
    "mais": "#F1F3F5",
    "enviar": (47, 111, 237),
    "enviar_apagado": (191, 211, 251),
}


def _limpar_markdown(t):
    t = re.sub(r"```[a-zA-Z]*\n?", "", t)
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
    t = re.sub(r"(?m)^#{1,6}\s*", "", t)
    t = re.sub(r"`([^`]+)`", r"\1", t)
    return t.strip()


def _redondo(c, x0, y0, x1, y1, r, **kw):
    r = min(r, (x1 - x0) / 2, (y1 - y0) / 2)
    pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1, x1 - r, y1,
           x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
    return c.create_polygon(pts, smooth=True, **kw)


def _maozinha(c, item):
    c.tag_bind(item, "<Enter>", lambda e: c.config(cursor="hand2"))
    c.tag_bind(item, "<Leave>", lambda e: c.config(cursor=""))


# ---------------- barra ----------------

class Barra:
    def __init__(self, root, s, ao_enviar, ao_nova, ao_esc):
        self.root, self.s = root, s
        self.ao_enviar, self.ao_nova, self.ao_esc = ao_enviar, ao_nova, ao_esc
        self.Wp, self.Hp, self.pad = int(330 * s), int(50 * s), int(12 * s)
        self.W, self.H = self.Wp + 2 * self.pad, self.Hp + 2 * self.pad
        self.dica = "Iniciar novo chat"
        self.com_dica = True
        self.ativo = False  # tem texto: botão de enviar forte

        self.fundo = tk.Toplevel(root)
        self.fundo.overrideredirect(True)
        self.fundo.attributes("-topmost", True)
        self.fundo.config(bg=CHAVE)
        self.cv = tk.Canvas(self.fundo, width=self.W, height=self.H, bg=CHAVE, highlightthickness=0)
        self.cv.pack()
        self.cv.bind("<Button-1>", self._clique)
        self.cv.bind("<Motion>", self._mover)
        if TEM_PIL:
            self.fundo.geometry(f"{self.W}x{self.H}")
            self.camada = Camada(self.fundo)
        else:
            self.fundo.wm_attributes("-transparentcolor", CHAVE)
            self.camada = None

        # campo de texto numa janelinha branca por cima da barra
        self.jcampo = tk.Toplevel(root)
        self.jcampo.overrideredirect(True)
        self.jcampo.attributes("-topmost", True)
        self.jcampo.config(bg="white")
        self.campo = tk.Entry(self.jcampo, font=("Segoe UI", 11), relief="flat", bd=0, bg="white",
                              fg=COR["dica"], insertbackground=COR["titulo"], highlightthickness=0)
        self.campo.pack(fill="both", expand=True)
        self.campo.insert(0, self.dica)
        self.campo.bind("<FocusIn>", self._entrar)
        self.campo.bind("<FocusOut>", self._sair)
        self.campo.bind("<KeyRelease>", lambda e: self._atualizar_botao())
        self.campo.bind("<Return>", lambda e: self._enviar())
        self.campo.bind("<Escape>", lambda e: self.ao_esc())
        self.cw = self.Wp - int(100 * s)
        self.ch = int(26 * s)
        self.jcampo.geometry(f"{self.cw}x{self.ch}")
        self._pintar()
        self.esconder()

    # --- desenho ---
    def _pintar(self):
        s, pad, Wp, Hp = self.s, self.pad, self.Wp, self.Hp
        cor_env = COR["enviar"] if self.ativo else COR["enviar_apagado"]
        if self.camada:
            k = 3
            img = Image.new("RGBA", (self.W * k, self.H * k), (0, 0, 0, 0))
            sombra = Image.new("L", img.size, 0)
            ImageDraw.Draw(sombra).rounded_rectangle(
                (pad * k, (pad + 3 * s) * k, (pad + Wp) * k, (pad + Hp + 3 * s) * k), radius=Hp * k / 2, fill=90)
            sombra = sombra.filter(ImageFilter.GaussianBlur(7 * s * k))
            img = Image.new("RGBA", img.size, (20, 30, 50, 0))
            img.putalpha(sombra)
            d = ImageDraw.Draw(img)
            d.rounded_rectangle((pad * k, pad * k, (pad + Wp) * k, (pad + Hp) * k), radius=Hp * k / 2,
                                fill=(255, 255, 255, 255))
            cy = (pad + Hp / 2) * k
            r = 16 * s * k
            mx = (pad + 25 * s) * k
            d.ellipse((mx - r, cy - r, mx + r, cy + r), fill=(241, 243, 245, 255))
            t = 7 * s * k
            lw = max(2, int(1.8 * s * k))
            d.line((mx - t, cy, mx + t, cy), fill=(60, 64, 67, 255), width=lw)
            d.line((mx, cy - t, mx, cy + t), fill=(60, 64, 67, 255), width=lw)
            ex = (pad + Wp - 25 * s) * k
            d.ellipse((ex - r, cy - r, ex + r, cy + r), fill=cor_env + (255,))
            a = 6 * s * k
            d.line((ex, cy + a, ex, cy - a), fill="white", width=lw)
            d.line((ex - a * 0.8, cy - a * 0.2, ex, cy - a), fill="white", width=lw)
            d.line((ex + a * 0.8, cy - a * 0.2, ex, cy - a), fill="white", width=lw)
            self.img = img.resize((self.W, self.H), Image.LANCZOS)
        else:
            c = self.cv
            c.delete("all")
            _redondo(c, pad, pad, pad + Wp, pad + Hp, Hp / 2, fill="white", outline=COR["borda"])
            cy = pad + Hp / 2
            c.create_oval(pad + 9 * s, cy - 16 * s, pad + 41 * s, cy + 16 * s, fill=COR["mais"], outline="")
            c.create_text(pad + 25 * s, cy, text="+", font=("Segoe UI", 14), fill="#3C4043")
            cor = "#%02x%02x%02x" % cor_env
            c.create_oval(pad + Wp - 41 * s, cy - 16 * s, pad + Wp - 9 * s, cy + 16 * s, fill=cor, outline="")
            c.create_text(pad + Wp - 25 * s, cy, text="↑", font=("Segoe UI Semibold", 13), fill="white")

    def _mostrar_img(self):
        if self.camada and self.visivel:
            self.camada.mostrar(self.img, self.x, self.y)

    # --- campo ---
    def _entrar(self, e=None):
        if self.com_dica:
            self.campo.delete(0, "end")
            self.campo.config(fg=COR["titulo"])
            self.com_dica = False

    def _sair(self, e=None):
        if not self.campo.get():
            self.campo.insert(0, self.dica)
            self.campo.config(fg=COR["dica"])
            self.com_dica = True

    def texto(self):
        return "" if self.com_dica else self.campo.get().strip()

    def limpar(self):
        self.campo.delete(0, "end")
        self._atualizar_botao()

    def trocar_dica(self, dica):
        self.dica = dica
        if self.com_dica:
            self.campo.delete(0, "end")
            self.campo.insert(0, dica)

    def _atualizar_botao(self):
        ativo = bool(self.texto())
        if ativo != self.ativo:
            self.ativo = ativo
            self._pintar()
            self._mostrar_img()

    def _enviar(self):
        t = self.texto()
        if t:
            self.ao_enviar(t)

    def focar(self):
        try:
            self.jcampo.focus_force()
            self.campo.focus_set()
            self._entrar()
        except tk.TclError:
            pass

    # --- cliques nos botões desenhados ---
    def _onde(self, x, y):
        s, pad, Wp, Hp = self.s, self.pad, self.Wp, self.Hp
        cy = pad + Hp / 2
        if abs(y - cy) <= 18 * s:
            if abs(x - (pad + 25 * s)) <= 18 * s:
                return "mais"
            if abs(x - (pad + Wp - 25 * s)) <= 18 * s:
                return "enviar"
        if pad <= x <= pad + Wp and pad <= y <= pad + Hp:
            return "barra"
        return None

    def _mover(self, e):
        self.cv.config(cursor="hand2" if self._onde(e.x, e.y) in ("mais", "enviar") else "")

    def _clique(self, e):
        onde = self._onde(e.x, e.y)
        if onde == "mais":
            self.ao_nova()
        elif onde == "enviar":
            self._enviar()
        elif onde == "barra":
            self.focar()

    # --- posição e visibilidade ---
    def posicionar(self, x, y):
        self.x, self.y = int(x), int(y)
        self.fundo.geometry(f"+{self.x}+{self.y}")
        cx = self.x + self.pad + int(50 * self.s)
        cy = self.y + self.pad + (self.Hp - self.ch) // 2
        self.jcampo.geometry(f"+{cx}+{cy}")
        self._mostrar_img()

    def mostrar(self):
        self.visivel = True
        self.fundo.deiconify()
        self.jcampo.deiconify()
        self.jcampo.lift()
        if not self.camada:
            self.cv.lift()
        self._mostrar_img()

    def esconder(self):
        self.visivel = False
        self.fundo.withdraw()
        self.jcampo.withdraw()

    def contem(self, px, py):
        return self.visivel and self.x <= px <= self.x + self.W and self.y <= py <= self.y + self.H

    def em_uso(self):
        try:
            foco = self.root.focus_get()
        except (KeyError, tk.TclError):
            foco = None
        return bool(self.texto()) or foco is self.campo


# ---------------- cartão das respostas ----------------

class Cartao:
    def __init__(self, root, s, ao_fechar):
        self.root, self.s = root, s
        self.W = int(330 * s)
        self.Hmax = int(380 * s)
        self.H = int(140 * s)
        self.ao_fechar = ao_fechar
        self.j = tk.Toplevel(root)
        self.j.overrideredirect(True)
        self.j.attributes("-topmost", True)
        self.j.config(bg=CHAVE)
        self.j.wm_attributes("-transparentcolor", CHAVE)
        self.c = tk.Canvas(self.j, width=self.W, height=self.H, bg=CHAVE, highlightthickness=0)
        self.c.pack()
        self.conv = tk.Canvas(self.j, bg=COR["cartao"], highlightthickness=0, bd=0)
        self.conv.bind("<MouseWheel>", lambda e: self.conv.yview_scroll(int(-e.delta / 120) * 3, "units"))
        self.c.bind("<MouseWheel>", lambda e: self.conv.yview_scroll(int(-e.delta / 120) * 3, "units"))
        self.f_texto = ("Segoe UI", 10)
        self.f_peq = ("Segoe UI", 8)
        self.visivel = False
        self.j.withdraw()

    def _moldura(self):
        c, s, W, H = self.c, self.s, self.W, self.H
        c.delete("all")
        c.config(width=W, height=H)
        _redondo(c, 3, 5, W - 1, H - 1, 18 * s, fill=COR["sombra"], outline="")
        _redondo(c, 1, 1, W - 3, H - 4, 18 * s, fill=COR["cartao"], outline=COR["borda"])
        c.create_text(18 * s, 20 * s, text="Chat rápido", anchor="w", font=("Segoe UI Semibold", 10),
                      fill=COR["titulo"])
        x = c.create_text(W - 18 * s, 19 * s, text="✕", anchor="e", font=("Segoe UI", 10), fill=COR["apoio"])
        c.tag_bind(x, "<Button-1>", lambda e: self.ao_fechar())
        _maozinha(c, x)
        c.create_window(int(12 * s), int(36 * s), window=self.conv, anchor="nw",
                        width=W - int(24 * s), height=H - int(48 * s))

    def desenhar(self, mensagens):
        cv, s = self.conv, self.s
        cv.delete("all")
        largura = self.W - int(24 * s)
        maximo = int(largura * 0.8)
        y = 4 * s
        for quem, texto in mensagens:
            eu = quem == "eu"
            t = cv.create_text(0, 0, text=texto, font=self.f_texto, width=maximo - 24 * s, anchor="nw",
                               fill=COR["eu_texto"] if eu else COR["claude_texto"])
            x0, y0, x1, y1 = cv.bbox(t)
            w, h = x1 - x0, y1 - y0
            bx0 = largura - w - 28 * s if eu else 4 * s
            cv.coords(t, bx0 + 12 * s, y + 8 * s)
            fundo = _redondo(cv, bx0, y, bx0 + w + 24 * s, y + h + 16 * s, 14 * s,
                             fill=COR["eu"] if eu else COR["claude"], outline="")
            cv.tag_lower(fundo)
            y += h + 16 * s
            if not eu and not texto.startswith("Pensando"):
                cp = cv.create_text(bx0 + 6 * s, y + 4 * s, text="Copiar", anchor="nw", font=self.f_peq,
                                    fill=COR["apoio"])
                cv.tag_bind(cp, "<Button-1>", lambda e, tx=texto, item=cp: self._copiar(tx, item))
                _maozinha(cv, cp)
                y += 18 * s
            y += 8 * s
        novo_h = int(min(self.Hmax, max(110 * s, y + 52 * s)))
        if novo_h != self.H or not self.c.find_all():
            self.H = novo_h
            self._moldura()
        cv.config(scrollregion=(0, 0, largura, max(y, self.H - 48 * s)))
        cv.yview_moveto(1.0)

    def _copiar(self, texto, item):
        self.root.clipboard_clear()
        self.root.clipboard_append(texto)
        self.conv.itemconfig(item, text="Copiado")
        self.root.after(1200, lambda: self.conv.winfo_exists() and self.conv.itemconfig(item, text="Copiar"))

    def posicionar(self, x_meio, y_base):
        self.j.geometry(f"+{int(x_meio - self.W / 2)}+{int(max(0, y_base - self.H))}")

    def mostrar(self):
        self.visivel = True
        self.j.deiconify()
        self.j.lift()

    def esconder(self):
        self.visivel = False
        self.j.withdraw()

    def contem(self, px, py):
        if not self.visivel:
            return False
        x, y = self.j.winfo_x(), self.j.winfo_y()
        return x <= px <= x + self.W and y <= py <= y + self.H


# ---------------- conjunto ----------------

class ChatRapido:
    def __init__(self, root, escala, ao_comecar, ao_terminar):
        self.root = root
        self.ao_comecar, self.ao_terminar = ao_comecar, ao_terminar
        self.sessao = None
        self.rodando = False
        self.mensagens = []
        self.pontos = 0
        self.aberto = False
        self.barra = Barra(root, escala, self.enviar, self.nova_conversa, self.fechar)
        self.cartao = Cartao(root, escala, self.fechar)
        self.ultimo_pos = None

    # --- abrir e fechar ---
    def abrir(self, focar=False):
        if not self.aberto:
            self.aberto = True
            self.barra.mostrar()
            if self.mensagens:
                self.cartao.mostrar()
            if self.ultimo_pos:
                self.posicionar(*self.ultimo_pos)
        if focar:
            self.root.after(60, self.barra.focar)

    def fechar(self):
        self.aberto = False
        self.barra.esconder()
        self.cartao.esconder()

    def em_uso(self, cursor):
        """Fica aberto enquanto há conversa, texto, foco, resposta a caminho ou cursor por cima."""
        return (self.rodando or bool(self.mensagens) or self.barra.em_uso()
                or self.barra.contem(*cursor) or self.cartao.contem(*cursor))

    def posicionar(self, x_meio, y_topo_mascote, y_pes):
        self.ultimo_pos = (x_meio, y_topo_mascote, y_pes)
        self.barra.posicionar(x_meio - self.barra.W / 2, y_pes - self.barra.pad - 4)
        self.cartao.posicionar(x_meio, y_topo_mascote + 30)

    # --- conversa ---
    def _animar_pensando(self):
        if not self.rodando or not self.mensagens:
            return
        self.pontos = (self.pontos + 1) % 4
        self.mensagens[-1] = ("claude", "Pensando" + "." * self.pontos)
        self.cartao.desenhar(self.mensagens)
        self.root.after(350, self._animar_pensando)

    def enviar(self, pergunta):
        if self.rodando:
            return
        self.barra.limpar()
        self.mensagens.append(("eu", pergunta))
        self.mensagens.append(("claude", "Pensando"))
        self.rodando = True
        self.cartao.desenhar(self.mensagens)
        self.cartao.mostrar()
        if self.ultimo_pos:
            self.posicionar(*self.ultimo_pos)
        self.barra.trocar_dica("Continuar a conversa")
        self._animar_pensando()
        self.ao_comecar()

        def rodar():
            env = dict(os.environ, MASCOTE_INTERNO="1")
            cmd = ["claude", "-p", pergunta, "--output-format", "json"]
            if self.sessao:
                cmd += ["--resume", self.sessao]
            try:
                r = subprocess.run(cmd, cwd=str(Path.home()), env=env, capture_output=True, text=True,
                                   encoding="utf-8", timeout=300, creationflags=0x08000000)
                try:
                    dados = json.loads(r.stdout)
                    saida, sessao = dados.get("result") or "Sem resposta.", dados.get("session_id")
                except (ValueError, AttributeError):
                    saida, sessao = (r.stdout or r.stderr or "Sem resposta.").strip(), None
            except FileNotFoundError:
                saida, sessao = "Não achei o Claude Code instalado (comando claude).", None
            except subprocess.TimeoutExpired:
                saida, sessao = "Demorou demais. Tente pelo Claude.", None
            self.root.after(0, lambda: self._fim(_limpar_markdown(saida), sessao))

        threading.Thread(target=rodar, daemon=True).start()

    def _fim(self, saida, sessao):
        self.rodando = False
        if sessao:
            self.sessao = sessao
        self.mensagens[-1] = ("claude", saida)
        self.cartao.desenhar(self.mensagens)
        if self.ultimo_pos:
            self.posicionar(*self.ultimo_pos)
        self.ao_terminar()

    def nova_conversa(self):
        if self.rodando:
            return
        self.sessao = None
        self.mensagens = []
        self.cartao.esconder()
        self.barra.trocar_dica("Iniciar novo chat")
        self.barra.focar()
