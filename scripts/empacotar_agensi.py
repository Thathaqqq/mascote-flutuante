"""Monta o .zip da versão skill (para a Agensi e outras lojas de skills).

  python scripts/empacotar_agensi.py

Gera dist/mascote-flutuante-skill-<versão>.zip com uma pasta mascote-flutuante/
contendo SKILL.md, scripts, personagens, README e licença. O SKILL.md sai de
agensi/SKILL.modelo.md, com as partes comuns copiadas da skill do plugin, para
as duas versões não ficarem diferentes. Fica de fora o gancho (registrar_estado.py):
na skill, quem acompanha as conversas é o vigia.
"""
import json
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
FORA = {"registrar_estado.py", "empacotar_agensi.py"}
TIPOS = {".py", ".pyw", ".json", ".png"}  # só o que o mascote usa (nada de arquivos soltos do editor)


def skill_md():
    plugin = (RAIZ / "skills" / "mascote" / "SKILL.md").read_text(encoding="utf-8")
    corpo = plugin.split("---", 2)[2]
    ini = corpo.index("## Criar um personagem com a foto")
    fim = corpo.index("## Como o mascote funciona")
    comum = corpo[ini:fim].replace("${CLAUDE_PLUGIN_ROOT}", "<pasta da skill>")
    modelo = (RAIZ / "agensi" / "SKILL.modelo.md").read_text(encoding="utf-8")
    texto = modelo.replace("{{COMUM}}", comum)
    if "CLAUDE_PLUGIN_ROOT" in texto:
        raise SystemExit("O SKILL.md da skill ainda cita CLAUDE_PLUGIN_ROOT")
    return texto


def main():
    versao = json.loads((RAIZ / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
    destino = RAIZ / "dist" / f"mascote-flutuante-skill-{versao}.zip"
    destino.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("mascote-flutuante/SKILL.md", skill_md())
        z.write(RAIZ / "agensi" / "README.md", "mascote-flutuante/README.md")
        z.write(RAIZ / "LICENSE", "mascote-flutuante/LICENSE")
        for pasta in ("scripts", "personagens"):
            for arq in sorted((RAIZ / pasta).iterdir()):
                if arq.is_file() and arq.name not in FORA and arq.suffix in TIPOS:
                    z.write(arq, f"mascote-flutuante/{pasta}/{arq.name}")
    print(f"Pacote criado: {destino}")


if __name__ == "__main__":
    main()
