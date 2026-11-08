"""Classement des mentions par Claude : la vidéo est-elle recommandée, et dans le sujet ?

Petits volumes (le cas courant : quelques dizaines de mentions par semaine) : appels directs en
parallèle, terminés en quelques minutes. Gros volumes : API Message Batches, moitié prix mais
sans délai garanti en dessous de 24 h — un premier lot de 1 031 mentions n'était pas revenu au
bout de 2 h. Les verdicts sont mis en cache dans data/classements.json : un commentaire déjà
classé ne repart jamais chez Claude.
Sans ANTHROPIC_API_KEY, l'étape est sautée et les mentions restent « non_classe ».
"""

from __future__ import annotations

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from .commun import DOSSIER_DONNEES, Interet, ecrire_json, lire_json

CHEMIN = DOSSIER_DONNEES / "classements.json"
CHEMIN_LOTS = DOSSIER_DONNEES / "lots_en_cours.json"
# L'exécution GitHub est coupée à 120 min : on rend la main avant pour publier le site quand même.
ATTENTE_MAX = int(os.environ.get("HUGUES_TUBE_ATTENTE_MAX", "4500"))
# Tri court et répétitif : Haiku suffit et coûte quelques centimes par mois à ce volume.
MODELE = os.environ.get("HUGUES_TUBE_MODELE", "claude-haiku-5-5")
# Tâche de tri courte : un effort bas suffit et divise le coût de réflexion.
EFFORT = os.environ.get("HUGUES_TUBE_EFFORT", "low")
VERDICTS = ("recommande", "neutre", "critique", "hors_sujet")
TAILLE_LOT = 5000
# En dessous, le surcoût des appels directs (×2 sur quelques centimes) vaut mieux qu'une attente
# imprévisible qui ferait expirer l'exécution GitHub.
SEUIL_DIRECT = int(os.environ.get("HUGUES_TUBE_SEUIL_DIRECT", "3000"))
PARALLELE = 8

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


def _params(interet: Interet, el: dict, videos: dict) -> dict:
    return {
        "model": MODELE,
        "max_tokens": 2000,
        "system": SYSTEME,
        "output_config": {"effort": EFFORT, "format": {"type": "json_schema", "schema": SCHEMA}},
        "messages": [{"role": "user", "content": _message(interet, el, videos)}],
    }


def _recolter(client, lots: dict, index: dict, cache: dict, attendre: bool) -> None:
    """Récupère les lots terminés ; avec attendre, patiente jusqu'à ATTENTE_MAX."""
    limite = time.monotonic() + (ATTENTE_MAX if attendre else 0)
    for lot_id in list(lots):
        while client.messages.batches.retrieve(lot_id).processing_status != "ended":
            if time.monotonic() >= limite:
                print(f"  Lot {lot_id} pas encore terminé : repris au prochain passage.", file=sys.stderr)
                break
            time.sleep(30)
        else:
            n_ok = 0
            for resultat in client.messages.batches.results(lot_id):
                c = lots[lot_id].get(resultat.custom_id)
                if c is None or c not in index or resultat.result.type != "succeeded":
                    continue  # erreur ou expiration : la mention sera renvoyée au prochain passage
                verdicts = _lire_reponse(resultat.result.message, index[c][1]["videos"])
                cache[c] = verdicts if verdicts is not None else {"_refus": True}
                n_ok += 1
            print(f"  Lot {lot_id} : {n_ok}/{len(lots[lot_id])} classées.", file=sys.stderr)
            del lots[lot_id]
            ecrire_json(CHEMIN, cache)
            ecrire_json(CHEMIN_LOTS, lots)


def _classer_direct(client, restants: list, videos: dict, cache: dict) -> None:
    def un(i, el):
        return cle(i.id, el["id"]), el, client.messages.create(**_params(i, el, videos))

    n_ok = n_err = 0
    with ThreadPoolExecutor(PARALLELE) as pool:
        futurs = [pool.submit(un, i, el) for i, el in restants]
        for n, f in enumerate(as_completed(futurs), 1):
            try:
                c, el, message = f.result()
            except Exception as e:  # noqa: BLE001 — une mention en échec sera retentée au passage suivant
                n_err += 1
                if n_err <= 3:
                    print(f"  Échec d'un appel : {type(e).__name__}: {e}", file=sys.stderr)
                continue
            verdicts = _lire_reponse(message, el["videos"])
            cache[c] = verdicts if verdicts is not None else {"_refus": True}
            n_ok += 1
            if n % 100 == 0:
                ecrire_json(CHEMIN, cache)
                print(f"  {n}/{len(restants)} mentions traitées", file=sys.stderr)
    ecrire_json(CHEMIN, cache)
    print(f"  Appels directs à {MODELE} : {n_ok} classées, {n_err} en échec.", file=sys.stderr)


def classer(a_classer: list[tuple[Interet, dict]], videos: dict) -> dict:
    """a_classer : couples (centre d'intérêt, élément HN) dont au moins une vidéo est candidate."""
    cache = lire_json(CHEMIN, {})
    if all(cle(i.id, el["id"]) in cache for i, el in a_classer):
        return cache
    if not os.environ.get("ANTHROPIC_API_KEY"):
        n = sum(1 for i, el in a_classer if cle(i.id, el["id"]) not in cache)
        print(f"  ANTHROPIC_API_KEY absente : {n} mentions restent non classées.", file=sys.stderr)
        return cache

    import anthropic  # importé ici : le reste de la chaîne tourne sans le SDK

    # Le SDK retente déjà les 429 et 5xx ; en parallèle, on lui laisse plus de marge.
    client = anthropic.Anthropic(max_retries=6)
    index = {cle(i.id, el["id"]): (i, el) for i, el in a_classer}
    lots = lire_json(CHEMIN_LOTS, {})
    _recolter(client, lots, index, cache, attendre=False)

    # Mentions parties dans un lot pas encore revenu : ne pas les renvoyer (double paiement).
    en_vol = {c for lot in lots.values() for c in lot.values()}
    restants = [(i, el) for c, (i, el) in index.items() if c not in cache and c not in en_vol]
    if not restants:
        return cache
    if len(restants) <= SEUIL_DIRECT:
        _classer_direct(client, restants, videos, cache)
        return cache

    for debut in range(0, len(restants), TAILLE_LOT):
        # custom_id n'accepte que [A-Za-z0-9_-]{1,64} : on passe par un index et une table locale.
        table = {f"m{n}": (i, el) for n, (i, el) in enumerate(restants[debut:debut + TAILLE_LOT])}
        lot_api = client.messages.batches.create(requests=[
            {"custom_id": cid, "params": _params(i, el, videos)} for cid, (i, el) in table.items()])
        lots[lot_api.id] = {cid: cle(i.id, el["id"]) for cid, (i, el) in table.items()}
        # Enregistré avant d'attendre : si l'exécution est interrompue, le passage suivant
        # récupère ce lot au lieu de le payer une seconde fois.
        ecrire_json(CHEMIN_LOTS, lots)
        print(f"  Lot {lot_api.id} : {len(table)} mentions envoyées à {MODELE}.", file=sys.stderr)
    _recolter(client, lots, index, cache, attendre=True)
    return cache
