"""Arquivinhos de estado que o mascote lê: um por conversa, em ~/.claude/mascote/estado.

Quem grava: o gancho do plugin (registrar_estado.py) ou, sem o plugin, o vigia (vigia.py).
"""
import json
import os
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
BASE = CONFIG_DIR / "mascote"
PASTA = BASE / "estado"
MARCA_GANCHOS = BASE / "ganchos"  # o gancho mexe nela a cada evento: sinal de que o plugin está ativo


def limpar_pedido(texto):
    """Começo do pedido da pessoa, numa linha só. Avisos automáticos do sistema (começam com <) não contam."""
    pedido = " ".join((texto or "").split())
    return "" if pedido.startswith("<") else pedido[:120]


def ler(sessao):
    try:
        return json.loads((PASTA / f"{sessao}.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def gravar(registro):
    PASTA.mkdir(parents=True, exist_ok=True)
    arquivo = PASTA / f"{registro['sessao']}.json"
    tmp = arquivo.with_name(f"{arquivo.stem}.{registro.get('fonte', 'gancho')}.tmp")
    tmp.write_text(json.dumps(registro, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, arquivo)


def apagar(sessao):
    (PASTA / f"{sessao}.json").unlink(missing_ok=True)
