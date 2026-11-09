"""Collecte Reddit via Arctic Shift, archive publique et gratuite de Reddit.

L'API officielle de Reddit refuse les requêtes non authentifiées (403) et la recherche plein texte
d'Arctic Shift expire presque toujours (« Timeout. Maybe slow down a bit »). On parcourt donc
simplement tous les posts et commentaires d'un subreddit par ordre chronologique, et on filtre
les liens YouTube localement : requêtes légères, que le service supporte.

Parcours du plus récent au plus ancien, avec un budget de temps par passage : les données
récentes (celles qui pèsent le plus dans le score) arrivent en premier, l'historique se complète
de semaine en semaine. Le subreddit fait office de filtre thématique : pas de mot-clé.
"""

from __future__ import annotations

import sys
import time

from .commun import DOSSIER_DONNEES, Interet, ecrire_json, http_json, lire_json
from .extraction import ids_videos, masquer_emails

API = "https://arctic-shift.photon-reddit.com/api"
# « Si vous ne faites que quelques requêtes par seconde, rien à craindre » (README d'Arctic Shift).
PAUSE = 1.0
CHAMPS = {
    "comments": "id,author,created_utc,body,link_id",
    "posts": "id,author,created_utc,title,selftext,url",
}
# Comptes qui ne recommandent rien : bots de modération et auteurs supprimés.
AUTEURS_IGNORES = {"[deleted]", "AutoModerator", "[removed]"}


def _page(type_: str, subreddit: str, avant: int) -> list[dict] | None:
    for tentative in range(5):
        code, corps = http_json(f"{API}/{type_}/search", {
            "subreddit": subreddit, "before": avant, "sort": "desc",
            "limit": "auto", "fields": CHAMPS[type_],
        })
        time.sleep(PAUSE)
        if code == 200 and corps and corps.get("data") is not None:
            return corps["data"]
        # 422 « Timeout » ou 429 : le service est chargé, on ralentit.
        time.sleep(10 * (tentative + 1))
    return None


def _element(type_: str, subreddit: str, d: dict) -> dict | None:
    if d.get("author") in AUTEURS_IGNORES or not d.get("author"):
        return None
    if type_ == "comments":
        brut = d.get("body") or ""
        videos = ids_videos(brut)
        fil = (d.get("link_id") or "").removeprefix("t3_")
        url = f"https://www.reddit.com/r/{subreddit}/comments/{fil}/_/{d['id']}/"
        titre = None
    else:
        brut = (d.get("url") or "") + "\n" + (d.get("selftext") or "")
        videos = ids_videos(brut)
        fil = d["id"]
        url = f"https://www.reddit.com/r/{subreddit}/comments/{fil}/"
        titre = d.get("title")
    if not videos:
        return None
    texte = masquer_emails(brut.strip())
    return {
        "id": f"reddit:{d['id']}",
        "source": "reddit",
        "communaute": f"r/{subreddit}",
        "type": "commentaire" if type_ == "comments" else "article",
        # Préfixe de source : « alice » sur Reddit et « alice » sur HN ne sont pas forcément la même personne.
        "auteur": f"reddit:{d['author']}",
        "date": int(d["created_utc"]),
        "fil": f"reddit:{fil}",
        "titre_fil": titre,
        "texte": texte if len(texte) <= 1500 else texte[:1500] + " […]",
        "videos": videos,
        "url": url,
        "mots": [],
    }


def collecter(interet: Interet, echeance: float, maintenant: int | None = None) -> dict:
    """Met à jour data/reddit/<id>.json jusqu'à l'échéance (time.monotonic) et renvoie les éléments."""
    conf = interet.brut.get("reddit") or {}
    if not conf.get("subreddits"):
        return {}
    maintenant = maintenant or int(time.time())
    chemin = DOSSIER_DONNEES / "reddit" / f"{interet.id}.json"
    etat = lire_json(chemin, {"curseurs": {}, "elements": {}})
    elements = etat["elements"]
    plancher = interet.depuis_ts

    for subreddit in conf["subreddits"]:
        for type_ in ("posts", "comments"):
            cle = f"{subreddit}|{type_}"
            c = etat["curseurs"].setdefault(cle, {"plus_recent": None, "plus_ancien": None})
            n_avant = len(elements)
            # 1. Rattrapage : du présent jusqu'au plus récent déjà vu. 2. Historique : vers le plancher.
            fenetres = []
            if c["plus_recent"] is not None:
                fenetres.append(("rattrapage", maintenant + 1, c["plus_recent"]))
            if c["plus_ancien"] is None:
                fenetres.append(("historique", maintenant + 1, plancher))
            elif c["plus_ancien"] > plancher:
                fenetres.append(("historique", c["plus_ancien"], plancher))
            for nature, avant, borne in fenetres:
                recent_vu = None
                while avant > borne and time.monotonic() < echeance:
                    page = _page(type_, subreddit, avant)
                    if page is None:
                        print(f"  [reddit] r/{subreddit} {type_} : service indisponible, reprise au "
                              f"prochain passage", file=sys.stderr)
                        break
                    if not page:
                        avant = borne
                        break
                    for d in page:
                        el = _element(type_, subreddit, d)
                        if el and int(d["created_utc"]) >= plancher:
                            elements.setdefault(el["id"], el)
                    plus_vieux = min(int(d["created_utc"]) for d in page)
                    plus_jeune = max(int(d["created_utc"]) for d in page)
                    recent_vu = max(recent_vu or 0, plus_jeune)
                    if c["plus_recent"] is None:
                        c["plus_recent"] = plus_jeune
                    # Une page dont tout tient dans la même seconde bouclerait : on recule d'une seconde.
                    avant = plus_vieux if plus_vieux < avant else avant - 1
                    if nature == "historique":
                        c["plus_ancien"] = max(avant, plancher)
                    ecrire_json(chemin, etat)
                # Un rattrapage interrompu laisserait un trou entre son point d'arrêt et l'ancien
                # « plus récent » : on n'avance ce repère que si la fenêtre a été parcourue en entier.
                if nature == "rattrapage" and avant <= borne and recent_vu:
                    c["plus_recent"] = max(c["plus_recent"], recent_vu)
            etat_txt = ("complet" if c["plus_ancien"] is not None and c["plus_ancien"] <= plancher
                        else "à poursuivre")
            print(f"  [reddit] r/{subreddit} {type_} : +{len(elements) - n_avant} ({etat_txt})",
                  file=sys.stderr)
    ecrire_json(chemin, etat)
    return elements
