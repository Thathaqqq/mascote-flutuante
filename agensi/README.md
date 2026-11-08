# Mascote Flutuante (skill)

A floating desktop mascot that shows what Claude Code is doing: **working**, **needs you** or **done**. It sits on top of your windows, follows the cursor with its eyes, jumps when you click and has a quick chat bar. The mascot's texts are in Portuguese.

Meet **Frida**, a black pug in 3D. Her big eyes follow your cursor, she tilts her head when she's curious and her ears bounce when she jumps. She wags her tail and sticks her tongue out when your work is ready. While Claude works, she reads from side to side. When Claude needs you, she jumps. Other characters: a 3D blue morpho butterfly, pixel characters (Clawd, cat, robot, ghost), and your own from a photo of your pet.

## Install

1. Unzip `mascote-flutuante` into your agent's skills folder (Claude Code: `~/.claude/skills/`).
2. Install Python 3 and Pillow: `python -m pip install pillow` (Mac: `python3 -m pip install pillow`).
3. In Claude Code, type `/mascote-flutuante` (or "liga o mascote").

## How it knows what Claude is doing

This is the skill version, without hooks. The mascot reads the end of Claude Code's conversation history **on your own computer** (`~/.claude/projects`) and works out the state:

- *Working* and *done*: reliable.
- *Needs you*: exact when Claude asks you a question. When Claude is waiting for a permission, it's a guess: a tool with no result after 15 seconds. A long-running command may show up as "needs you".
- Nothing leaves your computer and there's no network access. It keeps only the first 120 characters of each conversation's last request, to show in the list.
- Status tracking works with Claude Code. In other agents the mascot opens and its commands work, but it doesn't follow their work.

For exact states and auto-start with Claude, use the free plugin version (with hooks): `claude plugin marketplace add Thathaqqq/mascote-flutuante`, then `claude plugin install mascote-flutuante@mascote-flutuante`.

Windows and Mac. Open source (MIT): https://github.com/Thathaqqq/mascote-flutuante

---

**Em português:** mascote que mostra o que o Claude Code está fazendo, com a Frida, uma pug preta em 3D. Descompacte em `~/.claude/skills/`, instale o Pillow e digite `/mascote-flutuante`. Esta versão lê o histórico das conversas no próprio computador. O aviso "precisa de você" é um palpite quando o Claude espera uma permissão. Para o estado exato, use o plugin (com ganchos).
