"""Point d'entrée : python -m tube [collecte|classement|site|tout]."""

from __future__ import annotations

import argparse
import os
import sys
import time

from . import classement, collecte_heo, collecte_hn, collecte_reddit, enrichissement, score, site
from .commun import DOSSIER_DONNEES, charger_interets, ecrire_json, lire_json


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="tube")
    p.add_argument("etape", choices=["collecte", "classement", "site", "tout"], nargs="?", default="tout")
    p.add_argument("--interet", help="limiter à un centre d'intérêt (son id)")
    p.add_argument("--sources", default="hn,reddit,heo",
                   help="sources à collecter, séparées par des virgules (hn, reddit, heo)")
    args = p.parse_args(argv)

    maintenant = int(time.time())
    interets = charger_interets()
    if args.interet:
        interets = [i for i in interets if i.id == args.interet]
        if not interets:
            print(f"Centre d'intérêt inconnu : {args.interet}", file=sys.stderr)
            return 2

    sources = set(args.sources.split(","))
    collecter = args.etape in ("collecte", "tout")
    # Budgets en minutes, partagés à parts égales entre centres d'intérêt : l'exécution GitHub est
    # coupée à 120 min et le classement doit encore tourner après la collecte.
    budget_reddit = float(os.environ.get("HUGUES_TUBE_BUDGET_REDDIT", "40")) * 60 / len(interets)
    budget_heo = float(os.environ.get("HUGUES_TUBE_BUDGET_HEO", "25")) * 60

    elements = {}
    for i in interets:
        elements[i.id] = {}
        if collecter and "hn" in sources:
            print(f"Collecte Hacker News — {i.titre}", file=sys.stderr)
            elements[i.id].update(collecte_hn.collecter(i, maintenant))
        else:
            elements[i.id].update(lire_json(DOSSIER_DONNEES / "hn" / f"{i.id}.json", {"elements": {}})["elements"])
        if collecter and "reddit" in sources and i.brut.get("reddit"):
            print(f"Collecte Reddit — {i.titre}", file=sys.stderr)
            elements[i.id].update(collecte_reddit.collecter(i, time.monotonic() + budget_reddit, maintenant))
        else:
            elements[i.id].update(lire_json(DOSSIER_DONNEES / "reddit" / f"{i.id}.json", {"elements": {}})["elements"])
        if collecter and "heo" in sources and i.brut.get("hisse_et_oh"):
            print(f"Collecte Hisse et Oh — {i.titre}", file=sys.stderr)
            elements[i.id].update(collecte_heo.collecter(i, time.monotonic() + budget_heo, maintenant))
        else:
            elements[i.id].update(lire_json(DOSSIER_DONNEES / "heo" / f"{i.id}.json", {"elements": {}})["elements"])

    if args.etape == "collecte":
        return 0

    candidates = {i.id: score.candidates(elements[i.id]) for i in interets}
    toutes = set().union(*candidates.values()) if candidates else set()
    print(f"Métadonnées YouTube : {len(toutes)} vidéos candidates", file=sys.stderr)
    videos = enrichissement.enrichir(toutes, maintenant)

    a_classer = [(i, el) for i in interets for el in elements[i.id].values()
                 if set(el["videos"]) & candidates[i.id]]
    print(f"Classement : {len(a_classer)} mentions concernées", file=sys.stderr)
    classements = classement.classer(a_classer, videos)

    # Fusion avec le dernier résultat : un passage limité à un centre d'intérêt ne vide pas les autres pages.
    resultats = lire_json(DOSSIER_DONNEES / "resultats.json", {})
    resultats.update({i.id: score.classer_videos(i, elements[i.id], classements, videos, maintenant)
                      for i in interets})
    for i in interets:
        print(f"  {i.titre} : {len(resultats[i.id])} vidéos retenues", file=sys.stderr)
    ecrire_json(DOSSIER_DONNEES / "resultats.json", resultats)

    if args.etape in ("site", "tout"):
        site.construire(resultats, charger_interets(), maintenant)
        print("Site généré dans _site/", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
