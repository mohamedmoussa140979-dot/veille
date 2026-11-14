"""Garde-fous communs : aucun test n'a le droit d'ouvrir une connexion réseau."""

from __future__ import annotations

import socket

import pytest


@pytest.fixture(autouse=True)
def _pas_de_reseau(monkeypatch):
    connexion_reelle = socket.socket.connect

    def refuser(self, adresse, *args, **kwargs):
        hote = adresse[0] if isinstance(adresse, tuple) else str(adresse)
        if hote in ("127.0.0.1", "::1", "localhost"):
            return connexion_reelle(self, adresse, *args, **kwargs)
        raise RuntimeError(f"Accès réseau interdit en test : {adresse!r}")

    monkeypatch.setattr(socket.socket, "connect", refuser)


class FausseReponse:
    """Réponse HTTP minimale, compatible avec ce que les modules attendent de requests."""

    def __init__(self, statut=200, json_=None, texte=None, entetes=None, contenu=None):
        self.status_code = statut
        self._json = json_
        self.text = texte if texte is not None else ("" if json_ is None else str(json_))
        self.content = contenu if contenu is not None else self.text.encode()
        self.headers = entetes or {}

    @property
    def ok(self):
        return self.status_code < 400

    def json(self):
        if self._json is None:
            raise ValueError("pas de JSON")
        return self._json


class FauxClient:
    """Client scénarisé : renvoie les réponses dans l'ordre (ou lève l'exception donnée)."""

    def __init__(self, scenario):
        self.scenario = list(scenario)
        self.appels = []

    def request(self, methode, url, **kw):
        self.appels.append({"methode": methode, "url": url, **kw})
        if not self.scenario:
            raise AssertionError(f"appel imprévu : {methode} {url}")
        suivant = self.scenario.pop(0)
        if callable(suivant):
            suivant = suivant(methode, url, kw)
        if isinstance(suivant, Exception):
            raise suivant
        return suivant

    def get(self, url, **kw):
        return self.request("GET", url, **kw)

    def post(self, url, **kw):
        return self.request("POST", url, **kw)
