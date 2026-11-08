# Hugues Tube

Les vidéos YouTube que les passionnés se recommandent vraiment, plutôt que celles que
l'algorithme pousse. Publié sur **https://tube.bronac.net**.

Inspiré de HackerTube (Karpathy, novembre 2026), qui a extrait de 20 ans de commentaires
Hacker News les vidéos citées encore et encore. Ici, même principe, restreint à trois centres d'intérêt :

| Centre d'intérêt | Fichier | Demi-vie d'une recommandation |
|---|---|---|
| Agents IA et automatisation | `interests/agents-ia.yaml` | 12 mois |
| Navigation hauturière | `interests/navigation-hauturiere.yaml` | 10 ans |
| Trading automatisé avec Claude | `interests/trading-claude.yaml` | 3 ans |

## La chaîne

```
collecte HN ──► liens YouTube (regex) ──► candidates (≥ 2 auteurs) ──► oEmbed YouTube ──► Claude ──► score ──► _site/
```

1. **Collecte** (`tube/collecte_hn.py`) : API publique Algolia de Hacker News, une requête par
   mot-clé × {youtube, youtu} × {commentaire, article}. Incrémentale : chaque passage ne
   récupère que la période depuis le précédent.
2. **Candidates** : seules les vidéos citées par au moins deux auteurs distincts continuent.
   Ce filtre gratuit évite d'envoyer à Claude des milliers de liens isolés.
3. **Métadonnées** (`tube/enrichissement.py`) : titre, chaîne, disponibilité via l'oEmbed
   public de YouTube, sans clé d'API.
4. **Classement** (`tube/classement.py`) : Claude lit chaque commentaire et dit si la vidéo est
   recommandée, simplement citée, critiquée ou hors sujet. API Message Batches (moitié prix),
   verdicts mis en cache dans `data/classements.json` : rien n'est classé deux fois.
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
python -m pytest -q
```

Sans `ANTHROPIC_API_KEY`, le classement est sauté : le site se construit quand même, sur le
seul nombre d'auteurs, et l'affiche en tête de page.

Variables facultatives : `HUGUES_TUBE_MODELE` (défaut `claude-opus-5-5`),
`HUGUES_TUBE_EFFORT` (défaut `low`).

## Ajouter un centre d'intérêt

Créer un YAML dans `interests/` sur le modèle des trois existants. L'`id` est la clé des fichiers
de `data/` et l'adresse de la page : ne plus le changer une fois publié.

## Publication

`.github/workflows/site.yml` tourne chaque lundi, sur demande, et à chaque push de code sur `main`.
Il versionne `data/` puis publie `_site/` sur GitHub Pages, avec le fichier `CNAME` pour
`tube.bronac.net`.
