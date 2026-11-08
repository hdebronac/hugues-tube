from datetime import date

from tube.commun import Interet
from tube.score import candidates, classer_videos

MAINTENANT = 1_800_000_000
AN = 365 * 86400

INTERET = Interet(id="test", titre="Test", description="", demi_vie_mois=12, depuis=date(2020, 1, 1),
                  mots_cles=("x",), consigne_classement="")
VIDEOS = {v: {"etat": "disponible", "titre": v, "chaine": "c", "url_chaine": None}
          for v in ("AAAAAAAAAAA", "BBBBBBBBBBB", "CCCCCCCCCCC")}


def el(id_, auteur, videos, age_ans=0.0):
    return {"id": id_, "auteur": auteur, "date": int(MAINTENANT - age_ans * AN), "fil": "1",
            "titre_fil": None, "texte": "", "videos": videos, "mots": ["x"], "type": "commentaire"}


def test_un_auteur_qui_se_repete_ne_compte_qu_une_fois():
    elements = {str(n): el(str(n), "seul", ["AAAAAAAAAAA"]) for n in range(10)}
    assert candidates(elements) == set()
    assert classer_videos(INTERET, elements, {}, VIDEOS, MAINTENANT) == []


def test_auteurs_distincts_et_hors_sujet():
    elements = {"1": el("1", "a", ["AAAAAAAAAAA", "BBBBBBBBBBB"]),
                "2": el("2", "b", ["AAAAAAAAAAA", "BBBBBBBBBBB"])}
    classements = {"test:1": {"BBBBBBBBBBB": {"verdict": "hors_sujet", "type_contenu": "autre"}},
                   "test:2": {"BBBBBBBBBBB": {"verdict": "hors_sujet", "type_contenu": "autre"}}}
    r = classer_videos(INTERET, elements, classements, VIDEOS, MAINTENANT)
    assert [v["id"] for v in r] == ["AAAAAAAAAAA"]
    assert r[0]["auteurs"] == 2


def test_critique_fait_baisser_et_recence_compte():
    rec = {"verdict": "recommande", "type_contenu": "technique"}
    crit = {"verdict": "critique", "type_contenu": "technique"}
    elements = {"1": el("1", "a", ["AAAAAAAAAAA"]), "2": el("2", "b", ["AAAAAAAAAAA"]),
                "3": el("3", "a", ["BBBBBBBBBBB"], age_ans=3), "4": el("4", "b", ["BBBBBBBBBBB"], age_ans=3),
                "5": el("5", "a", ["CCCCCCCCCCC"]), "6": el("6", "b", ["CCCCCCCCCCC"]),
                "7": el("7", "c", ["CCCCCCCCCCC"])}
    classements = {f"test:{n}": {v: rec for v in elements[str(n)]["videos"]} for n in range(1, 7)}
    classements["test:7"] = {"CCCCCCCCCCC": crit}
    r = {v["id"]: v["score"] for v in classer_videos(INTERET, elements, classements, VIDEOS, MAINTENANT)}
    assert r["AAAAAAAAAAA"] > r["BBBBBBBBBBB"]  # mêmes soutiens, mais plus récents
    assert r["AAAAAAAAAAA"] > r["CCCCCCCCCCC"]  # un critique retire du poids


def test_video_supprimee_exclue():
    elements = {"1": el("1", "a", ["AAAAAAAAAAA"]), "2": el("2", "b", ["AAAAAAAAAAA"])}
    videos = {"AAAAAAAAAAA": {"etat": "indisponible"}}
    assert classer_videos(INTERET, elements, {}, videos, MAINTENANT) == []
