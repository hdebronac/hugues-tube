"""Chemins, chargement des centres d'intérêt et accès HTTP partagés par toutes les étapes."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_INTERETS = RACINE / "interests"
DOSSIER_DONNEES = RACINE / "data"
DOSSIER_SITE = RACINE / "_site"

# Un nom de client générique : rien qui identifie la personne derrière le dépôt.
USER_AGENT = "hugues-tube/0.1 (+https://tube.bronac.net)"


@dataclass(frozen=True)
class Interet:
    id: str
    titre: str
    description: str
    demi_vie_mois: float
    depuis: date
    mots_cles: tuple[str, ...]
    consigne_classement: str
    brut: dict = field(default_factory=dict, compare=False, repr=False)

    @property
    def depuis_ts(self) -> int:
        return int(datetime(self.depuis.year, self.depuis.month, self.depuis.day,
                            tzinfo=UTC).timestamp())


def charger_interets() -> list[Interet]:
    interets = []
    for chemin in sorted(DOSSIER_INTERETS.glob("*.yaml")):
        d = yaml.safe_load(chemin.read_text(encoding="utf-8"))
        depuis = d["depuis"]
        if isinstance(depuis, str):
            depuis = date.fromisoformat(depuis)
        interets.append(Interet(
            id=d["id"],
            titre=d["titre"],
            description=" ".join(d["description"].split()),
            demi_vie_mois=float(d["demi_vie_mois"]),
            depuis=depuis,
            mots_cles=tuple(d["mots_cles"]),
            consigne_classement=" ".join(d["consigne_classement"].split()),
            brut=d,
        ))
    if len({i.id for i in interets}) != len(interets):
        raise SystemExit("Deux fichiers de interests/ portent le même id.")
    return interets


def lire_json(chemin: Path, defaut):
    if not chemin.exists():
        return defaut
    return json.loads(chemin.read_text(encoding="utf-8"))


def ecrire_json(chemin: Path, donnees) -> None:
    """Écriture atomique et triée : les fichiers de data/ sont versionnés, un diff stable les rend relisibles."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    tmp = chemin.with_suffix(chemin.suffix + ".tmp")
    tmp.write_text(json.dumps(donnees, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                   encoding="utf-8")
    tmp.replace(chemin)


def http_json(url: str, params: dict | None = None, essais: int = 4, pause: float = 2.0):
    """GET JSON avec reprise sur erreur réseau ou 429/5xx. Renvoie (code, corps) ; corps vaut None hors 200."""
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for tentative in range(essais):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and tentative < essais - 1:
                time.sleep(pause * 2 ** tentative)
                continue
            return e.code, None
        except (urllib.error.URLError, TimeoutError):
            if tentative < essais - 1:
                time.sleep(pause * 2 ** tentative)
                continue
            raise
    return None, None


def http_texte(url: str, essais: int = 3, pause: float = 5.0) -> tuple[int | None, str | None]:
    """GET d'une page HTML, mêmes reprises que http_json."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for tentative in range(essais):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, r.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and tentative < essais - 1:
                time.sleep(pause * 2 ** tentative)
                continue
            return e.code, None
        except (urllib.error.URLError, TimeoutError):
            if tentative < essais - 1:
                time.sleep(pause * 2 ** tentative)
                continue
            return None, None
    return None, None
