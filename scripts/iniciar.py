"""Liga, desliga e configura o mascote.

  python iniciar.py              liga o mascote (se já estiver ligado, não faz nada)
  python iniciar.py auto         usado ao abrir o Claude: liga só se o início automático estiver ativo
  python iniciar.py parar        desliga
  python iniciar.py recarregar   relê configuração e personagens
  python iniciar.py validar ARQ  confere um personagem personalizado
  python iniciar.py foto FOTO NOME   cria um personagem a partir de uma foto (tira o fundo se for liso)
  python iniciar.py config CHAVE VALOR   ex.: config personagem Gato | config mini sim
"""
import json
import socket
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
BASE = Path.home() / ".claude" / "mascote"
CONFIG = BASE / "config.json"
PORTA = 47653
CHAVES_SIM_NAO = {"mini", "seguir", "automatico", "som", "pousar"}


def enviar(comando):
    try:
        with socket.create_connection(("127.0.0.1", PORTA), timeout=1) as s:
            s.sendall(comando.encode())
        return True
    except OSError:
        return False


def ler_config():
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except Exception:
        return {}


def ligar():
    if enviar("oi"):
        print("O mascote já está ligado.")
        return
    exe = Path(sys.executable)
    if sys.platform == "win32":
        pythonw = exe.with_name("pythonw.exe")
        exe = pythonw if pythonw.exists() else exe
        subprocess.Popen([str(exe), str(AQUI / "mascote.pyw")], cwd=str(AQUI),
                         creationflags=0x00000008 | 0x00000200,  # sem console, processo à parte
                         close_fds=True)
    else:
        subprocess.Popen([str(exe), str(AQUI / "mascote.pyw")], cwd=str(AQUI), start_new_session=True,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("Mascote ligado.")


def validar(caminho):
    erros = []
    try:
        p = json.loads(Path(caminho).read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Arquivo inválido: {e}")
        return False
    if not p.get("nome"):
        erros.append("falta 'nome'")
    if p.get("tipo") in ("borboleta3d", "foto"):
        img = Path(caminho).parent / p.get("imagem", "")
        if not img.is_file():
            erros.append(f"não achei a imagem '{p.get('imagem')}' na mesma pasta")
        else:
            try:
                from PIL import Image
                foto = Image.open(img)
                if foto.mode != "RGBA" or foto.getchannel("A").getextrema()[0] > 0:
                    erros.append("a foto precisa ter fundo transparente (PNG recortado)")
            except ImportError:
                erros.append("falta o Pillow (python -m pip install pillow)")
        print("Personagem OK." if not erros else "Problemas: " + "; ".join(erros))
        return not erros
    mapa, cores = p.get("mapa"), p.get("cores")
    if not isinstance(mapa, list) or not mapa:
        erros.append("falta 'mapa' (lista de linhas)")
    if not isinstance(cores, dict) or not cores:
        erros.append("falta 'cores'")
    if not erros:
        if len(mapa) > 16 or max(len(l) for l in mapa) > 16:
            erros.append("o desenho pode ter no máximo 16 x 16 quadradinhos")
        usados = {ch for l in mapa for ch in l} - {"."}
        faltando = usados - set(cores)
        if faltando:
            erros.append(f"letras sem cor definida: {', '.join(sorted(faltando))}")
        for k, v in cores.items():
            if not (isinstance(v, str) and v.startswith("#") and len(v) == 7):
                erros.append(f"cor de '{k}' precisa ser no formato #RRGGBB")
    print("Personagem OK." if not erros else "Problemas: " + "; ".join(erros))
    return not erros


def main():
    acao = sys.argv[1] if len(sys.argv) > 1 else "ligar"
    if acao == "auto":
        if ler_config().get("automatico", True):
            ligar()
    elif acao == "ligar":
        ligar()
    elif acao == "parar":
        print("Mascote desligado." if enviar("sair") else "O mascote não estava ligado.")
    elif acao == "recarregar":
        enviar("recarregar")
    elif acao == "validar":
        sys.exit(0 if validar(sys.argv[2]) else 1)
    elif acao == "foto":
        sys.path.insert(0, str(AQUI))
        import recorte
        arq, aviso = recorte.criar_personagem(sys.argv[2], " ".join(sys.argv[3:]))
        print(f"Personagem criado: {arq}")
        if aviso:
            print(aviso)
    elif acao == "config":
        chave, valor = sys.argv[2], " ".join(sys.argv[3:])
        cfg = ler_config()
        if chave in CHAVES_SIM_NAO:
            valor = valor.lower() in ("sim", "s", "true", "1", "ligado")
        cfg[chave] = valor
        BASE.mkdir(parents=True, exist_ok=True)
        CONFIG.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        enviar("recarregar")
        print(f"{chave} = {valor}")
    else:
        print(__doc__)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Erro: {e}")
