"""The notebook example must keep working: the tutorials are built on it."""

from __future__ import annotations

import pytest
from examples.notebook.cli import Session, build_parser
from examples.notebook.notebook import Add, Clear, Import, Notebook, Rename, make_registry

from komandaro import Invoker, ParameterError


@pytest.fixture
def notebook():
    return Notebook(["Buy milk", "Call Bob"])


def test_registry_describes_the_application():
    registry = make_registry()
    assert registry.ids == ["add", "rm", "mv", "import", "clear"]
    assert [p.name for p in registry.get("mv").parameters] == ["position", "text"]
    assert list(registry.groups) == ["notes", "danger"]


def test_add_and_remove_derive_undo_from_the_result(notebook):
    invoker = Invoker(notebook, make_registry())
    assert invoker.run("add", text="Water plants") == 3
    assert invoker.run("rm", position=1) == "Buy milk"
    assert notebook.notes == ["Call Bob", "Water plants"]
    invoker.undo()
    invoker.undo()
    assert notebook.notes == ["Buy milk", "Call Bob"]


def test_rename_uses_a_memento(notebook):
    cmd = Rename(notebook, position=2, text="Call Alice")
    cmd.execute()
    assert cmd.memento == "Call Bob"
    cmd.undo()
    assert notebook.notes[1] == "Call Bob"


def test_clear_is_a_plain_command_class(notebook):
    cmd = Clear(notebook)
    assert cmd.execute() == 2
    assert notebook.notes == []
    cmd.undo()
    assert notebook.notes == ["Buy milk", "Call Bob"]


def test_import_is_an_atomic_macro(notebook):
    macro = Import(notebook, notes=["a", "b"])
    assert len(macro.commands) == 2
    assert macro.execute() == [3, 4]
    macro.undo()
    assert notebook.notes == ["Buy milk", "Call Bob"]
    with pytest.raises(ParameterError):
        Import(notebook, notes=[])


def test_parser_is_generated_from_the_registry():
    parser = build_parser(make_registry(), lang=None)
    ns = parser.parse_args(["mv", "--position", "2", "--text", "x"])
    assert (ns.command, ns.position, ns.text) == ("mv", 2, "x")
    ns = parser.parse_args(["import", "--notes", "a", "b"])
    assert ns.notes == ["a", "b"]


def test_session_end_to_end(capsys):
    session = Session(lang="en")  # explicit: Session() would follow the machine's locale
    for line in [
        'add --text "Buy milk"',
        "mv --position 1 --text Milk",
        "undo",
        "rm --position 7",
        "add",  # argparse error: missing --text
        "list",
    ]:
        assert session.run_line(line) is True
    assert session.run_line("quit") is False
    out = capsys.readouterr().out
    assert "[executed] Add a note" in out
    assert "[undone] Rename a note" in out
    assert "! IndexError: 7" in out
    assert out.rstrip().endswith("1. Buy milk")
    assert session.notebook.notes == ["Buy milk"]


def test_session_translates_labels_and_errors(capsys):
    session = Session(lang="fr")
    session.run_line("undo")
    session.run_line('add --text "Acheter du lait"')
    out = capsys.readouterr().out
    assert "Rien à annuler" in out
    assert "Ajouter une note" in out  # needs the compiled notebook.mo (see conftest)


def test_add_requires_non_empty_text(notebook):
    with pytest.raises(ParameterError) as info:
        Add(notebook, text="")
    assert info.value.issues[0].name == "text"
