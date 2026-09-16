"""Check complete gettext identifiers and translation placeholders, portably."""

from __future__ import annotations

from pathlib import Path
from string import Template
from typing import Any

from babel.messages import frontend
from babel.messages.catalog import Catalog
from babel.messages.extract import extract_from_dir
from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po

ROOT = Path(__file__).resolve().parent.parent


def read_catalogue(path: Path, locale: str | None = None) -> Catalog:
    with path.open("rb") as stream:
        return read_po(stream, locale=locale, abort_invalid=True)


def entries(catalogue: Catalog) -> dict[tuple[Any, Any], Any]:
    """Include contexts, multiline ids and plurals; omit the metadata header."""
    return {(message.context, message.id): message for message in catalogue if message.id}


def placeholders(text: str) -> set[str]:
    template = Template(text)
    if not template.is_valid():
        raise ValueError(f"invalid string.Template syntax: {text!r}")
    return set(template.get_identifiers())


def check_translations(template: Catalog, english: Catalog, translated: Catalog) -> None:
    expected = entries(template)
    defaults = entries(english)
    messages = entries(translated)
    for key in expected:
        default = defaults.get(key)
        if default is None or default.fuzzy or not default.string:
            raise ValueError(f"missing or fuzzy English translation: {key!r}")
        default_strings = (default.string,) if isinstance(default.string, str) else default.string
        if not all(default_strings):
            raise ValueError(f"incomplete English plural translation: {key!r}")
        message = messages.get(key)
        if message is None or not message.string:
            continue  # Non-English catalogues may deliberately fall back to English.
        if message.fuzzy:
            raise ValueError(f"fuzzy translation: {key!r}")
        strings = (message.string,) if isinstance(message.string, str) else message.string
        # Plural forms can differ by locale; all forms share their substitutions.
        required = set().union(*(placeholders(text) for text in default_strings))
        for text in strings:
            if text and placeholders(text) != required:
                raise ValueError(f"placeholder mismatch for {key!r}: {text!r}")


def compile_catalogues(localedir: Path, domain: str) -> None:
    paths = sorted(localedir.glob(f"*/LC_MESSAGES/{domain}.po"))
    if not paths:
        raise ValueError(f"no catalogues for {domain!r} in {localedir}")
    template = read_catalogue(localedir / f"{domain}.pot")
    english = read_catalogue(localedir / "en" / "LC_MESSAGES" / f"{domain}.po", "en")
    for path in paths:
        catalogue = read_catalogue(path, path.parent.parent.name)
        check_translations(template, english, catalogue)
        problems = list(catalogue.check())
        if problems:
            raise ValueError(f"invalid catalogue {path}: {problems}")
        with path.with_suffix(".mo").open("wb") as stream:
            write_mo(stream, catalogue)


def check_domain(root: Path, source: Path, localedir: Path, domain: str) -> None:
    with (root / "babel.cfg").open(encoding="utf-8") as stream:
        parse_mapping = getattr(frontend, "parse_mapping_cfg", None) or frontend.parse_mapping
        methods, options = parse_mapping(stream)
    fresh = Catalog()
    for _filename, _line, message, comments, context in extract_from_dir(
        source, method_map=methods, options_map=options
    ):
        fresh.add(message, auto_comments=comments, context=context)
    saved = read_catalogue(localedir / f"{domain}.pot")
    if entries(fresh).keys() != entries(saved).keys():
        missing = entries(fresh).keys() - entries(saved).keys()
        stale = entries(saved).keys() - entries(fresh).keys()
        raise ValueError(f"{domain}.pot is stale; missing={missing!r}, obsolete={stale!r}")
    compile_catalogues(localedir, domain)
    print(f"{domain}: {len(entries(saved))} message ids and catalogues checked")


def main() -> None:
    check_domain(ROOT, ROOT / "src", ROOT / "src/komandaro/locale", "komandaro")
    check_domain(ROOT, ROOT / "examples/notebook", ROOT / "examples/notebook/locale", "notebook")


if __name__ == "__main__":
    main()
