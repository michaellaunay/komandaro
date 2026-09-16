# Releasing to PyPI

[Version française](../fr/releasing.md).

The `Release` workflow publishes through PyPI trusted publishing (OIDC). Build
jobs have read-only repository access; only the separate publish jobs receive
`id-token: write`. They download distributions and do not check out the repository.
A release is published only after quality gates and wheel-install checks pass
on the configured Python 3.12, 3.13 and 3.14 matrix.

## Publisher and environment setup

For an existing PyPI project, configure its trusted publisher in the project's
publishing settings. A pending publisher is only needed before a project's first
upload; do not assume that the project is absent. Configure:

| Field | Production | Test |
|---|---|---|
| Owner / repository | `michaellaunay` / `komandaro` | same |
| Workflow | `release.yml` | same |
| Environment | `pypi` | `testpypi` |
| Project | `komandaro` | `komandaro` |

Create the matching GitHub environments. Restrict production deployment refs to
version tags, require an independent reviewer where available, and protect the
main branch and release tags with repository rules. These are administrator
settings: committing the workflow does not configure or prove them.

Actions are pinned by full commit SHA. Dependabot proposes action updates; review
those changes instead of replacing the pins with moving major tags. Python build
and development dependencies are not a fully locked supply chain.

## Prepare a version

Do not republish 0.3.0. Select a new version, update both `pyproject.toml` and
`src/komandaro/__init__.py`, and move the relevant Unreleased changelog entries.
Review [migration and security changes](reliability.md), particularly authorization
on undo/redo, context identity, broken macros and observer exception isolation.

In a clean checkout and virtual environment:

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

Use an empty `dist/` directory; archive or remove only previous generated build
outputs as appropriate. No manual `pybabel compile` step is needed. The isolated
build hook regenerates MO files, including when rebuilding a wheel from the sdist.
The wheel smoke check installs runtime dependencies in a temporary environment,
then imports the installed wheel with `python -I` outside the checkout.

## TestPyPI and production

A manual `target=testpypi` run may use a branch or a matching version tag. TestPyPI
is a separate index and may not contain all runtime dependencies. To inspect a
published test wheel, download that exact version without dependencies from
TestPyPI, then install that local wheel in a fresh environment using the usual
index for its dependencies. Do not mix public and test indexes indiscriminately.

Production requires an exact tag `v<project.version>` for both tag-triggered and
manual runs. Selecting `target=pypi` on a branch is rejected before building.
A version-mismatched tag is rejected for either index. After all checks pass,
create and push only the intended new tag, for example using the already updated
project metadata:

```bash
version="$(python -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')"
git tag -a "v$version" -m "Release $version"
git push origin "v$version"
```

Ensure that the tag points to the reviewed commit containing the hardened workflow.
Do not move an already published release tag. A published version cannot be reused
for a corrected upload; publish a new version. These patches do not create a tag,
push commits, change environment protections or publish anything automatically.

After publishing, install the exact released version in a new environment and
check imports, translations and a complete command/undo/redo cycle. The wheel
built on Python 3.12 is the artifact uploaded after all matrix jobs succeed.

Official references: [PyPI trusted publishers](https://docs.pypi.org/trusted-publishers/)
and [GitHub deployment environments](https://docs.github.com/en/actions/deployment/targeting-different-environments/using-environments-for-deployment).
