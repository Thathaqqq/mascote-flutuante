"""Gancho do Claude Code: grava o estado de cada sessão para o mascote ler.

Uso (em settings.json): python registrar_estado.py <evento>
Recebe pelo stdin o JSON que o Claude Code manda para os ganchos.
"""
import json
import os
import sys
import time
from pathlib import Path

PASTA = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "mascote" / "estado"

ESTADO_POR_EVENTO = {
    "UserPromptSubmit": "trabalhando",
    "PreToolUse": "trabalhando",
    "PostToolUse": "trabalhando",
    "Notification": "esperando",
    "Stop": "pronto",
    "StopFailure": "bloqueado",
}


def main():
    if os.environ.get("MASCOTE_INTERNO"):
        return  # conversa do chat rápido do próprio mascote
    evento = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        dados = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except Exception:
        dados = {}
    evento = evento or dados.get("hook_event_name", "")
    sessao = dados.get("session_id") or "sem-id"
    PASTA.mkdir(parents=True, exist_ok=True)
    arquivo = PASTA / f"{sessao}.json"

    if evento == "SessionEnd":
        arquivo.unlink(missing_ok=True)
        return

    estado = ESTADO_POR_EVENTO.get(evento)
    if not estado:
        return

    anterior = {}
    if arquivo.exists():
        try:
            anterior = json.loads(arquivo.read_text(encoding="utf-8"))
        except Exception:
            anterior = {}

    registro = {
        "sessao": sessao,
        "estado": estado,
        "pasta": dados.get("cwd") or anterior.get("pasta", ""),
        "pedido": anterior.get("pedido", ""),
        "aviso": "",
        "quando": time.time(),
        "fins": anterior.get("fins", 0) + (1 if evento == "Stop" else 0),  # quantas vezes terminou
        "chamadas": anterior.get("chamadas", 0) + (1 if evento == "Notification" else 0),
    }
    if evento == "UserPromptSubmit":
        pedido = " ".join((dados.get("prompt") or "").split())
        if pedido and not pedido.startswith("<"):  # avisos automáticos do sistema não são pedido da pessoa
            registro["pedido"] = pedido[:120]
    if evento == "Notification":
        registro["aviso"] = (dados.get("message") or "")[:160]

    tmp = arquivo.with_suffix(".tmp")
    tmp.write_text(json.dumps(registro, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, arquivo)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # o gancho nunca pode atrapalhar o Claude
