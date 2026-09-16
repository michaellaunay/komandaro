"""Shared fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest
from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po

from komandaro.i18n import DEFAULT_LOCALEDIR, DOMAIN


class Calculator:
    """A tiny mutable context used throughout the tests."""

    def __init__(self, value: int = 0) -> None:
        self.value = value
        self.log: list[str] = []


@pytest.fixture
def calc() -> Calculator:
    return Calculator()


@pytest.fixture(scope="session")
def localedir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Compile the versioned .po catalogues into a temporary locale dir.

    The .mo files are not versioned; CI compiles them with ``pybabel`` before
    the tests, but this fixture makes the i18n tests self-sufficient.
    """
    out = tmp_path_factory.mktemp("locale")
    for po in DEFAULT_LOCALEDIR.glob(f"*/LC_MESSAGES/{DOMAIN}.po"):
        lang = po.parent.parent.name
        target = out / lang / "LC_MESSAGES"
        target.mkdir(parents=True)
        with po.open("rb") as fh:
            catalog = read_po(fh, locale=lang)
        with (target / f"{DOMAIN}.mo").open("wb") as fh:
            write_mo(fh, catalog)
    return out
