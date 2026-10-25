---
name: mascote
description: Liga, desliga e configura o mascote flutuante do Claude (personagem, modo mini, seguir o cursor, abrir junto com o Claude) e cria personagens personalizados a partir de uma descrição. Use quando a pessoa disser "mascote", "pet", "ligar/desligar o mascote", "trocar o personagem", "criar meu personagem", "quero um mascote de gato roxo" ou digitar /mascote.
---

# Mascote do Claude

O mascote é uma janelinha que fica por cima das outras e mostra o que o Claude está fazendo. Os scripts estão em `${CLAUDE_PLUGIN_ROOT}/scripts`. Funciona no Windows com Python 3 instalado.

Todos os comandos abaixo usam `python "${CLAUDE_PLUGIN_ROOT}/scripts/iniciar.py" ...`.

## O que a pessoa pode pedir

| Pedido | Comando |
|---|---|
| Ligar | `iniciar.py` |
| Desligar | `iniciar.py parar` |
| Trocar personagem | `iniciar.py config personagem <Nome>` |
| Modo mini | `iniciar.py config mini sim` (ou `nao`) |
| Seguir o cursor | `iniciar.py config seguir sim` (ou `nao`) |
| Abrir junto com o Claude | `iniciar.py config automatico sim` (ou `nao`) |

Personagens prontos: Borboleta IBA (3D), Clawd, Borboleta, Gato, Robô, Fantasma (arquivos em `${CLAUDE_PLUGIN_ROOT}/personagens`).

Requisito para o 3D e para as bordas suaves: Pillow (`python -m pip install pillow`). Sem ele o mascote funciona, mas só com os personagens de quadradinhos. Se faltar, pergunte à pessoa antes de instalar.

## Criar uma borboleta 3D a partir de uma foto

Serve para qualquer borboleta fotografada de cima, de asas abertas.

1. Peça a foto (PNG com fundo transparente; se vier com fundo, recorte antes e mostre o resultado).
2. Copie a foto para `~/.claude/mascote/personagens/` e grave ao lado um `<nome>.json`:

```json
{"nome": "Minha borboleta", "tipo": "borboleta3d", "imagem": "minha-borboleta.png", "centro": 0.5}
```

`centro` é onde fica o corpo na largura da foto (0.5 = no meio). As asas da foto ganham volume e batida; o corpo e as antenas da foto são trocados por um modelo 3D.
3. `iniciar.py validar "<arquivo .json>"` e depois `iniciar.py config personagem "<nome>"`.

Sem pedido específico (só "/mascote"): ligue o mascote e diga em uma linha o que dá para mudar.

## Criar um personagem personalizado

1. Pergunte só o que faltar: como ele é (bicho, objeto, cores). Uma pergunta por vez.
2. Desenhe em quadradinhos e grave em `~/.claude/mascote/personagens/<nome-sem-espaco>.json`:

```json
{
  "nome": "Gato Roxo",
  "cores": {"X": "#8B5CF6", "E": "#111111", "N": "#F9A8D4"},
  "mapa": [
    ".X........X.",
    ".XX......XX.",
    ".XXXXXXXXXX.",
    ".XEXXXXXXEX.",
    ".XXXXNNXXXX.",
    "..XXXXXXXX..",
    ".XXXXXXXXXX.",
    ".XXXXXXXXXX.",
    ".X.X....X.X."
  ]
}
```

Regras do desenho:
- Cada texto de `mapa` é uma linha; cada letra é um quadradinho. `.` é vazio.
- Tamanho ideal 12 colunas x 9 linhas; no máximo 16 x 16. Todas as linhas com o mesmo tamanho, desenho simétrico.
- `X` é o corpo (usado também quando o personagem pisca). `E` são os olhos: eles acompanham o cursor, então deixe um quadradinho de corpo em volta.
- `B` não encolhe na animação (bom para o meio do corpo, como o tronco da borboleta).
- Outras letras são livres; toda letra usada precisa de cor em `cores`, no formato `#RRGGBB`.
- Evite cor muito escura no corpo inteiro (some em tela escura) e o preto puro `#010203` (é a cor de fundo transparente).

3. Confira: `iniciar.py validar "<arquivo>"`. Corrija até dar "Personagem OK."
4. Aplique: `iniciar.py config personagem "<nome>"` (o mascote recarrega sozinho).
5. Diga à pessoa que ele já aparece no menu do botão direito, em Personagem.

## Como o mascote funciona (para explicar se perguntarem)

- Balão e cor: azul trabalhando, amarelo precisa de você, verde pronto para revisar, vermelho algo travou.
- Clique no mascote: abre o Claude. Clique no número: lista de conversas. Botão direito: menu.
- Chat rápido: pergunta curta respondida ali mesmo, sem abrir o Claude (usa o comando `claude` do Claude Code).
- Os olhos seguem o cursor, ele pula quando você clica em qualquer lugar e diz "Oi!" quando o cursor passa por cima. Com "Seguir o cursor", ele anda atrás do mouse.
- O estado vem dos ganchos do plugin, gravados em `~/.claude/mascote/estado`. Só guarda o começo do último pedido de cada conversa, no próprio computador.
