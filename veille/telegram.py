"""Telegram : un seul bot, en-têtes par type, découpage sûr, repli texte brut (spec § 8.1)."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field

from veille.journal import Journal

LIMITE_TELEGRAM = 4096
RESERVE_ENTETE = 80  # place gardée pour « emoji <b>Titre</b> (n/N) »
API = "https://api.telegram.org"

ENTETES = {
    "alerte": "🔔 Alerte",
    "matin": "🌅 Synthèse matin",
    "soir": "🌆 Synthèse soir",
    "marches": "📈 Marchés",
    "awb": "🏦 AWB",
    "sante": "⚠️ Santé",
    "test": "🧪 Test",
}

_ATOME_HTML = re.compile(r"<[^>]*>|&[#a-zA-Z0-9]+;|\s+|[^\s<&]+|[<&]")
_ATOME_BRUT = re.compile(r"\s+|\S+")
_BALISE = re.compile(r"<(/?)([a-zA-Z][\w-]*)")
_PART_MIN = 0.3  # une coupure n'est « bonne » que si le message est déjà rempli à 30 %


class ErreurTelegram(Exception):
    pass


def echapper(texte: str) -> str:
    return html.escape(texte, quote=False)


# --- découpage --------------------------------------------------------------------------


def _maj_pile(pile: list, atome: str) -> list:
    if not atome.startswith("<"):
        return pile
    m = _BALISE.match(atome)
    if not m or atome.endswith("/>"):
        return pile
    nom = m.group(2).lower()
    if m.group(1):  # fermeture
        return pile[:-1] if pile and pile[-1][1] == nom else pile
    return [*pile, (atome, nom)]


def _fermetures(pile: list) -> str:
    return "".join(f"</{nom}>" for _, nom in reversed(pile))


def _niveau_coupure(atome: str) -> int | None:
    if not atome.isspace():
        return None
    if atome.count("\n") >= 2:
        return 0  # fin de paragraphe
    return 1 if "\n" in atome else 2  # fin de ligne, sinon espace


def decouper(texte: str, limite: int = LIMITE_TELEGRAM, *, html_actif: bool = True) -> list[str]:
    """Découpe en morceaux de `limite` caractères au plus, sur frontière de paragraphe si possible.

    Mode HTML : jamais au milieu d'une balise ou d'une entité ; une balise ouverte à la coupure
    est fermée en fin de morceau puis rouverte au début du suivant.
    """
    if len(texte) <= limite:
        return [texte]
    atomes = _ATOME_HTML.findall(texte) if html_actif else _ATOME_BRUT.findall(texte)
    morceaux: list[str] = []
    reouvrir: list = []
    i = 0
    while i < len(atomes):
        pile = list(reouvrir)
        courant = [t for t, _ in reouvrir]
        longueur = sum(len(t) for t in courant)
        bonnes: dict[int, tuple] = {}
        toutes: dict[int, tuple] = {}
        j = i
        deborde = False
        while j < len(atomes):
            atome = atomes[j]
            nouvelle = _maj_pile(pile, atome) if html_actif else pile
            if longueur + len(atome) + len(_fermetures(nouvelle)) > limite:
                deborde = True
                break
            courant.append(atome)
            pile = nouvelle
            longueur += len(atome)
            j += 1
            niveau = _niveau_coupure(atome)
            if niveau is not None:
                point = (j, list(pile), len(courant))
                toutes[niveau] = point
                if longueur >= _PART_MIN * limite:
                    bonnes[niveau] = point
        if not deborde:
            _ajouter(morceaux, courant, pile)
            break
        choix = next((d[n] for d in (bonnes, toutes) for n in (0, 1, 2) if n in d), None)
        if choix is not None:
            suite, pile_coupure, nb = choix
            _ajouter(morceaux, courant[:nb], pile_coupure)
            reouvrir, i = pile_coupure, suite
        elif j > i:  # aucune frontière : on coupe entre deux atomes
            _ajouter(morceaux, courant, pile)
            reouvrir, i = pile, j
        else:  # un seul atome dépasse : coupe de force au milieu du mot
            place = limite - longueur - len(_fermetures(pile))
            if place <= 0 or atomes[i].startswith("<"):
                raise ValueError("balise plus longue que la limite : découpage impossible")
            atomes[i : i + 1] = [atomes[i][:place], atomes[i][place:]]
    return morceaux


def _ajouter(morceaux: list[str], courant: list[str], pile: list) -> None:
    corps = "".join(courant).rstrip()
    if corps.strip():
        morceaux.append(corps + _fermetures(pile))


# --- texte brut -------------------------------------------------------------------------

_LIEN = re.compile(r"""<a\s+[^>]*href=["']([^"']+)["'][^>]*>(.*?)</a>""", re.S | re.I)
_TOUTE_BALISE = re.compile(r"<[^>]+>")


def html_vers_texte(contenu: str) -> str:
    sans_liens = _LIEN.sub(lambda m: f"{m.group(2)} ({m.group(1)})", contenu)
    return html.unescape(_TOUTE_BALISE.sub("", sans_liens))


# --- envoi ------------------------------------------------------------------------------


def entete(type_: str, partie: int = 1, total: int = 1, *, html_actif: bool = True) -> str:
    emoji, _, titre = ENTETES[type_].partition(" ")
    titre = f"<b>{titre}</b>" if html_actif else titre
    suffixe = f" ({partie}/{total})" if total > 1 else ""
    return f"{emoji} {titre}{suffixe}"


@dataclass
class ResultatEnvoi:
    parties: int = 0
    repli_texte: bool = False
    ids: list[int] = field(default_factory=list)


def _refus_de_format(statut: int, description: str) -> bool:
    d = description.lower()
    return statut == 400 and any(
        mot in d for mot in ("parse entities", "find end tag", "start tag", "end tag")
    )


def _poster(client, token: str, charge: dict, journal: Journal | None):
    reponse = client.post(f"{API}/bot{token}/sendMessage", json=charge)
    try:
        corps = reponse.json()
    except ValueError:
        corps = {}
    if reponse.status_code == 200 and corps.get("ok"):
        return corps["result"]["message_id"], None
    description = corps.get("description") or (reponse.text or "")[:200]
    return None, (reponse.status_code, description)


def envoyer(
    type_: str,
    corps: str,
    *,
    token: str,
    chat_id: str,
    client,
    journal: Journal | None = None,
    silencieux: bool = False,
) -> ResultatEnvoi:
    """Envoie `corps` (HTML Telegram) avec l'en-tête du type ; découpe si nécessaire."""
    if type_ not in ENTETES:
        raise ValueError(f"type de message inconnu : {type_}")
    masquer = journal.masquer if journal else (lambda t: t)
    morceaux = decouper(corps, LIMITE_TELEGRAM - RESERVE_ENTETE)
    total = len(morceaux)
    resultat = ResultatEnvoi(parties=total)

    for n, morceau in enumerate(morceaux, 1):
        base = {
            "chat_id": chat_id,
            "link_preview_options": {"is_disabled": True},
            "disable_notification": silencieux,
        }
        texte = f"{entete(type_, n, total)}\n\n{morceau}"
        id_, erreur = _poster(client, token, {**base, "text": texte, "parse_mode": "HTML"}, journal)
        if erreur and _refus_de_format(*erreur):
            if journal:
                journal.avertir("telegram_repli_texte", erreur[1], partie=f"{n}/{total}")
            resultat.repli_texte = True
            brut = f"{entete(type_, n, total, html_actif=False)}\n\n{html_vers_texte(morceau)}"
            id_ = None
            for sous in decouper(brut, LIMITE_TELEGRAM, html_actif=False):
                id_, erreur = _poster(client, token, {**base, "text": sous}, journal)
                if erreur:
                    break
        if erreur:
            raise ErreurTelegram(masquer(f"Telegram HTTP {erreur[0]} : {erreur[1]}"))
        resultat.ids.append(id_)
    return resultat
