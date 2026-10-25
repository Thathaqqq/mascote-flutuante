"""Borboleta em 3D a partir de uma foto vista de cima.

- Asas: a própria foto. Cada lado vira asa da frente e asa de trás, e cada asa
  é dividida em faixas que se curvam, como uma asa de verdade batendo.
- Corpo: cabeça, tórax e abdômen modelados como volumes redondos com luz e sombra
  (o corpo e as antenas da foto são apagados para dar lugar ao modelo).
- Antenas: curvas em 3D com a pontinha arredondada, que se inclinam para o cursor.
- Luz fixa no mundo: o brilho furta-cor da morpho aparece quando a asa encara a luz.
Só usa Pillow.
"""
import math
from collections import OrderedDict

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter

SUPER = 2          # desenha no dobro e reduz, para as bordas ficarem suaves
FAIXAS = 6         # faixas por asa (curvatura suave)
COR_CORPO = (32, 45, 67)


def _resolver(m, v):
    """Eliminação de Gauss (8 x 8)."""
    n = len(v)
    a = [row[:] + [v[i]] for i, row in enumerate(m)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(a[r][c]))
        a[c], a[p] = a[p], a[c]
        if abs(a[c][c]) < 1e-9:
            raise ValueError("plano degenerado")
        for r in range(n):
            if r != c:
                k = a[r][c] / a[c][c]
                for j in range(c, n + 1):
                    a[r][j] -= k * a[c][j]
    return [a[i][n] / a[i][i] for i in range(n)]


def _coef_perspectiva(destino, origem):
    """Coeficientes do Pillow que levam cada ponto da tela de volta à textura."""
    m, v = [], []
    for (x, y), (X, Y) in zip(destino, origem):
        m.append([x, y, 1, 0, 0, 0, -x * X, -y * X]); v.append(X)
        m.append([0, 0, 0, x, y, 1, -x * Y, -y * Y]); v.append(Y)
    return _resolver(m, v)


def _norm(v):
    n = math.sqrt(sum(c * c for c in v)) or 1.0
    return [c / n for c in v]


def _girar(p, yaw, pitch, roll):
    x, y, z = p
    c, s = math.cos(roll), math.sin(roll)
    x, y = x * c - y * s, x * s + y * c
    c, s = math.cos(pitch), math.sin(pitch)
    y, z = y * c - z * s, y * s + z * c
    c, s = math.cos(yaw), math.sin(yaw)
    x, z = x * c + z * s, -x * s + z * c
    return [x, y, z]


def _normal(pts):
    u = [pts[1][i] - pts[0][i] for i in range(3)]
    v = [pts[3][i] - pts[0][i] for i in range(3)]
    return _norm([u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]])


def _esfera(tam, luz):
    """Bolinha sombreada (para montar o corpo)."""
    img = Image.new("RGBA", (tam, tam), (0, 0, 0, 0))
    px = img.load()
    r = tam / 2
    meio = _norm([luz[0], luz[1], luz[2] + 1])
    for y in range(tam):
        for x in range(tam):
            nx, ny = (x + 0.5 - r) / r, (y + 0.5 - r) / r
            d = nx * nx + ny * ny
            if d > 1:
                continue
            nz = math.sqrt(1 - d)
            dif = max(0.0, nx * luz[0] + ny * luz[1] + nz * luz[2])
            esp = max(0.0, nx * meio[0] + ny * meio[1] + nz * meio[2]) ** 18
            k = 0.45 + 0.9 * dif
            cor = [min(255, int(c * k + 150 * esp)) for c in COR_CORPO]
            borda = min(1.0, (1 - math.sqrt(d)) * r / 1.2)  # borda suave
            px[x, y] = (cor[0], cor[1], cor[2], int(255 * borda))
    return img


class Borboleta3D:
    def __init__(self, caminho, centro=0.5, envergadura=150):
        img = Image.open(caminho).convert("RGBA")
        esc = envergadura * SUPER / img.width
        img = img.resize((max(4, round(img.width * esc)), max(4, round(img.height * esc))), Image.LANCZOS)
        self.W, self.H = W, H = img.size
        self.cx = cx = round(W * centro)
        self._limpar_corpo_da_foto(img)
        self.tex = img

        # medidas do corpo, proporcionais à foto (morpho vista de cima)
        self.y_div = round(H * 0.49)  # onde a asa da frente encontra a de trás
        self.r_corpo = W * 0.034

        # faixas de textura: lado (+1 dir, -1 esq), asa ("frente"/"tras")
        self.faixas = []
        for lado in (1, -1):
            largura = (W - cx) if lado == 1 else cx
            for asa, (ya, yb) in (("frente", (0, self.y_div)), ("tras", (self.y_div - 2, H))):
                for k in range(FAIXAS):
                    u0 = largura * k / FAIXAS
                    u1 = min(largura, largura * (k + 1) / FAIXAS + 2)
                    if lado == 1:
                        caixa = (round(cx + u0), ya, round(cx + u1), yb)
                    else:
                        caixa = (round(cx - u1), ya, round(cx - u0), yb)
                    recorte = img.crop(caixa)
                    if recorte.getbbox() is None:
                        continue
                    self.faixas.append({"lado": lado, "asa": asa, "k": k, "u0": u0, "u1": u1,
                                        "ya": ya, "yb": yb, "img": recorte})

        self.OW = round(W * 1.3)
        self.OH = round(H * 1.9)
        self.D = W * 3.0
        self.luz = _norm([-0.4, -0.6, 0.7])
        self.meio_luz = _norm([self.luz[0], self.luz[1], self.luz[2] + 1])
        self.bola = _esfera(96, self.luz)
        self.bolas = {}
        self.cache = OrderedDict()

    def _limpar_corpo_da_foto(self, img):
        """Apaga da foto o corpo e as antenas (o modelo 3D entra no lugar)."""
        W, H, cx = self.W, self.H, self.cx
        r, g, b, a = img.split()
        azul = ImageChops.subtract(b, r).point(lambda v: 255 if v > 50 else 0)
        azul = ImageChops.multiply(azul, a.point(lambda v: 255 if v > 128 else 0))
        perto_do_azul = azul.filter(ImageFilter.MaxFilter(9))
        escuro = img.convert("L").point(lambda v: 255 if v < 95 else 0)
        escuro = ImageChops.multiply(escuro, a.point(lambda v: 255 if v > 20 else 0))
        # antenas: traços escuros longe do azul, na região acima da cabeça
        regiao = Image.new("L", img.size, 0)
        ImageDraw.Draw(regiao).rectangle((cx - W * 0.2, 0, cx + W * 0.2, H * 0.47), fill=255)
        antenas = ImageChops.multiply(ImageChops.multiply(escuro, ImageChops.invert(perto_do_azul)), regiao)
        # corpo: pixels escuros na faixa do meio
        m = W * 0.036
        faixa = Image.new("L", img.size, 0)
        ImageDraw.Draw(faixa).rectangle((cx - m, H * 0.3, cx + m, H), fill=255)
        corpo = ImageChops.multiply(escuro.filter(ImageFilter.MaxFilter(3)), faixa)
        apagar = ImageChops.lighter(antenas.filter(ImageFilter.MaxFilter(3)), corpo)
        img.putalpha(ImageChops.subtract(a, apagar))

    # --- geometria ---
    def _proj(self, p):
        k = self.D / (self.D - p[2])
        return (p[0] * k + self.OW / 2, p[1] * k + self.OH / 2)

    def _bola(self, raio):
        tam = max(2, int(raio * 2))
        if tam not in self.bolas:
            self.bolas[tam] = self.bola.resize((tam, tam), Image.LANCZOS)
        return self.bolas[tam]

    def _asas(self, batida, giro, brilho):
        """Monta as faixas de asa como peças (z, imagem, posição)."""
        H = self.H
        pecas = []
        bend = (7 + batida * 0.12) * 2 / (FAIXAS - 1)  # a ponta curva mais quando a asa sobe
        for f in self.faixas:
            lado, k = f["lado"], f["k"]
            base = batida if f["asa"] == "frente" else batida * 0.82 + 4
            # caminho ao longo da asa: cada faixa um pouco mais inclinada que a anterior
            x = z = 0.0
            larg = f["u1"] - f["u0"]
            passo = (f["u1"] - f["u0"]) if k == 0 else larg
            for i in range(k):
                ang = math.radians(base + bend * i)
                tamanho_i = (self.W - self.cx if lado == 1 else self.cx) / FAIXAS
                x += tamanho_i * math.cos(ang)
                z += tamanho_i * math.sin(ang)
            ang = math.radians(base + bend * k)
            x1, z1 = x + passo * math.cos(ang), z + passo * math.sin(ang)
            ya, yb = f["ya"] - H / 2, f["yb"] - H / 2
            local = [[lado * x, ya, z], [lado * x1, ya, z1], [lado * x1, yb, z1], [lado * x, yb, z]]
            pts = [_girar(p, *giro) for p in local]
            n = _normal(pts)
            if _normal(local)[2] < 0:
                n = [-c for c in n]
            tela = [self._proj(p) for p in pts]
            w, h = f["img"].size
            tex = [(0, 0), (w, 0), (w, h), (0, h)] if lado == 1 else [(w, 0), (0, 0), (0, h), (w, h)]
            x0 = int(min(p[0] for p in tela)) - 1
            y0 = int(min(p[1] for p in tela)) - 1
            x1b = int(max(p[0] for p in tela)) + 2
            y1b = int(max(p[1] for p in tela)) + 2
            if x1b - x0 < 2 or y1b - y0 < 2:
                continue
            try:
                coef = _coef_perspectiva([(p[0] - x0, p[1] - y0) for p in tela], tex)
            except ValueError:
                continue
            camada = f["img"].transform((x1b - x0, y1b - y0), Image.PERSPECTIVE, coef, Image.BICUBIC)
            avesso = n[2] < 0
            dif = max(0.0, sum(a * b for a, b in zip(n, self.luz)))
            fator = (0.72 + 0.38 * dif) * (0.5 if avesso else 1.0)
            rgb = ImageEnhance.Brightness(camada.convert("RGB")).enhance(fator)
            esp = max(0.0, sum(a * b for a, b in zip(n, self.meio_luz))) ** 12
            forca = min(0.85, esp * 0.7 + brilho * 0.35)
            if forca > 0.02 and not avesso:
                rgb = Image.blend(rgb, ImageChops.screen(rgb, Image.new("RGB", rgb.size, (44, 167, 218))), forca)
            rgb.putalpha(camada.getchannel("A"))
            pecas.append((sum(p[2] for p in pts) / 4, rgb, (x0, y0)))
        return pecas

    def _corpo(self, giro, rel_antena):
        """Cabeça, tórax e abdômen como bolinhas em fila; antenas como curvas."""
        H, R = self.H, self.r_corpo
        # (posição ao longo do corpo em fração de H, raio em fração de R)
        perfil = [(-0.075, 0.85), (-0.045, 1.0), (-0.01, 1.15), (0.03, 1.2), (0.07, 1.1),
                  (0.11, 0.95), (0.15, 0.9), (0.19, 0.85), (0.23, 0.78), (0.27, 0.68),
                  (0.31, 0.56), (0.345, 0.42), (0.37, 0.3)]
        pecas = []
        pontos = []
        for i in range(len(perfil) - 1):
            (ya, ra), (yb, rb) = perfil[i], perfil[i + 1]
            for j in range(3):
                t = j / 3
                pontos.append((ya + (yb - ya) * t, ra + (rb - ra) * t))
        pontos.append(perfil[-1])
        for yf, rf in pontos:
            raio = R * rf
            p = _girar([0, yf * H, raio * 0.7], *giro)
            k = self.D / (self.D - p[2])
            x, y = self._proj(p)
            bola = self._bola(raio * k)
            pecas.append((p[2] + 1, bola, (int(x - bola.width / 2), int(y - bola.height / 2))))
        # cabeça um pouco destacada à frente
        cabeca = _girar([0, -0.10 * H, R * 0.6], *giro)
        k = self.D / (self.D - cabeca[2])
        bola = self._bola(R * 0.95 * k)
        x, y = self._proj(cabeca)
        pecas.append((cabeca[2] + 1, bola, (int(x - bola.width / 2), int(y - bola.height / 2))))

        # antenas: saem da cabeça para cima e para os lados, um pouco inclinadas para o cursor
        incl_x = max(-1.0, min(1.0, rel_antena[0] / 300)) * 0.12 * H
        incl_y = max(-1.0, min(1.0, rel_antena[1] / 300)) * 0.05 * H
        antenas = []
        for lado in (-1, 1):
            linha = []
            for i in range(9):
                t = i / 8
                px_ = lado * (0.012 * H + 0.11 * H * t) + incl_x * t * t
                py_ = -0.11 * H - 0.30 * H * t + 0.06 * H * t * t + incl_y * t * t
                pz_ = R * 0.8 + 0.10 * H * t
                linha.append(self._proj(_girar([px_, py_, pz_], *giro)))
            antenas.append(linha)
        return pecas, antenas

    def desenhar(self, batida, yaw, pitch, roll, brilho=0.0, rel_antena=(0, 0)):
        """batida: 0 = asas abertas, 80 = quase fechadas (graus). Ângulos em graus.
        Devolve (imagem RGBA em tamanho normal, centro do corpo)."""
        chave = (round(batida / 3), round(yaw / 3), round(pitch / 3), round(roll / 3), round(brilho * 5),
                 round(rel_antena[0] / 60), round(rel_antena[1] / 60))
        if chave in self.cache:
            self.cache.move_to_end(chave)
            return self.cache[chave]
        giro = tuple(math.radians(chave[i] * 3) for i in (1, 2, 3))
        pecas = self._asas(chave[0] * 3, giro, chave[4] / 5)
        corpo, antenas = self._corpo(giro, (chave[5] * 60, chave[6] * 60))
        pecas += corpo
        pecas.sort(key=lambda p: p[0])

        tela = Image.new("RGBA", (self.OW, self.OH), (0, 0, 0, 0))
        for _, img, pos in pecas:
            tela.alpha_composite(img, (max(0, pos[0]), max(0, pos[1])),
                                 (max(0, -pos[0]), max(0, -pos[1])))
        d = ImageDraw.Draw(tela)
        for linha in antenas:
            d.line(linha, fill=COR_CORPO + (255,), width=max(2, round(self.W / 140)), joint="curve")
            px_, py_ = linha[-1]
            r = max(2, self.W / 110)
            d.ellipse((px_ - r, py_ - r, px_ + r, py_ + r), fill=COR_CORPO + (255,))
        tela = tela.resize((self.OW // SUPER, self.OH // SUPER), Image.LANCZOS)
        resultado = (tela, (self.OW / 2 / SUPER, self.OH / 2 / SUPER))
        self.cache[chave] = resultado
        if len(self.cache) > 300:
            self.cache.popitem(last=False)
        return resultado


def sombra_de(sprite, altura):
    """Sombra no chão com o formato da borboleta: achatada, borrada e mais fraca quanto mais alto ela voa."""
    a = sprite.getchannel("A")
    w, h = sprite.size
    a = a.resize((w, max(2, h // 5)), Image.BILINEAR)
    pad = 12
    tela = Image.new("L", (w + 2 * pad, a.height + 2 * pad), 0)
    tela.paste(a, (pad, pad))
    tela = tela.filter(ImageFilter.GaussianBlur(3 + altura / 6))
    forca = max(0.25, 0.55 - altura / 80)
    tela = tela.point(lambda v: int(v * forca))
    s = Image.new("RGBA", tela.size, (20, 30, 50, 0))
    s.putalpha(tela)
    return s


def _lerp(a, b, k):
    return a + (b - a) * k


class Voo:
    """Como a borboleta se mexe: estado do Claude + o que o cursor está fazendo."""

    def __init__(self):
        self.fase = 0.0
        self.t = 0.0
        self.centro = 30.0   # ângulo médio das asas
        self.amp = 20.0      # quanto as asas batem
        self.freq = 1.0      # batidas por segundo
        self.yaw = 0.0
        self.pitch = 25.0
        self.roll = 0.0
        self.altura = 0.0    # quanto está acima do chão (px)
        self.brilho = 0.0
        self.susto_ate = 0.0
        self.agito_ate = 0.0

    def susto(self):
        self.susto_ate = self.t + 0.8

    def agito(self):
        self.agito_ate = max(self.agito_ate, self.t + 0.45)

    def passo(self, dt, estado, rel, dentro, andando, virado):
        """rel: posição do cursor em relação à borboleta (px). Devolve a pose."""
        self.t += dt
        t = self.t
        perto = math.hypot(*rel) < 170

        if estado == "trabalhando":
            c, a, f, alt = 34, 34, 3.2, 10 + 4 * math.sin(t * 2.1)
        elif estado == "esperando":
            c, a, f, alt = 34, 38, 4.4, 16 + 9 * abs(math.sin(t * 2.6))
        elif estado == "pronto":
            c, a, f, alt = 14, 12, 0.8, 4
        elif estado == "bloqueado":
            c, a, f, alt = 58, 8, 0.6, 0
        else:  # pousada, abrindo e fechando devagar como quem toma sol
            c, a, f, alt = 34, 26, 0.35, 0
            if perto:
                c, a, f, alt = 32, 30, 1.8, 6
        if dentro:  # cursor em cima: abre as asas e se mostra
            c, a, f = 10, 8, 0.9
        if andando:
            c, a, f, alt = 34, 36, 5.0, 12 + 5 * math.sin(t * 9)
        if t < self.agito_ate:
            c, a, f, alt = 34, 36, 6.0, max(alt, 10)
        if t < self.susto_ate:
            c, a, f, alt = 36, 40, 7.5, 22

        k = min(1.0, dt * 4)
        self.centro = _lerp(self.centro, c, k)
        self.amp = _lerp(self.amp, a, k)
        self.freq = _lerp(self.freq, f, k)
        self.altura = _lerp(self.altura, alt, min(1.0, dt * 5))
        self.fase += 2 * math.pi * self.freq * dt
        batida = max(0.0, min(80.0, self.centro + self.amp * math.sin(self.fase)))

        yaw_alvo = max(-1.0, min(1.0, rel[0] / 320)) * 34
        pitch_alvo = 25 + max(-1.0, min(1.0, rel[1] / 320)) * 18
        roll_alvo = 0.0
        if andando:
            yaw_alvo, roll_alvo = virado * 28, -virado * 14
        if estado == "bloqueado":
            pitch_alvo += 14
        if t < self.susto_ate:
            yaw_alvo = -yaw_alvo
            roll_alvo = 10 * math.sin(t * 30)
        self.yaw = _lerp(self.yaw, yaw_alvo, min(1.0, dt * 5))
        self.pitch = _lerp(self.pitch, pitch_alvo, min(1.0, dt * 5))
        self.roll = _lerp(self.roll, roll_alvo, min(1.0, dt * 6))

        brilho_alvo = 0.5 + 0.5 * math.sin(t * 3) if estado == "pronto" else (0.4 if dentro else 0.0)
        self.brilho = _lerp(self.brilho, brilho_alvo, min(1.0, dt * 4))
        return batida, self.yaw, self.pitch, self.roll, self.brilho, self.altura
