"""Vigia: descobre o que o Claude Code está fazendo lendo o histórico das conversas.

É o substituto dos ganchos (hooks) para quem instala o mascote só como skill, sem
o plugin. O Claude Code grava cada conversa em ~/.claude/projects/<pasta>/<id>.jsonl;
o vigia lê o fim desses arquivos e grava o mesmo arquivinho de estado que o
gancho grava (~/.claude/mascote/estado/<id>.json), então a janela do mascote
funciona igual.

Como o estado é deduzido (a última coisa que aconteceu na conversa):
- mensagem da pessoa ou resultado de ferramenta -> trabalhando
- resposta do Claude que terminou o turno       -> pronto
- erro da API                                   -> algo travou
- pergunta para a pessoa (AskUserQuestion, plano) -> precisa de você
- ferramenta que pode pedir permissão parada há um tempo, sem resultado
                                                -> precisa de você (palpite: um
  comando demorado e um pedido de permissão parecem iguais no histórico)
"""
import json
import os
import time
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
PROJETOS = CONFIG_DIR / "projects"
PASTA_ESTADO = CONFIG_DIR / "mascote" / "estado"

JANELA = 12 * 3600          # só olha conversas mexidas nas últimas 12 h
ESPERA_PERMISSAO = 15       # segundos parada numa ferramenta até virar "precisa de você"
FIM_DO_ARQUIVO = 256 * 1024  # quanto do fim do arquivo é lido
PARADA_DEMAIS = 30 * 60     # "trabalhando" sem nada novo por tanto tempo: conversa largada
PRONTO_ANTIGO = 10 * 60     # ao abrir o mascote, conversas terminadas há mais que isso não aparecem
PERGUNTAM = {"AskUserQuestion", "ExitPlanMode"}
# ferramentas que não pedem permissão (ou rodam sozinhas por muito tempo): nunca viram "precisa de você"
SEM_PERMISSAO = {"Read", "Glob", "Grep", "LS", "NotebookRead", "TodoWrite", "TaskCreate", "TaskUpdate",
                 "TaskGet", "TaskList", "Task", "Agent", "Skill", "ToolSearch", "Monitor", "TaskOutput"}
NAO_INTERATIVAS = {"sdk-cli", "sdk-py", "sdk-ts"}  # claude -p e SDK (inclui o chat rápido do mascote)


def _texto_da_pessoa(conteudo):
    if isinstance(conteudo, str):
        return conteudo
    if isinstance(conteudo, list):
        partes = [b.get("text", "") for b in conteudo if isinstance(b, dict) and b.get("type") == "text"]
        if partes and not any(isinstance(b, dict) and b.get("type") == "tool_result" for b in conteudo):
            return " ".join(partes)
    return None


def ler_fim(caminho):
    """Linhas JSON do fim do arquivo (a primeira, possivelmente cortada, é descartada)."""
    with open(caminho, "rb") as f:
        f.seek(0, os.SEEK_END)
        tam = f.tell()
        inicio = max(0, tam - FIM_DO_ARQUIVO)
        f.seek(inicio)
        bruto = f.read()
    linhas = bruto.split(b"\n")
    if inicio > 0:
        linhas = linhas[1:]
    registros = []
    for linha in linhas:
        try:
            registros.append(json.loads(linha))
        except ValueError:
            continue
    return registros


def resumir(registros):
    """Estado da conversa pelos registros, do mais antigo ao mais novo.
    Devolve dict com estado, ferramenta pendente, pedido, pasta, sessao, interativa."""
    r = {"estado": None, "pendente": None, "pedido": "", "pasta": "", "sessao": None, "interativa": True,
         "aviso": ""}
    for reg in registros:
        tipo = reg.get("type")
        if tipo == "last-prompt" and reg.get("lastPrompt") and not r["pedido"]:
            r["pedido"] = " ".join(reg["lastPrompt"].split())[:120]
            continue
        if tipo not in ("user", "assistant") or reg.get("isSidechain") or reg.get("isMeta"):
            continue
        r["sessao"] = reg.get("sessionId") or r["sessao"]
        r["pasta"] = reg.get("cwd") or r["pasta"]
        if reg.get("entrypoint") in NAO_INTERATIVAS:
            r["interativa"] = False
        msg = reg.get("message") or {}
        conteudo = msg.get("content")
        if tipo == "user":
            texto = _texto_da_pessoa(conteudo)
            if texto is None:  # resultado de ferramenta: o Claude continua
                r["estado"], r["pendente"] = "trabalhando", None
                continue
            texto = " ".join(texto.split())
            if texto.startswith("[Request interrupted"):
                r["estado"], r["pendente"] = "parado", None
            elif texto and not texto.startswith("<"):  # avisos automáticos começam com <
                r["estado"], r["pendente"] = "trabalhando", None
                r["pedido"] = texto[:120]
        else:
            if reg.get("isApiErrorMessage"):
                r["estado"], r["pendente"] = "bloqueado", None
                continue
            parada = msg.get("stop_reason")
            usos = [b for b in (conteudo or []) if isinstance(b, dict) and b.get("type") == "tool_use"]
            if usos:
                r["estado"], r["pendente"] = "trabalhando", usos[-1].get("name", "")
            elif parada in ("end_turn", "stop_sequence", "max_tokens", "refusal"):
                r["estado"], r["pendente"] = "pronto", None
            elif r["pendente"] is None:
                r["estado"] = "trabalhando"
    return r


class Vigia:
    def __init__(self):
        self.vistos = {}    # caminho -> (mtime, tamanho, resumo)
        self.ultimos = {}   # sessao -> estado gravado por último
        self.primeira = True

    def estado_agora(self, resumo, mtime, agora):
        estado = resumo["estado"]
        pendente = resumo["pendente"]
        parada = agora - mtime
        if estado == "trabalhando" and parada > PARADA_DEMAIS:
            return "parado"  # a conversa foi fechada no meio (ou o Claude caiu)
        if estado == "pronto" and parada > PRONTO_ANTIGO and resumo["sessao"] not in self.ultimos:
            return "parado"  # já tinha terminado antes de o mascote abrir: não enche a lista
        if estado == "trabalhando" and pendente:
            if pendente in PERGUNTAM:
                return "esperando"
            if pendente not in SEM_PERMISSAO and not pendente.startswith("mcp__") and parada > ESPERA_PERMISSAO:
                return "esperando"
        return estado

    def atualizar(self):
        """Lê as conversas recentes e grava os estados. Chamado a cada segundo pelo mascote."""
        if not PROJETOS.exists():
            return
        agora = time.time()
        PASTA_ESTADO.mkdir(parents=True, exist_ok=True)
        for arq in PROJETOS.glob("*/*.jsonl"):
            try:
                st = arq.stat()
            except OSError:
                continue
            if agora - st.st_mtime > JANELA:
                continue
            visto = self.vistos.get(arq)
            if visto and visto[0] == st.st_mtime and visto[1] == st.st_size:
                resumo = visto[2]
            else:
                try:
                    resumo = resumir(ler_fim(arq))
                except OSError:
                    continue
                self.vistos[arq] = (st.st_mtime, st.st_size, resumo)
            if not resumo["sessao"] or not resumo["interativa"] or not resumo["estado"]:
                continue
            self.gravar(resumo, self.estado_agora(resumo, st.st_mtime, agora), st.st_mtime)
        self.primeira = False

    def gravar(self, resumo, estado, mtime):
        sessao = resumo["sessao"]
        arquivo = PASTA_ESTADO / f"{sessao}.json"
        anterior = {}
        if arquivo.exists():
            try:
                anterior = json.loads(arquivo.read_text(encoding="utf-8"))
            except Exception:
                anterior = {}
            # o gancho do plugin está ativo para esta conversa: ele manda, o vigia não mexe
            if anterior.get("fonte") != "vigia" and anterior.get("quando", 0) >= mtime - 60:
                return
        if estado == "parado":
            if anterior.get("fonte") == "vigia":
                arquivo.unlink(missing_ok=True)
            self.ultimos[sessao] = estado
            return
        antes = self.ultimos.get(sessao, anterior.get("estado"))
        if antes == estado and anterior:
            return
        mudou = antes is not None and antes != estado and not self.primeira
        registro = {
            "sessao": sessao,
            "estado": estado,
            "pasta": resumo["pasta"] or anterior.get("pasta", ""),
            "pedido": resumo["pedido"] or anterior.get("pedido", ""),
            "aviso": "Talvez esteja pedindo permissão" if estado == "esperando" else "",
            "quando": mtime if not mudou else time.time(),
            "fins": anterior.get("fins", 0) + (1 if mudou and estado == "pronto" else 0),
            "chamadas": anterior.get("chamadas", 0) + (1 if mudou and estado == "esperando" else 0),
            "fonte": "vigia",
        }
        tmp = arquivo.with_suffix(".tmp")
        tmp.write_text(json.dumps(registro, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, arquivo)
        self.ultimos[sessao] = estado
