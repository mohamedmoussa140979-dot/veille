"""État sur la branche `data` : dépôts Git locaux réels (aucun réseau)."""

import json
import subprocess
import threading

import pytest

from veille.etat import ErreurEtat, EtatGit
from veille.journal import Journal


def git(*args, cwd):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def distant(tmp_path):
    """Dépôt nu servant de « GitHub », avec une branche main (code) mais pas de branche data."""
    nu = tmp_path / "distant.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(nu)], check=True)
    travail = tmp_path / "amorce"
    subprocess.run(["git", "init", "-q", "-b", "main", str(travail)], check=True)
    (travail / "code.py").write_text("print('code')\n")
    git("add", ".", cwd=travail)
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "code", cwd=travail)
    git("push", "-q", str(nu), "main", cwd=travail)
    return nu


def etat(distant, tmp_path, nom, **kw):
    return EtatGit(
        tmp_path / nom,
        str(distant),
        journal=Journal(sortie=lambda _: None),
        sleep=lambda _: None,
        **kw,
    ).ouvrir()


def test_creation_de_la_branche_data_si_absente(distant, tmp_path):
    e = etat(distant, tmp_path, "a")
    assert git("branch", "--list", "data", cwd=distant) != ""
    # la branche data est orpheline : elle ne contient rien du code de main
    assert git("ls-tree", "-r", "--name-only", "data", cwd=distant).split() == [".gitkeep"]
    assert e.lire("n_existe_pas.json") is None


def test_ecriture_puis_lecture_depuis_un_autre_clone(distant, tmp_path):
    a = etat(distant, tmp_path, "a")
    a.modifier_json("state/vus.json", lambda d: {**d, "bct": ["https://x.tn/1"]}, defaut={})
    b = etat(distant, tmp_path, "b")
    assert b.lire_json("state/vus.json") == {"bct": ["https://x.tn/1"]}


def test_pas_de_commit_vide_quand_rien_ne_change(distant, tmp_path):
    a = etat(distant, tmp_path, "a")
    a.modifier_json("state/x.json", lambda d: {"v": 1}, defaut={})
    avant = git("rev-list", "--count", "data", cwd=distant)
    assert a.modifier_json("state/x.json", lambda d: {"v": 1}, defaut={}) is False
    assert git("rev-list", "--count", "data", cwd=distant) == avant


def test_ajout_de_lignes_jsonl(distant, tmp_path):
    a = etat(distant, tmp_path, "a")
    a.ajouter_lignes("articles/2026-11-14.jsonl", ['{"id": 1}', '{"id": 2}'])
    a.ajouter_lignes("articles/2026-11-14.jsonl", ['{"id": 3}'])
    assert a.lire("articles/2026-11-14.jsonl").splitlines() == [
        '{"id": 1}',
        '{"id": 2}',
        '{"id": 3}',
    ]


def test_conflit_reprise_sur_contenu_frais(distant, tmp_path):
    """A lit, B pousse entre-temps : la poussée de A est refusée puis rejouée sur l'état de B."""
    a = etat(distant, tmp_path, "a")
    b = etat(distant, tmp_path, "b")
    appels = []

    def fonction_a(tx):
        appels.append(1)
        compteur = json.loads(tx.lire("c.json", "0"))
        if len(appels) == 1:  # entre la lecture et la poussée de A, B écrit
            b.modifier_json("c.json", lambda _: 10, defaut=0)
        tx.ecrire("c.json", json.dumps(compteur + 1))

    a.transaction("incrément de A", fonction_a)
    assert len(appels) == 2  # rejouée une fois
    assert a.lire_json("c.json") == 11  # ni la valeur de B ni celle de A n'est perdue


def test_a9_deux_taches_simultanees_sans_perte(distant, tmp_path):
    """Deux tâches écrivent en même temps dans le même fichier et dans des fichiers distincts."""
    etat(distant, tmp_path, "amorce")  # crée la branche data une fois
    erreurs = []

    def tache(nom, fois):
        try:
            e = etat(distant, tmp_path, nom, essais=30)
            for k in range(fois):
                e.modifier_json("state/compteur.json", lambda d: {"n": d["n"] + 1}, defaut={"n": 0})
                e.ajouter_lignes(f"articles/{nom}.jsonl", [json.dumps({"k": k})])
        except Exception as exc:  # pragma: no cover - remonté par l'assertion
            erreurs.append(exc)

    fils = [threading.Thread(target=tache, args=(n, 4)) for n in ("t1", "t2")]
    [f.start() for f in fils]
    [f.join() for f in fils]
    assert not erreurs
    lecteur = etat(distant, tmp_path, "lecteur")
    assert lecteur.lire_json("state/compteur.json") == {"n": 8}
    for nom in ("t1", "t2"):
        assert len(lecteur.lire(f"articles/{nom}.jsonl").splitlines()) == 4


def test_echec_definitif_apres_les_essais(distant, tmp_path):
    a = etat(distant, tmp_path, "a", essais=2)
    # on rend la poussée impossible : le dépôt distant refuse toute mise à jour
    hook = distant / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\necho refus >&2\nexit 1\n")
    hook.chmod(0o755)
    with pytest.raises(ErreurEtat):
        a.ajouter_lignes("x.jsonl", ["1"])


def test_les_chemins_hors_du_depot_sont_refuses(distant, tmp_path):
    a = etat(distant, tmp_path, "a")
    with pytest.raises(ValueError):
        a.transaction("évasion", lambda tx: tx.ecrire("../dehors.txt", "x"))
    with pytest.raises(ValueError):
        a.transaction("évasion", lambda tx: tx.ecrire("/absolu.txt", "x"))


def test_suppression_de_fichier(distant, tmp_path):
    a = etat(distant, tmp_path, "a")
    a.ajouter_lignes("tmp.txt", ["x"])
    a.transaction("ménage", lambda tx: tx.supprimer("tmp.txt"))
    assert a.lire("tmp.txt") is None
