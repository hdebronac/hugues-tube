# Règles de ce dépôt

Site statique qui recense les vidéos YouTube recommandées par des communautés de passionnés.
Voir [`README.md`](README.md) pour la chaîne et l'usage.

## Ce qui s'édite et ce qui se génère

| Édité à la main | Généré — ne pas toucher |
|---|---|
| `interests/*.yaml`, `tube/**`, `site/**`, `tests/**` | `_site/**` (ignoré par git) |
| | `data/**` (écrit par la chaîne, versionné pour l'incrémental) |

## Invariants

- **Auteurs distincts.** Un même auteur ne compte qu'une fois par vidéo. C'est ce qui sépare
  une recommandation collective d'une autopromotion.
- **Pas de verdict inventé.** Un refus, une réponse tronquée ou un JSON invalide de Claude
  laissent la mention « non_classe ». Ne jamais remplacer par un défaut « recommande ».
- **Les `id` des centres d'intérêt sont immuables** une fois publiés : ils nomment les fichiers
  de `data/` et les pages du site.
- **Aucun secret dans le dépôt.** La clé Anthropic vit dans les secrets GitHub Actions.
- Le client HTTP s'annonce sous un nom générique (`USER_AGENT` dans `tube/commun.py`) : pas
  d'adresse personnelle dans les en-têtes.

## Vérifier avant d'affirmer

- `python -m pytest -q` et `ruff check .` avant tout commit.
- Ouvrir le site produit (`_site/index.html`) : un contrôle automatique ne voit pas une page vide
  ou un titre mal échappé.

## Style

Français partout — code, commentaires, messages de commit, sorties de script. Commits atomiques,
format `<type>(portée): <description>`. Les commentaires expliquent pourquoi, pas quoi.
