"""Reject untagged production publishing and version/tag mismatches."""

import os
import tomllib
from pathlib import Path


def validate_release(ref: str, target: str, version: str) -> None:
    if target not in {"testpypi", "pypi"}:
        raise ValueError("unknown publication target")
    expected = f"refs/tags/v{version}"
    if target == "pypi" and ref != expected:
        raise ValueError(f"PyPI publishing requires {expected!r}, not {ref!r}")
    if ref.startswith("refs/tags/v") and ref != expected:
        raise ValueError(f"tag does not match project version {version!r}")


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    validate_release(
        os.environ["GITHUB_REF"], os.environ["PUBLISH_TARGET"], project["project"]["version"]
    )
