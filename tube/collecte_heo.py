"""Collecte du forum Hisse et Oh (voile, francophone).

Le robots.txt autorise les fils de discussion et demande 5 s entre deux requêtes. Le site ne
liste que les 10 dernières pages de chaque section (~750 fils) et n'a ni plan de site ni
recherche exploitable sans JavaScript : on suit donc les fils récents et on accumule semaine
après semaine. Les identifiants de messages sont des ObjectId MongoDB, dont les 4 premiers
octets donnent la date de publication : c'est notre seule date absolue (la page affiche « 5j »).
"""

from __future__ import annotations

import html
import re
import sys
import time

from .commun import DOSSIER_DONNEES, Interet, ecrire_json, http_texte, lire_json
from .extraction import ids_videos, texte_brut

BASE = "https://www.hisse-et-oh.com"
CRAWL_DELAY = 5.0  # exigé par le robots.txt du site
PAGES_LISTE = 10  # au-delà, le site renvoie une liste vide
# Un fil revu il y a moins d'une semaine n'a guère de chances d'avoir de nouvelles vidéos.
REVOIR_APRES = 6 * 86400

_RE_TITRE = re.compile(r'<h1 class="h4">(.*?)</h1>', re.DOTALL)
_RE_SUJET = re.compile(r'class="card mb-2 discuss-topic"><a id="([0-9a-f]{24})"></a>(.*?)'
                       r'(?=<div class="answer-card|$)', re.DOTALL)
_RE_REPONSE = re.compile(r'<div class="answer-card[^"]*" data-id="([0-9a-f]{24})"(.*?)'
                         r'(?=<div class="answer-card|$)', re.DOTALL)
_RE_AUTEUR = re.compile(r"<a href='/sailors/(\d+)'>([^<]+)</a>")
_RE_CONTENU_SUJET = re.compile(r'<div class="discuss-content">(.*?)</div><div class="note', re.DOTALL)
_RE_CONTENU_REPONSE = re.compile(r'<div class="answer-content">(.*?)</div><hr', re.DOTALL)


def date_objectid(oid: str) -> int:
    return int(oid[:8], 16)


def fils_de_la_liste(page_html: str, section: str) -> list[str]:
    vus: dict[str, None] = {}
    for slug in re.findall(rf'href="/{section}/([a-z0-9-]+)"', page_html):
        vus.setdefault(slug, None)
    return list(vus)


def messages(page_html: str) -> list[dict]:
    """Messages d'un fil : (id, auteur, texte HTML). Le sujet d'abord, puis les réponses."""
    sortie = []
    m = _RE_SUJET.search(page_html)
    if m:
        bloc = m.group(2)
        contenu = _RE_CONTENU_SUJET.search(bloc)
        auteur = _RE_AUTEUR.search(bloc[contenu.end():] if contenu else bloc)
        if contenu and auteur:
            sortie.append({"id": m.group(1), "auteur": html.unescape(auteur.group(2)).strip(),
                           "html": contenu.group(1)})
    for m in _RE_REPONSE.finditer(page_html):
        bloc = m.group(2)
        auteur = _RE_AUTEUR.search(bloc)
        contenu = _RE_CONTENU_REPONSE.search(bloc)
        if auteur and contenu:
            sortie.append({"id": m.group(1), "auteur": html.unescape(auteur.group(2)).strip(),
                           "html": contenu.group(1)})
    return sortie


def _get(url: str) -> str | None:
    code, corps = http_texte(url)
    time.sleep(CRAWL_DELAY)
    return corps if code == 200 else None


def collecter(interet: Interet, echeance: float, maintenant: int | None = None) -> dict:
    sections = (interet.brut.get("hisse_et_oh") or {}).get("sections") or []
    if not sections:
        return {}
    maintenant = maintenant or int(time.time())
    chemin = DOSSIER_DONNEES / "heo" / f"{interet.id}.json"
    etat = lire_json(chemin, {"fils": {}, "elements": {}})
    elements = etat["elements"]

    a_voir: list[tuple[str, str]] = []
    for section in sections:
        for page in range(1, PAGES_LISTE + 1):
            if time.monotonic() >= echeance:
                break
            corps = _get(f"{BASE}/{section}" + (f"?page={page}" if page > 1 else ""))
            if not corps:
                break
            slugs = fils_de_la_liste(corps, section)
            if not slugs:
                break
            a_voir += [(section, s) for s in slugs]

    n_avant, n_fils = len(elements), 0
    for section, slug in a_voir:
        if time.monotonic() >= echeance:
            print("  [heo] budget de temps atteint : suite au prochain passage", file=sys.stderr)
            break
        cle = f"{section}/{slug}"
        if maintenant - etat["fils"].get(cle, {}).get("vu_le", 0) < REVOIR_APRES:
            continue
        corps = _get(f"{BASE}/{cle}")
        if not corps:
            continue
        n_fils += 1
        titre_m = _RE_TITRE.search(corps)
        titre = texte_brut(titre_m.group(1)) if titre_m else slug.replace("-", " ")
        for msg in messages(corps):
            videos = ids_videos(msg["html"])
            if not videos:
                continue
            elements[f"heo:{msg['id']}"] = {
                "id": f"heo:{msg['id']}",
                "source": "hisse_et_oh",
                "communaute": "Hisse et Oh",
                "type": "commentaire",
                "auteur": f"heo:{msg['auteur']}",
                "date": date_objectid(msg["id"]),
                "fil": f"heo:{cle}",
                "titre_fil": titre,
                "texte": texte_brut(msg["html"]),
                "videos": videos,
                "url": f"{BASE}/{cle}#{msg['id']}",
                "mots": [],
            }
        etat["fils"][cle] = {"vu_le": maintenant}
        if n_fils % 20 == 0:
            ecrire_json(chemin, etat)
    ecrire_json(chemin, etat)
    print(f"  [heo] {n_fils} fils lus, +{len(elements) - n_avant} messages avec vidéo", file=sys.stderr)
    return elements
