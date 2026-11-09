# Hugues Tube

Les vidéos YouTube que les passionnés se recommandent vraiment, plutôt que celles que
l'algorithme pousse. Publié sur **https://tube.bronac.net**.

Inspiré de HackerTube (Karpathy, novembre 2026), qui a extrait de 20 ans de commentaires
Hacker News les vidéos citées encore et encore. Ici, même principe, étendu à Reddit et au forum
de voile Hisse et Oh, et restreint à trois centres d'intérêt :

| Centre d'intérêt | Fichier | Demi-vie d'une recommandation |
|---|---|---|
| Agents IA et automatisation | `interests/agents-ia.yaml` | 12 mois |
| Navigation hauturière | `interests/navigation-hauturiere.yaml` | 10 ans |
| Trading automatisé avec Claude | `interests/trading-claude.yaml` | 3 ans |

## La chaîne

```
collecte HN + Reddit + Hisse et Oh ──► liens YouTube (regex) ──► candidates (≥ 2 auteurs) ──► oEmbed YouTube ──► Claude ──► score ──► _site/
```

1. **Collecte**, trois sources déclarées dans chaque YAML de `interests/` :
   - **Hacker News** (`tube/collecte_hn.py`) : API publique Algolia, une requête par
     mot-clé × {youtube, youtu} × {commentaire, article}, tolérance aux fautes coupée et mot-clé
     revérifié localement. Incrémentale.
   - **Reddit** (`tube/collecte_reddit.py`) : archive publique [Arctic Shift](https://arctic-shift.photon-reddit.com).
     L'API officielle refuse les requêtes anonymes et la recherche plein texte d'Arctic Shift
     expire : on parcourt posts et commentaires des subreddits listés, du plus récent au plus
     ancien, sous budget de temps (`HUGUES_TUBE_BUDGET_REDDIT`, 40 min par défaut). L'historique
     se complète de semaine en semaine. Le subreddit sert de filtre thématique.
   - **Hisse et Oh** (`tube/collecte_heo.py`) : fils récents des sections listées (le site n'en
     expose que dix pages), 5 s entre requêtes comme l'exige son robots.txt, budget
     `HUGUES_TUBE_BUDGET_HEO` (25 min). Un fil n'est relu qu'au bout de six jours.
   - Écartés : **Cruisers Forum** et **YBW**, protégés par un défi anti-robots qu'on ne contourne pas.
2. **Candidates** : seules les vidéos citées par au moins deux auteurs distincts continuent.
   Ce filtre gratuit évite d'envoyer à Claude des milliers de liens isolés.
3. **Métadonnées** (`tube/enrichissement.py`) : titre, chaîne, disponibilité via l'oEmbed
   public de YouTube, sans clé d'API.
4. **Classement** (`tube/classement.py`) : Claude lit chaque commentaire et dit si la vidéo est
   recommandée, simplement citée, critiquée ou hors sujet. Appels directs en parallèle jusqu'à
   3 000 mentions (quelques minutes) ; au-delà, API Message Batches (moitié prix, mais jusqu'à
   24 h, lots repris d'un passage à l'autre). Verdicts mis en cache dans `data/classements.json` :
   rien n'est classé deux fois.
5. **Score** (`tube/score.py`) : somme, par auteur distinct, de sa recommandation la plus forte,
   pondérée par l'ancienneté (demi-vie propre au centre d'intérêt), bonus si la vidéo est citée
   sur plusieurs années.
6. **Site** (`tube/site.py`) : HTML statique, une page par centre d'intérêt, filtre et tri côté navigateur.

## Usage

```bash
pip install -e ".[claude,dev]"
python -m tube            # tout : collecte, classement, site
python -m tube collecte   # collecte seule
python -m tube site       # sans nouvelle collecte
python -m tube --interet agents-ia
python -m tube collecte --sources reddit   # une seule source (hn, reddit, heo)
python -m pytest -q
```

Sans `ANTHROPIC_API_KEY`, le classement est sauté : le site se construit quand même, sur le
seul nombre d'auteurs, et l'affiche en tête de page.

Variables facultatives : `HUGUES_TUBE_MODELE` (défaut `claude-haiku-5-5`),
`HUGUES_TUBE_EFFORT` (défaut `low`).

## Ajouter un centre d'intérêt

Créer un YAML dans `interests/` sur le modèle des trois existants. L'`id` est la clé des fichiers
de `data/` et l'adresse de la page : ne plus le changer une fois publié.

## Publication

`.github/workflows/site.yml` tourne chaque lundi, sur demande, et à chaque push de code sur `main`.
Il versionne `data/` puis publie `_site/` sur GitHub Pages, avec le fichier `CNAME` pour
`tube.bronac.net`.
