"""Validate wheel/sdist contents without importing the working tree."""

from __future__ import annotations

import argparse
import gettext
import io
import tarfile
import zipfile
from pathlib import Path

LANGUAGES = ("en", "fr", "eo")


def check_wheel(path: Path) -> None:
    with zipfile.ZipFile(path) as wheel:
        names = set(wheel.namelist())
        required = {"komandaro/py.typed"} | {
            f"komandaro/locale/{lang}/LC_MESSAGES/komandaro.mo" for lang in LANGUAGES
        }
        missing = required - names
        if missing:
            raise ValueError(f"wheel is missing: {sorted(missing)}")
        if not any(name.endswith(".dist-info/licenses/LICENSE") for name in names):
            raise ValueError("wheel is missing its license")
        for lang in LANGUAGES:
            raw = wheel.read(f"komandaro/locale/{lang}/LC_MESSAGES/komandaro.mo")
            translation = gettext.GNUTranslations(io.BytesIO(raw))
            if translation.gettext("nothing_to_undo") == "nothing_to_undo":
                raise ValueError(f"unusable {lang} catalogue")
    print(f"wheel checked: {path.name}")


def check_sdist(path: Path) -> None:
    with tarfile.open(path) as archive:
        names = {name.partition("/")[2] for name in archive.getnames()}
    required = {"pyproject.toml", "hatch_build.py", "tools/check_catalogues.py", "LICENSE"}
    required |= {f"src/komandaro/locale/{lang}/LC_MESSAGES/komandaro.po" for lang in LANGUAGES}
    missing = required - names
    if missing:
        raise ValueError(f"sdist is missing: {sorted(missing)}")
    print(f"sdist checked: {path.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", type=Path, default=Path("dist"))
    directory = parser.parse_args().directory
    wheels = sorted(directory.glob("*.whl"))
    sources = sorted(directory.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sources) != 1:
        raise ValueError("expected exactly one wheel and one sdist; use a clean output directory")
    check_wheel(wheels[0])
    check_sdist(sources[0])


if __name__ == "__main__":
    main()
