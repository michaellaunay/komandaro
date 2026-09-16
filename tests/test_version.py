"""The version is declared twice; they must agree (the release workflow checks the tag)."""

from __future__ import annotations

import tomllib
from pathlib import Path

import komandaro


def test_dunder_version_matches_pyproject():
    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    with pyproject.open("rb") as fh:
        declared = tomllib.load(fh)["project"]["version"]
    assert komandaro.__version__ == declared
