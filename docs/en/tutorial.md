# Tutorial — from a function to an undoable, multi-interface command

*Version française : [`docs/fr/tutorial.md`](../fr/tutorial.md)*

In this tutorial you build the logic of a small **notebook** (a list of
notes) as Komandaro commands, then drive it from Python, and finally see a
command-line interface generated from it. The finished code lives in
[`examples/notebook/`](../../examples/notebook/) and is exercised by the
test suite, so everything below runs as shown.

Every code block is a doctest: `python -m pytest` executes it.

## 0. Install

```bash
pip install "komandaro[dev]"
```

Python 3.12 or later. The `[dev]` extra brings `babel` (translations) and
`pytest`.

## 1. The context: your application state

A **context** is whatever object holds the state your commands act on. It
can be a dataclass, a database session, a Plone site root — Komandaro does
not care. Ours is a list of notes:

```pycon
>>> from dataclasses import dataclass, field

>>> @dataclass
... class Notebook:
...     notes: list[str] = field(default_factory=list)

>>> nb = Notebook()

```

## 2. A first command: do it, undo it

A command is a **class** built from two functions: one that performs the
operation and returns a result, one that reverts it. Both receive the
context; `undo` also receives the result of `do`.

```pycon
>>> from komandaro import SimpleCommandFactory
>>> from komandaro.i18n import _

>>> def add(notebook, text):
...     notebook.notes.append(text)
...     return len(notebook.notes)  # position of the new note

>>> def undo_add(notebook, position, text):
...     del notebook.notes[position - 1]

>>> Add = SimpleCommandFactory(add, undo_add, _("Add a note"), id="add")

```

`_("Add a note")` marks the name as translatable (§8). `id="add"` is the
stable identifier front ends will use.

To run the command, instantiate the class with the context and the
parameters, then call `execute()`:

```pycon
>>> cmd = Add(nb, text="Buy milk")
>>> cmd.execute()
1
>>> nb.notes
['Buy milk']
>>> cmd.undo()
>>> nb.notes
[]
>>> cmd.redo()
1

```

The parameters are available as `cmd.params`; the result of the last
execution as `cmd.result`.

### One instance, one execution

A command instance runs exactly once. It moves through three states —
*ready*, *executed*, *undone* — and refuses calls that do not fit its
state:

```pycon
>>> from komandaro import CommandStateError
>>> cmd.is_ready, cmd.is_executed, cmd.is_undone
(False, True, False)
>>> try:
...     cmd.execute()
... except CommandStateError as error:
...     print(error)
Command Add a note has already been executed

```

To add another note, create another instance: `Add(nb, text="...")`. Each
instance is the record of one action, which is exactly what an undo
history needs.

## 3. Declare the parameters with a schema

So far `Add` accepts any keyword. Let us tell Komandaro — and every future
front end — what it needs: one parameter `text`, a non-empty line.

```pycon
>>> from zope.interface import Interface
>>> from zope.schema import TextLine

>>> class IText(Interface):
...     text = TextLine(title=_("Text"), description=_("Content of the note"), min_length=1)

>>> Add = SimpleCommandFactory(add, undo_add, _("Add a note"), schema=IText, id="add")

```

Parameters are now **validated when the command is created**, before
anything runs. All problems are reported together:

```pycon
>>> from komandaro import ParameterError
>>> try:
...     Add(nb, text="", colour="red")
... except ParameterError as error:
...     for issue in error.issues:
...         print(issue.name, "->", issue)
colour -> Unknown parameter colour
text -> Invalid value for parameter text: Value is too short

```

And the schema **describes** the command, which is what a CLI turns into
options and an HTML page into form fields:

```pycon
>>> from komandaro import describe
>>> for p in describe(Add.schema):
...     print(p.name, p.type, repr(p.title), p.required, p.python_type)
text TextLine 'Text' True <class 'str'>

```

## 4. When undo needs more than the result: the memento

Renaming a note overwrites the old text. The result of `do` (the new text)
is not enough to undo. Give the factory a `snapshot` function: it runs just
before `do`, and its value is handed to `undo` in place of the result.

```pycon
>>> from zope.schema import Int

>>> class IRename(Interface):
...     position = Int(title=_("Position"), min=1)
...     text = TextLine(title=_("New text"), min_length=1)

>>> def rename(notebook, position, text):
...     notebook.notes[position - 1] = text
...     return text

>>> def undo_rename(notebook, old_text, position, text):
...     notebook.notes[position - 1] = old_text

>>> def snapshot_rename(notebook, position, text):
...     return notebook.notes[position - 1]

>>> Rename = SimpleCommandFactory(
...     rename, undo_rename, _("Rename a note"), schema=IRename, snapshot=snapshot_rename, id="mv"
... )

>>> nb = Notebook(["Buy milk", "Call Bob"])
>>> cmd = Rename(nb, position=1, text="Buy oat milk")
>>> cmd.execute()
'Buy oat milk'
>>> cmd.memento
'Buy milk'
>>> cmd.undo()
>>> nb.notes
['Buy milk', 'Call Bob']

```

The snapshot is taken once, on the first execution, so `redo()` restores
the same starting point later.

## 5. Writing a command as a class

The factory covers most cases. When you need more (several methods, a
custom `redo`, inheritance), subclass `BaseCommand` and implement `_do`,
`_undo`, optionally `_snapshot` and `_redo`. The public `execute`/`undo`/
`redo` and the state machine come for free.

```pycon
>>> from komandaro import BaseCommand

>>> class Clear(BaseCommand):
...     id = "clear"
...     name = _("Clear the notebook")
...     description = _("Remove every note")
...
...     def _snapshot(self):
...         return list(self.context.notes)
...
...     def _do(self):
...         count = len(self.context.notes)
...         self.context.notes.clear()
...         return count
...
...     def _undo(self):
...         self.context.notes[:] = self.memento

>>> cmd = Clear(nb)
>>> cmd.execute()
2
>>> nb.notes
[]
>>> cmd.undo()
>>> nb.notes
['Buy milk', 'Call Bob']

```

## 6. Several commands as one: the macro

A `Macro` runs child commands in order and undoes them in reverse. It is
**atomic**: if a child fails, the children already run are undone before
the error propagates. Here, importing several notes is one action in the
history:

```pycon
>>> from komandaro import Macro
>>> from zope.schema import List

>>> class IImport(Interface):
...     notes = List(title=_("Notes"), value_type=TextLine(), min_length=1)

>>> class Import(Macro):
...     id = "import"
...     name = _("Import notes")
...     schema = IImport
...
...     def __init__(self, context, **params):
...         super().__init__(context, **params)
...         for text in self.params["notes"]:
...             self.add(Add(context, text=text))

>>> macro = Import(nb, notes=["Water plants", "Pay rent"])
>>> macro.execute()
[3, 4]
>>> nb.notes
['Buy milk', 'Call Bob', 'Water plants', 'Pay rent']
>>> macro.undo()
[None, None]
>>> nb.notes
['Buy milk', 'Call Bob']

```

## 7. Registry and invoker: the pieces a front end uses

Two objects turn a bag of command classes into an application:

* the **registry** is the catalogue: id → command class, with groups;
* the **invoker** runs commands against one context, keeps the undo/redo
  history and tells observers what happened.

```pycon
>>> from komandaro import Registry, Invoker

>>> registry = Registry()
>>> for cls in (Add, Rename, Import):
...     _entry = registry.register(cls, group="notes")
>>> _entry = registry.register(Clear, group="danger")
>>> registry.ids
['add', 'mv', 'import', 'clear']

>>> nb = Notebook()
>>> invoker = Invoker(nb, registry)
>>> invoker.run("add", text="Buy milk")
1
>>> invoker.run("add", text="Call Bob")
2
>>> invoker.run("mv", position=2, text="Call Alice")
'Call Alice'
>>> nb.notes
['Buy milk', 'Call Alice']
>>> invoker.undo()
>>> invoker.undo()
>>> nb.notes
['Buy milk']
>>> invoker.redo()
2
>>> [cmd.id for cmd in invoker.history]
['add', 'add']
>>> invoker.can_redo
True

```

Running a new command after an undo clears the redo stack, as in any
editor. Errors are typed and translatable:

```pycon
>>> from komandaro import HistoryError, RegistryError
>>> invoker.run("add", text="x")
3
>>> invoker.can_redo
False
>>> try:
...     invoker.run("nope")
... except RegistryError as error:
...     print(error)
Unknown command nope

```

### Listening to what happens

Subscribe a handler to receive an `Event` at each transition. This is how a
UI refreshes its undo button, or an audit log records actions:

```pycon
>>> log = []
>>> unsubscribe = invoker.subscribe(lambda e: log.append((e.kind.value, e.command.id)))
>>> invoker.undo()
>>> invoker.redo()
3
>>> log
[('undone', 'add'), ('redone', 'add')]
>>> unsubscribe()

```

## 8. Translating names, labels and errors

Every string you wrapped in `_()` is a lazy gettext message. Nothing is
translated until a front end asks for a language — so one server process
can serve French and Esperanto users at once.

The library translates its own messages (catalogues `en`, `fr`, `eo`):

```pycon
>>> from komandaro import translate
>>> try:
...     Add(nb, text="x").undo()
... except CommandStateError as error:
...     print(error.translate("fr"))
...     print(error.translate("eo"))
La commande Add a note ne peut pas être annulée dans son état actuel
La komando Add a note ne povas esti malfarita en sia nuna stato

```

Your application's own messages live in **its own domain**. Create the
marker once:

```python
from komandaro import make_gettext

_ = make_gettext("notebook")
```

then extract, translate and compile with Babel:

```bash
pybabel extract -F babel.cfg -o locale/notebook.pot myapp/
pybabel init -i locale/notebook.pot -d locale -D notebook -l fr
# edit locale/fr/LC_MESSAGES/notebook.po
pybabel compile -d locale -D notebook
```

and translate at render time with `translate(message, "fr", localedir)`.
The example application does exactly this: see
[`examples/notebook/locale/`](../../examples/notebook/locale/).

```pycon
>>> from pathlib import Path
>>> from examples.notebook.notebook import Add as NotebookAdd
>>> localedir = Path("examples/notebook/locale")
>>> translate(NotebookAdd.name, "fr", localedir)
'Ajouter une note'
>>> translate(NotebookAdd.name, "de", localedir)  # no catalogue: the message id
'Add a note'

```

## 9. A front end, for free (almost)

Nothing above mentions a terminal or a browser. A front end only needs to
**read the registry** to present the commands, and **drive the invoker**
to run what the user chose. [`examples/notebook/cli.py`](../../examples/notebook/cli.py)
does that with `argparse` in about a hundred lines: one sub-command per
registry entry, one option per `ParameterInfo`, `--help` translated.

```pycon
>>> from examples.notebook.cli import Session
>>> session = Session(lang="en")
>>> session.run_line('add --text "Buy milk"')
[executed] Add a note
1
True
>>> session.run_line("mv --position 1 --text Milk")
[executed] Rename a note
Milk
True
>>> session.run_line("undo")
[undone] Rename a note
True
>>> session.run_line("list")
1. Buy milk
True

```

`lang="en"` pins the language of the labels. Without it, `Session()`
follows the locale of your shell (`LANGUAGE`, `LC_ALL`, `LANG`), so on a
French machine the very same session prints `[executed] Ajouter une note`
— which is the feature at work, but not what a doctest can expect.

The same session in French:

```pycon
>>> Session(lang="fr").run_line("undo")
! Rien à annuler
True

```

Try it interactively:

```bash
python -m examples.notebook.cli --lang fr
```

Phase 3 of the roadmap turns this hand-written driver into a reusable
`komandaro.cli`, and adds HTML, TUI and JSON/MCP front ends on the same
principle. Read [`how-it-works.md`](how-it-works.md) for the ideas behind
each piece, [`examples.md`](examples.md) for more patterns and
[`architecture.md`](architecture.md) for the design.
