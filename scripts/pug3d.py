"""Frida, uma pug preta em 3D com jeito de desenho animado.

- Corpo, cabeça, bochechas, focinho, orelhas, patas e rabinho enrolado são
  volumes redondos com luz de estúdio: luz quente de frente, contraluz azulada
  no contorno (o brilho do pelo preto) e sombra suave embaixo.
- Olhos grandes e brilhantes, com íris castanha, pupila, dois pontos de luz e
  pálpebra que pisca. Ela acompanha o cursor com os olhos e com a cabeça.
- A cabeça gira e inclina separada do corpo, as orelhas balançam com o pulo,
  o rabo abana e a língua aparece quando ela está feliz.
- Amassa e estica ao pular (o corpo mantém o volume).
Só usa Pillow.
"""
import math
from collections import OrderedDict

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from borboleta3d import SUPER, _girar, _lerp, _norm
from foto3d import Bicho

# materiais: cor base, brilho (força, dureza), contraluz (força, cor)
MATERIAIS = {
    "pelo": ((40, 38, 46), (0.2, 9), (0.18, (120, 150, 215))),
    "focinho": ((22, 21, 26), (0.22, 14), (0.12, (110, 140, 200))),
    "nariz": ((14, 14, 17), (0.9, 40), (0.15, (110, 140, 200))),
    "lingua": ((240, 120, 150), (0.5, 24), (0.15, (255, 200, 210))),
    "coleira": ((232, 80, 140), (0.45, 22), (0.2, (255, 190, 220))),
    "plaquinha": ((236, 184, 72), (0.9, 30), (0.2, (255, 240, 200))),
}
COR_PELO = MATERIAIS["pelo"][0]
COR_RUGA = (18, 17, 22)


def _bola_base(mat, luz, tam=128):
    """Bola sombreada com luz de estúdio, no tamanho de referência."""
    cor, (esp_forca, esp_dureza), (rim_forca, rim_cor) = MATERIAIS[mat]
    meio = _norm([luz[0], luz[1], luz[2] + 1])
    img = Image.new("RGBA", (tam, tam), (0, 0, 0, 0))
    px = img.load()
    r = tam / 2
    for y in range(tam):
        for x in range(tam):
            nx, ny = (x + 0.5 - r) / r, (y + 0.5 - r) / r
            d = nx * nx + ny * ny
            if d > 1:
                continue
            nz = math.sqrt(1 - d)
            lam = nx * luz[0] + ny * luz[1] + nz * luz[2]
            dif = max(0.0, (lam + 0.35) / 1.35)              # luz "embrulhada", mais macia
            esp = max(0.0, nx * meio[0] + ny * meio[1] + nz * meio[2]) ** esp_dureza
            rim = (1 - nz) ** 2.6 * rim_forca * (0.6 + 0.4 * max(0.0, -nx * 0.3 + 0.7))
            oclusao = 1 - 0.35 * max(0.0, ny - 0.35)          # escurece embaixo
            k = (0.42 + 0.75 * dif) * oclusao
            c = [cor[i] * k + rim_cor[i] * rim + 255 * esp * esp_forca for i in range(3)]
            # leve calor na transição entre luz e sombra (pele por baixo do pelo)
            terminador = max(0.0, 1 - abs(lam) * 3) * 0.08
            c[0] += 60 * terminador
            borda = min(1.0, (1 - math.sqrt(d)) * r / 1.3)
            px[x, y] = (min(255, int(c[0])), min(255, int(c[1])), min(255, int(c[2])), int(255 * borda))
    return img


class Pug3D:
    def __init__(self, altura=130):
        self.S = altura * SUPER                # pixels por unidade (a pug tem 1 unidade de altura)
        self.OW = round(self.S * 1.35)
        self.OH = round(self.S * 1.25)
        self.chao = self.OH * 0.93
        self.D = 3.2                           # distância da câmera, em unidades
        self.luz = _norm([-0.45, -0.55, 0.75])
        self.bases = {m: _bola_base(m, self.luz) for m in MATERIAIS}
        self.bolas = OrderedDict()
        self.olhos = OrderedDict()
        self.cache = OrderedDict()

    # --- peças prontas ---
    def _bola(self, mat, w, h):
        w, h = max(2, int(w)), max(2, int(h))
        chave = (mat, w, h)
        if chave in self.bolas:
            self.bolas.move_to_end(chave)
            return self.bolas[chave]
        img = self.bases[mat].resize((w, h), Image.LANCZOS)
        self.bolas[chave] = img
        if len(self.bolas) > 600:
            self.bolas.popitem(last=False)
        return img

    def _olho(self, w, h, olhar, piscar, feliz):
        """Olho grande e brilhante: esclera, íris, pupila, dois pontos de luz e pálpebra."""
        w, h = max(4, int(w)), max(4, int(h))
        gx, gy = round(olhar[0] * 3) / 3, round(olhar[1] * 3) / 3
        chave = (w, h, gx, gy, round(piscar * 6), round(feliz * 4))
        if chave in self.olhos:
            self.olhos.move_to_end(chave)
            return self.olhos[chave]
        f = 4  # desenha maior e reduz, para ficar liso
        W, H = w * f, h * f
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        # esclera com sombra de cima (a pálpebra faz sombra no olho)
        d.ellipse((0, 0, W - 1, H - 1), fill=(236, 232, 226, 255))
        d.ellipse((W * 0.06, H * 0.18, W * 0.94, H * 1.02), fill=(250, 248, 244, 255))
        # íris e pupila, deslocadas para onde ela olha
        ri = W * 0.40
        cx, cy = W / 2 + gx * W * 0.14, H * 0.54 + gy * H * 0.10
        d.ellipse((cx - ri, cy - ri, cx + ri, cy + ri), fill=(74, 40, 20, 255))
        d.ellipse((cx - ri * 0.82, cy - ri * 0.82, cx + ri * 0.82, cy + ri * 0.82), fill=(112, 64, 30, 255))
        d.ellipse((cx - ri * 0.55, cy - ri * 0.1, cx + ri * 0.75, cy + ri * 0.85), fill=(150, 92, 44, 255))
        rp = ri * 0.55
        d.ellipse((cx - rp, cy - rp, cx + rp, cy + rp), fill=(10, 8, 8, 255))
        # pontos de luz (fixos em relação à luz, como nos desenhos)
        r1 = ri * 0.32
        d.ellipse((cx - ri * 0.55 - r1, cy - ri * 0.5 - r1, cx - ri * 0.55 + r1, cy - ri * 0.5 + r1),
                  fill=(255, 255, 255, 255))
        r2 = ri * 0.14
        d.ellipse((cx + ri * 0.35 - r2, cy + ri * 0.35 - r2, cx + ri * 0.35 + r2, cy + ri * 0.35 + r2),
                  fill=(255, 255, 255, 220))
        # pálpebra de cima (piscar) e de baixo (olhinho sorrindo)
        # as pálpebras são de pelo com a mesma luz da cabeça (não um disco chapado)
        pelo = self.bases["pelo"].resize((W, H), Image.BILINEAR).convert("RGB")
        palpebras = Image.new("L", (W, H), 0)
        dp = ImageDraw.Draw(palpebras)
        topo = H * (-0.05 + 1.1 * piscar)
        if topo > 0:
            dp.ellipse((-W * 0.2, topo - H * 1.4, W * 1.2, topo), fill=255)
        if feliz > 0.05:
            base = H * (1.05 - 0.38 * feliz)
            dp.ellipse((-W * 0.2, base, W * 1.2, base + H * 1.4), fill=255)
        img.paste(pelo, (0, 0), palpebras)
        if topo > 0:
            d.arc((-W * 0.2, topo - H * 1.4, W * 1.2, topo), 20, 160, fill=COR_RUGA + (255,), width=max(2, f))
        # recorta no formato do olho
        mascara = Image.new("L", (W, H), 0)
        ImageDraw.Draw(mascara).ellipse((0, 0, W - 1, H - 1), fill=255)
        img.putalpha(Image.composite(img.getchannel("A"), mascara, mascara))
        img = img.resize((w, h), Image.LANCZOS)
        self.olhos[chave] = img
        if len(self.olhos) > 400:
            self.olhos.popitem(last=False)
        return img

    # --- geometria ---
    def _tela(self, p):
        k = self.D / (self.D - p[2])
        return p[0] * k * self.S + self.OW / 2, p[1] * k * self.S + self.chao, k

    def desenhar(self, yaw, pitch, roll, amasso=1.0, lado=1, brilho=0.0, extra=None):
        """Ângulos em graus. extra: rabo (-1..1), piscar (0..1), lingua (0..1),
        orelha (-1..1), olhar (x, y em -1..1), feliz (0..1).
        Devolve (imagem RGBA em tamanho normal, ponto do chão entre as patas)."""
        e = extra or {}
        chave = (round(yaw / 3), round(pitch / 3), round(roll / 3), round(amasso * 25), lado,
                 round(e.get("rabo", 0) * 2), round(e.get("piscar", 0) * 6), round(e.get("lingua", 0) * 4),
                 round(e.get("orelha", 0) * 4), round(e.get("olhar", (0, 0))[0] * 3),
                 round(e.get("olhar", (0, 0))[1] * 3), round(e.get("feliz", 0) * 4), round(brilho * 3))
        if chave in self.cache:
            self.cache.move_to_end(chave)
            return self.cache[chave]
        resultado = self._montar(chave)
        self.cache[chave] = resultado
        if len(self.cache) > 300:
            self.cache.popitem(last=False)
        return resultado

    def _montar(self, chave):
        yaw, pitch, roll = chave[0] * 3, chave[1] * 3, chave[2] * 3
        amasso, lado = chave[3] / 25, chave[4]
        rabo, piscar, lingua = chave[5] / 2, chave[6] / 6, chave[7] / 4
        orelha, olhar = chave[8] / 4, (chave[9] / 3, chave[10] / 3)
        feliz, brilho = chave[11] / 4, chave[12] / 3

        # o corpo vira para o lado em que ela está olhando; a cabeça segue o cursor
        giro_corpo = (math.radians(lado * 10 + yaw * 0.25), 0.0, math.radians(roll * 0.15))
        giro_cabeca = (math.radians(yaw * 0.7), math.radians(-pitch), math.radians(roll))
        pescoco = [0.0, -0.50, 0.02]
        estica_y = amasso
        estica_x = 1 / math.sqrt(max(0.5, amasso))

        def no_mundo(p, cabeca):
            if cabeca:
                q = [p[i] - pescoco[i] for i in range(3)]
                q = _girar(q, *giro_cabeca)
                p = [q[i] + pescoco[i] for i in range(3)]
            p = _girar(p, *giro_corpo)
            return [p[0] * estica_x, p[1] * estica_y, p[2] * estica_x]

        pecas = []  # (z, função que desenha)
        mascara = Image.new("L", (self.OW, self.OH), 0)  # silhueta da cabeça: o rosto não passa dela

        def bola(mat, centro, raios, cabeca=False):
            p = no_mundo(centro, cabeca)
            x, y, k = self._tela(p)
            w = raios[0] * 2 * k * self.S * estica_x
            h = raios[1] * 2 * k * self.S * estica_y
            img = self._bola(mat, w, h)
            pos = (int(x - img.width / 2), int(y - img.height / 2))
            if cabeca:
                mascara.paste(255, pos, img.getchannel("A"))

            def f(tela, img=img, pos=pos):
                tela.alpha_composite(img, (max(0, pos[0]), max(0, pos[1])), (max(0, -pos[0]), max(0, -pos[1])))
            # ordena pela frente de cada bola (não pelo centro): bola grande ao lado de bola pequena
            pecas.append((p[2] + raios[2] * 0.6, f))
            return p

        # corpo sentado
        for s in (-1, 1):
            bola("pelo", (s * 0.20, -0.13, -0.06), (0.17, 0.14, 0.19))        # coxas
            bola("pelo", (s * 0.27, -0.03, 0.06), (0.08, 0.035, 0.09))         # patas de trás
        bola("pelo", (0, -0.30, -0.03), (0.25, 0.27, 0.22))                     # barriga/costas
        bola("pelo", (0, -0.33, 0.10), (0.17, 0.20, 0.13))               # peito
        for s in (-1, 1):
            bola("pelo", (s * 0.095, -0.13, 0.13), (0.075, 0.125, 0.075))        # patas da frente
            bola("pelo", (s * 0.10, -0.028, 0.17), (0.075, 0.034, 0.08))  # pezinhos

        # rabinho enrolado em cima do quadril, para o lado, abanando (aparece por cima das costas)
        abano = rabo * 0.06
        for i in range(10):
            a = i / 10 * 2 * math.pi * 0.85
            bola("pelo", (0.12 + abano + 0.075 * math.cos(a), -0.56 + 0.06 * math.sin(a),
                          -0.17 - 0.008 * i), (0.042, 0.042, 0.042))

        # coleira rosa com plaquinha dourada
        # a coleira é uma faixa (só a metade da frente aparece)
        cima, baixo = [], []
        for i in range(25):
            a = math.radians(-100 + 200 * i / 24)
            for anel, dy in ((cima, -0.024), (baixo, 0.024)):
                anel.append(no_mundo((0.175 * math.sin(a), -0.505 + 0.012 * math.cos(a) + dy, 0.145 * math.cos(a)),
                                     False))

        def coleira(tela, cima=cima, baixo=baixo):
            d = ImageDraw.Draw(tela)
            c = [self._tela(p)[:2] for p in cima]
            b = [self._tela(p)[:2] for p in baixo]
            d.polygon(c + b[::-1], fill=MATERIAIS["coleira"][0] + (255,))
            lw = max(1, round(self.S / 160))
            d.line(c, fill=(255, 170, 205, 255), width=lw, joint="curve")
            d.line(b, fill=(150, 40, 90, 255), width=lw, joint="curve")
        pecas.append((no_mundo((0, -0.505, 0.145), False)[2] + 0.05, coleira))  # por cima do peito
        bola("plaquinha", (0, -0.465, 0.21), (0.032, 0.036, 0.012))

        # cabeça larga de pug, bochechas fofas e a máscara escura do focinho
        cabeca_z = bola("pelo", (0, -0.72, 0.0), (0.285, 0.235, 0.22), True)[2] + 0.22 * 0.6
        bola("pelo", (0, -0.80, 0.03), (0.22, 0.13, 0.17), True)                 # testa
        for s in (-1, 1):
            bola("pelo", (s * 0.15, -0.63, 0.11), (0.14, 0.11, 0.11), True)      # bochechas
            bola("focinho", (s * 0.058, -0.618, 0.19), (0.075, 0.06, 0.06), True)  # beicinhos
        bola("focinho", (0, -0.575, 0.15), (0.07, 0.045, 0.05), True)              # queixo
        nariz_z = bola("nariz", (0, -0.668, 0.245), (0.058, 0.038, 0.03), True)[2] + 0.03 * 0.6
        if lingua > 0.05:
            bola("lingua", (0, -0.555 + 0.02 * lingua, 0.205), (0.042, 0.03 + 0.04 * lingua, 0.02), True)

        # orelhinhas dobradas para a frente, balançando com o pulo
        for s in (-1, 1):
            pts3 = [(s * 0.13, -0.94, 0.07), (s * 0.255, -0.895, 0.04),
                    (s * 0.285, -0.755 + 0.035 * orelha, 0.12), (s * 0.215, -0.80 + 0.03 * orelha, 0.16)]
            mundo = [no_mundo(p, True) for p in pts3]

            def f(tela, mundo=mundo):
                pts = [self._tela(p)[:2] for p in mundo]
                x0, y0 = int(min(p[0] for p in pts)), int(min(p[1] for p in pts))
                x1, y1 = int(max(p[0] for p in pts)) + 2, int(max(p[1] for p in pts)) + 2
                forma = Image.new("L", (x1 - x0, y1 - y0), 0)
                ImageDraw.Draw(forma).polygon([(x - x0, y - y0) for x, y in pts], fill=255)
                pano = self._bola("focinho", (x1 - x0) * 1.2, (y1 - y0) * 1.2).crop((0, 0, x1 - x0, y1 - y0))
                pano.putalpha(forma)  # pano dobrado, com a luz de uma bola
                tela.alpha_composite(pano, (max(0, x0), max(0, y0)), (max(0, -x0), max(0, -y0)))
                ImageDraw.Draw(tela).line(pts + pts[:1], fill=(12, 12, 16, 255), width=max(1, round(self.S / 200)),
                                          joint="curve")
            # presas à cabeça: sempre por cima dela, mesmo quando ela vira
            pecas.append((max(sum(p[2] for p in mundo) / 4, cabeca_z) + 0.08, f))

        # rosto (olhos, rugas, narinas, boca): uma camada recortada pela silhueta da cabeça
        rosto = Image.new("RGBA", (self.OW, self.OH), (0, 0, 0, 0))

        # olhos: grandes, com encurtamento quando a cabeça vira e inclinados com ela
        for s in (-1, 1):
            centro = (s * 0.13, -0.765, 0.165)
            p = no_mundo(centro, True)
            x, y, k = self._tela(p)
            normal = _norm(_girar(_girar([s * 0.45, -0.1, 0.9], *giro_cabeca), *giro_corpo))
            if normal[2] < 0.3:
                continue  # do outro lado da cabeça
            w = 0.16 * k * self.S * estica_x * normal[2]
            h = 0.165 * k * self.S * estica_y
            olho = self._olho(w, h, olhar, piscar, feliz)
            if abs(roll) > 1:
                olho = olho.rotate(-roll, resample=Image.BICUBIC, expand=True)
            rosto.alpha_composite(olho, (int(x - olho.width / 2), int(y - olho.height / 2)))

        # rugas, narinas e boca: desenhadas por cima da cabeça (linha escura + brilho logo acima)
        def detalhes(tela):
            d = ImageDraw.Draw(tela)
            lw = max(1, round(self.S / 95))

            def curva(fn, n=7, cor=COR_RUGA + (255,), largura=lw, brilho_acima=True):
                pts = [self._tela(no_mundo(fn(i / (n - 1)), True))[:2] for i in range(n)]
                if brilho_acima:
                    d.line([(x, y - largura) for x, y in pts], fill=(68, 70, 86, 255), width=max(1, largura // 2),
                           joint="curve")
                d.line(pts, fill=cor, width=largura, joint="curve")
            # dobra grande em cima do nariz
            curva(lambda t: (0.18 * (t - 0.5), -0.71 - 0.028 * math.sin(t * math.pi), 0.215), largura=lw + 1)
            # rugas da testa
            curva(lambda t: (0.10 * (t - 0.5), -0.885 - 0.012 * math.sin(t * math.pi), 0.19), n=5)
            for s in (-1, 1):
                curva(lambda t, s=s: (s * (0.035 + 0.075 * t), -0.85 + 0.025 * t * t, 0.20), n=5)
            # narinas
            for s in (-1, 1):
                x, y, k = self._tela(no_mundo((s * 0.024, -0.664, 0.275), True))
                r = 0.011 * k * self.S
                d.ellipse((x - r * 1.3, y - r, x + r * 1.3, y + r), fill=(0, 0, 0, 255))
            # boquinha: sorri mais quando ela está feliz
            sorriso = 0.010 + 0.022 * feliz
            curva(lambda t: (0.07 * (2 * t - 1), -0.592 + sorriso * (1 - (2 * t - 1) ** 2), 0.235),
                  cor=(6, 6, 8, 255), brilho_acima=False)
            if lingua > 0.3:  # risquinho no meio da língua
                curva(lambda t: (0, -0.575 + 0.035 * lingua * t, 0.225), n=3, cor=(200, 80, 110, 255),
                      largura=max(1, lw // 2), brilho_acima=False)
        detalhes(rosto)
        rosto.putalpha(ImageChops.multiply(rosto.getchannel("A"), mascara))

        def colar_rosto(tela):
            tela.alpha_composite(rosto)
        pecas.append((max(cabeca_z, nariz_z) + 0.01, colar_rosto))

        pecas.sort(key=lambda p: p[0])
        tela = Image.new("RGBA", (self.OW, self.OH), (0, 0, 0, 0))
        for _, f in pecas:
            f(tela)
        # contraluz azulada só no contorno de cima e da direita (o brilho do pelo preto)
        a = tela.getchannel("A")
        dsl = max(2, round(self.S / 45))
        deslocada = Image.new("L", a.size, 0)
        deslocada.paste(a, (-dsl, dsl))
        rim = Image.composite(Image.new("L", a.size, 0), a, deslocada.point(lambda v: 255 if v > 128 else 0))
        rim = rim.filter(ImageFilter.GaussianBlur(dsl / 3)).point(lambda v: int(v * 0.75))
        luz_rim = Image.new("RGBA", a.size, (150, 178, 235, 0))
        luz_rim.putalpha(Image.composite(rim, Image.new("L", a.size, 0), a))
        tela.alpha_composite(luz_rim)
        if brilho > 0.05:  # contorno de luz azulada quando está feliz ou com o cursor em cima
            borda = tela.getchannel("A").point(lambda v: 255 if v > 128 else 0)
            halo = Image.new("RGBA", tela.size, (150, 185, 255, 0))
            halo.putalpha(borda.filter(ImageFilter.GaussianBlur(self.S / 60)).point(lambda v: int(v * 0.35 * brilho)))
            halo.alpha_composite(tela)
            tela = halo
        tela = tela.resize((self.OW // SUPER, self.OH // SUPER), Image.LANCZOS)
        return tela, (self.OW / 2 / SUPER, self.chao / SUPER)


class Frida(Bicho):
    """Como a Frida se mexe: o pulo e o olhar do bichinho de foto, mais rabo, piscada, língua e orelhas."""

    def __init__(self):
        super().__init__()
        self.rabo = 0.0
        self.vel_rabo = 1.0
        self.piscar_em = 3.0
        self.lingua = 0.0
        self.feliz = 0.0
        self.orelha = 0.0
        self.olhar = (0.0, 0.0)

    def passo(self, dt, estado, rel, dentro, andando, virado, espelhar=True):
        yaw, pitch, roll, amasso, lado, brilho, alt = super().passo(dt, estado, rel, dentro, andando, virado, espelhar)
        t = self.t

        # rabo: abana rápido quando o trabalho fica pronto ou quando ganha atenção
        if estado == "pronto" or dentro:
            vel = 3.5
        elif estado == "esperando":
            vel = 2.8
        elif estado == "trabalhando":
            vel = 1.6
        elif estado == "bloqueado":
            vel = 0.0
        else:
            vel = 0.8
        self.vel_rabo = _lerp(self.vel_rabo, vel, min(1.0, dt * 3))
        self.rabo += self.vel_rabo * dt * 2

        # piscada de vez em quando (duas seguidas às vezes)
        piscar = 0.0
        if t > self.piscar_em:
            fase = (t - self.piscar_em) / 0.16
            piscar = math.sin(min(1.0, fase) * math.pi)
            if fase >= 1:
                self.piscar_em = t + (0.25 if (t * 13.7) % 1 < 0.2 else 2.5 + (t * 7.1) % 3)
        if estado == "bloqueado":
            piscar = max(piscar, 0.45)  # olhinho caído

        feliz_alvo = 1.0 if (estado == "pronto" or dentro) else 0.0
        self.feliz = _lerp(self.feliz, feliz_alvo, min(1.0, dt * 4))
        lingua_alvo = 1.0 if (estado == "pronto" or dentro or andando) else (0.5 if estado == "esperando" else 0.0)
        self.lingua = _lerp(self.lingua, lingua_alvo, min(1.0, dt * 5))

        # orelhas: atrasam um pouco em relação ao corpo, como pano
        self.orelha = _lerp(self.orelha, max(-1.0, min(1.0, -self.vel / 250)), min(1.0, dt * 8))

        # olhar: segue o cursor; trabalhando, lê de um lado para o outro
        if estado == "trabalhando" and not dentro:
            alvo = (math.sin(t * 1.3) * 0.8, 0.5)
        else:
            alvo = (max(-1.0, min(1.0, rel[0] / 250)), max(-1.0, min(1.0, rel[1] / 250)))
        self.olhar = (_lerp(self.olhar[0], alvo[0], min(1.0, dt * 8)),
                      _lerp(self.olhar[1], alvo[1], min(1.0, dt * 8)))

        extra = {"rabo": math.sin(self.rabo * math.pi), "piscar": piscar, "lingua": self.lingua, "orelha": self.orelha,
                 "olhar": self.olhar, "feliz": self.feliz}
        return yaw, pitch, roll, amasso, lado, brilho, alt, extra
