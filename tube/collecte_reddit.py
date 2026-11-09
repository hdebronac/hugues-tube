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


def _page(type_: str, subreddit: str, avant: int | None = None,
          apres: int | None = None) -> list[dict] | None:
    params = {"subreddit": subreddit, "limit": "auto", "fields": CHAMPS[type_]}
    if apres is not None:
        params |= {"after": apres, "sort": "asc"}
    else:
        params |= {"before": avant, "sort": "desc"}
    for tentative in range(5):
        code, corps = http_json(f"{API}/{type_}/search", params)
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

    flux = []
    for entree in conf["subreddits"]:
        # « ClaudeAI » ou « {nom: ClaudeAI, types: [posts]} » pour un subreddit trop actif.
        nom, types = (entree, ("posts", "comments")) if isinstance(entree, str) else (
            entree["nom"], tuple(entree.get("types", ("posts", "comments"))))
        flux += [(nom, t) for t in types]
    for n, (subreddit, type_) in enumerate(flux):
        # Parts égales du temps restant : sans cela, un subreddit très actif consommerait tout
        # le budget et les suivants ne seraient jamais parcourus.
        echeance_flux = time.monotonic() + max(0.0, echeance - time.monotonic()) / (len(flux) - n)
        cle = f"{subreddit}|{type_}"
        c = etat["curseurs"].setdefault(cle, {"plus_recent": None, "plus_ancien": None})
        n_avant = len(elements)

        def garder(page, type_=type_, subreddit=subreddit):
            for d in page:
                el = _element(type_, subreddit, d)
                if el and int(d["created_utc"]) >= plancher:
                    elements.setdefault(el["id"], el)

        # 1. Rattrapage, dans l'ordre chronologique : le repère « plus récent » avance page après
        #    page, un passage interrompu reprend donc exactement où il s'est arrêté.
        while c["plus_recent"] is not None and time.monotonic() < echeance_flux:
            page = _page(type_, subreddit, apres=c["plus_recent"])
            if not page:
                break  # à jour, ou service indisponible
            garder(page)
            plus_jeune = max(int(d["created_utc"]) for d in page)
            c["plus_recent"] = plus_jeune if plus_jeune > c["plus_recent"] else c["plus_recent"] + 1
            ecrire_json(chemin, etat)
            if len(page) < 100:
                break

        # 2. Historique, du plus récent vers le plancher : les données qui pèsent le plus d'abord.
        avant = c["plus_ancien"] if c["plus_ancien"] is not None else maintenant + 1
        while avant > plancher and time.monotonic() < echeance_flux:
            page = _page(type_, subreddit, avant=avant)
            if page is None:
                print(f"  [reddit] r/{subreddit} {type_} : service indisponible, reprise au "
                      f"prochain passage", file=sys.stderr)
                break
            if not page:
                avant = plancher
            else:
                garder(page)
                plus_vieux = min(int(d["created_utc"]) for d in page)
                if c["plus_recent"] is None:
                    c["plus_recent"] = max(int(d["created_utc"]) for d in page)
                # Une page dont tout tient dans la même seconde bouclerait : on recule d'une seconde.
                avant = plus_vieux if plus_vieux < avant else avant - 1
            c["plus_ancien"] = max(avant, plancher)
            ecrire_json(chemin, etat)

        etat_txt = ("complet" if c["plus_ancien"] is not None and c["plus_ancien"] <= plancher
                    else "à poursuivre")
        print(f"  [reddit] r/{subreddit} {type_} : +{len(elements) - n_avant} ({etat_txt})",
              file=sys.stderr)
    ecrire_json(chemin, etat)
    return elements
