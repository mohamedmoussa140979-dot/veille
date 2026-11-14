"""Messages 📈 : point Bourse (17:20) et clôture internationale (22:45), spec § 5 et § 6.4."""

from __future__ import annotations

import html

from veille.marches.formats import date_courte, nombre, signe
from veille.telegram import echapper


def _lien(texte: str, url: str | None) -> str:
    return (
        f'<a href="{html.escape(url, quote=True)}">{echapper(texte)}</a>'
        if url
        else echapper(texte)
    )


def message_bourse(b: dict | None, jour: str | None = None) -> str:
    """Corps du message Bourse ; source muette ou séance non publiée : message explicite."""
    if b is None:
        return "Bourse de Tunis : données indisponibles (source muette). Aucun chiffre affiché."
    if jour and b["seance"] != jour:
        return (
            f"Séance du {date_courte(jour)} non encore publiée. "
            f"Dernière séance disponible : {date_courte(b['seance'])}."
        )
    entete = f"<b>Bourse de Tunis · séance du {date_courte(b['seance'])}</b>"
    if b["provisoire"]:
        entete += " <i>(provisoire)</i>"
    lignes = [entete]
    for i in b["indices"]:
        annee = (
            f" · depuis le 1er janvier {signe(i['variation_annee_pct'])}"
            if i.get("variation_annee_pct") is not None
            else ""
        )
        lignes.append(
            f"• {_lien(i['libelle'], i['source_url'])} {nombre(i['valeur'])} "
            f"({signe(i['variation_pct'])}){annee}"
        )
    for titre, liste in (
        ("Plus fortes hausses", b["hausses"]),
        ("Plus fortes baisses", b["baisses"]),
    ):
        if liste:
            lignes.append(f"\n<b>{titre}</b>")
            lignes += [
                f"• {_lien(v['libelle'], v['source_url'])} {nombre(v['valeur'], 3)} "
                f"({signe(v['variation_pct'])})"
                for v in liste
            ]
    cap = b.get("capitaux")
    if cap:
        txt = f"\n<b>Capitaux échangés</b> : {nombre(cap['capitaux_mtnd'])} MTND"
        if cap.get("transactions"):
            txt += f" · {nombre(cap['transactions'], 0)} transactions"
        lignes.append(txt + (" (estimés)" if cap.get("estimes") else ""))
    lignes.append("\nSource : Bourse de Tunis")
    return "\n".join(lignes)


def message_international(tableau: dict, taux: dict) -> str:
    """Corps du message de clôture internationale : une ligne par instrument, tiret si absent."""
    lignes = ["<b>Clôture internationale</b>"]
    for ligne in tableau["lignes"]:
        if ligne["valeur"] is None:
            lignes.append(f"• {echapper(ligne['libelle'])} : —")
            continue
        decimales = 4 if ligne["cle"] in ("eurusd", "eur_tnd", "usd_tnd") else 2
        unite = (
            f" {ligne['unite']}"
            if ligne["unite"] and ligne["unite"] not in ("points", "dinars")
            else ""
        )
        lignes.append(
            f"• {_lien(ligne['libelle'], ligne['source_url'])} "
            f"{nombre(ligne['valeur'], decimales)}{unite} ({signe(ligne['variation_pct'])})"
        )
    tmm = taux.get("tmm")
    if tmm:
        lignes.append(
            f"\n• {_lien('TMM', tmm['source_url'])} {nombre(tmm['valeur'])} % ({tmm['periode']})"
        )
    lignes.append("\nSources : Yahoo Finance, BCT (cours moyens)")
    return "\n".join(lignes)
