from tube.extraction import ids_videos, texte_brut


def test_formats_courants():
    html_ = (
        'voir <a href="https:&#x2F;&#x2F;www.youtube.com&#x2F;watch?v=dQw4w9WgXcQ&amp;t=42" rel="nofollow">'
        'https:&#x2F;&#x2F;www.youtube.com&#x2F;watch?v=dQw4w9...</a> et youtu.be/abcdefghijk, '
        "https://www.youtube.com/watch?feature=share&v=ZYXWVUTSRQP "
        "https://youtube.com/shorts/AAAAAAAAAAA https://www.youtube-nocookie.com/embed/BBBBBBBBBBB"
    )
    assert ids_videos(html_) == ["dQw4w9WgXcQ", "abcdefghijk", "ZYXWVUTSRQP", "AAAAAAAAAAA", "BBBBBBBBBBB"]


def test_texte_visible_tronque_ignore():
    # HN tronque le texte du lien : « dQw4w9... » ne doit pas produire un faux identifiant.
    assert ids_videos("https://www.youtube.com/watch?v=dQw4w9...") == []


def test_identifiant_trop_long_ignore():
    assert ids_videos("https://youtu.be/abcdefghijkl") == []


def test_chaine_et_playlist_ignorees():
    assert ids_videos("https://www.youtube.com/@Chaine https://www.youtube.com/playlist?list=PL123") == []


def test_texte_brut_garde_les_urls():
    t = texte_brut('Super<p><a href="https:&#x2F;&#x2F;youtu.be&#x2F;abcdefghijk">lien</a> &amp; co')
    assert "https://youtu.be/abcdefghijk" in t
    assert "<" not in t and "& co" in t


def test_motif_mot_cle():
    from tube.collecte_hn import motif
    assert motif("agent").search("AI Agents are here")
    assert motif("backtest").search("my backtesting rig")
    assert not motif("agent").search("reagent")
    assert motif("RAG").search("simple RAG pipeline")
    assert not motif("RAG").search("road rage")
    assert motif("ocean crossing").search("an Ocean  crossing in 2019")


def test_emails_masques():
    t = texte_brut("SEEKING WORK<p>Email: jane.doe+hn@example.co.uk")
    assert "@" not in t and "[e-mail masqué]" in t
