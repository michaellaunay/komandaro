"""Notebook — the example application used by the tutorial.

The *logic* of a tiny notebook (add, remove, rename, clear, import notes)
written once as Komandaro commands.  Nothing here knows about the command
line: see ``cli.py`` for a front end built from this registry.

Run the tests with ``python -m pytest tests/test_examples.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from zope.interface import Interface
from zope.schema import Int, List, TextLine

from komandaro import BaseCommand, Macro, Registry, SimpleCommandFactory, make_gettext

# The application has its own gettext domain, separate from the library's.
_ = make_gettext("notebook")


# --------------------------------------------------------------------------
# Context: the application state every command works on
# --------------------------------------------------------------------------


@dataclass
class Notebook:
    notes: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        if not self.notes:
            return "(empty)"
        return "\n".join(f"{i}. {note}" for i, note in enumerate(self.notes, 1))


# --------------------------------------------------------------------------
# Parameter schemas: what each command needs from the user
# --------------------------------------------------------------------------


class IText(Interface):
    text = TextLine(title=_("Text"), description=_("Content of the note"), min_length=1)


class IPosition(Interface):
    position = Int(title=_("Position"), description=_("1-based position of the note"), min=1)


class IRename(Interface):
    position = Int(title=_("Position"), min=1)
    text = TextLine(title=_("New text"), min_length=1)


class IImport(Interface):
    notes = List(title=_("Notes"), value_type=TextLine(), min_length=1)


# --------------------------------------------------------------------------
# Commands whose undo derives from the result
# --------------------------------------------------------------------------


def add(notebook: Notebook, text: str) -> int:
    notebook.notes.append(text)
    return len(notebook.notes)  # the position of the new note


def undo_add(notebook: Notebook, position: int, text: str) -> None:
    del notebook.notes[position - 1]


Add = SimpleCommandFactory(add, undo_add, _("Add a note"), schema=IText, id="add")


def remove(notebook: Notebook, position: int) -> str:
    if position > len(notebook.notes):
        raise IndexError(position)
    return notebook.notes.pop(position - 1)  # the removed text is all undo needs


def undo_remove(notebook: Notebook, removed: str, position: int) -> None:
    notebook.notes.insert(position - 1, removed)


Remove = SimpleCommandFactory(remove, undo_remove, _("Remove a note"), schema=IPosition, id="rm")


# --------------------------------------------------------------------------
# Commands whose undo needs a memento (state captured before execution)
# --------------------------------------------------------------------------


def rename(notebook: Notebook, position: int, text: str) -> str:
    notebook.notes[position - 1] = text
    return text


def undo_rename(notebook: Notebook, old_text: str, position: int, text: str) -> None:
    notebook.notes[position - 1] = old_text


def snapshot_rename(notebook: Notebook, position: int, text: str) -> str:
    return notebook.notes[position - 1]  # remembered before it is overwritten


Rename = SimpleCommandFactory(
    rename, undo_rename, _("Rename a note"), schema=IRename, snapshot=snapshot_rename, id="mv"
)


class Clear(BaseCommand):
    """The same idea written as a class instead of with the factory."""

    id = "clear"
    name = _("Clear the notebook")
    description = _("Remove every note")
    schema = None

    def _snapshot(self) -> list[str]:
        return list(self.context.notes)

    def _do(self) -> int:
        count = len(self.context.notes)
        self.context.notes.clear()
        return count

    def _undo(self) -> None:
        self.context.notes[:] = self.memento


# --------------------------------------------------------------------------
# A macro: several notes imported as one atomic, undoable action
# --------------------------------------------------------------------------


class Import(Macro):
    id = "import"
    name = _("Import notes")
    description = _("Add several notes as one action")
    schema = IImport

    def __init__(self, context: Notebook, **params: object) -> None:
        super().__init__(context, **params)
        for text in self.params["notes"]:
            self.add(Add(context, text=text))


# --------------------------------------------------------------------------
# The registry: the catalogue a front end reads to build itself
# --------------------------------------------------------------------------


def make_registry() -> Registry:
    registry = Registry()
    registry.register(Add, group="notes")
    registry.register(Remove, group="notes")
    registry.register(Rename, group="notes")
    registry.register(Import, group="notes")
    registry.register(Clear, group="danger")
    return registry
