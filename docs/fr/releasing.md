# Publier sur PyPI

[English version](../en/releasing.md).

Le workflow `Release` utilise la publication de confiance PyPI (OIDC). Les jobs
de construction n'ont qu'un accès en lecture au dépôt. Seuls les jobs séparés
de publication reçoivent `id-token: write` ; ils téléchargent les distributions
sans extraire le dépôt. La publication attend les contrôles de qualité et
d'installation des roues sur la matrice configurée Python 3.12, 3.13 et 3.14.

## Éditeur et environnements

Pour un projet PyPI existant, configurez son éditeur de confiance dans les
paramètres de publication du projet. Un éditeur « en attente » ne sert qu'avant
le premier envoi ; ne présumez pas que le projet n'existe pas.

| Champ | Production | Test |
|---|---|---|
| Propriétaire / dépôt | `michaellaunay` / `komandaro` | identiques |
| Workflow | `release.yml` | identique |
| Environnement | `pypi` | `testpypi` |
| Projet | `komandaro` | `komandaro` |

Créez les environnements GitHub correspondants. Restreignez la production aux
étiquettes de version, exigez une validation indépendante quand elle est
disponible, et protégez la branche principale ainsi que les étiquettes de
publication. Ces réglages sont administratifs : le commit du workflow ne les
configure pas et ne prouve pas leur présence.

Les actions sont épinglées sur des SHA complets ; Dependabot propose leurs mises
à jour. Relisez ces propositions au lieu de remettre des références majeures
mobiles. Les dépendances Python de construction et de développement ne sont pas
pour autant totalement verrouillées.

## Préparer la version

Ne republiez pas 0.3.0. Choisissez une nouvelle version, modifiez `pyproject.toml`
et `src/komandaro/__init__.py`, puis déplacez les entrées Unreleased du changelog.
Relisez les [changements de contrat](reliability.md) : contrôle d'undo/redo,
identité des contextes, macros inutilisables et isolation des observateurs.

Depuis une copie propre et un environnement virtuel :

```bash
python -m pip install -e ".[dev]" build twine
python tools/check_catalogues.py
ruff check .
ruff format --check .
mypy
python -m pytest --cov
python -m build
python -m twine check --strict dist/*
python tools/check_dist.py
python tools/smoke_wheel.py
```

Utilisez un répertoire `dist/` vide ; archivez ou supprimez uniquement les anciennes
sorties de construction selon votre besoin. `pybabel compile` n'est plus un
prérequis manuel. Le hook isolé régénère les MO, y compris pour une roue reconstruite
depuis le sdist. Le contrôle d'installation crée un environnement temporaire,
installe la roue et ses dépendances, puis l'importe hors dépôt avec `python -I`.

## TestPyPI et production

Un lancement manuel `target=testpypi` accepte une branche ou une étiquette de
version concordante. TestPyPI est indépendant de PyPI et peut ne pas contenir
toutes les dépendances. Pour examiner la roue de test publiée, téléchargez cette
version exacte sans dépendances depuis TestPyPI, puis installez le fichier local
dans un environnement neuf en résolvant ses dépendances sur l'index habituel.
Ne mélangez pas sans discernement les deux index.

La production exige une étiquette exacte `v<project.version>`, y compris lors
d'un lancement manuel. `target=pypi` depuis une branche est refusé avant la
construction. Une étiquette ne correspondant pas à la version est refusée pour
les deux index. Après les vérifications, créez et poussez seulement l'étiquette
prévue, par exemple depuis les métadonnées déjà mises à jour :

```bash
version="$(python -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')"
git tag -a "v$version" -m "Release $version"
git push origin "v$version"
```

Vérifiez que l'étiquette pointe vers le commit relu contenant le workflow durci.
Ne déplacez pas une étiquette déjà publiée. Une version publiée ne se réutilise
pas pour renvoyer des fichiers corrigés : créez une nouvelle version. Les patchs
ne créent aucune étiquette, ne poussent aucun commit, ne changent aucune protection
administrative et ne publient rien par eux-mêmes.

Après publication, installez la version exacte dans un nouvel environnement et
vérifiez imports, traductions et cycle commande/annulation/rétablissement. La roue
construite sous Python 3.12 est publiée après réussite de toute la matrice.

Références officielles : [éditeurs de confiance PyPI](https://docs.pypi.org/trusted-publishers/)
et [environnements GitHub](https://docs.github.com/en/actions/deployment/targeting-different-environments/using-environments-for-deployment).
