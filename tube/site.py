"""Génération du site statique : une page d'accueil, une page par centre d'intérêt."""

from __future__ import annotations

import html
import json
import shutil
from datetime import UTC, datetime

from .commun import DOSSIER_SITE, RACINE, Interet

DOMAINE = "tube.bronac.net"
MAX_PAR_PAGE = 500

STYLE = """
:root{--fond:#f7f6f2;--carte:#fff;--texte:#1d1d1b;--doux:#6b6a65;--trait:#e3e1da;--accent:#0b5f8a;--pastille:#eef4f8}
@media (prefers-color-scheme:dark){:root{--fond:#141413;--carte:#1f1f1d;--texte:#ecebe6;--doux:#a3a29b;--trait:#33322f;--accent:#6fb6dd;--pastille:#1d2a32}}
*{box-sizing:border-box}
body{margin:0;background:var(--fond);color:var(--texte);font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
header,main,footer{max-width:1200px;margin:0 auto;padding:0 16px}
header{padding-top:32px;padding-bottom:8px}
h1{font-size:1.9rem;margin:0 0 4px;letter-spacing:-.01em}
.sous{color:var(--doux);margin:0 0 16px;max-width:70ch}
nav.fil{font-size:.9rem;margin-bottom:12px}
.interets{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px;margin:24px 0}
.interet{background:var(--carte);border:1px solid var(--trait);border-radius:12px;padding:20px;display:block;color:inherit}
.interet:hover{border-color:var(--accent);text-decoration:none}
.interet h2{margin:0 0 6px;font-size:1.2rem}.interet p{margin:0;color:var(--doux);font-size:.95rem}
.interet .n{margin-top:12px;color:var(--accent);font-weight:600}
.outils{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0 20px}
.outils input,.outils select{font:inherit;padding:8px 10px;border:1px solid var(--trait);border-radius:8px;background:var(--carte);color:var(--texte)}
.outils input{flex:1 1 240px;min-width:0}
.grille{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:16px;padding:0;margin:0;list-style:none}
.video{background:var(--carte);border:1px solid var(--trait);border-radius:12px;overflow:hidden;display:flex;flex-direction:column}
.video img{width:100%;aspect-ratio:16/9;object-fit:cover;display:block;background:var(--trait)}
.corps{padding:12px 14px 14px;display:flex;flex-direction:column;gap:6px;flex:1}
.rang{color:var(--doux);font-size:.8rem;font-variant-numeric:tabular-nums}
.titre{font-weight:600;line-height:1.3}
.chaine{color:var(--doux);font-size:.9rem}
.meta{display:flex;flex-wrap:wrap;gap:6px;font-size:.78rem}
.meta span{background:var(--pastille);border-radius:999px;padding:2px 8px}
details{font-size:.85rem;margin-top:auto}summary{cursor:pointer;color:var(--doux)}
details ul{margin:6px 0 0;padding-left:18px}
.avertissement{background:var(--pastille);border-radius:8px;padding:10px 14px;font-size:.9rem;margin:0 0 16px}
footer{color:var(--doux);font-size:.85rem;padding-top:32px;padding-bottom:32px}
.vide{color:var(--doux)}
"""

SCRIPT = """
const D=JSON.parse(document.getElementById('donnees').textContent);
const g=document.getElementById('grille'),q=document.getElementById('q'),tri=document.getElementById('tri'),
      ty=document.getElementById('type'),n=document.getElementById('n');
const esc=s=>(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const an=t=>new Date(t*1000).getFullYear();
const V={recommande:'recommande',neutre:'cite',critique:'critique',non_classe:'non classé'};
function rendre(){
  const t=q.value.trim().toLowerCase();
  let l=D.filter(v=>!t||(v.titre||'').toLowerCase().includes(t)||(v.chaine||'').toLowerCase().includes(t));
  if(ty.value)l=l.filter(v=>v.type_contenu===ty.value);
  if(tri.value==='auteurs')l=[...l].sort((a,b)=>b.auteurs-a.auteurs||b.score-a.score);
  if(tri.value==='recent')l=[...l].sort((a,b)=>b.derniere-a.derniere);
  n.textContent=l.length+' vidéo'+(l.length>1?'s':'');
  g.innerHTML=l.length?l.map(v=>`<li class="video">
   <a href="https://www.youtube.com/watch?v=${v.id}" target="_blank" rel="noopener"><img loading="lazy" alt="" src="https://i.ytimg.com/vi/${v.id}/mqdefault.jpg"></a>
   <div class="corps"><div class="rang">n° ${v.rang} · score ${v.score.toFixed(2)}</div>
   <a class="titre" href="https://www.youtube.com/watch?v=${v.id}" target="_blank" rel="noopener">${esc(v.titre)||'Vidéo YouTube '+v.id}</a>
   <div class="chaine">${esc(v.chaine)||'&nbsp;'}</div>
   <div class="meta"><span>${v.auteurs} recommandeur${v.auteurs>1?'s':''}</span><span>${an(v.premiere)===an(v.derniere)?an(v.premiere):an(v.premiere)+'–'+an(v.derniere)}</span>${v.type_contenu?`<span>${esc(v.type_contenu.replace('_',' '))}</span>`:''}</div>
   <details><summary>${v.mentions} mention${v.mentions>1?'s':''} · ${esc((v.sources||['Hacker News']).join(', '))}</summary><ul>${v.discussions.map(d=>`<li><a href="${esc(d.url||'https://news.ycombinator.com/item?id='+d.id)}" target="_blank" rel="noopener">${esc(d.titre_fil)||'discussion'}</a> · ${esc(d.communaute||'Hacker News')} · ${an(d.date)} · ${V[d.verdict]||d.verdict}</li>`).join('')}</ul></details>
   </div></li>`).join(''):'<p class="vide">Aucune vidéo ne correspond.</p>';
}
[q,tri,ty].forEach(e=>e.addEventListener('input',rendre));rendre();
"""


def _page(titre: str, corps: str, description: str, script: str = "") -> str:
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(titre)}</title>
<meta name="description" content="{html.escape(description)}">
<link rel="icon" href="favicon.svg" type="image/svg+xml">
<style>{STYLE}</style></head>
<body>{corps}{script}</body></html>
"""


def _pied(maj: str) -> str:
    return ('<footer>Vidéos que les membres de <a href="https://news.ycombinator.com">Hacker News</a>, '
            'de Reddit (via l\'archive <a href="https://arctic-shift.photon-reddit.com">Arctic Shift</a>) '
            'et du forum <a href="https://www.hisse-et-oh.com">Hisse et Oh</a> se recommandent, classées '
            f'par nombre d\'auteurs distincts. Mise à jour du {maj}.</footer>')


def construire(resultats: dict[str, list[dict]], interets: list[Interet], maintenant: int) -> None:
    if DOSSIER_SITE.exists():
        shutil.rmtree(DOSSIER_SITE)
    DOSSIER_SITE.mkdir(parents=True)
    maj = datetime.fromtimestamp(maintenant, UTC).strftime("%d/%m/%Y")

    cartes = []
    for i in interets:
        n = len(resultats.get(i.id, []))
        cartes.append(f'<a class="interet" href="{i.id}.html"><h2>{html.escape(i.titre)}</h2>'
                      f'<p>{html.escape(i.description)}</p><div class="n">{n} vidéos</div></a>')
    accueil = (f'<header><h1>Hugues Tube</h1><p class="sous">Les vidéos YouTube que les passionnés '
               f'se recommandent vraiment, plutôt que celles que l\'algorithme pousse.</p></header>'
               f'<main><div class="interets">{"".join(cartes)}</div></main>{_pied(maj)}')
    (DOSSIER_SITE / "index.html").write_text(
        _page("Hugues Tube", accueil, "Vidéos recommandées par les communautés de passionnés."),
        encoding="utf-8")

    for i in interets:
        liste = resultats.get(i.id, [])[:MAX_PAR_PAGE]
        donnees = [{**v, "rang": n} for n, v in enumerate(liste, 1)]
        part = (sum(v["part_classee"] for v in liste) / len(liste)) if liste else 0
        avert = ""
        if part < 0.5:
            avert = ('<p class="avertissement">Le tri par Claude (recommandation ou critique, '
                     'pertinence) n\'a pas encore tourné sur la plupart de ces mentions : le classement '
                     'repose surtout sur le nombre de personnes qui citent chaque vidéo.</p>')
        types = sorted({v["type_contenu"] for v in liste if v["type_contenu"]})
        options = "".join(f'<option value="{t}">{t.replace("_", " ")}</option>' for t in types)
        corps = (f'<header><nav class="fil"><a href="index.html">← Hugues Tube</a></nav>'
                 f'<h1>{html.escape(i.titre)}</h1><p class="sous">{html.escape(i.description)}</p></header>'
                 f'<main>{avert}<div class="outils">'
                 f'<input id="q" type="search" placeholder="Filtrer par titre ou chaîne" aria-label="Filtrer">'
                 f'<select id="tri" aria-label="Trier"><option value="score">Score</option>'
                 f'<option value="auteurs">Nombre de recommandeurs</option>'
                 f'<option value="recent">Mention la plus récente</option></select>'
                 f'<select id="type" aria-label="Type de contenu"><option value="">Tous les types</option>{options}</select>'
                 f'<span id="n" class="rang" style="align-self:center"></span></div>'
                 f'<ul id="grille" class="grille"></ul></main>{_pied(maj)}')
        # « </ » fermerait la balise script si un titre de vidéo le contenait.
        js = json.dumps(donnees, ensure_ascii=False).replace("</", "<\\/")
        script = f'<script type="application/json" id="donnees">{js}</script><script>{SCRIPT}</script>'
        (DOSSIER_SITE / f"{i.id}.html").write_text(_page(f"{i.titre} — Hugues Tube", corps, i.description, script),
                                                   encoding="utf-8")

    (DOSSIER_SITE / "CNAME").write_text(DOMAINE + "\n", encoding="utf-8")
    (DOSSIER_SITE / ".nojekyll").write_text("", encoding="utf-8")
    favicon = RACINE / "site" / "favicon.svg"
    if favicon.exists():
        shutil.copy(favicon, DOSSIER_SITE / "favicon.svg")
