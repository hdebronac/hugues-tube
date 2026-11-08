"""Classement des mentions par Claude : la vidéo est-elle recommandée, et dans le sujet ?

Passe par l'API Message Batches (moitié prix, asynchrone). Les verdicts sont mis en cache dans
data/classements.json : un commentaire déjà classé ne repart jamais chez Claude.
Sans ANTHROPIC_API_KEY, l'étape est sautée et les mentions restent « non_classe ».
"""

from __future__ import annotations

import json
import os
import sys
import time

from .commun import DOSSIER_DONNEES, Interet, ecrire_json, lire_json

CHEMIN = DOSSIER_DONNEES / "classements.json"
# Tri court et répétitif : Haiku suffit et coûte quelques centimes par mois à ce volume.
MODELE = os.environ.get("HUGUES_TUBE_MODELE", "claude-haiku-5-5")
# Tâche de tri courte : un effort bas suffit et divise le coût de réflexion.
EFFORT = os.environ.get("HUGUES_TUBE_EFFORT", "low")
VERDICTS = ("recommande", "neutre", "critique", "hors_sujet")
TAILLE_LOT = 5000

SCHEMA = {
    "type": "object",
    "properties": {
        "videos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "verdict": {"type": "string", "enum": list(VERDICTS)},
                    "type_contenu": {"type": "string",
                                     "enum": ["technique", "conference", "retour_experience",
                                              "vlog", "autre"]},
                },
                "required": ["id", "verdict", "type_contenu"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["videos"],
    "additionalProperties": False,
}

SYSTEME = """Tu tries des liens YouTube cités dans des commentaires de Hacker News pour un site \
qui recense les vidéos que les passionnés d'un sujet se recommandent.

Pour chaque vidéo citée, donne :
- verdict :
  - « recommande » : l'auteur la conseille, la cite comme référence ou exemple à voir ;
  - « neutre » : citée comme source ou au passage, sans jugement ;
  - « critique » : citée pour être contredite, moquée ou dénoncée ;
  - « hors_sujet » : la vidéo ne relève pas du sujet décrit ci-dessous, quel que soit le ton.
- type_contenu : technique, conference, retour_experience, vlog ou autre.

Juge d'après le commentaire et le titre de la vidéo quand il est fourni. En cas de doute entre \
recommande et neutre, choisis neutre."""


def cle(interet_id: str, element_id: str) -> str:
    return f"{interet_id}:{element_id}"


def _message(interet: Interet, el: dict, videos: dict) -> str:
    lignes = [f"Sujet : {interet.titre}. {interet.consigne_classement}", ""]
    if el.get("titre_fil"):
        lignes.append(f"Fil de discussion : {el['titre_fil']}")
    lignes += ["Commentaire :", el["texte"] or "(article sans texte)", "", "Vidéos citées :"]
    for vid in el["videos"]:
        titre = (videos.get(vid) or {}).get("titre") or "titre inconnu"
        lignes.append(f"- {vid} : {titre}")
    return "\n".join(lignes)


def _lire_reponse(message, attendus: list[str]) -> dict | None:
    if message.stop_reason != "end_turn":
        # Refus ou réponse tronquée : on n'invente pas de verdict, la mention reste non classée.
        return None
    texte = next((b.text for b in message.content if b.type == "text"), None)
    if not texte:
        return None
    try:
        donnees = json.loads(texte)
    except json.JSONDecodeError:
        return None
    verdicts = {v["id"]: {"verdict": v["verdict"], "type_contenu": v["type_contenu"]}
                for v in donnees.get("videos", []) if v.get("id") in attendus}
    return verdicts or None


def classer(a_classer: list[tuple[Interet, dict]], videos: dict) -> dict:
    """a_classer : couples (centre d'intérêt, élément HN) dont au moins une vidéo est candidate."""
    cache = lire_json(CHEMIN, {})
    restants = [(i, el) for i, el in a_classer if cle(i.id, el["id"]) not in cache]
    if not restants:
        return cache
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(f"  ANTHROPIC_API_KEY absente : {len(restants)} mentions restent non classées.",
              file=sys.stderr)
        return cache

    import anthropic  # importé ici : le reste de la chaîne tourne sans le SDK

    client = anthropic.Anthropic()
    for debut in range(0, len(restants), TAILLE_LOT):
        lot = restants[debut:debut + TAILLE_LOT]
        # custom_id n'accepte que [A-Za-z0-9_-]{1,64} : on passe par un index et une table locale.
        table = {f"m{n}": (i, el) for n, (i, el) in enumerate(lot)}
        requetes = [{
            "custom_id": cid,
            "params": {
                "model": MODELE,
                "max_tokens": 2000,
                "system": SYSTEME,
                "output_config": {"effort": EFFORT,
                                  "format": {"type": "json_schema", "schema": SCHEMA}},
                "messages": [{"role": "user", "content": _message(i, el, videos)}],
            },
        } for cid, (i, el) in table.items()]
        lot_api = client.messages.batches.create(requests=requetes)
        print(f"  Lot {lot_api.id} : {len(requetes)} mentions envoyées à {MODELE}.", file=sys.stderr)
        while True:
            etat = client.messages.batches.retrieve(lot_api.id)
            if etat.processing_status == "ended":
                break
            time.sleep(30)
        n_ok = 0
        for resultat in client.messages.batches.results(lot_api.id):
            i, el = table[resultat.custom_id]
            if resultat.result.type != "succeeded":
                continue  # erreur ou expiration : reprise au prochain passage
            verdicts = _lire_reponse(resultat.result.message, el["videos"])
            if verdicts is None:
                verdicts = {"_refus": True}
            cache[cle(i.id, el["id"])] = verdicts
            n_ok += 1
        print(f"  Lot {lot_api.id} : {n_ok}/{len(requetes)} classées.", file=sys.stderr)
        ecrire_json(CHEMIN, cache)
    return cache
