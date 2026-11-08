# Mascote Flutuante (skill)

A floating desktop mascot that shows what Claude Code is doing: **working**, **needs you** or **done**. It sits on top of your windows, reacts to your cursor, jumps when you click and has a quick chat bar. The mascot's texts are in Portuguese.

Meet **Frida**, a black pug illustrated in an animated-film style. She gets volume, turns to your cursor's side, tilts her head when she's idle and curious, breathes and jumps when you click. While Claude works, she hops. When Claude needs you, she keeps jumping. When something breaks, she slumps with her head down. When your work is ready, she breaks into a big smile for a few seconds. She also smiles when you hover over her or click; the rest of the time she keeps a calm face. Other characters: a 3D blue morpho butterfly, pixel characters (Clawd, cat, robot, ghost), and your own from a photo of your pet.

## Install

1. Unzip `mascote-flutuante` into your agent's skills folder (Claude Code: `~/.claude/skills/`).
2. Install Python 3 and Pillow: `python -m pip install pillow` (Mac: `python3 -m pip install pillow`).
3. In Claude Code, type `/mascote-flutuante` (or "liga o mascote").

## How it knows what Claude is doing

This is the skill version, without hooks. The mascot reads the end of Claude Code's conversation history **on your own computer** (`~/.claude/projects`) and works out the state:

- *Working* and *done*: reliable.
- *Needs you*: exact when Claude asks you a question. When Claude is waiting for a permission, it's a guess: a tool with no result after 15 seconds. A long-running command may show up as "needs you".
- The mascot itself makes no network calls. It reads the history on your computer and keeps one small file per conversation in `~/.claude/mascote/estado`, with the state, the project folder and the first 120 characters of the last request. The quick chat is the exception: it sends your question through your own Claude Code.
- A guessed "needs you" plays no sound.
- If the plugin version is also installed, its hooks take over and history reading pauses.
- Status tracking works with Claude Code. In other agents the mascot opens and its commands work, but it doesn't follow their work.

For exact states and auto-start with Claude, use the free plugin version (with hooks): `claude plugin marketplace add Thathaqqq/mascote-flutuante`, then `claude plugin install mascote-flutuante@mascote-flutuante`.

Windows and Mac. Open source (MIT): https://github.com/Thathaqqq/mascote-flutuante

---

**Em português:** mascote que mostra o que o Claude Code está fazendo, com a Frida, uma pug preta ilustrada. Descompacte em `~/.claude/skills/`, instale o Pillow e digite `/mascote-flutuante`. Esta versão lê o histórico das conversas no próprio computador. O aviso "precisa de você" é um palpite quando o Claude espera uma permissão (e não toca som). Para o estado exato, use o plugin (com ganchos).
