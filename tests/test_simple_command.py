"""Life cycle of a SimpleCommand built with SimpleCommandFactory."""

from __future__ import annotations

import pytest
from zope.interface.verify import verifyObject

from komandaro import (
    BaseCommand,
    CommandStateError,
    ICommand,
    IExecutedCommand,
    ISimpleCommand,
    IUndoneCommand,
    SimpleCommand,
    SimpleCommandFactory,
)
from komandaro.i18n import Message, _


def add_five(ctx):
    ctx.value += 5
    return ctx.value


def undo_add_five(ctx, result):
    ctx.value -= 5
    return ctx.value


AddFive = SimpleCommandFactory(add_five, undo_add_five, _("Add five"), _("Adds 5 to the value"))


def test_factory_builds_a_simple_command_class():
    assert issubclass(AddFive, SimpleCommand)
    assert AddFive.__name__ == "AddFiveCommand"
    assert isinstance(AddFive.name, Message)
    assert AddFive.name == "Add five"
    assert AddFive.description == "Adds 5 to the value"
    assert ISimpleCommand.implementedBy(AddFive)


def test_factory_custom_class_name():
    cls = SimpleCommandFactory(add_five, undo_add_five, "x", class_name="Plus")
    assert cls.__name__ == "PlusCommand"


def test_functions_are_not_bound_to_the_instance(calc):
    # The historical bug: plain functions stored as class attributes became
    # bound methods and received (self, context).
    cmd = AddFive(calc)
    assert cmd.execute() == 5
    assert calc.value == 5


def test_state_transitions(calc):
    cmd = AddFive(calc)
    assert cmd.is_ready and ICommand.providedBy(cmd)
    assert not IExecutedCommand.providedBy(cmd)
    verifyObject(ICommand, cmd)

    cmd.execute()
    assert cmd.is_executed and IExecutedCommand.providedBy(cmd)
    assert not ICommand.providedBy(cmd)
    verifyObject(IExecutedCommand, cmd)
    assert cmd.result == 5

    assert cmd.undo() == 0
    assert cmd.is_undone and IUndoneCommand.providedBy(cmd)
    assert not IExecutedCommand.providedBy(cmd)
    verifyObject(IUndoneCommand, cmd)
    assert calc.value == 0

    assert cmd.redo() == 5
    assert cmd.is_executed
    assert calc.value == 5

    # the kind is never lost across state changes
    assert ISimpleCommand.providedBy(cmd)


def test_execute_twice_is_refused(calc):
    cmd = AddFive(calc)
    cmd.execute()
    with pytest.raises(CommandStateError) as info:
        cmd.execute()
    assert str(info.value) == "Command Add five has already been executed"
    assert calc.value == 5  # nothing happened


def test_undo_before_execute_is_refused(calc):
    cmd = AddFive(calc)
    with pytest.raises(CommandStateError, match="cannot be undone"):
        cmd.undo()


def test_redo_before_undo_is_refused(calc):
    cmd = AddFive(calc)
    cmd.execute()
    with pytest.raises(CommandStateError, match="cannot be redone"):
        cmd.redo()
    with pytest.raises(CommandStateError):
        AddFive(calc).redo()


def test_each_instance_has_its_own_state(calc):
    first, second = AddFive(calc), AddFive(calc)
    first.execute()
    assert first.is_executed and second.is_ready
    second.execute()
    assert calc.value == 10


def test_undo_receives_the_execute_result(calc):
    seen = {}

    def do(ctx):
        return "token"

    def undo(ctx, result):
        seen["result"] = result

    cmd = SimpleCommandFactory(do, undo, "spy")(calc)
    cmd.execute()
    cmd.undo()
    assert seen == {"result": "token"}


def test_repr_shows_state(calc):
    cmd = AddFive(calc)
    assert repr(cmd) == "<AddFiveCommand Add five [ready]>"
    cmd.execute()
    assert "[executed]" in repr(cmd)
    cmd.undo()
    assert "[undone]" in repr(cmd)


def test_subclassing_base_directly_requires_do(calc):
    with pytest.raises(NotImplementedError):
        BaseCommand(calc).execute()
