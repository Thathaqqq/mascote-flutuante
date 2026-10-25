"""Transforma uma foto qualquer num personagem do mascote.

- Foto já recortada (PNG com fundo transparente): só ajusta tamanho e corta as sobras.
- Foto com fundo: tenta tirar o fundo a partir das bordas. Funciona bem com fundo
  liso (parede, chão, lençol). Com fundo muito cheio de coisas, avisa para recortar
  antes (Paint do Windows: Remover plano de fundo; ou Canva).
"""
import json
import re
import unicodedata
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

PASTA_PERSONAGENS = Path.home() / ".claude" / "mascote" / "personagens"
MARCA = (255, 0, 254)


def _nome_arquivo(nome):
    s = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "personagem"


def _tem_transparencia(img):
    return img.mode == "RGBA" and img.getchannel("A").getextrema()[0] < 200


def tirar_fundo(img, tolerancia=38):
    """Pinta a partir das bordas tudo que for parecido com o fundo e apaga."""
    rgb = img.convert("RGB")
    w, h = rgb.size
    pontos = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]
    pontos += [(round(w * k / 8), 0) for k in range(1, 8)] + [(round(w * k / 8), h - 1) for k in range(1, 8)]
    pontos += [(0, round(h * k / 8)) for k in range(1, 8)] + [(w - 1, round(h * k / 8)) for k in range(1, 8)]
    for p in pontos:
        if rgb.getpixel(p) != MARCA:
            ImageDraw.floodfill(rgb, p, MARCA, thresh=tolerancia)
    r, g, b = rgb.split()
    fundo = ImageChops.multiply(ImageChops.multiply(r.point(lambda v: 255 if v == 255 else 0),
                                                    g.point(lambda v: 255 if v == 0 else 0)),
                                b.point(lambda v: 255 if v == 254 else 0))
    alfa = ImageChops.invert(fundo)
    # borda limpa e suave
    alfa = alfa.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.2))
    tirado = 1 - (sum(alfa.histogram()[i] * i for i in range(256)) / 255) / (w * h)
    saida = img.convert("RGBA")
    saida.putalpha(alfa)
    return saida, tirado


def criar_personagem(caminho_foto, nome, destino=PASTA_PERSONAGENS):
    """Cria o personagem e devolve (arquivo .json, aviso ou None)."""
    img = ImageOps.exif_transpose(Image.open(caminho_foto))
    img.thumbnail((900, 900), Image.LANCZOS)
    aviso = None
    if _tem_transparencia(img.convert("RGBA") if img.mode in ("RGBA", "LA", "P") else img):
        img = img.convert("RGBA")
    else:
        img, tirado = tirar_fundo(img)
        if tirado < 0.08:
            raise ValueError("Não consegui separar o fundo desta foto. Recorte antes (Paint do Windows: "
                             "Remover plano de fundo) e tente de novo com o PNG.")
        if tirado > 0.95:
            raise ValueError("O recorte apagou quase tudo. Use uma foto com fundo mais liso ou já recortada.")
        aviso = "Fundo tirado automaticamente. Se ficou feio, recorte antes e crie de novo."
    caixa = img.getchannel("A").point(lambda v: 255 if v > 40 else 0).getbbox()
    if caixa:
        img = img.crop(caixa)
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    base = _nome_arquivo(nome)
    img.save(destino / f"{base}.png")
    arq = destino / f"{base}.json"
    arq.write_text(json.dumps({"nome": nome, "tipo": "foto", "imagem": f"{base}.png"},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    return arq, aviso
