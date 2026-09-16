"""Shared fixtures."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po

from komandaro.i18n import DEFAULT_LOCALEDIR, DOMAIN

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_LOCALEDIR = ROOT / "examples" / "notebook" / "locale"


class Calculator:
    """A tiny mutable context used throughout the tests."""

    def __init__(self, value: int = 0) -> None:
        self.value = value
        self.log: list[str] = []


@pytest.fixture
def calc() -> Calculator:
    return Calculator()


def compile_catalogues(localedir: Path, domain: str) -> None:
    """Compile every ``<lang>/LC_MESSAGES/<domain>.po`` under *localedir* in place."""
    for po in localedir.glob(f"*/LC_MESSAGES/{domain}.po"):
        with po.open("rb") as fh:
            catalog = read_po(fh, locale=po.parent.parent.name)
        with po.with_suffix(".mo").open("wb") as fh:
            write_mo(fh, catalog)


@pytest.fixture(scope="session", autouse=True)
def english_environment() -> Iterator[None]:
    """Pin the process locale used by gettext when no language is given.

    ``translate(message)`` with ``language=None`` follows ``LANGUAGE``,
    ``LC_ALL``, ``LC_MESSAGES`` and ``LANG``; on a French machine the
    untranslated expectations of the tests would otherwise fail.
    ``LANGUAGE`` takes precedence over the other three, so it is enough.
    """
    saved = os.environ.get("LANGUAGE")
    os.environ["LANGUAGE"] = "en"
    try:
        yield
    finally:
        if saved is None:
            os.environ.pop("LANGUAGE", None)
        else:
            os.environ["LANGUAGE"] = saved


@pytest.fixture(scope="session", autouse=True)
def compiled_catalogues() -> Path:
    """Build the git-ignored ``.mo`` files so that every test (doctests included)
    can translate, whether or not ``pybabel compile`` was run beforehand."""
    compile_catalogues(DEFAULT_LOCALEDIR, DOMAIN)
    compile_catalogues(EXAMPLE_LOCALEDIR, "notebook")
    return DEFAULT_LOCALEDIR


@pytest.fixture(scope="session")
def localedir(compiled_catalogues: Path) -> Path:
    return compiled_catalogues
