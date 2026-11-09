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
