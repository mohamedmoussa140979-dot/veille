"""Critères A9 (aucune donnée sur main) et A10 (aucun secret ni e-mail dans les fichiers suivis)."""

import re
import subprocess
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent


def fichiers_suivis() -> list[str]:
    try:
        p = subprocess.run(
            ["git", "ls-files", "-z"], cwd=RACINE, capture_output=True, check=True, text=True
        )
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("pas de dépôt git (archive ?)")
    return [f for f in p.stdout.split("\0") if f]


# --- A9 : aucune donnée sur main --------------------------------------------------------

RACINES_AUTORISEES = {
    ".github", ".gitattributes", ".gitignore", "README.md", "config", "docs", "pyproject.toml",
    "requirements-dev.txt", "requirements.txt", "schema", "tests", "veille",
}  # fmt: skip
DOSSIERS_DE_DONNEES = ("state/", "articles/", "editions/", "sante/", "archive/")
TAILLE_MAX = 300_000  # un fichier de code ou de configuration ne pèse pas 300 Ko


def test_a9_rien_de_donnees_sur_main():
    for f in fichiers_suivis():
        racine = f.split("/")[0]
        assert racine in RACINES_AUTORISEES, f"fichier hors structure de code : {f}"
        assert not f.startswith(DOSSIERS_DE_DONNEES), f"donnée suivie sur main : {f}"
        assert not f.endswith((".jsonl", ".ndjson")), f"fichier de données suivi : {f}"
        assert (RACINE / f).stat().st_size < TAILLE_MAX, f"fichier trop gros pour du code : {f}"


# --- A10 : aucun secret, e-mail ou identifiant personnel --------------------------------

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
EMAILS_AUTORISES = re.compile(r"@users\.noreply\.github\.com$|^noreply@anthropic\.com$")
MOTIFS_SECRETS = {
    "clé Google": re.compile(r"AIza[0-9A-Za-z_-]{35}"),
    "clé Anthropic": re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
    "jeton Telegram": re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b"),
    "jeton GitHub": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,})"),
    "clé privée": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "topic ntfy": re.compile(r"ntfy\.sh/[\w-]+"),
    "chat id Telegram en clair": re.compile(r"TG_CHAT_ID\s*[:=]\s*['\"]?-?\d{6,}"),
}


def analyser(texte: str) -> list[str]:
    trouvailles = []
    for m in EMAIL.finditer(texte):
        if not EMAILS_AUTORISES.search(m.group(0)):
            trouvailles.append(f"e-mail : {m.group(0)}")
    for nom, motif in MOTIFS_SECRETS.items():
        if motif.search(texte):
            trouvailles.append(nom)
    return trouvailles


def test_a10_le_scanner_detecte_bien_ce_qu_il_doit_detecter():
    assert analyser("contact : prenom.nom@gmail.com")
    assert analyser("AIza" + "A" * 35)
    assert analyser("sk-ant-" + "a" * 30)
    assert analyser("123456789:" + "A" * 35)
    assert analyser("ghp_" + "a" * 36)
    assert analyser("curl https://ntfy.sh/mon-topic-1234")
    assert analyser("TG_CHAT_ID: 123456789")
    assert analyser("-----BEGIN PRIVATE KEY-----")


def test_a10_le_scanner_laisse_passer_le_legitime():
    assert not analyser("12345+utilisateur@users.noreply.github.com")
    assert not analyser("Co-Authored-By: Claude <noreply@anthropic.com>")
    assert not analyser("secrets.TG_CHAT_ID et ${{ secrets.GEMINI_API_KEY }}")
    assert not analyser("git -c user.email=t@t commit")


def test_a10_aucun_secret_ni_email_dans_les_fichiers_suivis():
    problemes = []
    for f in fichiers_suivis():
        texte = (RACINE / f).read_text(encoding="utf-8", errors="ignore")
        problemes += [f"{f} : {t}" for t in analyser(texte)]
    assert not problemes, "\n".join(problemes)
