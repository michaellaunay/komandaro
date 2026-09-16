"""Malformed input must produce usage errors, not tracebacks or false success."""

import argparse

import pytest
from examples.notebook.cli import Session, main, parse_bool
from examples.notebook.notebook import Import, Notebook


def test_missing_language_value_is_a_usage_error():
    with pytest.raises(SystemExit) as caught:
        main(["--lang"])
    assert caught.value.code == 2


def test_equals_language_option_is_used(capsys):
    assert main(["--lang=fr", "undo"]) == 1
    assert "Rien à annuler" in capsys.readouterr().out


@pytest.mark.parametrize("arguments", [["missing-command"], ["add"]])
def test_invalid_command_line_has_nonzero_status(arguments):
    assert main(arguments) == 2


def test_success_and_help_have_zero_status():
    assert main(["add", "--text", "hello"]) == 0
    assert main(["--help"]) == 0


def test_bad_quotes_do_not_end_an_interactive_session(capsys):
    session = Session(lang="en")
    assert session.run_line('add --text "unfinished') is True
    assert session.last_status == 2
    assert "ValueError" in capsys.readouterr().out
    assert session.run_line('add --text "recovered"') is True
    assert session.last_status == 0
    assert session.notebook.notes == ["recovered"]


@pytest.mark.parametrize("value", ["false", "0", "No", "off"])
def test_false_boolean_values_are_explicit(value):
    assert parse_bool(value) is False


@pytest.mark.parametrize("value", ["true", "1", "Yes", "on"])
def test_true_boolean_values_are_explicit(value):
    assert parse_bool(value) is True


def test_invalid_boolean_is_not_silently_false():
    with pytest.raises(argparse.ArgumentTypeError):
        parse_bool("flase")


def test_import_constructs_a_complete_tree_from_validated_parameters():
    notebook = Notebook()
    command = Import(notebook, notes=["a", "b", "c"])
    assert len(command.commands) == 3
    assert command.execute() == [1, 2, 3]
    command.undo()
    assert notebook.notes == []
