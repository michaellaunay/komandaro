"""A command-line front end generated from the notebook registry.

This is deliberately small (and hand-written): it is the shape of what
phase 3 will provide as a reusable ``komandaro.cli``.  Everything it knows
about the application comes from the registry: the list of sub-commands,
their options and help texts all derive from ``Entry`` and
``ParameterInfo``.

Usage::

    python -m examples.notebook.cli add --text "Buy milk"
    python -m examples.notebook.cli --lang fr             # interactive session
    python -m examples.notebook.cli --lang fr --help

In the interactive session you can type ``add --text "Buy milk"``, ``mv
--position 1 --text "Buy oat milk"``, ``undo``, ``redo``, ``list``,
``quit``.  The command line is parsed with ``shlex``, so quotes work.
"""

from __future__ import annotations

import argparse
import shlex
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from komandaro import (
    CommandStateError,
    HistoryError,
    Invoker,
    ParameterError,
    ParameterInfo,
    Registry,
    RegistryError,
    translate,
)

from .notebook import Notebook, make_registry

HERE = Path(__file__).parent
LOCALEDIR = HERE / "locale"  # application catalogues (domain "notebook")

# How a zope.schema field type becomes an argparse option.
CONVERTERS: dict[str, Callable[[str], Any]] = {
    "Int": int,
    "Float": float,
    "TextLine": str,
    "Text": str,
    "Bool": lambda s: s.lower() in {"1", "true", "yes", "on"},
}


def tr(message: str, lang: str | None) -> str:
    """Translate a message from any domain (library or application)."""
    return translate(
        message, lang, LOCALEDIR if getattr(message, "domain", "") == "notebook" else None
    )


def add_option(parser: argparse.ArgumentParser, info: ParameterInfo, lang: str | None) -> None:
    kwargs: dict[str, Any] = {
        "help": tr(info.description or info.title, lang),
        "required": info.required,
        "dest": info.name,
    }
    if info.type == "List":
        kwargs["nargs"] = "+"
        kwargs["type"] = str
    elif info.choices:
        kwargs["choices"] = info.choices
    else:
        kwargs["type"] = CONVERTERS.get(info.type, str)
    if info.default is not None:
        kwargs["default"] = info.default
    parser.add_argument(f"--{info.name}", **kwargs)


def build_parser(registry: Registry, lang: str | None) -> argparse.ArgumentParser:
    """One sub-command per registry entry, one option per parameter."""
    parser = argparse.ArgumentParser(prog="notebook", description=tr("Notebook", lang))
    parser.add_argument("--lang", default=lang, help="language code, e.g. fr")
    sub = parser.add_subparsers(dest="command")
    for entry in registry:
        p = sub.add_parser(
            entry.id, help=tr(entry.name, lang), description=tr(entry.description, lang)
        )
        for info in entry.parameters:
            add_option(p, info, lang)
    sub.add_parser("undo", help="undo the last command")
    sub.add_parser("redo", help="redo the last undone command")
    sub.add_parser("list", help="show the notebook")
    sub.add_parser("quit", help="leave the session")
    return parser


class Session:
    """Runs command lines against one notebook, with undo/redo."""

    def __init__(self, notebook: Notebook | None = None, lang: str | None = None) -> None:
        self.notebook = notebook or Notebook()
        self.lang = lang
        self.registry = make_registry()
        self.invoker = Invoker(self.notebook, self.registry)
        self.parser = build_parser(self.registry, lang)
        self.invoker.subscribe(
            lambda e: self.out(f"[{e.kind}] {tr(e.command.name, lang)}") if e.command else None
        )

    def out(self, text: str) -> None:
        print(text)

    def run_line(self, line: str) -> bool:
        """Execute one command line; return False when the session should end."""
        try:
            ns = self.parser.parse_args(shlex.split(line))
        except SystemExit:  # argparse already printed help or the error
            return True
        if ns.command in (None, "list"):
            self.out(str(self.notebook))
        elif ns.command == "quit":
            return False
        elif ns.command == "undo":
            self.safely(self.invoker.undo)
        elif ns.command == "redo":
            self.safely(self.invoker.redo)
        else:
            params = {
                k: v for k, v in vars(ns).items() if k not in {"command", "lang"} and v is not None
            }
            self.safely(lambda: self.invoker.run(ns.command, **params))
        return True

    def safely(self, action: Callable[[], Any]) -> None:
        try:
            result = action()
            if result is not None:
                self.out(str(result))
        except ParameterError as error:
            for name, message in error.translate(self.lang).items():
                self.out(f"! {name}: {message}")
        except (CommandStateError, HistoryError, RegistryError) as error:
            self.out(f"! {error.translate(self.lang)}")
        except (IndexError, ValueError) as error:
            self.out(f"! {type(error).__name__}: {error}")

    def loop(self, stdin: Any = sys.stdin) -> None:
        self.out("notebook — type 'list', 'undo', 'redo', 'quit' or a command; --help for details")
        for line in stdin:
            if not self.run_line(line):
                break


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    lang = None
    if "--lang" in argv:
        i = argv.index("--lang")
        lang = argv[i + 1]
        del argv[i : i + 2]
    session = Session(lang=lang)
    if argv:
        session.run_line(shlex.join(argv))
    else:
        session.loop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
