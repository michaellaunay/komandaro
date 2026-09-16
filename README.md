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

Requires Python ≥ 3.12, `zope.interface` and `zope.schema`.

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

### Parameters: declare once, reuse everywhere

Instead of reading ad-hoc attributes from the context, a command declares
the parameters it needs with `zope.schema` fields. They are validated when
the command is instantiated, and they describe the command to every front
end (a CLI derives options, an HTML front end a form, an API a JSON schema).

```pycon
>>> from zope.interface import Interface
>>> from zope.schema import Int
>>> from komandaro import describe

>>> class IAddParameters(Interface):
...     amount = Int(title=_("Amount"), description=_("Value to add"), min=1)

>>> def add(context, amount):
...     context.value += amount
...     return context.value
>>> def undo_add(context, result, amount):
...     context.value -= amount
...     return context.value

>>> Add = SimpleCommandFactory(add, undo_add, _("Add"), schema=IAddParameters, id="add")
>>> calc = Calculator()
>>> Add(calc, amount=5).execute()
5
>>> [(p.name, p.type, p.title, p.required) for p in describe(Add.schema)]
[('amount', 'Int', 'Amount', True)]
>>> from komandaro import ParameterError
>>> try:
...     Add(calc, amount=0, colour="red")
... except ParameterError as error:
...     print([issue.name for issue in error.issues])
['colour', 'amount']

```

When the inverse of an operation cannot be derived from its result, give the
factory a `snapshot(context, **params)` function: its value is captured
before execution and handed to `undo` in place of the result.

### Registry and invoker

A `Registry` catalogues command classes by id (and group); an `Invoker`
runs them against a context, keeps the undo/redo history and notifies
subscribers. A front end is then a loop over `registry` and calls to
`invoker.run(...)`:

```pycon
>>> from komandaro import Registry, Invoker
>>> registry = Registry()
>>> registry.register(Add, group="math")
Entry(id='add', command=<class 'komandaro.command.AddCommand'>, group='math', tags=frozenset())

>>> calc = Calculator()
>>> invoker = Invoker(calc, registry)
>>> unsubscribe = invoker.subscribe(lambda event: print(event.kind, event.command))
>>> invoker.run("add", amount=2)
executed <AddCommand Add [executed]>
2
>>> invoker.run("add", amount=40)
executed <AddCommand Add [executed]>
42
>>> invoker.undo()
undone <AddCommand Add [undone]>
2
>>> invoker.redo()
redone <AddCommand Add [executed]>
42
>>> [command.params["amount"] for command in invoker.history]
[2, 40]

```

### Internationalisation

Names, descriptions, field titles and error messages are lazy gettext
messages. Nothing is translated until a front end asks, with the locale of
*its* user:

```pycon
>>> from komandaro import translate
>>> translate(Add.name, "fr")
'Add'

```

The library ships catalogues for its own messages (`en`, `fr`, `eo`); your
application registers its own domain with `make_gettext("myapp")` and its
own catalogues. Every error type (`CommandStateError`, `ParameterError`,
`RegistryError`, `HistoryError`) has a `translate(language)` method.

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

Phase 1 (0.1) made the core sound: state machine, macros, i18n, tests and
CI. Phase 2 (0.2, this release) describes commands: parameter schemas,
memento hook, registry, invoker with history and events. Phase 3 adds the
generated front ends (CLI, HTML, TUI, JSON/MCP). Details in
[`docs/en/architecture.md`](docs/en/architecture.md).

## License

Komandaro is free software released under the
[GNU Affero General Public License v3.0 or later](LICENSE).
Copyright © 2014–2026 Michaël Launay.
