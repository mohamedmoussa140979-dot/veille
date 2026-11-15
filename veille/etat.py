"""État sur la branche `data` (spec § 9) : lecture, écriture par transaction, reprise sur conflit.

Principe : une transaction resynchronise le clone sur la branche distante, applique la
modification **sur le contenu frais**, commite, pousse. Si la poussée est refusée (une autre
tâche a écrit entre-temps), on recommence depuis le contenu frais : aucune écriture perdue.
"""

from __future__ import annotations

import base64
import copy
import json
import os
import random
import subprocess
import time
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from veille.journal import Journal


class ErreurEtat(Exception):
    pass


def _chemin_sur(chemin: str) -> PurePosixPath:
    p = PurePosixPath(chemin)
    if not chemin or p.is_absolute() or ".." in p.parts or p.parts[0] == ".git":
        raise ValueError(f"chemin d'état invalide : {chemin!r}")
    return p


class Transaction:
    """Modifications en attente ; rien n'est écrit sur disque avant `appliquer`."""

    def __init__(self, racine: Path):
        self._racine = racine
        self._ecritures: dict[str, str | None] = {}

    def lire(self, chemin: str, defaut: str | None = None) -> str | None:
        _chemin_sur(chemin)
        if chemin in self._ecritures:
            valeur = self._ecritures[chemin]
            return defaut if valeur is None else valeur
        fichier = self._racine / chemin
        return fichier.read_text(encoding="utf-8") if fichier.is_file() else defaut

    def ecrire(self, chemin: str, contenu: str) -> None:
        _chemin_sur(chemin)
        self._ecritures[chemin] = contenu

    def supprimer(self, chemin: str) -> None:
        _chemin_sur(chemin)
        self._ecritures[chemin] = None

    def ajouter(self, chemin: str, lignes: list[str]) -> None:
        existant = self.lire(chemin, "") or ""
        if existant and not existant.endswith("\n"):
            existant += "\n"
        self.ecrire(chemin, existant + "".join(ligne.rstrip("\n") + "\n" for ligne in lignes))

    def lister(self, dossier: str) -> list[str]:
        """Chemins des fichiers d'un dossier de la branche, écritures en attente comprises."""
        _chemin_sur(dossier)
        base = self._racine / dossier
        noms = (
            {f"{dossier}/{f.name}" for f in base.glob("*") if f.is_file()}
            if base.is_dir()
            else set()
        )
        for chemin, contenu in self._ecritures.items():
            if chemin.startswith(dossier + "/"):
                noms.add(chemin) if contenu is not None else noms.discard(chemin)
        return sorted(noms)

    def appliquer(self) -> None:
        for chemin, contenu in self._ecritures.items():
            fichier = self._racine / chemin
            if contenu is None:
                fichier.unlink(missing_ok=True)
            else:
                fichier.parent.mkdir(parents=True, exist_ok=True)
                fichier.write_text(contenu, encoding="utf-8", newline="\n")


def env_auth_github(token: str) -> dict[str, str]:
    """Authentification HTTPS de git par en-tête (le jeton ne figure ni dans l'URL ni dans la ligne
    de commande)."""
    identifiants = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    return {
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader",
        "GIT_CONFIG_VALUE_0": f"AUTHORIZATION: basic {identifiants}",
    }


class EtatGit:
    def __init__(
        self,
        dossier: str | Path,
        remote: str,
        *,
        branche: str = "data",
        env_git: dict[str, str] | None = None,
        essais: int = 6,
        sleep: Callable[[float], None] = time.sleep,
        journal: Journal | None = None,
        auteur_nom: str = "veille-bot",
        auteur_email: str = "veille-bot@users.noreply.github.com",
    ):
        self.dossier = Path(dossier)
        self.remote = remote
        self.branche = branche
        self.essais = essais
        self._sleep = sleep
        self.journal = journal
        self._env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", **(env_git or {})}
        self._config = [
            "-c", "core.autocrlf=false",
            "-c", "commit.gpgsign=false",
            "-c", f"user.name={auteur_nom}",
            "-c", f"user.email={auteur_email}",
        ]  # fmt: skip

    @classmethod
    def depuis_environnement(
        cls, dossier: str | Path = "_data", journal: Journal | None = None, **kw
    ) -> EtatGit:
        """Dans GitHub Actions : dépôt courant, jeton du workflow (GITHUB_TOKEN)."""
        depot = os.environ["GITHUB_REPOSITORY"]
        jeton = os.environ["GITHUB_TOKEN"]
        env = env_auth_github(jeton)
        if journal:
            journal.enregistrer_secret(jeton)
            journal.enregistrer_secret(env["GIT_CONFIG_VALUE_0"].split()[-1])
        return cls(dossier, f"https://github.com/{depot}.git", env_git=env, journal=journal, **kw)

    # -- git ---------------------------------------------------------------------------

    def _git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        p = subprocess.run(
            ["git", *self._config, *args],
            cwd=self.dossier,
            env=self._env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if check and p.returncode != 0:
            raise ErreurEtat(self._masquer(f"git {' '.join(args)} : {p.stderr.strip()}"))
        return p

    def _masquer(self, texte: str) -> str:
        return self.journal.masquer(texte) if self.journal else texte

    def _branche_distante_existe(self) -> bool:
        p = self._git("ls-remote", "--heads", "origin", self.branche)
        return bool(p.stdout.strip())

    def _synchroniser(self) -> None:
        self._git("fetch", "-q", "--depth", "1", "origin", self.branche)
        self._git("checkout", "-q", "-B", self.branche, "FETCH_HEAD")
        self._git("reset", "-q", "--hard", "FETCH_HEAD")
        self._git("clean", "-fdq")

    def ouvrir(self) -> EtatGit:
        """Prépare le clone ; crée la branche `data` (orpheline) si elle n'existe pas encore."""
        self.dossier.mkdir(parents=True, exist_ok=True)
        if not (self.dossier / ".git").exists():
            self._git("init", "-q")
        if self._git("remote", check=False).stdout.split():
            self._git("remote", "set-url", "origin", self.remote)
        else:
            self._git("remote", "add", "origin", self.remote)
        if not self._branche_distante_existe():
            self._creer_branche()
        self._synchroniser()
        return self

    def _creer_branche(self) -> None:
        self._git("checkout", "-q", "--orphan", self.branche)
        self._git("rm", "-rfq", "--ignore-unmatch", ".", check=False)
        (self.dossier / ".gitkeep").write_text("", encoding="utf-8")
        self._git("add", ".gitkeep")
        self._git("commit", "-q", "-m", "data: initialisation de la branche d'état")
        p = self._git("push", "origin", f"{self.branche}:{self.branche}", check=False)
        if p.returncode != 0 and not self._branche_distante_existe():
            raise ErreurEtat(self._masquer(f"création de la branche impossible : {p.stderr}"))
        if self.journal:
            self.journal.info("etat_branche_creee", self.branche)

    # -- lecture -----------------------------------------------------------------------

    def lire(self, chemin: str, defaut: str | None = None) -> str | None:
        _chemin_sur(chemin)
        fichier = self.dossier / chemin
        return fichier.read_text(encoding="utf-8") if fichier.is_file() else defaut

    def lire_json(self, chemin: str, defaut: Any = None) -> Any:
        brut = self.lire(chemin)
        return json.loads(brut) if brut else copy.deepcopy(defaut)

    def synchroniser(self) -> EtatGit:
        """Relit la branche distante (à appeler avant une lecture si d'autres tâches ont écrit)."""
        self._synchroniser()
        return self

    def lister(self, dossier: str) -> list[str]:
        """Chemins des fichiers d'un dossier de l'état (ex. `editions/2026-11-17-matin.json`)."""
        _chemin_sur(dossier)
        base = self.dossier / dossier
        return (
            sorted(f"{dossier}/{f.name}" for f in base.glob("*") if f.is_file())
            if base.is_dir()
            else []
        )

    # -- écriture ----------------------------------------------------------------------

    def transaction(self, message: str, fonction: Callable[[Transaction], None]) -> bool:
        """Applique `fonction` sur un état frais, commite, pousse. False si rien ne change."""
        derniere_erreur = ""
        for tentative in range(self.essais):
            self._synchroniser()
            tx = Transaction(self.dossier)
            fonction(tx)
            tx.appliquer()
            self._git("add", "-A")
            if not self._git("status", "--porcelain").stdout.strip():
                return False
            self._git("commit", "-q", "-m", message)
            p = self._git("push", "origin", f"{self.branche}:{self.branche}", check=False)
            if p.returncode == 0:
                return True
            derniere_erreur = self._masquer(p.stderr.strip().splitlines()[-1] if p.stderr else "")
            if self.journal:
                self.journal.avertir(
                    "etat_conflit",
                    "poussée refusée, reprise",
                    essai=tentative + 1,
                    detail=derniere_erreur,
                )
            self._sleep(random.uniform(0, 0.3 * (tentative + 1)))
        raise ErreurEtat(f"poussée impossible après {self.essais} essais : {derniere_erreur}")

    def modifier_json(
        self,
        chemin: str,
        fonction: Callable[[Any], Any],
        *,
        defaut: Any,
        message: str | None = None,
    ) -> bool:
        def appliquer(tx: Transaction) -> None:
            brut = tx.lire(chemin)
            courant = json.loads(brut) if brut else copy.deepcopy(defaut)
            nouveau = fonction(courant)
            tx.ecrire(
                chemin,
                json.dumps(nouveau, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                + "\n",
            )

        return self.transaction(message or f"data: {chemin}", appliquer)

    def ajouter_lignes(self, chemin: str, lignes: list[str], message: str | None = None) -> bool:
        return self.transaction(message or f"data: {chemin}", lambda tx: tx.ajouter(chemin, lignes))


class EtatLocal:
    """État dans un dossier, sans Git : tests et essais à blanc (même interface qu'EtatGit)."""

    def __init__(self, dossier: str | Path):
        self.dossier = Path(dossier)
        self.dossier.mkdir(parents=True, exist_ok=True)

    def ouvrir(self) -> EtatLocal:
        return self

    def lister(self, dossier: str) -> list[str]:
        """Chemins des fichiers d'un dossier de l'état (ex. `editions/2026-11-17-matin.json`)."""
        _chemin_sur(dossier)
        base = self.dossier / dossier
        return (
            sorted(f"{dossier}/{f.name}" for f in base.glob("*") if f.is_file())
            if base.is_dir()
            else []
        )

    def synchroniser(self) -> EtatLocal:
        return self

    def lire(self, chemin: str, defaut: str | None = None) -> str | None:
        _chemin_sur(chemin)
        fichier = self.dossier / chemin
        return fichier.read_text(encoding="utf-8") if fichier.is_file() else defaut

    def lire_json(self, chemin: str, defaut: Any = None) -> Any:
        brut = self.lire(chemin)
        return json.loads(brut) if brut else copy.deepcopy(defaut)

    def transaction(self, message: str, fonction: Callable[[Transaction], None]) -> bool:
        tx = Transaction(self.dossier)
        fonction(tx)
        tx.appliquer()
        return True

    def modifier_json(self, chemin, fonction, *, defaut, message=None) -> bool:
        def appliquer(tx: Transaction) -> None:
            brut = tx.lire(chemin)
            nouveau = fonction(json.loads(brut) if brut else copy.deepcopy(defaut))
            tx.ecrire(chemin, json.dumps(nouveau, ensure_ascii=False, sort_keys=True) + "\n")

        return self.transaction(message or chemin, appliquer)

    def ajouter_lignes(self, chemin: str, lignes: list[str], message: str | None = None) -> bool:
        return self.transaction(message or chemin, lambda tx: tx.ajouter(chemin, lignes))
