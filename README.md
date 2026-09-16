# Komandaro

[![CI](https://github.com/michaellaunay/komandaro/actions/workflows/ci.yml/badge.svg)](https://github.com/michaellaunay/komandaro/actions/workflows/ci.yml)
[![License: AGPL-3.0-or-later](https://img.shields.io/badge/license-AGPL--3.0--or--later-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](pyproject.toml)

**Komandaro** (Esperanto: *a set of commands*) is a small Python toolkit
implementing the *Command* design pattern with undo/redo, composite
commands and built-in internationalisation.

Its purpose is to let you **write application logic once, as commands, and
expose it through several user interfaces** — a command line, an HTML
form, a TUI, a JSON API or an AI agent tool — without duplicating or
touching that logic.

> Komandaro is the 2026 rebirth of `ecreall.command`, a 2014 prototype.
> See [`docs/en/architecture.md`](docs/en/architecture.md) (English) or
> [`docs/fr/architecture.md`](docs/fr/architecture.md) (French) for the
> design and the roadmap.

## Install

```bash
pip install komandaro            # library only
pip install "komandaro[dev]"     # + tests, babel, ruff, mypy
```

Requires Python ≥ 3.12 and `zope.interface`.

## Five-minute tour

A command is built from a *do* function and its inverse *undo* function.
Both receive the **context** — any object your application chooses.

```pycon
>>> from komandaro import SimpleCommandFactory
>>> from komandaro.i18n import _

>>> class Calculator:
...     def __init__(self, value=0):
...         self.value = value

>>> def add(context):
...     context.value += context.amount
...     return context.value
>>> def undo_add(context, result):
...     context.value -= context.amount
...     return context.value

>>> Add = SimpleCommandFactory(add, undo_add, _("Add"), _("Add an amount to the value"))

```

`SimpleCommandFactory` returns a **class**. Instantiate it once per
execution, bound to a context:

```pycon
>>> calc = Calculator()
>>> calc.amount = 5
>>> cmd = Add(calc)
>>> cmd
<AddCommand Add [ready]>
>>> cmd.execute()
5
>>> cmd.undo()
0
>>> cmd.redo()
5

```

A command runs exactly once. Its **state** is carried by marker
interfaces that front ends can query:

```pycon
>>> from komandaro import ICommand, IExecutedCommand, CommandStateError
>>> ICommand.providedBy(cmd), IExecutedCommand.providedBy(cmd)
(False, True)
>>> try:
...     cmd.execute()
... except CommandStateError as error:
...     print(error)
Command Add has already been executed

```

### Macros

A `Macro` groups commands. They run in order, undo in reverse order, and
the macro is **atomic**: if one child fails, the children already run are
undone before the exception propagates.

```pycon
>>> from komandaro import Macro
>>> calc = Calculator()
>>> calc.amount = 5
>>> batch = Macro(calc, [Add(calc), Add(calc), Add(calc)], name=_("Add three times"))
>>> batch.execute()
[5, 10, 15]
>>> batch.undo()
[10, 5, 0]
>>> calc.value
0

```

### Internationalisation

Names, descriptions and error messages are lazy gettext messages. Nothing
is translated until a front end asks, with the locale of *its* user:

```pycon
>>> from komandaro import translate
>>> translate(batch.name, "fr")
'Add three times'

```

The library ships catalogues for its own messages (`en`, `fr`, `eo`):

```pycon
>>> error = CommandStateError(_("Command %(name)s has already been executed"), name="Add")
>>> print(error.translate("fr"))  # doctest: +SKIP
La commande Add a déjà été exécutée

```

Your application registers its own domain with `make_gettext("myapp")`
and its own catalogues; see the architecture document.

## Development

```bash
git clone git@github.com:michaellaunay/komandaro.git && cd komandaro
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pybabel compile -d src/komandaro/locale -D komandaro   # build the .mo files
pytest                                                  # tests + README doctests
ruff check . && ruff format --check . && mypy
```

Updating translations after changing a `_()` string:

```bash
pybabel extract -F babel.cfg -o src/komandaro/locale/komandaro.pot src
pybabel update -i src/komandaro/locale/komandaro.pot -d src/komandaro/locale -D komandaro
# edit src/komandaro/locale/<lang>/LC_MESSAGES/komandaro.po, then
pybabel compile -d src/komandaro/locale -D komandaro
```

## Roadmap

Phase 1 (this release) makes the core sound: state machine, macros,
i18n, tests and CI. Next phases add parameter schemas, an invoker with
history, a command registry, and generated front ends (CLI, HTML, TUI,
JSON/MCP). Details in [`docs/en/architecture.md`](docs/en/architecture.md).

## License

Komandaro is free software released under the
[GNU Affero General Public License v3.0 or later](LICENSE).
Copyright © 2014–2026 Michaël Launay.
