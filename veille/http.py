"""Client HTTP commun : délais par hôte, nouveaux essais, en-têtes de navigateur, URL encodées."""

from __future__ import annotations

import time
from collections.abc import Callable
from urllib.parse import quote, urlsplit, urlunsplit

import requests

from veille.journal import Journal

HEADERS_NAVIGATEUR = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}
STATUTS_REESSAI = (429, 500, 502, 503, 504)

_SUR_CHEMIN = "/%:@!$&'()*+,;=-._~"
_SUR_REQUETE = "=&%+,;:@/?!$'()*-._~"


class ErreurReseau(Exception):
    """Aucune réponse HTTP n'a pu être obtenue après tous les essais."""


def encoder_url(url: str) -> str:
    """Encode les caractères non ASCII (France24 plantait sur « é ») sans doubler les %XX."""
    parties = urlsplit(url.strip())
    hote = parties.hostname or ""
    try:
        hote.encode("ascii")
    except UnicodeEncodeError:
        hote = hote.encode("idna").decode("ascii")
    reseau = hote
    if parties.username:  # rare ; on conserve les identifiants tels quels
        reseau = f"{parties.username}:{parties.password or ''}@{hote}"
    if parties.port:
        reseau += f":{parties.port}"
    chemin = quote(parties.path, safe=_SUR_CHEMIN)
    requete = quote(parties.query, safe=_SUR_REQUETE)
    return urlunsplit((parties.scheme, reseau, chemin, requete, ""))


def _attente_demandee(reponse) -> float | None:
    """Pause réclamée par le serveur : en-tête Retry-After, ou corps JSON de Telegram."""
    brut = (getattr(reponse, "headers", None) or {}).get("Retry-After")
    if brut is not None:
        try:
            return float(brut)
        except ValueError:
            pass
    try:
        corps = reponse.json()
        return float(corps["parameters"]["retry_after"])
    except (ValueError, KeyError, TypeError, AttributeError):
        return None


class Client:
    def __init__(
        self,
        session: requests.Session | None = None,
        *,
        essais: int = 3,
        attente: float = 2.0,
        facteur: float = 2.0,
        attente_max: float = 60.0,
        delai_hote: float = 0.0,
        timeout: float = 25.0,
        headers: dict[str, str] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        horloge: Callable[[], float] = time.monotonic,
        journal: Journal | None = None,
    ):
        self.session = session or requests.Session()
        self.essais = essais
        self.attente = attente
        self.facteur = facteur
        self.attente_max = attente_max
        self.delai_hote = delai_hote
        self.timeout = timeout
        self.headers = dict(HEADERS_NAVIGATEUR if headers is None else headers)
        self._sleep = sleep
        self._horloge = horloge
        self.journal = journal
        self._dernier_appel: dict[str, float] = {}

    # -- utilitaires -------------------------------------------------------------------

    def _masquer(self, texte: str) -> str:
        return self.journal.masquer(texte) if self.journal else texte

    def _pause_entre_essais(self, tentative: int, demandee: float | None) -> float:
        propre = self.attente * (self.facteur**tentative)
        return min(max(propre, demandee or 0.0), self.attente_max)

    def _attendre_hote(self, hote: str) -> None:
        maintenant = self._horloge()
        if self.delai_hote > 0 and hote in self._dernier_appel:
            manque = self._dernier_appel[hote] + self.delai_hote - maintenant
            if manque > 0:
                self._sleep(manque)

    # -- requête -----------------------------------------------------------------------

    def request(
        self,
        methode: str,
        url: str,
        *,
        essais: int | None = None,
        ssl_repli: bool = False,
        statuts_reessai: tuple[int, ...] = STATUTS_REESSAI,
        **kw,
    ):
        url = encoder_url(url)
        hote = urlsplit(url).hostname or ""
        kw["headers"] = {**self.headers, **kw.pop("headers", {})}
        kw.setdefault("timeout", self.timeout)
        total = essais if essais is not None else self.essais
        derniere_reponse = None
        derniere_erreur: Exception | None = None
        verifier_ssl = True

        for tentative in range(total):
            self._attendre_hote(hote)
            try:
                if not verifier_ssl:
                    kw["verify"] = False
                reponse = self.session.request(methode, url, **kw)
            except requests.exceptions.SSLError as exc:
                derniere_erreur = exc
                if ssl_repli and verifier_ssl:
                    verifier_ssl = False
                    if self.journal:
                        self.journal.avertir("http_ssl_repli", "certificat invalide", hote=hote)
                    continue  # nouvel essai immédiat, sans vérification du certificat
                break  # un certificat invalide ne se corrige pas en réessayant
            except (requests.ConnectionError, requests.Timeout) as exc:
                derniere_erreur = exc
                self._dernier_appel[hote] = self._horloge()
                if tentative + 1 < total:
                    self._sleep(self._pause_entre_essais(tentative, None))
                continue
            self._dernier_appel[hote] = self._horloge()
            if reponse.status_code in statuts_reessai:
                derniere_reponse = reponse
                if tentative + 1 < total:
                    self._sleep(self._pause_entre_essais(tentative, _attente_demandee(reponse)))
                continue
            return reponse

        if derniere_reponse is not None:
            return derniere_reponse
        raise ErreurReseau(
            self._masquer(f"{methode} {hote} : {type(derniere_erreur).__name__}: {derniere_erreur}")
        )

    def get(self, url: str, **kw):
        return self.request("GET", url, **kw)

    def post(self, url: str, **kw):
        return self.request("POST", url, **kw)
