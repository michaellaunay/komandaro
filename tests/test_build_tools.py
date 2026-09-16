"""Regression tests for semantic catalogue checks and isolated build hooks."""

import gettext
import io
from pathlib import Path

import pytest
from babel.messages.catalog import Catalog
from babel.messages.pofile import write_po
from tools.check_catalogues import check_translations, compile_catalogues, entries
from tools.check_dist import check_wheel


def test_complete_ids_include_multiline_context_and_plural():
    catalogue = Catalog()
    catalogue.add("first line\nsecond line", context="help")
    catalogue.add(("one", "many"))
    assert set(entries(catalogue)) == {("help", "first line\nsecond line"), (None, ("one", "many"))}


def test_mismatched_translation_placeholder_is_rejected():
    template, english, french = Catalog(), Catalog(), Catalog()
    template.add("greeting")
    english.add("greeting", "Hello ${name}")
    french.add("greeting", "Bonjour ${user}")
    with pytest.raises(ValueError, match="placeholder mismatch"):
        check_translations(template, english, french)


def test_missing_non_english_entry_can_fall_back():
    template, english = Catalog(), Catalog()
    template.add("greeting")
    english.add("greeting", "Hello ${name}")
    check_translations(template, english, Catalog())


def test_missing_english_entry_is_rejected():
    template = Catalog()
    template.add("greeting")
    with pytest.raises(ValueError, match="English"):
        check_translations(template, Catalog(), Catalog())


def test_compilation_starts_with_po_files_only(tmp_path):
    template = Catalog()
    template.add("greeting")
    english = Catalog(locale="en")
    english.add("greeting", "Hello ${name}")
    english_path = tmp_path / "en/LC_MESSAGES/demo.po"
    english_path.parent.mkdir(parents=True)
    for path, catalogue in ((tmp_path / "demo.pot", template), (english_path, english)):
        with path.open("wb") as stream:
            write_po(stream, catalogue)
    assert not list(tmp_path.rglob("*.mo"))
    compile_catalogues(tmp_path, "demo")
    translation = gettext.GNUTranslations(io.BytesIO(english_path.with_suffix(".mo").read_bytes()))
    assert translation.gettext("greeting") == "Hello ${name}"


def test_empty_wheel_is_rejected(tmp_path):
    import zipfile

    path = tmp_path / "empty.whl"
    with zipfile.ZipFile(path, "w"):
        pass
    with pytest.raises(ValueError, match="missing"):
        check_wheel(path)


def test_hook_and_helpers_are_included_in_source_build():
    import tomllib

    root = Path(__file__).resolve().parent.parent
    project = tomllib.loads((root / "pyproject.toml").read_text())
    config = project["tool"]["hatch"]["build"]
    assert config["hooks"]["custom"]["path"] == "hatch_build.py"
    assert {"hatch_build.py", "tools"} <= set(config["targets"]["sdist"]["include"])
    assert any(
        requirement.startswith("babel") for requirement in project["build-system"]["requires"]
    )
