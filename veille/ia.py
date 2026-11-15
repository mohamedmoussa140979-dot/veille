"""IA (spec § 7) : Gemini en principal, Claude en secours avec plafond mensuel, JSON validé."""

from __future__ import annotations

import json
import math
import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

import jsonschema

from veille import temps
from veille.config import plafond_claude_usd
from veille.http import ErreurReseau
from veille.journal import Journal

GEMINI_API = "https://generativelanguage.googleapis.com/v1beta"
CLAUDE_API = "https://api.anthropic.com/v1/messages"
CLAUDE_VERSION_API = "2023-06-01"
STATUTS_TRANSITOIRES = (None, 429, 500, 502, 503, 504)
EXCLUS_MODELES = (
    "image", "tts", "transcribe", "omni", "robotics", "lyria", "nano", "deep-research",
    "computer-use", "embedding", "embed", "gemma", "live", "audio", "pro", "aqa",
)  # fmt: skip


class ErreurIa(Exception):
    pass


class PlafondAtteint(ErreurIa):
    pass


@dataclass
class Resultat:
    texte: str
    fournisseur: str
    modele: str
    donnees: Any = None
    essais: int = 1


# --- Gemini -----------------------------------------------------------------------------


def classer_modeles(noms: list[str]) -> list[str]:
    """Ordre d'essai : alias « latest », versions décroissantes, préversions, puis « lite »."""

    def version(nom: str) -> float:
        m = re.search(r"gemini-(\d+(?:\.\d+)?)", nom)
        return float(m.group(1)) if m else 0.0

    def est_preversion(nom: str) -> bool:
        return "preview" in nom or "-exp" in nom

    gardes = [n for n in noms if "flash" in n and not any(x in n for x in EXCLUS_MODELES)]
    principaux = [n for n in gardes if "lite" not in n]
    legers = [n for n in gardes if "lite" in n]

    def tri(liste: list[str]) -> list[str]:
        alias = sorted(n for n in liste if n.endswith("-latest"))
        autres = [n for n in liste if not n.endswith("-latest")]
        autres.sort(key=lambda n: (est_preversion(n), -version(n), n))
        return alias + autres

    return tri(principaux) + tri(legers)


class Gemini:
    def __init__(
        self,
        cle: str,
        client,
        journal: Journal,
        *,
        attentes: tuple[float, ...] = (10, 30, 60),
        max_modeles: int = 6,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self._cle = cle
        self.client = client
        self.journal = journal
        self.attentes = tuple(attentes)
        self.max_modeles = max_modeles
        self._sleep = sleep
        self._modeles: list[str] | None = None

    @property
    def _en_tetes(self) -> dict[str, str]:
        return {"x-goog-api-key": self._cle, "Content-Type": "application/json"}

    def modeles(self) -> list[str]:
        if self._modeles is not None:
            return self._modeles
        noms: list[str] = []
        jeton = None
        try:
            for _ in range(5):
                params = {"pageSize": 200, **({"pageToken": jeton} if jeton else {})}
                r = self.client.get(f"{GEMINI_API}/models", headers=self._en_tetes, params=params)
                if r.status_code != 200:
                    raise ErreurIa(f"ListModels HTTP {r.status_code}")
                corps = r.json()
                noms += [
                    m["name"].removeprefix("models/")
                    for m in corps.get("models", [])
                    if "generateContent" in m.get("supportedGenerationMethods", [])
                ]
                jeton = corps.get("nextPageToken")
                if not jeton:
                    break
            retenus = classer_modeles(noms)
        except (ErreurIa, ErreurReseau, ValueError) as exc:
            self.journal.avertir("gemini_decouverte_echec", str(exc))
            retenus = []
        self._modeles = retenus or ["gemini-flash-latest"]
        self.journal.info("gemini_modeles", ", ".join(self._modeles[: self.max_modeles]))
        return self._modeles

    def _appel(self, modele: str, charge: dict) -> tuple[int | None, str | None, str]:
        try:
            r = self.client.post(
                f"{GEMINI_API}/models/{modele}:generateContent",
                headers=self._en_tetes,
                json=charge,
                essais=1,
                timeout=180,
            )
        except ErreurReseau as exc:
            return None, None, str(exc)
        if r.status_code != 200:
            return r.status_code, None, (r.text or "")[:300]
        try:
            parties = r.json()["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError, TypeError, ValueError):
            return 200, None, "réponse vide ou bloquée"
        texte = "".join(p.get("text", "") for p in parties if not p.get("thought")).strip()
        return 200, texte or None, "réponse vide" if not texte else ""

    def generer(
        self, prompt: str, *, systeme: str | None = None, json_mode: bool = False
    ) -> tuple[str, str]:
        charge: dict[str, Any] = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
        if systeme:
            charge["systemInstruction"] = {"parts": [{"text": systeme}]}
        if json_mode:
            charge["generationConfig"] = {
                "responseMimeType": "application/json",
                "temperature": 0.2,
            }
        ecartes: set[str] = set()
        derniere = "aucun modèle disponible"
        for tour in range(len(self.attentes) + 1):
            transitoire = False
            candidats = [m for m in self.modeles() if m not in ecartes][: self.max_modeles]
            for modele in candidats:
                statut, texte, detail = self._appel(modele, charge)
                if texte:
                    self.journal.info("gemini_modele_utilise", modele, tour=tour + 1)
                    return texte, modele
                detail = self.journal.masquer(detail)
                if statut in (401, 403) or (statut == 400 and "api key" in detail.lower()):
                    raise ErreurIa(f"clé Gemini refusée (HTTP {statut})")
                if statut == 404:
                    ecartes.add(modele)
                elif statut in STATUTS_TRANSITOIRES or statut == 200:
                    transitoire = True
                derniere = f"{modele} : HTTP {statut} {detail}".strip()
                self.journal.avertir("gemini_modele_echec", derniere, tour=tour + 1)
            if not transitoire or tour >= len(self.attentes):
                break
            self._sleep(self.attentes[tour])
        raise ErreurIa(f"Gemini indisponible ({derniere})")


# --- compteur de consommation Claude ----------------------------------------------------


class Compteur(Protocol):
    def depense(self, mois: str) -> float: ...
    def ajouter(self, mois: str, usd: float, entree: int, sortie: int) -> None: ...


class CompteurMemoire:
    def __init__(self):
        self.d: dict[str, dict[str, float]] = {}

    def depense(self, mois: str) -> float:
        return self.d.get(mois, {}).get("usd", 0.0)

    def ajouter(self, mois: str, usd: float, entree: int, sortie: int) -> None:
        m = self.d.setdefault(mois, {"usd": 0.0, "appels": 0, "entree": 0, "sortie": 0})
        m["usd"] = round(m["usd"] + usd, 6)
        m["appels"] += 1
        m["entree"] += entree
        m["sortie"] += sortie


class CompteurEtat:
    """Compteur tenu sur la branche `data` (spec § 7 : « compteur de consommation dans l'état »)."""

    CHEMIN = "state/claude.json"

    def __init__(self, etat):
        self.etat = etat

    def depense(self, mois: str) -> float:
        return float(self.etat.lire_json(self.CHEMIN, {}).get(mois, {}).get("usd", 0.0))

    def ajouter(self, mois: str, usd: float, entree: int, sortie: int) -> None:
        def maj(donnees: dict) -> dict:
            m = donnees.setdefault(mois, {"usd": 0.0, "appels": 0, "entree": 0, "sortie": 0})
            m["usd"] = round(m["usd"] + usd, 6)
            m["appels"] += 1
            m["entree"] += entree
            m["sortie"] += sortie
            return donnees

        self.etat.modifier_json(self.CHEMIN, maj, defaut={}, message="data: compteur Claude")


# --- Claude (secours) -------------------------------------------------------------------


class Claude:
    def __init__(
        self,
        cle: str,
        client,
        compteur: Compteur,
        journal: Journal,
        *,
        modele: str,
        prix_entree: float,
        prix_sortie: float,
        plafond_usd: float,
        max_tokens: int = 8000,
        effort: str | None = "low",
        mois: Callable[[], str] = temps.mois,
    ):
        self._cle = cle
        self.client = client
        self.compteur = compteur
        self.journal = journal
        self.modele = modele
        self.prix_entree = prix_entree
        self.prix_sortie = prix_sortie
        self.plafond_usd = plafond_usd
        self.max_tokens = max_tokens
        self.effort = effort
        self._mois = mois

    def _cout(self, entree: int, sortie: int) -> float:
        return (entree * self.prix_entree + sortie * self.prix_sortie) / 1_000_000

    def generer(
        self, prompt: str, *, systeme: str | None = None, max_tokens: int | None = None
    ) -> Resultat:
        limite = max_tokens or self.max_tokens
        mois = self._mois()
        depense = self.compteur.depense(mois)
        # Borne haute du coût de cet appel : 1 token pour 2 caractères en entrée (pessimiste).
        borne = self._cout(math.ceil((len(prompt) + len(systeme or "")) / 2), limite)
        if depense + borne > self.plafond_usd:
            raise PlafondAtteint(
                f"plafond Claude du mois atteint : {depense:.2f} $ dépensés + {borne:.2f} $ "
                f"possibles > {self.plafond_usd:.2f} $"
            )
        corps: dict[str, Any] = {
            "model": self.modele,
            "max_tokens": limite,
            "messages": [{"role": "user", "content": prompt}],
        }
        if systeme:
            corps["system"] = systeme
        if self.effort:
            corps["output_config"] = {"effort": self.effort}
        try:
            r = self.client.post(
                CLAUDE_API,
                headers={
                    "x-api-key": self._cle,
                    "anthropic-version": CLAUDE_VERSION_API,
                    "content-type": "application/json",
                },
                json=corps,
                essais=2,
                timeout=300,
            )
        except ErreurReseau as exc:
            raise ErreurIa(f"Claude injoignable : {exc}") from exc
        if r.status_code != 200:
            raise ErreurIa(
                self.journal.masquer(f"Claude HTTP {r.status_code} : {(r.text or '')[:300]}")
            )
        donnees = r.json()
        usage = donnees.get("usage", {})
        entree = (
            usage.get("input_tokens", 0)
            + usage.get("cache_creation_input_tokens", 0)
            + usage.get("cache_read_input_tokens", 0)
        )
        sortie = usage.get("output_tokens", 0)
        cout = self._cout(entree, sortie)
        self.compteur.ajouter(mois, cout, entree, sortie)  # facturé même en cas de refus
        self.journal.info("claude_appel", f"{cout:.4f} $", entree=entree, sortie=sortie)
        if donnees.get("stop_reason") == "refusal":
            raise ErreurIa("Claude a refusé la requête (refusal)")
        texte = "".join(
            b.get("text", "") for b in donnees.get("content", []) if b.get("type") == "text"
        ).strip()
        if not texte:
            raise ErreurIa("Claude : réponse vide")
        return Resultat(texte, "claude", self.modele)


# --- orchestrateur ----------------------------------------------------------------------


def extraire_json(texte: str) -> Any:
    brut = texte.strip()
    brut = re.sub(r"^```(?:json)?\s*|\s*```$", "", brut)
    try:
        return json.loads(brut)
    except json.JSONDecodeError:
        debut, fin = brut.find("{"), brut.rfind("}")
        if 0 <= debut < fin:
            return json.loads(brut[debut : fin + 1])
        raise


class Ia:
    def __init__(self, gemini: Gemini | None, claude: Claude | None, journal: Journal):
        self.gemini = gemini
        self.claude = claude
        self.journal = journal

    @classmethod
    def depuis_environnement(cls, parametres: dict, client, journal: Journal, etat=None) -> Ia:
        cfg = parametres["claude"]
        cle_gemini = os.environ.get("GEMINI_API_KEY")
        cle_claude = os.environ.get("ANTHROPIC_API_KEY")
        plafond = plafond_claude_usd(parametres)
        compteur = CompteurEtat(etat) if etat is not None else CompteurMemoire()
        gemini = (
            Gemini(
                cle_gemini,
                client,
                journal,
                attentes=tuple(parametres["gemini"]["attentes_s"]),
                max_modeles=parametres["gemini"]["max_modeles"],
            )
            if cle_gemini
            else None
        )
        claude = (
            Claude(
                cle_claude,
                client,
                compteur,
                journal,
                modele=cfg["modele"],
                prix_entree=cfg["prix_entree_usd_par_mtok"],
                prix_sortie=cfg["prix_sortie_usd_par_mtok"],
                plafond_usd=plafond,
                max_tokens=cfg["max_tokens"],
            )
            if cle_claude
            else None
        )
        return cls(gemini, claude, journal)

    def generer(
        self, prompt: str, *, systeme: str | None = None, json_mode: bool = False
    ) -> Resultat:
        try:
            if self.gemini is None:
                raise ErreurIa("clé Gemini absente")
            texte, modele = self.gemini.generer(prompt, systeme=systeme, json_mode=json_mode)
            return Resultat(texte, "gemini", modele)
        except ErreurIa as exc:
            self.journal.avertir("gemini_echec", str(exc))
            echec_gemini = exc
        if self.claude is None:
            raise ErreurIa(f"{echec_gemini} ; pas de secours Claude configuré") from echec_gemini
        try:
            resultat = self.claude.generer(prompt, systeme=systeme)
        except PlafondAtteint as exc:
            self.journal.erreur("claude_plafond_atteint", str(exc))
            raise
        except ErreurIa as exc:
            self.journal.erreur("claude_echec", str(exc))
            raise
        self.journal.avertir("claude_secours_utilise", "Gemini en échec", modele=resultat.modele)
        return resultat

    def generer_json(
        self,
        prompt: str,
        schema: dict,
        *,
        systeme: str | None = None,
        normaliser: Callable[[Any], Any] | None = None,
    ) -> Resultat:
        """JSON validé contre `schema` ; un JSON invalide donne un seul nouvel essai.

        `normaliser` corrige une forme équivalente mais inattendue avant validation (constat du
        14/11 : Gemini renvoie parfois la liste seule au lieu de l'objet qui l'enveloppe).
        """
        demande = prompt
        derniere = ""
        for essai in (1, 2):
            resultat = self.generer(demande, systeme=systeme, json_mode=True)
            try:
                donnees = extraire_json(resultat.texte)
                if normaliser:
                    donnees = normaliser(donnees)
                jsonschema.validate(donnees, schema)
            except jsonschema.ValidationError as exc:
                # message court : le message natif recopie toute la donnée invalide
                chemin = "/".join(str(p) for p in exc.absolute_path) or "racine"
                derniere = f"champ {chemin} : contrainte « {exc.validator} » non respectée"
                self.journal.avertir("ia_json_invalide", derniere, essai=essai)
                demande = (
                    f"{prompt}\n\nTa réponse précédente n'était pas conforme au schéma "
                    f"({derniere}). Réponds uniquement par un JSON valide, de la forme demandée."
                )
                continue
            except ValueError as exc:
                derniere = str(exc).splitlines()[0][:200]
                self.journal.avertir("ia_json_invalide", derniere, essai=essai)
                demande = (
                    f"{prompt}\n\nTa réponse précédente n'était pas un JSON valide conforme au "
                    f"schéma ({derniere}). Réponds uniquement par un JSON valide."
                )
                continue
            resultat.donnees = donnees
            resultat.essais = essai
            return resultat
        raise ErreurIa(f"JSON invalide après 2 essais : {derniere}")
