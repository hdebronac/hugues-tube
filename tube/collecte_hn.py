"""Collecte Hacker News via l'API publique Algolia.

On ne garde que les commentaires et les articles qui contiennent au moins un lien YouTube :
c'est ce filtre gratuit, avant tout appel à Claude, qui rend le coût supportable.
"""

from __future__ import annotations

import re
import sys
import time

from .commun import DOSSIER_DONNEES, Interet, ecrire_json, http_json, lire_json
from .extraction import ids_videos, texte_brut

API = "https://hn.algolia.com/api/v1/search_by_date"
# Algolia plafonne une requête à 1000 résultats paginés : au-delà, on coupe la fenêtre en deux.
PLAFOND = 1000
PAR_PAGE = 500
# L'API autorise 10 000 requêtes par heure ; on reste très en dessous.
PAUSE = 0.25
# Recouvrement lors d'une reprise incrémentale, pour ne rien perdre aux bornes.
RECOUVREMENT = 2 * 86400


def _requete(texte: str, type_: str, debut: int, fin: int, page: int):
    code, corps = http_json(API, {
        "query": texte,
        "tags": type_,
        "hitsPerPage": PAR_PAGE,
        "page": page,
        "numericFilters": f"created_at_i>={debut},created_at_i<{fin}",
        # Sans cela, « MCP » ramène aussi « MVP », « MCU »… : 2 072 résultats au lieu de 148.
        "typoTolerance": "false",
    })
    time.sleep(PAUSE)
    if code != 200 or corps is None:
        raise RuntimeError(f"Algolia a répondu {code} pour « {texte} » ({type_}, {debut}–{fin})")
    return corps


def _fenetre(texte: str, type_: str, debut: int, fin: int):
    premiere = _requete(texte, type_, debut, fin, 0)
    if premiere["nbHits"] > PLAFOND and fin - debut > 3600:
        milieu = (debut + fin) // 2
        yield from _fenetre(texte, type_, debut, milieu)
        yield from _fenetre(texte, type_, milieu, fin)
        return
    yield from premiere["hits"]
    for page in range(1, premiere.get("nbPages", 1)):
        yield from _requete(texte, type_, debut, fin, page)["hits"]


def motif(mot: str) -> re.Pattern:
    """Mot-clé reconnu localement, en complément d'Algolia qui cherche aussi dans l'auteur et l'URL.

    Un sigle en capitales (LLM, MCP, RAG) est cherché tel quel, pluriel admis : en minuscules,
    « rag » attraperait « rage ». Un mot ordinaire accepte quelques terminaisons (agents,
    backtesting) et des espaces multiples entre les mots d'une expression.
    """
    corps = r"\s+".join(re.escape(m) for m in mot.split())
    if mot.isupper():
        return re.compile(rf"\b{corps}s?\b")
    return re.compile(rf"(?<![a-z0-9]){corps}(?:s|es|ing|ed|ic)?\b", re.IGNORECASE)


def _element(hit: dict, interet: Interet, mot: str) -> dict | None:
    if "comment" in hit.get("_tags", []):
        html_ = hit.get("comment_text")
        videos = ids_videos(html_)
        titre = hit.get("story_title")
        type_ = "commentaire"
    else:
        html_ = hit.get("story_text") or ""
        videos = ids_videos((hit.get("url") or "") + " " + html_)
        titre = hit.get("title")
        type_ = "article"
    if not videos or not hit.get("author"):
        return None
    # Le titre du fil compte : un lien posté sous « Show HN: mon agent » est dans le sujet.
    if not motif(mot).search(texte_brut(html_, limite=10**6) + " " + (titre or "")):
        return None
    return {
        "id": str(hit["objectID"]),
        "type": type_,
        "auteur": hit["author"],
        "date": int(hit["created_at_i"]),
        "fil": str(hit.get("story_id") or hit["objectID"]),
        "titre_fil": titre,
        "texte": texte_brut(html_) if type_ == "commentaire" else (titre or ""),
        "videos": videos,
        "mots": [mot],
    }


def collecter(interet: Interet, maintenant: int | None = None) -> dict:
    """Met à jour data/hn/<id>.json et renvoie le dictionnaire complet des éléments retenus."""
    maintenant = maintenant or int(time.time())
    chemin = DOSSIER_DONNEES / "hn" / f"{interet.id}.json"
    etat = lire_json(chemin, {"curseurs": {}, "elements": {}})
    elements: dict = etat["elements"]

    for mot in interet.mots_cles:
        # Algolia découpe « youtu.be » en « youtu » : deux requêtes pour couvrir les deux formes.
        for suffixe in ("youtube", "youtu"):
            texte = f"{mot} {suffixe}"
            for type_ in ("comment", "story"):
                cle = f"{texte}|{type_}"
                debut = max(interet.depuis_ts, etat["curseurs"].get(cle, 0) - RECOUVREMENT)
                n_avant = len(elements)
                for hit in _fenetre(texte, type_, debut, maintenant + 1):
                    el = _element(hit, interet, mot)
                    if el is None:
                        continue
                    existant = elements.get(el["id"])
                    if existant:
                        existant["mots"] = sorted(set(existant["mots"]) | {mot})
                    else:
                        elements[el["id"]] = el
                etat["curseurs"][cle] = maintenant
                print(f"  [{interet.id}] « {texte} » {type_} : +{len(elements) - n_avant}",
                      file=sys.stderr)
        # Sauvegarde après chaque mot-clé : une collecte interrompue reprend sans tout refaire.
        ecrire_json(chemin, etat)
    return elements
