"""Personagem de ilustração animado como fantoche: cada parte se mexe no próprio ponto.

A ilustração continua a mesma (nada estica nem achata). Orelhas e rabo giram
na base, os olhos piscam, a boca abre (troca suave para a imagem sorrindo só na
região da boca), a pata da frente sobe e, de vez em quando, sai um espirro.
As partes e os pontos de giro vêm do .json do personagem ("partes"). Só usa Pillow.
"""
import math

from PIL import Image, ImageChops, ImageDraw, ImageFilter


def _poli_mascara(tam, pts, borrar=1.2):
    m = Image.new("L", tam, 0)
    ImageDraw.Draw(m).polygon([tuple(p) for p in pts], fill=255)
    return m.filter(ImageFilter.GaussianBlur(borrar)) if borrar else m


def _elipse_mascara(tam, cx, cy, rx, ry, borrar=1.5):
    m = Image.new("L", tam, 0)
    ImageDraw.Draw(m).ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=255)
    return m.filter(ImageFilter.GaussianBlur(borrar)) if borrar else m


def _preencher(img, buraco, vezes=10):
    """Fecha o buraco com o pelo em volta (borra para dentro, várias vezes). Serve para pelo escuro."""
    img = img.copy()
    vazio = Image.new("RGBA", img.size, (0, 0, 0, 0))
    img = Image.composite(vazio, img, buraco)
    for i in range(vezes):
        b = img.filter(ImageFilter.GaussianBlur(3 + i))
        img = Image.composite(b, img, buraco)
    a = ImageChops.lighter(img.getchannel("A"), buraco)
    img.putalpha(a)
    return img


def _onda(x):
    x = max(0.0, min(1.0, x))
    return math.sin(math.pi * x)


class Peca:
    """Um pedaço recortado com ponto de giro."""

    def __init__(self, img, mascara, pivo):
        caixa = mascara.getbbox() or (0, 0, 1, 1)
        m = 14  # folga para girar
        self.x0 = max(0, caixa[0] - m)
        self.y0 = max(0, caixa[1] - m)
        x1, y1 = min(img.width, caixa[2] + m), min(img.height, caixa[3] + m)
        pedaco = img.copy()  # cor intacta; só a transparência segue a máscara (sem escurecer a borda)
        pedaco.putalpha(ImageChops.multiply(img.getchannel("A"), mascara))
        self.img = pedaco.crop((self.x0, self.y0, x1, y1))
        self.pivo = (pivo[0] - self.x0, pivo[1] - self.y0)

    def colar(self, tela, ang=0.0, dx=0, dy=0):
        im = self.img if abs(ang) < 0.3 else self.img.rotate(ang, resample=Image.BICUBIC, center=self.pivo)
        tela.alpha_composite(im, (self.x0 + int(dx), max(0, self.y0 + int(dy))),
                             (0, max(0, -(self.y0 + int(dy)))))


class Fantoche:
    def __init__(self, img_caminho, partes, feliz_caminho=None):
        img = Image.open(img_caminho).convert("RGBA")
        self.tam = img.size
        tam = img.size
        base = img.copy()
        self.pecas = {}
        P = partes

        # cabeça: onde o buraco das orelhas é pelo (dentro da cabeça) e não fundo
        cab = P.get("cabeca")
        if cab and isinstance(cab[0], (list, tuple)):  # contorno da cabeça (por baixo das orelhas)
            cab_m = _poli_mascara(tam, cab, borrar=0)
        elif cab:  # ou uma elipse: cx, cy, rx, ry
            cab_m = _elipse_mascara(tam, *cab, borrar=0)
        else:
            cab_m = Image.new("L", tam, 0)

        def tirar(mascara_dura, encher):
            """Tira a parte da base: dentro de 'encher' vira pelo, fora vira fundo."""
            nonlocal base
            dentro = ImageChops.multiply(mascara_dura, encher)
            fora = ImageChops.subtract(mascara_dura, encher)
            base.putalpha(ImageChops.subtract(base.getchannel("A"), fora))
            if dentro.getbbox():
                base = _preencher(base, dentro)

        def mascara_peca(pts):
            return _poli_mascara(tam, pts, borrar=0).filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(0.7))

        for nome in ("orelha_e", "orelha_d"):
            if isinstance(P.get(nome), dict) and P[nome].get("contorno") and P[nome].get("pivo"):
                pts, pivo = P[nome]["contorno"], P[nome]["pivo"]
                self.pecas[nome] = Peca(img, mascara_peca(pts), pivo)
                tirar(_poli_mascara(tam, pts, borrar=0).filter(ImageFilter.MaxFilter(5)), cab_m)

        if isinstance(P.get("rabo"), dict) and P["rabo"].get("contorno") and P["rabo"].get("pivo"):
            pts, pivo = P["rabo"]["contorno"], P["rabo"]["pivo"]
            self.pecas["rabo"] = Peca(img, mascara_peca(pts), pivo)
            corpo = Image.new("L", tam, 0)
            ImageDraw.Draw(corpo).rectangle((0, 0, P["rabo"].get("corpo_ate_x", 0), tam[1]), fill=255)
            tirar(_poli_mascara(tam, pts, borrar=0).filter(ImageFilter.MaxFilter(5)), corpo)

        self.subida_pata = 0
        if isinstance(P.get("pata"), dict) and P["pata"].get("contorno"):
            pts = P["pata"]["contorno"]
            topo = min(p[1] for p in pts)
            dura = _poli_mascara(tam, pts, borrar=0)
            grad = Image.new("L", tam, 0)
            dg = ImageDraw.Draw(grad)
            for y in range(tam[1]):
                dg.line([(0, y), (tam[0], y)], fill=0 if y < topo else min(255, int((y - topo) * 255 / 34)))
            m = ImageChops.multiply(dura.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(0.7)), grad)
            self.pecas["pata"] = Peca(img, m, (0, 0))
            self.subida_pata = P["pata"].get("sobe", 26)
            # o pedaço de baixo da perna vira chão quando a pata sobe (só onde ela deixa de cobrir)
            corte = Image.new("L", tam, 0)
            ImageDraw.Draw(corte).rectangle((0, P["pata"].get("chao_desde", 350), tam[0], tam[1]), fill=255)
            self._pata_sai = ImageChops.multiply(dura.filter(ImageFilter.MaxFilter(3)), corte)
            self._pata_cache = {}

        self.olhos = P.get("olhos", [])
        # cor da pálpebra: o pelo em volta dos olhos
        self.cor_palpebra = (34, 32, 38)
        if self.olhos:
            cx, cy, rx, ry = self.olhos[0]
            anel = img.crop((int(cx - rx * 1.6), int(cy - ry * 2.0), int(cx + rx * 1.6), int(cy - ry * 1.2))).convert("RGB")
            px = list(anel.getdata())
            if px:
                self.cor_palpebra = tuple(sum(c[i] for c in px) // len(px) for i in range(3))

        self.boca = None
        if feliz_caminho and "boca" in P:
            feliz = Image.open(feliz_caminho).convert("RGBA")
            if feliz.size == tam:
                dif = ImageChops.difference(img.convert("RGB"), feliz.convert("RGB")).convert("L")
                dif = dif.point(lambda v: 255 if v > 45 else 0).filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(3))
                bm = ImageChops.multiply(dif, _elipse_mascara(tam, *P["boca"], borrar=8))
                caixa = bm.getbbox()
                if caixa:  # sem diferença dentro da boca: fica sem troca
                    self.boca = (feliz.crop(caixa), bm.crop(caixa), caixa)

        self.base = base
        self.img_orig = img

    def _palpebras(self, tela, fecha):
        if fecha <= 0.03:
            return
        tam = tela.size
        for cx, cy, rx, ry in self.olhos:
            topo = cy - ry - 1
            fundo = topo + (2 * ry + 2) * fecha
            arco = [(cx - rx - 2 + (2 * rx + 4) * i / 20, fundo + 2.5 * fecha * math.sin(math.pi * i / 20)) for i in range(21)]
            m = Image.new("L", tam, 0)
            ImageDraw.Draw(m).polygon([(cx - rx - 2, topo - 6), (cx + rx + 2, topo - 6)] + arco[::-1], fill=255)
            olho = Image.new("L", tam, 0)
            ImageDraw.Draw(olho).ellipse((cx - rx - 3, cy - ry - 3, cx + rx + 3, cy + ry + 3), fill=255)
            m = ImageChops.multiply(m, olho).filter(ImageFilter.GaussianBlur(0.9))
            # pálpebra feita do pelo logo acima do olho (mesma textura), mais escura perto dos cílios
            alto = int(2 * ry + 10)
            pelo = self.img_orig.crop((int(cx - rx - 4), int(topo - 6 - alto), int(cx + rx + 4), int(topo - 6)))
            pelo = pelo.resize((pelo.width, int(fundo - topo) + 12))
            sombra = Image.new("L", pelo.size, 0)
            ds = ImageDraw.Draw(sombra)
            for y in range(pelo.height):
                ds.line([(0, y), (pelo.width, y)], fill=int(150 * (y / max(1, pelo.height - 1)) ** 2))
            pelo = Image.composite(Image.new("RGBA", pelo.size, (8, 6, 10, 255)), pelo, sombra)
            camada = Image.new("RGBA", tam, (0, 0, 0, 0))
            camada.paste(pelo, (int(cx - rx - 4), int(topo - 6)))
            tela.paste(camada, (0, 0), m)
            if fecha > 0.6:
                ImageDraw.Draw(tela).line(arco[2:-2], fill=(10, 8, 12, 255), width=2)

    def desenhar(self, p, altura):
        """p: pose (ver pose_padrao). Devolve a imagem já no tamanho de tela (altura em pixels)."""
        tela = self.base.copy()
        sobe = round(self.subida_pata * p["pata"]) if "pata" in self.pecas else 0
        if sobe:
            if sobe not in self._pata_cache:
                cobre = self.pecas["pata"].img.getchannel("A")
                cobre_tudo = Image.new("L", self.tam, 0)
                cobre_tudo.paste(cobre, (self.pecas["pata"].x0, self.pecas["pata"].y0 - sobe))
                cobre_tudo = cobre_tudo.point(lambda v: 255 if v > 60 else 0)
                vazio = ImageChops.subtract(self._pata_sai, cobre_tudo).filter(ImageFilter.GaussianBlur(1.0))
                self._pata_cache[sobe] = vazio
            tela.putalpha(ImageChops.subtract(tela.getchannel("A"), self._pata_cache[sobe]))
        for nome, chave in (("rabo", "rabo"), ("orelha_e", "orelha_e"), ("orelha_d", "orelha_d")):
            if nome in self.pecas:
                self.pecas[nome].colar(tela, p[chave])
        if "pata" in self.pecas:
            self.pecas["pata"].colar(tela, 0, 0, -sobe)
        if self.boca and p["boca"] > 0.02:
            camada, mascara, caixa = self.boca
            a = mascara.point(lambda v: int(v * min(1.0, p["boca"])))
            tela.paste(camada, caixa[:2], a)
        self._palpebras(tela, p["olhos"])
        if p.get("espirro", 0) > 0.05 and "boca" in self.__dict__ and self.olhos:
            d = ImageDraw.Draw(tela)
            bx = sum(o[0] for o in self.olhos) / len(self.olhos)
            by = max(o[1] for o in self.olhos) + 55
            k = p["espirro"]
            for dx, dy in ((-30, 4), (0, 16), (30, 4), (-16, 26), (18, 26)):
                x, y, r = bx + dx * (0.5 + k), by + dy * (0.5 + k), 4 * k
                d.ellipse((x - r, y - r, x + r, y + r), fill=(205, 225, 245, 230))
        esc = altura / tela.height
        tela = tela.resize((max(4, round(tela.width * esc)), max(4, round(tela.height * esc))), Image.LANCZOS)
        if abs(p.get("inclina", 0)) > 0.3:
            pe = (tela.width / 2, tela.height)
            tela = tela.rotate(p["inclina"], resample=Image.BICUBIC, center=pe, expand=False)
        return tela


def pose_padrao():
    return {"orelha_e": 0.0, "orelha_d": 0.0, "olhos": 0.0, "boca": 0.0, "rabo": 0.0,
            "pata": 0.0, "inclina": 0.0, "desce": 0.0, "espirro": 0.0}


class Animador:
    """Fica parada e só dá sinal: pisca, mexe a orelha, balança o rabo; late, dá a pata, espirra."""

    def __init__(self):
        self.t = 0.0
        self.gesto = None
        self.gesto_t0 = 0.0
        self.prox_piscada = 2.5
        self.prox_orelha = 5.0
        self.prox_inclina = 9.0

    def comecar(self, gesto):
        self.gesto, self.gesto_t0 = gesto, self.t

    def pose(self, dt):
        self.t += dt
        t = self.t
        p = pose_padrao()
        if t > self.prox_piscada:
            k = (t - self.prox_piscada) / 0.18
            p["olhos"] = _onda(k)
            if k >= 1:
                self.prox_piscada = t + 3 + (t * 3.7) % 3
        if t > self.prox_orelha:
            k = (t - self.prox_orelha) / 0.4
            p["orelha_d"] = -7 * _onda(k)
            if k >= 1:
                self.prox_orelha = t + 6 + (t * 5.3) % 5
        p["rabo"] = 7 * math.sin(t * 2.2)
        if t > self.prox_inclina:
            k = (t - self.prox_inclina) / 1.6
            p["inclina"] = 6 * _onda(k)
            if k >= 1:
                self.prox_inclina = t + 10 + (t * 2.9) % 6

        g, f = self.gesto, t - self.gesto_t0
        if g == "latido":
            for ini in (0.0, 0.45):  # au, au
                k = (f - ini) / 0.32
                if 0 <= k <= 1:
                    w = _onda(k)
                    p["boca"] = w
                    p["orelha_e"], p["orelha_d"] = 7 * w, -7 * w  # orelhas balançam
                    p["desce"] = -2 * w
                    p["rabo"] = 18 * math.sin(t * 16)
            if f > 1.0:
                self.gesto = None
        elif g == "pata":
            if f < 0.3:
                s = _onda(f / 0.6)
            elif f < 1.3:
                s = 1 - 0.25 * (0.5 + 0.5 * math.sin((f - 0.3) / 1.0 * 4 * math.pi))
            elif f < 1.6:
                s = _onda(0.5 + (f - 1.3) / 0.6)
            else:
                s, self.gesto = 0.0, None
            p["pata"] = s
            p["inclina"] = 4 * min(1.0, f / 0.3) if f < 1.6 else 0
            p["rabo"] = 15 * math.sin(t * 12)
        elif g == "espirro":
            if f < 0.5:  # puxa o ar
                w = f / 0.5
                p["olhos"] = 0.55 * w
                p["boca"] = 0.25 * w
                p["desce"] = -3 * w
            elif f < 0.75:  # atchim!
                w = _onda((f - 0.5) / 0.25)
                p["olhos"] = 1.0
                p["boca"] = 0.5
                p["desce"] = 4 * w
                p["orelha_e"], p["orelha_d"] = 9 * w, -9 * w
                p["espirro"] = (f - 0.5) / 0.25 + 0.2
            elif f < 1.15:
                p["olhos"] = 1 - (f - 0.75) / 0.4
                p["espirro"] = max(0.0, 1.2 - (f - 0.75) * 3)
            else:
                self.gesto = None
        return p
