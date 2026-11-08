"""Vigia: descobre o que o Claude Code está fazendo lendo o histórico das conversas.

É o substituto dos ganchos (hooks) para quem instala o mascote só como skill, sem
o plugin. O Claude Code grava cada conversa em ~/.claude/projects/<pasta>/<id>.jsonl;
o vigia lê o que foi acrescentado nesses arquivos e grava o mesmo arquivinho de
estado que o gancho grava, então a janela do mascote funciona igual.

Como o estado é deduzido:
- mensagem da pessoa ou resultado de ferramenta -> trabalhando
- resposta do Claude que terminou o turno       -> pronto
- erro da API                                   -> algo travou
- pergunta para a pessoa (AskUserQuestion, plano) -> precisa de você
- ferramenta que pode pedir permissão sem resultado há mais de 15 s
                                                -> precisa de você, como palpite
  (um comando demorado e um pedido de permissão parecem iguais no histórico;
  o palpite não toca som)
Se o plugin estiver ativo (o gancho mexeu na marca há pouco), o vigia não faz nada.
"""
import json
import time
from datetime import datetime

import estado

PROJETOS = estado.CONFIG_DIR / "projects"

JANELA = 12 * 3600          # só olha conversas mexidas nas últimas 12 h
ESPERA_PERMISSAO = 15       # segundos com uma ferramenta sem resultado até virar "precisa de você"
PARADA_DEMAIS = 30 * 60     # "trabalhando" sem nada novo por tanto tempo: conversa largada
PRONTO_ANTIGO = 10 * 60     # ao abrir o mascote, conversas terminadas há mais que isso não aparecem
LER_NO_INICIO = 2 * 1024 * 1024  # na primeira leitura, quanto do fim do arquivo é lido
PROCURAR_A_CADA = 5         # segundos entre buscas por conversas novas
PERGUNTAM = {"AskUserQuestion", "ExitPlanMode"}
# ferramentas que não pedem permissão (ou rodam sozinhas por muito tempo): nunca viram "precisa de você"
SEM_PERMISSAO = {"Read", "Glob", "Grep", "LS", "NotebookRead", "TodoWrite", "TaskCreate", "TaskUpdate",
                 "TaskGet", "TaskList", "Task", "Agent", "Skill", "ToolSearch", "Monitor", "TaskOutput"}
EDICAO = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
NAO_INTERATIVAS = {"sdk-cli", "sdk-py", "sdk-ts"}  # claude -p e SDK (inclui o chat rápido do mascote)


def _quando(reg):
    try:
        return datetime.fromisoformat(reg["timestamp"].replace("Z", "+00:00")).timestamp()
    except Exception:
        return time.time()


def _texto_da_pessoa(conteudo):
    if isinstance(conteudo, str):
        return conteudo
    if isinstance(conteudo, list):
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in conteudo):
            return None
        partes = [b.get("text", "") for b in conteudo if isinstance(b, dict) and b.get("type") == "text"]
        if partes:
            return " ".join(partes)
    return None


class Conversa:
    """O que se sabe de uma conversa, atualizado a cada linha nova do histórico."""

    def __init__(self):
        self.pos = None       # até onde o arquivo já foi lido
        self.resto = b""      # linha ainda sendo escrita
        self.sessao = None
        self.pasta = ""
        self.pedido = ""
        self.interativa = True
        self.permissao = "default"
        self.estado = None
        self.abertas = {}     # ferramentas sem resultado: id -> (nome, quando)
        self.fins = 0         # turnos terminados vistos depois de o mascote abrir
        self.perguntas = set()  # ids das perguntas à pessoa já vistas

    def ler(self, caminho, tamanho):
        primeira = self.pos is None
        if not primeira and tamanho < self.pos:  # arquivo reescrito: começa de novo
            self.__init__()
            primeira = True
        if primeira:
            self.pos = max(0, tamanho - LER_NO_INICIO)
        with open(caminho, "rb") as f:
            f.seek(self.pos)
            bruto = f.read(tamanho - self.pos)
        if primeira and self.pos > 0:
            corte = bruto.find(b"\n")
            bruto = bruto[corte + 1:] if corte >= 0 else b""
        self.pos = tamanho
        linhas = (self.resto + bruto).split(b"\n")
        self.resto = linhas.pop()
        for linha in linhas:
            try:
                reg = json.loads(linha)
            except ValueError:
                continue
            if isinstance(reg, dict):
                self.registro(reg, contar=not primeira)

    def registro(self, reg, contar):
        tipo = reg.get("type")
        if tipo == "last-prompt" and reg.get("lastPrompt"):
            self.pedido = estado.limpar_pedido(reg["lastPrompt"]) or self.pedido
            return
        if tipo not in ("user", "assistant") or reg.get("isSidechain") or reg.get("isMeta"):
            return
        if reg.get("isCompactSummary") or reg.get("isVisibleInTranscriptOnly"):
            return  # resumo do /compact: não é pedido da pessoa
        self.sessao = reg.get("sessionId") or self.sessao
        self.pasta = reg.get("cwd") or self.pasta
        if reg.get("entrypoint") in NAO_INTERATIVAS:
            self.interativa = False
        msg = reg.get("message") or {}
        conteudo = msg.get("content")
        if tipo == "user":
            self.permissao = reg.get("permissionMode") or self.permissao
            texto = _texto_da_pessoa(conteudo)
            if texto is None:  # resultado de ferramenta: fecha aquela ferramenta, o Claude continua
                for b in conteudo if isinstance(conteudo, list) else []:
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        self.abertas.pop(b.get("tool_use_id"), None)
                self.estado = "trabalhando"
                return
            texto = " ".join(texto.split())
            if texto.startswith("[Request interrupted"):
                self.estado, self.abertas = "parado", {}
            elif texto and not texto.startswith("<"):  # avisos automáticos começam com <
                self.estado, self.abertas = "trabalhando", {}
                self.pedido = estado.limpar_pedido(texto) or self.pedido
            return
        if reg.get("isApiErrorMessage"):
            self.estado, self.abertas = "bloqueado", {}
            return
        usos = [b for b in (conteudo if isinstance(conteudo, list) else [])
                if isinstance(b, dict) and b.get("type") == "tool_use"]
        for u in usos:
            self.abertas[u.get("id")] = (u.get("name", ""), _quando(reg))
            if u.get("name") in PERGUNTAM and contar:
                self.perguntas.add(u.get("id"))  # cada pergunta conta uma vez (para o som)
        if usos:
            self.estado = "trabalhando"
        elif msg.get("stop_reason") in ("end_turn", "stop_sequence", "max_tokens", "refusal"):
            if self.estado != "pronto" and contar:
                self.fins += 1  # conta cada término, mesmo os que duram menos de um segundo
            self.estado, self.abertas = "pronto", {}
        elif not self.abertas:
            self.estado = "trabalhando"

    def pode_pedir_permissao(self, nome):
        if nome in SEM_PERMISSAO or nome.startswith("mcp__"):
            return False
        if self.permissao in ("bypassPermissions", "auto"):
            return False
        return not (self.permissao == "acceptEdits" and nome in EDICAO)

    def agora(self, agora, mtime):
        """(estado, é palpite?) neste momento."""
        if self.estado == "trabalhando":
            if any(nome in PERGUNTAM for nome, _ in self.abertas.values()):
                return "esperando", False
            if any(self.pode_pedir_permissao(nome) and agora - desde > ESPERA_PERMISSAO
                   for nome, desde in self.abertas.values()):
                return "esperando", True
            if agora - mtime > PARADA_DEMAIS:
                return "parado", False  # a conversa foi fechada no meio (ou o Claude caiu)
        return self.estado, False


class Vigia:
    def __init__(self):
        self.conversas = {}   # caminho -> Conversa
        self.gravado = {}     # sessao -> o que foi gravado por último
        self.arquivos = []
        self.procurou = 0.0
        self.inicio = time.time()

    def ganchos_ativos(self, agora):
        try:
            return agora - estado.MARCA_GANCHOS.stat().st_mtime < JANELA
        except OSError:
            return False

    def atualizar(self):
        """Lê o que mudou nas conversas e grava os estados. Chamado a cada segundo pelo mascote."""
        agora = time.time()
        if self.ganchos_ativos(agora):
            if self.conversas or self.procurou == 0.0:
                self.limpar(agora, tudo=True)  # o plugin manda: tira o que o vigia tinha gravado
                self.conversas, self.gravado, self.procurou = {}, {}, -1.0
            return
        if agora - self.procurou > PROCURAR_A_CADA:
            self.procurou = agora
            self.arquivos = list(PROJETOS.glob("*/*.jsonl")) if PROJETOS.exists() else []
            self.limpar(agora)
        for arq in self.arquivos:
            try:
                st = arq.stat()
                if agora - st.st_mtime > JANELA:
                    continue
                c = self.conversas.setdefault(arq, Conversa())
                if c.pos != st.st_size:
                    c.ler(arq, st.st_size)
                if c.sessao and c.interativa and c.estado:
                    self.gravar(c, agora, st.st_mtime)
            except Exception:
                continue  # um arquivo com problema não pode parar os outros

    def gravar(self, c, agora, mtime):
        atual, palpite = c.agora(agora, mtime)
        if atual == "parado" or (c.sessao not in self.gravado and atual == "pronto"
                                 and mtime < self.inicio - PRONTO_ANTIGO):
            # parado, ou já tinha terminado antes de o mascote abrir: não aparece
            if self.gravado.get(c.sessao) != "fora":
                if estado.ler(c.sessao).get("fonte") == "vigia":
                    estado.apagar(c.sessao)
                self.gravado[c.sessao] = "fora"
            return
        marca = (atual, palpite, c.pedido, c.fins, len(c.perguntas))
        if self.gravado.get(c.sessao) == marca:
            return
        anterior = estado.ler(c.sessao)
        if anterior and anterior.get("fonte") != "vigia":
            return  # gravado pelo gancho: não mexe
        mudou = anterior.get("estado") != atual
        estado.gravar({
            "sessao": c.sessao,
            "estado": atual,
            "pasta": c.pasta,
            "pedido": c.pedido,
            "aviso": "Talvez esteja pedindo permissão" if palpite else "",
            "quando": agora if (mudou and anterior) else anterior.get("quando", mtime),
            "fins": c.fins,
            "chamadas": len(c.perguntas),
            "palpite": palpite,
            "fonte": "vigia",
        })
        self.gravado[c.sessao] = marca

    def limpar(self, agora, tudo=False):
        """Apaga estados do vigia antigos (ou todos, quando o plugin assume)."""
        if not estado.PASTA.exists():
            return
        for arq in estado.PASTA.glob("*.json"):
            try:
                r = json.loads(arq.read_text(encoding="utf-8"))
                if r.get("fonte") == "vigia" and (tudo or agora - r.get("quando", 0) > JANELA):
                    arq.unlink()
            except Exception:
                continue
