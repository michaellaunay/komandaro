"""History invariants and observer isolation without parameter schemas."""

import logging

import pytest

from komandaro import EventKind, HistoryError, Invoker, SimpleCommandFactory


def make_command(calc, *, fail=None):
    def do(ctx):
        if fail == "execute":
            raise ValueError("business failure")
        ctx.value += 1
        return ctx.value

    def undo(ctx, result):
        if fail == "undo":
            raise ValueError("business failure")
        ctx.value -= 1
        return ctx.value

    return SimpleCommandFactory(do, undo, "change")(calc)


@pytest.mark.parametrize("limit", [True, False, 1.5, "2", object()])
def test_invalid_limit_types_fail_at_construction(calc, limit):
    with pytest.raises(TypeError):
        Invoker(calc, limit=limit)
    assert calc.value == 0


def test_limit_is_checked_on_reassignment(calc):
    invoker = Invoker(calc, limit=2)
    with pytest.raises(ValueError):
        invoker.limit = -1
    assert invoker.limit == 2
    with pytest.raises(ValueError):
        Invoker(calc, limit=-1)


def test_zero_limit_and_changed_limit_apply_to_redo(calc):
    invoker = Invoker(calc, limit=0)
    invoker.run(make_command(calc))
    assert calc.value == 1 and not invoker.can_undo
    invoker.limit = None
    invoker.run(make_command(calc))
    invoker.run(make_command(calc))
    invoker.undo()
    invoker.limit = 1
    invoker.redo()
    assert len(invoker.history) == 1


def test_observer_failures_do_not_change_results_or_skip_other_observers(calc, caplog):
    invoker = Invoker(calc)
    seen = []

    def broken(event):
        raise RuntimeError("observer failure")

    invoker.subscribe(broken)
    invoker.subscribe(seen.append)
    with caplog.at_level(logging.ERROR, logger="komandaro.invoker"):
        assert invoker.run(make_command(calc)) == 1
        assert invoker.undo() == 0
        assert invoker.redo() == 1
        invoker.clear()
    assert [event.kind for event in seen] == [
        EventKind.EXECUTED,
        EventKind.UNDONE,
        EventKind.REDONE,
        EventKind.CLEARED,
    ]
    assert len(caplog.records) == 4
    assert calc.value == 1 and not invoker.can_undo


@pytest.mark.parametrize("action", ["execute", "undo", "redo"])
def test_observer_cannot_mask_business_exception(calc, action):
    invoker = Invoker(calc)
    command = make_command(calc, fail=action if action != "redo" else None)
    if action != "execute":
        invoker.run(command)
    if action == "redo":
        invoker.undo()
        command.do_it = make_command(calc, fail="execute").do_it

    def broken(event):
        raise RuntimeError("observer failure")

    invoker.subscribe(broken)
    with pytest.raises(ValueError, match="business failure"):
        invoker.run(command) if action == "execute" else getattr(invoker, action)()
    if action == "undo":
        assert invoker.history == (command,)
    elif action == "redo":
        assert invoker.undone == (command,)
    else:
        assert not invoker.history


def test_unsubscribe_is_idempotent_and_registrations_are_independent(calc):
    invoker = Invoker(calc)
    seen = []
    first = invoker.subscribe(seen.append)
    second = invoker.subscribe(seen.append)
    first()
    first()
    invoker.clear()
    assert len(seen) == 1
    second()
    second()
    invoker.clear()
    assert len(seen) == 1
    with pytest.raises(TypeError):
        invoker.subscribe(None)


@pytest.mark.parametrize("action", ["run", "undo", "redo", "clear"])
def test_reentrant_observers_cannot_mutate_history(calc, action):
    invoker = Invoker(calc)
    errors = []

    def reenter(event):
        try:
            invoker.run(make_command(calc)) if action == "run" else getattr(invoker, action)()
        except HistoryError as error:
            errors.append(error)

    invoker.subscribe(reenter)
    command = make_command(calc)
    invoker.run(command)
    assert calc.value == 1 and invoker.history == (command,)
    assert len(errors) == 1
    invoker.undo()
    assert calc.value == 0 and invoker.undone == (command,)


def test_reentrancy_from_business_callback_is_rejected_and_guard_released(calc):
    invoker = Invoker(calc)
    command = SimpleCommandFactory(lambda ctx: invoker.clear(), lambda c, r: None, "bad")(calc)
    with pytest.raises(HistoryError, match="in progress"):
        invoker.run(command)
    assert not invoker.history and command.is_ready
    assert invoker.run(make_command(calc)) == 1


def test_policy_reentrancy_is_rejected(calc):
    invoker = Invoker(calc)

    class ReentrantPolicy:
        def permits(self, subject, required, command):
            invoker.clear()
            return True

    invoker.policy = ReentrantPolicy()
    with pytest.raises(HistoryError):
        invoker.run(make_command(calc))
    assert not invoker.history and calc.value == 0


def test_observer_interrupt_propagates_after_consistent_history_update(calc):
    invoker = Invoker(calc)

    def interrupt(event):
        raise KeyboardInterrupt

    unsubscribe = invoker.subscribe(interrupt)
    command = make_command(calc)
    with pytest.raises(KeyboardInterrupt):
        invoker.run(command)
    assert command.is_executed and invoker.history == (command,)
    unsubscribe()
    invoker.undo()
    assert calc.value == 0
