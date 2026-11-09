---
name: mascote-flutuante
description: Floating desktop mascot (pet) that shows what Claude Code is doing (working, needs you, done) - including Frida, a black pug. Turns the mascot on/off, configures it and creates custom characters. Use when the person says "mascote", "mascot", "pet", "ligar/desligar o mascote", "trocar o personagem", "Frida", "criar meu personagem" or types /mascote-flutuante.
---

# Mascote flutuante

O mascote é uma janelinha que fica por cima das outras e mostra o que o Claude Code está fazendo. Funciona no Windows e no Mac com Python 3 instalado. Os textos do mascote são em português.

Os scripts estão na pasta `scripts` ao lado deste SKILL.md (a pasta da skill). Nos comandos abaixo, `<pasta da skill>` é essa pasta; use o caminho completo e entre aspas. No Mac, use `python3` no lugar de `python`.

A pasta `~/.claude` citada abaixo é a pasta de configuração do Claude Code; se a variável `CLAUDE_CONFIG_DIR` estiver definida, o mascote usa essa pasta no lugar.

## Como ele sabe o que o Claude está fazendo

Esta versão é a skill, sem ganchos (hooks). O mascote lê, no próprio computador, o fim do histórico das conversas do Claude Code (`~/.claude/projects`) e deduz o estado:

- **Trabalhando** e **Pronto para revisar**: confiáveis.
- **Precisa de você**: certo quando o Claude faz uma pergunta; quando ele espera uma permissão, é um palpite (uma ferramenta parada há mais de 15 segundos, sem resposta). Um comando demorado pode aparecer como "precisa de você".
- O mascote em si não usa a internet: ele lê o histórico no próprio computador e guarda, em `~/.claude/mascote/estado`, um arquivinho por conversa com o estado, a pasta do projeto e o começo do último pedido. O chat rápido é a exceção: ele manda a pergunta pelo seu Claude Code.
- Quando o palpite é "talvez pedindo permissão", o mascote não toca som.
- Se o plugin do mascote também estiver instalado, os ganchos dele mandam e a leitura do histórico fica parada.
- Em outros assistentes (Cursor, Codex etc.) o mascote abre e os comandos funcionam, mas ele não acompanha o trabalho: o histórico que ele lê é o do Claude Code.

Para o estado exato (com ganchos e abrindo junto com o Claude), instale o plugin: `claude plugin marketplace add Thathaqqq/mascote-flutuante` e `claude plugin install mascote-flutuante@mascote-flutuante`.

## O que a pessoa pode pedir

Todos os comandos usam `python "<pasta da skill>/scripts/iniciar.py" ...`.

| Pedido | Comando |
|---|---|
| Ligar | `iniciar.py vigia` |
| Desligar | `iniciar.py parar` |
| Trocar personagem | `iniciar.py config personagem <Nome>` |
| Modo mini | `iniciar.py config mini sim` (ou `nao`) |
| Seguir o cursor | `iniciar.py config seguir sim` (ou `nao`) |
| Aviso sonoro | `iniciar.py config som sim` (ou `nao`) |
| Pousar na janela ativa | `iniciar.py config pousar sim` (ou `nao`) |

Ligue sempre com `iniciar.py vigia` (e não só `iniciar.py`): é o que faz o mascote ler o histórico.

Sem pedido específico (só "/mascote-flutuante"): ligue o mascote com `iniciar.py vigia` e diga em uma linha o que dá para mudar.

Personagens prontos: Frida (pug preta, ilustrada), Borboleta Azul (3D), Borboleta, Gato, Robô, Fantasma (arquivos em `<pasta da skill>/personagens`).

Requisito para os personagens 3D e para as bordas suaves: Pillow (`python -m pip install pillow`). Sem ele o mascote funciona, mas só com os personagens de quadradinhos. Se faltar, pergunte à pessoa antes de instalar.

## A Frida

Pug preta ilustrada no estilo de desenho animado, animada como um fantoche: cada parte se mexe no próprio ponto, sem esticar a imagem. Fica parada a maior parte do tempo: pisca, balança uma orelha e o rabo, inclina a cabeça e espirra de vez em quando. Só dá sinal: late quando o Claude precisa de você, dá a pata quando o trabalho fica pronto para revisar e fica de olhos meio fechados quando algo trava. Para usar: `iniciar.py config personagem Frida`.

{{COMUM}}
## Como o mascote funciona (para explicar se perguntarem)

- Balão e cor: azul trabalhando, amarelo precisa de você, verde pronto para revisar, vermelho algo travou.
- Clique no mascote: vai para a conversa que está chamando; cada clique leva à próxima. Clique no número: lista de conversas. Botão direito: menu.
- Chat rápido: barra embaixo do mascote, aparece com o mouse em cima ou Ctrl+Alt+Espaço; usa o comando `claude` do Claude Code.
- Os olhos seguem o cursor; quando você clica em qualquer lugar, os de quadradinhos pulam e os de foto sorriem; ele diz "Oi!" quando o cursor passa por cima. Com "Seguir o cursor", ele anda atrás do mouse.
- Os estados ficam em `~/.claude/mascote/estado`, no próprio computador.
