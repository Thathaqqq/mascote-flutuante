"""Personagem feito de uma foto recortada (ex.: o seu cachorro).

A foto vira uma superfície levemente abaulada, como um boneco de papelão com
volume: ela gira para o cursor com perspectiva, a luz muda conforme o giro,
inclina a cabeça, respira, pula com amassadinho na aterrissagem e se vira
para o lado do cursor. Só usa Pillow.
"""
import math
from collections import OrderedDict

from PIL import Image, ImageEnhance, ImageOps

from borboleta3d import SUPER, _coef_perspectiva, _girar, _lerp, _norm

TIRAS = 12  # faixas verticais que dão o volume


class Foto3D:
    def __init__(self, caminho, altura=130):
        img = Image.open(caminho).convert("RGBA")
        caixa = img.getchannel("A").getbbox()
        if caixa:
            img = img.crop(caixa)
        esc = altura * SUPER / img.height
        img = img.resize((max(4, round(img.width * esc)), max(4, round(img.height * esc))), Image.LANCZOS)
        self.W, self.H = img.size
        self.lados = {1: img, -1: ImageOps.mirror(img)}
        self.tiras = {}
        for lado, im in self.lados.items():
            self.tiras[lado] = []
            for i in range(TIRAS):
                x0 = round(self.W * i / TIRAS)
                x1 = min(self.W, round(self.W * (i + 1) / TIRAS) + 2)
                self.tiras[lado].append((x0, x1, im.crop((x0, 0, x1, self.H))))
        self.OW = round(self.W * 1.5)
        self.OH = round(self.H * 1.5)
        self.D = max(self.W, self.H) * 3.2
        self.bojo = self.W * 0.16  # quanto o meio "salta" para a frente
        self.luz = _norm([-0.4, -0.5, 0.75])
        self.cache = OrderedDict()

    def _z(self, x):
        u = (x / self.W) * 2 - 1
        return self.bojo * math.sqrt(max(0.0, 1 - u * u))

    def _proj(self, p):
        k = self.D / (self.D - p[2])
        return (p[0] * k + self.OW / 2, p[1] * k + self.OH / 2)

    def desenhar(self, yaw, pitch, roll, amasso=1.0, lado=1, brilho=0.0):
        """amasso: 1 normal, <1 achatado, >1 esticado. lado: 1 original, -1 espelhado.
        Devolve (imagem RGBA em tamanho normal, ponto dos pés)."""
        chave = (round(yaw / 3), round(pitch / 3), round(roll / 2), round(amasso * 40), lado, round(brilho * 4))
        if chave in self.cache:
            self.cache.move_to_end(chave)
            return self.cache[chave]
        giro = (math.radians(chave[0] * 3), math.radians(chave[1] * 3), math.radians(chave[2] * 2))
        sy = chave[3] / 40
        sx = 1 / math.sqrt(sy)  # amassa sem mudar o volume
        W, H = self.W, self.H
        tela = Image.new("RGBA", (self.OW, self.OH), (0, 0, 0, 0))
        pecas = []
        for x0, x1, tira in self.tiras[lado]:
            # pés no chão: o ponto de apoio (y = H/2) não se mexe ao amassar
            def p(x, y):
                return [(x - W / 2) * sx, (y - H / 2) * sy + H / 2 * (1 - sy), self._z(x) * sx]
            local = [p(x0, 0), p(x1, 0), p(x1, H), p(x0, H)]
            pts = [_girar(q, *giro) for q in local]
            u = [pts[1][i] - pts[0][i] for i in range(3)]
            v = [pts[3][i] - pts[0][i] for i in range(3)]
            n = _norm([u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]])
            if n[2] < 0:
                n = [-c for c in n]
            tela_pts = [self._proj(q) for q in pts]
            bx0 = int(min(q[0] for q in tela_pts)) - 1
            by0 = int(min(q[1] for q in tela_pts)) - 1
            bx1 = int(max(q[0] for q in tela_pts)) + 2
            by1 = int(max(q[1] for q in tela_pts)) + 2
            w, h = tira.size
            try:
                coef = _coef_perspectiva([(q[0] - bx0, q[1] - by0) for q in tela_pts],
                                         [(0, 0), (w, 0), (w, h), (0, h)])
            except ValueError:
                continue
            camada = tira.transform((bx1 - bx0, by1 - by0), Image.PERSPECTIVE, coef, Image.BICUBIC)
            dif = max(0.0, sum(a * b for a, b in zip(n, self.luz)))
            fator = 0.86 + 0.2 * dif + 0.12 * chave[5] / 4  # luz suave: a foto continua parecida
            rgb = ImageEnhance.Brightness(camada.convert("RGB")).enhance(fator)
            rgb.putalpha(camada.getchannel("A"))
            pecas.append((sum(q[2] for q in pts) / 4, rgb, (bx0, by0)))
        pecas.sort(key=lambda t: t[0])
        for _, img, pos in pecas:
            tela.alpha_composite(img, (max(0, pos[0]), max(0, pos[1])), (max(0, -pos[0]), max(0, -pos[1])))
        pe = self._proj(_girar([0, H / 2, self.bojo], *giro))
        tela = tela.resize((self.OW // SUPER, self.OH // SUPER), Image.LANCZOS)
        resultado = (tela, (pe[0] / SUPER, pe[1] / SUPER))
        self.cache[chave] = resultado
        if len(self.cache) > 300:
            self.cache.popitem(last=False)
        return resultado


class Bicho:
    """Como um bichinho de foto se mexe: estado do Claude + o que o cursor faz."""

    def __init__(self):
        self.t = 0.0
        self.yaw = 0.0
        self.pitch = 0.0
        self.roll = 0.0
        self.lado = 1
        self.altura = 0.0
        self.vel = 0.0
        self.amasso = 1.0
        self.brilho = 0.0
        self.pulo_ate = 0.0
        self.susto_ate = 0.0
        self.inclinar_ate = 0.0
        self.proxima_inclinada = 4.0

    def susto(self):
        self.susto_ate = self.t + 0.6
        self._pular(260)

    def agito(self):
        if self.altura < 1:
            self._pular(170)

    def _pular(self, forca):
        if self.altura < 2:
            self.vel = forca

    def passo(self, dt, estado, rel, dentro, andando, virado, espelhar=True):
        self.t += dt
        t = self.t

        # vira para o lado do cursor (com folga, para não ficar trocando)
        if espelhar:
            if andando:
                self.lado = virado
            elif rel[0] > 60:
                self.lado = 1
            elif rel[0] < -60:
                self.lado = -1

        yaw_alvo = max(-1.0, min(1.0, rel[0] / 300)) * 22
        pitch_alvo = max(-1.0, min(1.0, rel[1] / 300)) * 10
        roll_alvo = 0.0
        respiro = 1 + 0.018 * math.sin(t * 2.2)

        if estado == "trabalhando":
            if self.altura < 1 and math.sin(t * 7) > 0.95:
                self._pular(110)  # trotinho
        elif estado == "esperando":
            if self.altura < 1:
                self._pular(220)  # pulando, querendo atenção
        elif estado == "bloqueado":
            pitch_alvo += 12
            respiro *= 0.94
        elif estado != "pronto":
            # parado à toa: de vez em quando inclina a cabeça, curioso (com trabalho pronto, fica quieto)
            if t > self.proxima_inclinada:
                self.inclinar_ate = t + 1.4
                self.proxima_inclinada = t + 5 + (t * 7.3) % 5
        if dentro:
            self.inclinar_ate = max(self.inclinar_ate, t + 0.2)
            if self.altura < 1 and math.sin(t * 5) > 0.9:
                self._pular(120)
        if t < self.inclinar_ate:
            roll_alvo = 11 * self.lado
        if andando:
            roll_alvo = -6 * virado
            if self.altura < 1:
                self._pular(140)
        if t < self.susto_ate:
            yaw_alvo = -yaw_alvo

        # física simples do pulo, com amassadinho ao aterrissar
        g = 900
        if self.altura > 0 or self.vel > 0:
            self.vel -= g * dt
            self.altura = max(0.0, self.altura + self.vel * dt)
            if self.altura == 0.0:
                self.amasso = 0.82
                self.vel = 0.0
        amasso_alvo = respiro * (1.06 if self.vel > 60 else 1.0)
        self.amasso = _lerp(self.amasso, amasso_alvo, min(1.0, dt * 9))

        self.yaw = _lerp(self.yaw, yaw_alvo, min(1.0, dt * 5))
        self.pitch = _lerp(self.pitch, pitch_alvo, min(1.0, dt * 5))
        self.roll = _lerp(self.roll, roll_alvo, min(1.0, dt * 7))
        self.brilho = _lerp(self.brilho, 1.0 if (dentro or estado == "pronto") else 0.0, min(1.0, dt * 4))
        return self.yaw, self.pitch, self.roll, self.amasso, self.lado, self.brilho, self.altura
