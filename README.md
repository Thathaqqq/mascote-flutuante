# Mascote do Claude

Um bonequinho que fica num canto da tela, por cima das outras janelas, e mostra o que o Claude está fazendo enquanto você trabalha em outro programa.

| Balão | Cor | Quando |
|---|---|---|
| Trabalhando | azul | o Claude está executando um pedido |
| Precisa de você | amarelo | o Claude parou esperando uma permissão ou resposta |
| Pronto para revisar | verde | o Claude terminou |
| Algo travou | vermelho | a conversa parou com erro |

## O que ele faz

- Clique no mascote: abre a janela do Claude.
- Clique no número ao lado dele: lista das conversas, com o estado de cada uma e o começo do último pedido.
- Botão direito: menu com chat rápido, modo mini, seguir o cursor, personagem e sair.
- Chat rápido: uma caixinha para perguntas curtas, respondidas ali mesmo, sem abrir o Claude.
- Os olhos acompanham o cursor do mouse; ele pula quando você clica em qualquer lugar e diz "Oi!" quando o cursor passa por cima.
- Seguir o cursor: ele anda atrás do mouse pela tela.
- Modo mini: fica pequeno, só com o número colorido.
- Arraste para mudar de lugar; ele lembra onde ficou.

## Personagens

Prontos: Borboleta IBA (3D), Clawd, Borboleta, Gato, Robô e Fantasma.

A Borboleta IBA usa a foto da morpho-azul do logo do Instituto Borboleta Azul, com uso animado autorizado pela gestão do Instituto em 25/10/2026. As asas da foto ganham volume, curvatura e brilho conforme a luz; corpo e antenas são modelados em 3D. Ela reage ao cursor:

| O que o cursor faz | O que ela faz |
|---|---|
| Fica longe e parado | Pousa e abre e fecha as asas devagar |
| Chega perto | Acorda e bate as asas mais rápido |
| Passa por cima | Abre bem as asas, com brilho |
| Muda de lado | Vira o corpo e as antenas para o cursor |
| Chega muito rápido | Se assusta e bate as asas forte |
| Clica em qualquer lugar | Dá uma agitada |
| "Seguir o cursor" ligado | Voa atrás do mouse, inclinando nas curvas |

Também dá para transformar qualquer foto de borboleta (vista de cima, fundo transparente) numa borboleta 3D: peça "/mascote cria uma borboleta 3D com esta foto".

**Com a sua foto:** botão direito no mascote > Personagem > Criar personagem com foto... Escolha a foto (do seu cachorro, gato, de você) e dê um nome. Com fundo liso, o fundo sai sozinho; com fundo cheio de coisas, recorte antes no Paint do Windows (Remover plano de fundo). O personagem de foto vira para o lado do cursor, inclina a cabeça curioso, respira, pula quando você clica, fica pulando quando o Claude precisa de você e rebola quando ele termina.

Para criar um de quadradinhos, peça ao Claude: "/mascote cria um personagem de cachorro caramelo". Ele desenha, confere e já troca. Também dá para desenhar à mão: menu do botão direito, Personagem, Abrir pasta de personagens; lá há um exemplo comentado no arquivo `exemplo.json.txt`.

## Instalar

Precisa de Windows, Python 3 instalado e Claude Code (aplicativo Claude, aba Code, ou o terminal). Para a borboleta 3D e as bordas suaves, também do Pillow:

```bash
python -m pip install pillow
```

No terminal:

```bash
claude plugin marketplace add Thathaqqq/mascote-flutuante
```

```bash
claude plugin install mascote-flutuante@mascote-flutuante
```

Depois feche e abra o Claude. O mascote aparece sozinho ao abrir uma conversa. Para ligar à mão, digite `/mascote` em qualquer conversa.

## Configurar

Pelo menu do botão direito ou pedindo ao Claude com `/mascote`:

- trocar personagem
- modo mini
- seguir o cursor
- abrir junto com o Claude (liga e desliga o início automático)
- desligar

## Privacidade

Tudo fica no seu computador, em `~/.claude/mascote`. O mascote guarda só o estado de cada conversa e os primeiros 120 caracteres do último pedido, para mostrar na lista. Conversas paradas há mais de 12 horas somem da lista. O chat rápido usa a sua própria conta do Claude.

## Desinstalar

```bash
claude plugin uninstall mascote-flutuante@mascote-flutuante
```

## Licença

MIT. Autora: Thaís Quaranta.
