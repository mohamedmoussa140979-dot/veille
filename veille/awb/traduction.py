"""Traduction française des titres et résumés AWB : services gratuits non officiels (spec § 6.1).

Ordre : Google « gtx », puis Google « clients5 », puis MyMemory ; sinon le texte d'origine est
conservé (le lien « Lire en français » reste disponible). Le nombre de traductions réussies est
suivi pour le contrôle de santé dédié du lot V5.
"""

from __future__ import annotations

import os
from urllib.parse import quote_plus

from veille.http import ErreurReseau

MAX_CARACTERES = 450  # MyMemory limite la requête à 500 octets
ECHECS_MAX_GTX = 3  # après 3 échecs, gtx n'est plus essayé pendant ce passage


def extraire_clients5(data) -> str:
    """Texte traduit d'une réponse « clients5 » (formes : ["t"], [["t", "en"]], [[["t", "o"]]])."""
    if not isinstance(data, list) or not data:
        return ""
    premier = data[0]
    if isinstance(premier, str):
        return premier
    if isinstance(premier, list) and premier:
        if isinstance(premier[0], str):
            return "".join(x[0] for x in data if x and isinstance(x[0], str))
        if isinstance(premier[0], list):
            return "".join(seg[0] for seg in premier if seg and isinstance(seg[0], str))
    return ""


class Traducteur:
    def __init__(self, client, journal=None):
        self.client = client
        self.journal = journal
        self._cache: dict[tuple[str, str], str] = {}
        self._echecs_gtx = 0
        self.demandees = 0
        self.reussies = 0

    def _json(self, url: str):
        r = self.client.get(url, essais=1, timeout=12)
        if r.status_code != 200:
            raise ErreurReseau(f"HTTP {r.status_code}")
        return r.json()

    def _gtx(self, texte: str, source: str) -> str:
        data = self._json(
            "https://translate.googleapis.com/translate_a/single"
            f"?client=gtx&sl={source}&tl=fr&dt=t&q={quote_plus(texte)}"
        )
        return "".join(seg[0] for seg in data[0] if seg and seg[0])

    def _clients5(self, texte: str, source: str) -> str:
        data = self._json(
            "https://clients5.google.com/translate_a/t"
            f"?client=dict-chrome-ex&sl={source}&tl=fr&q={quote_plus(texte)}"
        )
        return extraire_clients5(data)

    def _mymemory(self, texte: str, source: str) -> str:
        langue = "en" if source in ("auto", "en") else source
        url = f"https://api.mymemory.translated.net/get?q={quote_plus(texte)}&langpair={langue}|fr"
        if os.environ.get("MYMEMORY_MAIL"):  # facultatif (spec § 11) : relève le quota gratuit
            url += f"&de={quote_plus(os.environ['MYMEMORY_MAIL'])}"
        return (self._json(url).get("responseData") or {}).get("translatedText") or ""

    def traduire(self, texte: str, source: str = "auto") -> str:
        texte = (texte or "").strip()[:MAX_CARACTERES]
        if not texte or source == "fr":
            return texte
        cle = (texte, source)
        if cle in self._cache:
            return self._cache[cle]
        self.demandees += 1
        etapes = [("clients5", self._clients5), ("mymemory", self._mymemory)]
        if self._echecs_gtx < ECHECS_MAX_GTX:
            etapes.insert(0, ("gtx", self._gtx))
        for nom, fonction in etapes:
            try:
                sortie = fonction(texte, source).strip()
            except (ErreurReseau, ValueError, KeyError, IndexError, TypeError) as exc:
                if nom == "gtx":
                    self._echecs_gtx += 1
                if self.journal:
                    self.journal.avertir("awb_traduction_service", f"{nom} : {str(exc)[:80]}")
                continue
            if sortie:
                self.reussies += 1
                self._cache[cle] = sortie
                return sortie
        self._cache[cle] = texte  # tous les services ont échoué : texte d'origine
        return texte
