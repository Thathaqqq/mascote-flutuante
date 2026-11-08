"""Gancho do Claude Code: grava o estado de cada sessão para o mascote ler.

Uso (em settings.json): python registrar_estado.py <evento>
Recebe pelo stdin o JSON que o Claude Code manda para os ganchos.
"""
import json
import os
import sys
import time

import estado

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
    estado.PASTA.mkdir(parents=True, exist_ok=True)
    estado.MARCA_GANCHOS.touch()  # avisa o vigia que o plugin cuida das conversas

    if evento == "SessionEnd":
        estado.apagar(sessao)
        return

    novo = ESTADO_POR_EVENTO.get(evento)
    if not novo:
        return

    anterior = estado.ler(sessao)
    registro = {
        "sessao": sessao,
        "estado": novo,
        "pasta": dados.get("cwd") or anterior.get("pasta", ""),
        "pedido": anterior.get("pedido", ""),
        "aviso": "",
        "quando": time.time(),
        "fins": anterior.get("fins", 0) + (1 if evento == "Stop" else 0),  # quantas vezes terminou
        "chamadas": anterior.get("chamadas", 0) + (1 if evento == "Notification" else 0),
        "fonte": "gancho",
    }
    if evento == "UserPromptSubmit":
        registro["pedido"] = estado.limpar_pedido(dados.get("prompt")) or registro["pedido"]
    if evento == "Notification":
        registro["aviso"] = (dados.get("message") or "")[:160]
    estado.gravar(registro)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # o gancho nunca pode atrapalhar o Claude
