"""Idioma dos textos do mascote: português ou inglês.

Os textos do código continuam em português; `tr("texto")` devolve o mesmo texto em
português ou a tradução em inglês. O idioma vem da configuração ("idioma": "pt", "en"
ou "auto"); em "auto" (ou sem nada), segue o idioma do computador. Se não der para
descobrir o idioma do computador, fica em português.
"""
import os
import re
import subprocess
import sys

EN = {
    # estados e balões
    "Trabalhando": "Working",
    "Precisa de você": "Needs you",
    "Pronto para revisar": "Ready for review",
    "Algo travou": "Something is stuck",
    "Trabalhando em {n}": "Working on {n}",
    "Clique para ir à conversa": "Click to open it",
    "Oi!": "Hi!",
    "Au! Au!": "Woof! Woof!",
    "Talvez esteja pedindo permissão": "May be asking for permission",
    # tempo
    "agora": "now",
    "há {n} min": "{n} min ago",
    "há {n} h": "{n} h ago",
    # menu
    "Abrir o Claude": "Open Claude",
    "Conversas": "Conversations",
    "Chat rápido": "Quick chat",
    "Modo mini": "Mini mode",
    "Seguir o cursor": "Follow the cursor",
    "Abrir junto com o Claude": "Open together with Claude",
    "Aviso sonoro (padrão das conversas)": "Sound alert (default for conversations)",
    "Meu arquivo de som": "My sound file",
    "Som do aviso": "Alert sound",
    "Pousar na janela ativa": "Land on the active window",
    "Criar personagem com foto...": "Create character from photo...",
    "Abrir pasta de personagens": "Open characters folder",
    "Recarregar personagens": "Reload characters",
    "Personagem": "Character",
    "Idioma": "Language",
    "Automático": "Automatic",
    "Sair": "Quit",
    "Ctrl+Alt+Espaço": "Ctrl+Alt+Space",
    "Control+Option+Espaço": "Control+Option+Space",
    # sons
    "Notificação": "Notification",
    "Mensagem": "Message",
    "Calendário": "Calendar",
    "Sino": "Bell",
    "Carrilhão": "Chimes",
    "Acorde": "Chord",
    "Toque": "Ring",
    "Proximidade": "Proximity",
    "Cutucada": "Nudge",
    # janelas de escolha
    "Escolha o som do aviso": "Choose the alert sound",
    "Sons": "Sounds",
    "Todos": "All",
    "Escolha a foto do seu personagem": "Choose the photo for your character",
    "Fotos": "Photos",
    "Nome do personagem": "Character name",
    "Como ele se chama?": "What is its name?",
    "Mascote": "Mascot",
    # lista de conversas
    "Fechar": "Close",
    "Nenhuma conversa nas últimas 12 horas.": "No conversations in the last 12 hours.",
    "Som ligado": "Sound on",
    "Sem som": "Muted",
    "Conversa": "Conversation",
    "Parada": "Idle",
    "Não achei a janela do Claude aberta.": "I could not find an open Claude window.",
    # chat rápido
    "Iniciar novo chat": "Start a new chat",
    "Continuar a conversa": "Continue the conversation",
    "Pensando": "Thinking",
    "Copiar": "Copy",
    "Copiado": "Copied",
    "Sem resposta.": "No response.",
    "Não achei o Claude Code instalado (comando claude).": "I could not find Claude Code installed (claude command).",
    "Demorou demais. Tente pelo Claude.": "It took too long. Try it in Claude.",
    # personagem com foto
    "Não consegui separar o fundo desta foto. Recorte antes (Paint do Windows: Remover plano de fundo) "
    "e tente de novo com o PNG.":
        "I could not separate the background of this photo. Cut it out first (Windows Paint: Remove background) "
        "and try again with the PNG.",
    "O recorte apagou quase tudo. Use uma foto com fundo mais liso ou já recortada.":
        "The cut-out erased almost everything. Use a photo with a plainer background or one already cut out.",
    "Fundo tirado automaticamente. Se ficou feio, recorte antes e crie de novo.":
        "Background removed automatically. If it looks bad, cut it out first and create it again.",
}

# personagens prontos: nome guardado na configuração -> nome mostrado em inglês
NOMES_EN = {"Borboleta Azul": "Blue Butterfly", "Borboleta": "Butterfly", "Gato": "Cat",
            "Robô": "Robot", "Fantasma": "Ghost"}
# o caminho de volta, para aceitar o nome em inglês em `iniciar.py config personagem`
PERSONAGENS_EN = {en.lower(): pt for pt, en in NOMES_EN.items()}

_atual = None  # "pt" ou "en"; None = ainda não definido
_sistema = False  # idioma do computador, descoberto uma vez só (False = ainda não procurou)


def _do_sistema():
    """Idioma do computador: "pt", "en" (qualquer outro idioma) ou None se não der para saber."""
    try:
        if sys.platform == "win32":
            import ctypes
            cod = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            return "pt" if (cod & 0x3FF) == 0x16 else "en"  # 0x16 = português
        if sys.platform == "darwin":
            r = subprocess.run(["defaults", "read", "-g", "AppleLanguages"], capture_output=True,
                               text=True, timeout=2)
            achou = re.search(r"[A-Za-z]{2,3}", r.stdout)
            if achou:
                return "pt" if achou.group(0).lower() == "pt" else "en"
    except Exception:
        pass
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        valor = (os.environ.get(var) or "").lower()
        if re.match(r"[a-z]{2,3}([_.@-]|$)", valor):  # "c", "c.utf-8" e "posix" não dizem o idioma
            return "pt" if valor.startswith("pt") else "en"
    return None


def definir(escolha=None):
    """Define o idioma a partir da configuração: "pt", "en" ou qualquer outra coisa = automático."""
    global _atual, _sistema
    escolha = str(escolha or "").strip().lower()
    if escolha in ("pt", "en"):
        _atual = escolha
    else:
        if _sistema is False:
            _sistema = _do_sistema()
        _atual = _sistema or "pt"
    return _atual


def atual():
    return _atual or definir()


def tr(texto):
    """O texto no idioma atual. Texto sem tradução (nome de personagem da pessoa, por exemplo) volta igual."""
    if not texto or atual() != "en":
        return texto
    return EN.get(texto, texto)


def tr_nome(nome):
    """Nome de personagem no idioma atual: só os personagens prontos têm nome em inglês."""
    return NOMES_EN.get(nome, nome) if atual() == "en" else nome
