"""Repérage des vidéos YouTube dans le HTML des commentaires Hacker News."""

from __future__ import annotations

import html
import re

# L'identifiant fait exactement 11 caractères ; le lookahead négatif écarte un identifiant
# tronqué ou prolongé. HN raccourcit le texte visible des liens (« dQw4w9... ») mais garde l'URL
# complète dans href : on lit donc le HTML brut déséchappé, pas le seul texte affiché.
_RE_VIDEO = re.compile(
    r"""(?:youtube(?:-nocookie)?\.com/
          (?:watch\?(?:[^\s"'<>]*?&)?v=|embed/|shorts/|live/|v/)
        |youtu\.be/)
        ([A-Za-z0-9_-]{11})(?![A-Za-z0-9_-])""",
    re.VERBOSE | re.IGNORECASE,
)
_RE_BALISE = re.compile(r"<[^>]+>")
# Le dépôt est public et versionne data/ : les adresses que des auteurs HN laissent dans leurs
# annonces « Seeking work » n'ont rien à faire dans le classement, on ne les republie pas.
_RE_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
EMAIL_MASQUE = "[e-mail masqué]"


def masquer_emails(texte: str) -> str:
    return _RE_EMAIL.sub(EMAIL_MASQUE, texte)


def ids_videos(texte_html: str | None) -> list[str]:
    """Identifiants distincts, dans l'ordre d'apparition."""
    if not texte_html:
        return []
    # Deux passes : HN encode « / » en &#x2F; et « & » en &amp; dans les href.
    texte = html.unescape(html.unescape(texte_html))
    vus: dict[str, None] = {}
    for m in _RE_VIDEO.finditer(texte):
        vus.setdefault(m.group(1), None)
    return list(vus)


def texte_brut(texte_html: str | None, limite: int = 1500) -> str:
    """Texte lisible pour le classement par Claude, liens conservés sous forme d'URL."""
    if not texte_html:
        return ""
    t = texte_html.replace("<p>", "\n\n")
    t = re.sub(r'<a\s+href="([^"]*)"[^>]*>.*?</a>', r"\1", t, flags=re.DOTALL)
    t = html.unescape(_RE_BALISE.sub("", t))
    t = masquer_emails(re.sub(r"\n{3,}", "\n\n", t).strip())
    return t if len(t) <= limite else t[:limite] + " […]"
