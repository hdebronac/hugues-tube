from tube.collecte_heo import date_objectid, fils_de_la_liste, messages
from tube.collecte_reddit import _element

PAGE_FIL = """<div class="card mb-2 discuss-topic"><a id="6aea72a78ce7325cb9351024"></a><h1 class="h4">Titre</h1>
<div class="card-body py-1"><div class="discuss-content"><p>Regardez https://youtu.be/abcdefghijk</p></div><div class="note x">
</div><a href='/sailors/1'>capitaine</a></div>
<div class="answer-card card mb-2 h-answer__discuss item-comment even" data-id="6aead22e8f850441e70a0354" id="x">
<a href='/sailors/2'>Dim31</a><div class="answer-content"><p><iframe src='https:///www.youtube.com/embed/bUdhyn2HofE?is=x'></iframe></p></div><hr/>
<div class="answer-card card mb-2 odd" data-id="6aeada079bb49a87d00a04c1" id="y">
<a href='/sailors/3'>Polmar</a><div class="answer-content"><p>Pas de vidéo</p></div><hr/>"""


def test_messages_heo():
    ms = messages(PAGE_FIL)
    assert [(m["id"][:4], m["auteur"]) for m in ms] == [("6aea", "capitaine"), ("6aea", "Dim31"),
                                                         ("6aea", "Polmar")]
    assert "youtube.com/embed/bUdhyn2HofE" in ms[1]["html"]


def test_date_objectid():
    assert date_objectid("6aead22e8f850441e70a0354") == 0x6AEAD22E


def test_liste_heo_dedoublonnee():
    assert fils_de_la_liste('<a href="/sailing/a-b"></a><a href="/sailing/a-b"></a><a href="/sailing/c"></a>',
                            "sailing") == ["a-b", "c"]


def test_element_reddit():
    el = _element("comments", "sailing", {"id": "k1", "author": "bob", "created_utc": 1700000000,
                                          "body": "great https://youtu.be/abcdefghijk mail me a@b.fr",
                                          "link_id": "t3_p9"})
    assert el["auteur"] == "reddit:bob" and el["videos"] == ["abcdefghijk"]
    assert el["url"] == "https://www.reddit.com/r/sailing/comments/p9/_/k1/"
    assert "@" not in el["texte"]
    assert _element("comments", "sailing", {"id": "k2", "author": "AutoModerator", "created_utc": 1,
                                            "body": "https://youtu.be/abcdefghijk", "link_id": "t3_p"}) is None


def test_collecte_reddit_historique_puis_rattrapage(tmp_path, monkeypatch):
    import time as t
    from datetime import date

    import tube.collecte_reddit as cr
    from tube.commun import Interet

    # Un commentaire par heure, un lien YouTube sur deux ; pages de 100 au plus, comme l'API.
    flux = [{"id": f"c{h}", "author": f"u{h % 7}", "created_utc": 1_000_000 + h * 3600,
             "body": "https://youtu.be/abcdefghijk" if h % 2 else "rien", "link_id": "t3_p"}
            for h in range(450)]

    def page(type_, subreddit, avant=None, apres=None):
        if apres is not None:
            return sorted((d for d in flux if d["created_utc"] > apres), key=lambda d: d["created_utc"])[:100]
        return sorted((d for d in flux if d["created_utc"] < avant), key=lambda d: -d["created_utc"])[:100]

    monkeypatch.setattr(cr, "_page", page)
    monkeypatch.setattr(cr, "DOSSIER_DONNEES", tmp_path)
    interet = Interet(id="t", titre="T", description="", demi_vie_mois=1, depuis=date(1970, 1, 1),
                      mots_cles=(), consigne_classement="",
                      brut={"reddit": {"subreddits": [{"nom": "s", "types": ["comments"]}]}})
    maintenant = 1_000_000 + 400 * 3600  # les 50 dernières heures n'existent pas encore
    visibles = [d for d in flux if d["created_utc"] <= maintenant]
    flux_complet, flux[:] = list(flux), visibles

    els = cr.collecter(interet, t.monotonic() + 60, maintenant)
    assert len(els) == sum(1 for d in visibles if d["body"] != "rien")

    flux[:] = flux_complet  # une semaine plus tard : de nouveaux commentaires
    els = cr.collecter(interet, t.monotonic() + 60, 1_000_000 + 500 * 3600)
    assert len(els) == sum(1 for d in flux_complet if d["body"] != "rien")
