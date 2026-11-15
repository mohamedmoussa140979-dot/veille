"""Messages de santé : ⚠️ une ligne par anomalie avec l'action suggérée ; ✅ du dimanche (§ 10)."""

from __future__ import annotations

from veille.sante.controle import Anomalie
from veille.telegram import echapper


def message_anomalies(anomalies: list[Anomalie], semaine: str | None = None) -> str:
    """Corps du message ⚠️ (l'en-tête est ajouté à l'envoi) : un point par anomalie."""
    n = len(anomalies)
    lignes = [f"<b>{n} anomalie{'s' if n > 1 else ''} à regarder</b>"]
    for a in anomalies:
        lignes.append(f"• {echapper(a.texte)}\n  ➜ {echapper(a.action)}")
    if semaine:
        lignes.append(echapper(semaine))
    return "\n\n".join(lignes)


def phrase_semaine(editions: int, alertes: int) -> str:
    return (
        f"Cette semaine : {editions} édition{'s' if editions > 1 else ''}, "
        f"{alertes} alerte{'s' if alertes > 1 else ''}."
    )


def message_semaine_complete(editions: int, alertes: int) -> str:
    return f"Aucune anomalie. {phrase_semaine(editions, alertes)}"
