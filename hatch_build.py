"""Compile translations in clean source, wheel, sdist and editable builds."""

from pathlib import Path
from runpy import run_path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        # Do not import komandaro: build isolation has no runtime dependencies.
        root = Path(self.root)
        helpers = run_path(str(root / "tools" / "check_catalogues.py"))
        helpers["compile_catalogues"](root / "src" / "komandaro" / "locale", "komandaro")
