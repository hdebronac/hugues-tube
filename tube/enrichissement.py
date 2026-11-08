"""Titre, chaîne et miniature des vidéos via l'oEmbed public de YouTube (sans clé d'API).

L'oEmbed ne donne ni la durée ni la date de publication ; c'est suffisant pour afficher la page
et pour éliminer les vidéos supprimées. Une clé YouTube Data API pourra compléter plus tard.
"""

from __future__ import annotations

import sys
import time

from .commun import DOSSIER_DONNEES, ecrire_json, http_json, lire_json

CHEMIN = DOSSIER_DONNEES / "videos.json"
OEMBED = "https://www.youtube.com/oembed"
# Une vidéo supprimée peut réapparaître (rare) ; une vérification annuelle suffit.
REVERIFIER_APRES = 365 * 86400


def enrichir(ids: set[str], maintenant: int | None = None) -> dict:
    maintenant = maintenant or int(time.time())
    videos = lire_json(CHEMIN, {})
    a_faire = sorted(i for i in ids
                     if i not in videos or maintenant - videos[i]["verifie_le"] > REVERIFIER_APRES)
    for n, vid in enumerate(a_faire, 1):
        code, corps = http_json(OEMBED, {"url": f"https://www.youtube.com/watch?v={vid}",
                                         "format": "json"})
        if code == 200 and corps:
            fiche = {"etat": "disponible", "titre": corps.get("title"),
                     "chaine": corps.get("author_name"), "url_chaine": corps.get("author_url")}
        elif code == 401:
            # 401 = intégration désactivée par l'auteur : la vidéo existe, sans métadonnées oEmbed.
            fiche = {"etat": "non_integrable", "titre": None, "chaine": None, "url_chaine": None}
        elif code in (400, 403, 404):
            fiche = {"etat": "indisponible", "titre": None, "chaine": None, "url_chaine": None}
        else:
            # Erreur transitoire : on ne fige rien, on réessaiera au prochain passage.
            continue
        fiche["verifie_le"] = maintenant
        videos[vid] = fiche
        if n % 50 == 0:
            print(f"  oEmbed : {n}/{len(a_faire)}", file=sys.stderr)
            ecrire_json(CHEMIN, videos)
        time.sleep(0.1)
    ecrire_json(CHEMIN, videos)
    return videos
