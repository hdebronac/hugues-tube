"""Classement des vidéos d'un centre d'intérêt.

Le critère qui compte est le nombre d'auteurs DISTINCTS qui recommandent une vidéo : un même
passionné qui poste dix fois son lien favori ne doit pas peser dix fois.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

from .commun import Interet

POIDS = {"recommande": 1.0, "neutre": 0.4, "non_classe": 0.7, "critique": -1.0}
SECONDES_PAR_MOIS = 30.44 * 86400
# Seuil d'entrée : une vidéo citée par une seule personne n'est pas une recommandation collective.
AUTEURS_MIN = 2


def verdict(classements: dict, interet_id: str, element_id: str, video_id: str) -> tuple[str, str | None]:
    c = classements.get(f"{interet_id}:{element_id}")
    if not c or c.get("_refus"):
        return "non_classe", None
    v = c.get(video_id)
    if not v:
        return "non_classe", None
    return v["verdict"], v.get("type_contenu")


def candidates(elements: dict) -> set[str]:
    """Vidéos citées par au moins AUTEURS_MIN auteurs, avant tout classement (filtre gratuit)."""
    auteurs = defaultdict(set)
    for el in elements.values():
        for vid in el["videos"]:
            auteurs[vid].add(el["auteur"])
    return {vid for vid, a in auteurs.items() if len(a) >= AUTEURS_MIN}


def classer_videos(interet: Interet, elements: dict, classements: dict, videos: dict,
                   maintenant: int) -> list[dict]:
    mentions = defaultdict(list)
    for el in elements.values():
        for vid in el["videos"]:
            v, type_ = verdict(classements, interet.id, el["id"], vid)
            if v == "hors_sujet":
                continue
            mentions[vid].append((el, v, type_))

    resultats = []
    for vid, liste in mentions.items():
        fiche = videos.get(vid)
        if not fiche or fiche["etat"] == "indisponible":
            continue
        # Par auteur, on garde sa contribution la plus forte en valeur absolue.
        par_auteur: dict[str, float] = {}
        for el, v, _ in liste:
            age_mois = max(0.0, (maintenant - el["date"]) / SECONDES_PAR_MOIS)
            w = POIDS[v] * 0.5 ** (age_mois / interet.demi_vie_mois)
            if abs(w) > abs(par_auteur.get(el["auteur"], 0.0)):
                par_auteur[el["auteur"]] = w
        positifs = sum(1 for w in par_auteur.values() if w > 0)
        if positifs < AUTEURS_MIN:
            continue
        annees = {datetime.fromtimestamp(el["date"], UTC).year for el, _, _ in liste}
        # Une vidéo encore citée des années plus tard a fait ses preuves ; bonus plafonné à ×2.
        etalement = min(2.0, 1 + 0.15 * (len(annees) - 1))
        score = sum(par_auteur.values()) * etalement
        if score <= 0:
            continue
        types = [t for _, _, t in liste if t]
        classees = sum(1 for _, v, _ in liste if v != "non_classe")
        discussions = sorted(liste, key=lambda m: (m[1] != "recommande", -m[0]["date"]))
        resultats.append({
            "id": vid,
            "titre": fiche.get("titre"),
            "chaine": fiche.get("chaine"),
            "url_chaine": fiche.get("url_chaine"),
            "score": round(score, 3),
            "auteurs": positifs,
            "mentions": len(liste),
            "premiere": min(el["date"] for el, _, _ in liste),
            "derniere": max(el["date"] for el, _, _ in liste),
            "type_contenu": max(set(types), key=types.count) if types else None,
            "part_classee": round(classees / len(liste), 2),
            "discussions": [{"id": el["id"], "fil": el["fil"], "titre_fil": el.get("titre_fil"),
                             "date": el["date"], "verdict": v}
                            for el, v, _ in discussions[:5]],
        })
    resultats.sort(key=lambda r: (-r["score"], r["id"]))
    return resultats
