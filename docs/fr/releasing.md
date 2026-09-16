# Publier sur PyPI

*English version: [`docs/en/releasing.md`](../en/releasing.md)*

Komandaro est publié par le workflow GitHub Actions `Release`
(`.github/workflows/release.yml`) grâce à la **publication de confiance**
(*trusted publishing*) de PyPI : PyPI fait confiance à un jeton OpenID
Connect de courte durée émis par GitHub pour ce dépôt, ce workflow et cet
environnement précis. Aucun jeton d'API n'est créé, stocké ni renouvelé.

## Mise en place, une seule fois

### 1. Déclarer l'éditeur sur PyPI (avant le premier envoi)

Le projet n'existe pas encore sur PyPI : on déclare donc un éditeur « en
attente » (*pending publisher*), qui créera le projet au premier envoi
réussi.

1. Connectez-vous sur <https://pypi.org>, ouvrez *Your account →
   Publishing*.
2. Sous *Add a new pending publisher → GitHub*, renseignez :

   | champ | valeur |
   |---|---|
   | PyPI project name | `komandaro` |
   | Owner | `michaellaunay` |
   | Repository name | `komandaro` |
   | Workflow name | `release.yml` |
   | Environment name | `pypi` |

3. Cliquez sur *Add*. L'éditeur est lié au compte qui le déclare : ce
   compte devient propriétaire du projet.

Répétez sur <https://test.pypi.org> avec l'environnement `testpypi` pour
disposer d'un envoi à blanc (recommandé pour la première publication).

### 2. Créer les environnements GitHub

Dans le dépôt, *Settings → Environments → New environment* : créez `pypi`
et, optionnellement, `testpypi`. Pour `pypi`, envisagez *Required
reviewers* (vous-même) : le job de publication attend alors un clic, ce
qui protège à peu de frais d'une étiquette poussée par erreur.

### 3. S'assurer que le workflow est dans le commit étiqueté

Une étiquette déclenche le workflow *du commit qu'elle désigne*. Le fichier
`release.yml` doit donc être commité avant de créer l'étiquette.

## À chaque version

1. Incrémentez la version dans **les deux** fichiers `pyproject.toml` et
   `src/komandaro/__init__.py` (`tests/test_version.py` garantit leur
   cohérence) et ajoutez l'entrée de `CHANGELOG.md`.
2. Commitez, puis lancez les vérifications localement :

   ```bash
   python -m pytest
   ruff check . && ruff format --check . && mypy
   ```

3. Envoi à blanc optionnel : *Actions → Release → Run workflow → target:
   testpypi*, puis `pip install -i https://test.pypi.org/simple/ komandaro`
   dans un virtualenv jetable.
4. Étiquetez et poussez :

   ```bash
   git tag v0.2.1
   git push && git push --tags
   ```

Le workflow vérifie alors que l'étiquette correspond à `pyproject.toml`,
exécute la suite de tests, compile les catalogues gettext, construit la
sdist et la roue, contrôle les métadonnées (`twine check --strict`) ainsi
que la présence des `.mo` et de `py.typed` dans la roue, puis publie.

Une étiquette créée avant l'existence de `release.yml` ne déclenche jamais
le workflow et ne demande aucune action : `v0.2.0` est une étiquette git
de ce type, jamais publiée, et la première version sur PyPI est `0.2.1`.
Ce n'est que si une *future* étiquette est poussée par erreur avant que son
commit ne soit prêt qu'il faut la déplacer (`git tag -d vX.Y.Z`,
`git push --delete origin vX.Y.Z`, ré-étiqueter) — et seulement tant que
rien n'a été publié sous cette version : une fois sur PyPI, une version ne
peut jamais être renvoyée, seulement remplacée par une version supérieure.

## Publication à la main (secours)

Seulement si le workflow ne peut pas s'exécuter. Utilisez un jeton d'API
limité au projet, jamais votre mot de passe :

```bash
pip install build twine
pybabel compile -d src/komandaro/locale -D komandaro
rm -rf dist && python -m build && twine check --strict dist/*
TWINE_USERNAME=__token__ TWINE_PASSWORD=pypi-... twine upload dist/*
```

(`--repository testpypi` pour un envoi à blanc, avec un jeton TestPyPI.)

## Après la première publication

* Le badge et le lien *Homepage* sur PyPI viennent de `pyproject.toml`
  (`[project.urls]`) ; la description longue est `README.md`, dont les
  liens sont absolus pour fonctionner sur PyPI.
* Ajoutez `python -m pip install komandaro` à votre liste de contrôle :
  installez la roue publiée dans un virtualenv neuf et exécutez le premier
  bloc du tutoriel.
