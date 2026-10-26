# Mascote do Claude

Um bonequinho que fica num canto da tela, por cima das outras janelas, e mostra o que o Claude está fazendo enquanto você trabalha em outro programa.

| Balão | Cor | Quando |
|---|---|---|
| Trabalhando | azul | o Claude está executando um pedido |
| Precisa de você | amarelo | o Claude parou esperando uma permissão ou resposta |
| Pronto para revisar | verde | o Claude terminou |
| Algo travou | vermelho | a conversa parou com erro |

## O que ele faz

- Clique no mascote: vai direto para a conversa que está chamando (primeiro as que precisam de você, depois as travadas e as prontas). Clique de novo: vai para a próxima que está chamando. Sem nenhuma chamando, abre o Claude.
- Clique no número ao lado dele: lista das conversas, com o título, o estado de cada uma e o começo do último pedido. Clicar numa conversa abre aquela conversa no aplicativo do Claude (aba Code). Conversas do terminal abrem só o Claude.
- Botão direito: menu com chat rápido, modo mini, seguir o cursor, personagem e sair.
- Chat rápido: uma barra arredondada embaixo do mascote ("Iniciar novo chat"). Aparece ao passar o mouse nele ou com Ctrl+Alt+Espaço (no Mac, Control+Option+Espaço), de qualquer programa. As respostas aparecem em balões num cartão acima do mascote, e a conversa continua de uma pergunta para outra. O "+" começa uma conversa nova; Esc fecha.
- Os olhos acompanham o cursor do mouse; ele pula quando você clica em qualquer lugar e diz "Oi!" quando o cursor passa por cima.
- Seguir o cursor: ele anda atrás do mouse pela tela.
- Modo mini: fica pequeno, só com o número colorido.
- Aviso sonoro: um som discreto do sistema quando uma conversa precisa de você ou termina. Na lista de conversas, cada uma tem "Som ligado" ou "Sem som": clique para escolher só para aquela conversa. O "Aviso sonoro" do menu vale para as conversas que você não ajustou. Em "Som do aviso", no menu, você escolhe o som (Notificação, Mensagem, E-mail, Calendário, Sino, Ding, Carrilhão, Acorde, Tada, Toque, Proximidade ou Cutucada); ao escolher, ele toca para você ouvir. Em "Meu arquivo de som", use um som seu (WAV ou MP3).
- Pousar na janela ativa (só Windows por enquanto): ele senta na borda de cima da janela que você está usando e vai junto quando você troca de janela.
- Arraste para mudar de lugar; ele lembra onde ficou.

## Personagens

Prontos: Borboleta IBA (3D), Clawd, Borboleta, Gato, Robô e Fantasma.

A Borboleta IBA usa a foto da morpho-azul do logo do Instituto Borboleta Azul, com uso animado autorizado pela gestão do Instituto em 25/10/2026. As asas da foto ganham volume, curvatura e brilho conforme a luz; corpo e antenas são modelados em 3D. Ela reage ao cursor:

| O que o cursor faz | O que ela faz |
|---|---|
| Trabalhos acabaram | Pousa e fica parada, de asas abertas |
| Passa por cima | Abre bem as asas, com brilho |
| Muda de lado | Vira o corpo e as antenas para o cursor |
| Chega muito rápido | Se assusta e bate as asas forte |
| Asa vira de costas | Mostra o lado de baixo, marrom, como na morpho de verdade |
| Clica em qualquer lugar | Dá uma agitada |
| "Seguir o cursor" ligado | Voa atrás do mouse, inclinando nas curvas |

Também dá para transformar qualquer foto de borboleta (vista de cima, fundo transparente) numa borboleta 3D: peça "/mascote cria uma borboleta 3D com esta foto".

**Com a sua foto:** botão direito no mascote > Personagem > Criar personagem com foto... Escolha a foto (do seu cachorro, gato, de você) e dê um nome. Com fundo liso, o fundo sai sozinho; com fundo cheio de coisas, recorte antes no Paint do Windows (Remover plano de fundo). O personagem de foto vira para o lado do cursor, inclina a cabeça curioso, respira, pula quando você clica, fica pulando quando o Claude precisa de você e rebola quando ele termina.

Para criar um de quadradinhos, peça ao Claude: "/mascote cria um personagem de cachorro caramelo". Ele desenha, confere e já troca. Também dá para desenhar à mão: menu do botão direito, Personagem, Abrir pasta de personagens; lá há um exemplo comentado no arquivo `exemplo.json.txt`.

## Instalar

Funciona no Windows e no Mac. Precisa de Python 3 e do Claude Code (aplicativo Claude, aba Code, ou o terminal). Para a borboleta 3D, os personagens de foto e as bordas suaves, também do Pillow:

```bash
python -m pip install pillow
```

No Mac, use `python3 -m pip install pillow`. O Python do site python.org já vem com o Tk, que desenha a janela; no Python do Homebrew, instale também com `brew install python-tk`. Na primeira vez, o Mac pode pedir permissão de Monitoramento de Entrada (Ajustes do Sistema > Privacidade e Segurança) para o mascote perceber cliques e o atalho fora da janela dele.

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
- aviso sonoro
- pousar na janela ativa
- desligar

## Privacidade

Tudo fica no seu computador, em `~/.claude/mascote` (ou na pasta indicada por `CLAUDE_CONFIG_DIR`, se você usa mais de uma conta). O mascote guarda só o estado de cada conversa e os primeiros 120 caracteres do último pedido, para mostrar na lista. Conversas paradas há mais de 12 horas somem da lista. O chat rápido usa a sua própria conta do Claude.

## Desinstalar

```bash
claude plugin uninstall mascote-flutuante@mascote-flutuante
```

## Licença

MIT. Autora: Thaís Quaranta.
