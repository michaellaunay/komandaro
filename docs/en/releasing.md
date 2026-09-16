# Releasing to PyPI

*Version française : [`docs/fr/releasing.md`](../fr/releasing.md)*

Komandaro is published by the `Release` GitHub Actions workflow
(`.github/workflows/release.yml`) using PyPI **trusted publishing**: PyPI
trusts a short-lived OpenID Connect token issued by GitHub for that exact
repository, workflow and environment. No API token is created, stored or
rotated.

## One-time setup

### 1. Register the publisher on PyPI (before the first upload)

The project does not exist on PyPI yet, so register a *pending* publisher —
it creates the project on the first successful upload.

1. Log in to <https://pypi.org>, open *Your account → Publishing*.
2. Under *Add a new pending publisher → GitHub*, fill in:

   | field | value |
   |---|---|
   | PyPI project name | `komandaro` |
   | Owner | `michaellaunay` |
   | Repository name | `komandaro` |
   | Workflow name | `release.yml` |
   | Environment name | `pypi` |

3. Click *Add*. The publisher is bound to the account that registers it:
   that account becomes the project owner.

Repeat on <https://test.pypi.org> with environment name `testpypi` if you
want dry runs (recommended for the first release).

### 2. Create the GitHub environments

In the repository, *Settings → Environments → New environment*: create
`pypi` and, optionally, `testpypi`. For `pypi`, consider *Required
reviewers* (yourself): the publish job then waits for a click, which is a
cheap safeguard against an accidental tag push.

### 3. Make sure the workflow is on the tagged commit

A tag triggers the workflow *of the commit it points to*. The
`release.yml` file must therefore be committed before the tag is created.

## Every release

1. Bump the version in **both** `pyproject.toml` and
   `src/komandaro/__init__.py` (`tests/test_version.py` keeps them
   consistent) and add the `CHANGELOG.md` entry.
2. Commit, then run the checks locally:

   ```bash
   python -m pytest
   ruff check . && ruff format --check . && mypy
   ```

3. Optional dry run: *Actions → Release → Run workflow → target: testpypi*,
   then `pip install -i https://test.pypi.org/simple/ komandaro` in a
   scratch virtualenv.
4. Tag and push:

   ```bash
   git tag v0.2.1
   git push && git push --tags
   ```

The workflow then: checks that the tag matches `pyproject.toml`, runs the
test suite, compiles the gettext catalogues, builds the sdist and the
wheel, verifies the metadata (`twine check --strict`) and that the wheel
ships the `.mo` files and `py.typed`, and publishes.

A tag created before `release.yml` existed never triggers the workflow
and needs no action: `v0.2.0` is such a git-only tag, it was never
published, and the first version on PyPI is `0.2.1`. Only if a *future*
tag is pushed by mistake before its commit is right should it be moved
(`git tag -d vX.Y.Z`, `git push --delete origin vX.Y.Z`, re-tag) — and
only while nothing was published under that version: once a version is on
PyPI it can never be re-uploaded, only superseded by a higher one.

## Publishing by hand (fallback)

Only if the workflow cannot run. Use an API token scoped to the project,
never your password:

```bash
pip install build twine
pybabel compile -d src/komandaro/locale -D komandaro
rm -rf dist && python -m build && twine check --strict dist/*
TWINE_USERNAME=__token__ TWINE_PASSWORD=pypi-... twine upload dist/*
```

(`--repository testpypi` for a dry run, with a TestPyPI token.)

## After the first release

* The badge and the *Homepage* link on PyPI come from `pyproject.toml`
  (`[project.urls]`); the long description is `README.md`, whose links are
  absolute so that they work on PyPI.
* Add `python -m pip install komandaro` to your own checklist: install the
  published wheel in a fresh virtualenv and run the tutorial's first block.
