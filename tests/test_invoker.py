"""Invoker: history, undo/redo, events."""

from __future__ import annotations

import pytest
from zope.interface import Interface
from zope.schema import Int

from komandaro import EventKind, HistoryError, Invoker, Registry, SimpleCommandFactory
from komandaro.i18n import _


class IAmount(Interface):
    amount = Int(title=_("Amount"))


def add(ctx, amount):
    ctx.value += amount
    return ctx.value


def undo_add(ctx, result, amount):
    ctx.value -= amount
    return ctx.value


def boom(ctx):
    raise ValueError("boom")


Add = SimpleCommandFactory(add, undo_add, _("Add"), schema=IAmount, id="add")
Boom = SimpleCommandFactory(boom, lambda c, r: None, _("Boom"), id="boom")


@pytest.fixture
def invoker(calc):
    reg = Registry()
    reg.register(Add)
    reg.register(Boom)
    return Invoker(calc, reg)


def test_run_by_id_and_by_instance(invoker, calc):
    assert invoker.run("add", amount=2) == 2
    assert invoker.run(Add(calc, amount=3)) == 5
    assert len(invoker) == 2
    assert [c.params["amount"] for c in invoker] == [2, 3]
    assert invoker.can_undo and not invoker.can_redo


def test_params_only_with_id(invoker, calc):
    with pytest.raises(TypeError):
        invoker.run(Add(calc, amount=1), amount=2)


def test_undo_redo_stacks(invoker, calc):
    invoker.run("add", amount=1)
    invoker.run("add", amount=10)
    assert invoker.undo() == 1
    assert calc.value == 1
    assert [c.params["amount"] for c in invoker.undone] == [10]
    assert invoker.undo() == 0
    assert not invoker.can_undo and invoker.can_redo
    assert invoker.redo() == 1
    assert invoker.redo() == 11
    assert not invoker.can_redo
    assert calc.value == 11


def test_new_command_clears_redo(invoker, calc):
    invoker.run("add", amount=1)
    invoker.undo()
    assert invoker.can_redo
    invoker.run("add", amount=5)
    assert not invoker.can_redo
    assert calc.value == 5


def test_nothing_to_undo_or_redo(invoker, localedir):
    with pytest.raises(HistoryError) as info:
        invoker.undo()
    assert str(info.value) == "Nothing to undo"
    assert info.value.translate("fr", localedir=localedir) == "Rien à annuler"
    with pytest.raises(HistoryError, match="Nothing to redo"):
        invoker.redo()


def test_history_limit(calc):
    reg = Registry()
    reg.register(Add)
    invoker = Invoker(calc, reg, limit=2)
    for amount in (1, 2, 3):
        invoker.run("add", amount=amount)
    assert [c.params["amount"] for c in invoker.history] == [2, 3]


def test_events(invoker, calc):
    seen = []
    unsubscribe = invoker.subscribe(lambda e: seen.append((e.kind, e.command and e.command.id)))
    invoker.run("add", amount=1)
    invoker.undo()
    invoker.redo()
    with pytest.raises(ValueError):
        invoker.run("boom")
    invoker.clear()
    assert seen == [
        (EventKind.EXECUTED, "add"),
        (EventKind.UNDONE, "add"),
        (EventKind.REDONE, "add"),
        (EventKind.FAILED, "boom"),
        (EventKind.CLEARED, None),
    ]
    assert not invoker.can_undo
    unsubscribe()
    invoker.run("add", amount=1)
    assert len(seen) == 5


def test_failed_event_carries_the_error(invoker):
    events = []
    invoker.subscribe(events.append)
    with pytest.raises(ValueError):
        invoker.run("boom")
    assert isinstance(events[0].error, ValueError)
    assert events[0].at is not None
    assert not invoker.can_undo  # a failed command is not recorded


def test_failed_undo_keeps_the_command_in_history(calc):
    def bad_undo(ctx, result):
        raise RuntimeError("cannot undo")

    Bad = SimpleCommandFactory(lambda c: 1, bad_undo, "Bad")
    invoker = Invoker(calc)
    invoker.run(Bad(calc))
    with pytest.raises(RuntimeError):
        invoker.undo()
    assert invoker.can_undo


def test_create_requires_a_registry(calc):
    with pytest.raises(HistoryError, match="no registry"):
        Invoker(calc).run("add")
