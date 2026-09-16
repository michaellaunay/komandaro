"""Failure injection tests for command trees and compensation."""

import pytest
from zope.interface import Interface, alsoProvides
from zope.interface.verify import verifyObject

from komandaro import (
    CommandStateError,
    IBrokenCommand,
    Macro,
    SimpleCommandFactory,
)


def change(ctx, label, failures=None):
    failures = failures if failures is not None else set()

    def do(context):
        if "do" in failures:
            raise ValueError(f"do {label}")
        context.log.append(f"do {label}")
        context.value += 1
        return label

    def undo(context, result):
        context.log.append(f"undo {label}")
        if "undo" in failures:
            raise RuntimeError(f"undo {label}")
        context.value -= 1

    return SimpleCommandFactory(do, undo, label)(ctx)


@pytest.mark.parametrize("nested", [False, True])
def test_failed_execute_can_be_retried(calc, nested):
    failures = {"do"}
    first = change(calc, "first")
    if nested:
        first = Macro(calc, [first, change(calc, "inner")])
    macro = Macro(calc, [first, change(calc, "last", failures)])
    with pytest.raises(ValueError, match="do last"):
        macro.execute()
    assert calc.value == 0 and macro.is_ready
    assert all(child.is_ready for child in macro.commands)
    assert first.result is None
    failures.clear()
    macro.execute()
    assert calc.value == (3 if nested else 2)
    macro.undo()
    assert calc.value == 0


def test_failed_redo_restores_undone_state_and_can_be_retried(calc):
    failures = set()
    macro = Macro(calc, [change(calc, "a"), change(calc, "b", failures)])
    macro.execute()
    macro.undo()
    failures.add("do")
    with pytest.raises(ValueError, match="do b"):
        macro.redo()
    assert macro.is_undone and calc.value == 0
    assert all(child.is_undone for child in macro.commands)
    failures.clear()
    macro.redo()
    assert macro.is_executed and calc.value == 2


def test_failed_undo_compensates_in_forward_order(calc):
    failures = {"undo"}
    macro = Macro(calc, [change(calc, "a", failures), change(calc, "b"), change(calc, "c")])
    macro.execute()
    with pytest.raises(RuntimeError, match="undo a"):
        macro.undo()
    assert calc.value == 3 and macro.is_executed
    assert calc.log[-5:] == ["undo c", "undo b", "undo a", "do b", "do c"]
    assert all(child.is_executed for child in macro.commands)
    failures.clear()
    macro.undo()
    assert calc.value == 0


def test_all_compensations_are_attempted_and_failures_remain_visible(calc):
    macro = Macro(
        calc,
        [change(calc, "a", {"undo"}), change(calc, "b", {"undo"}), change(calc, "c", {"do"})],
    )
    with pytest.raises(ExceptionGroup) as caught:
        macro.execute()
    assert [str(error) for error in caught.value.exceptions] == ["do c", "undo b", "undo a"]
    assert calc.log[-2:] == ["undo b", "undo a"]
    assert macro.is_broken and not macro.is_ready
    verifyObject(IBrokenCommand, macro)
    for action in (macro.execute, macro.undo, macro.redo):
        with pytest.raises(CommandStateError, match="recovery"):
            action()
    with pytest.raises(CommandStateError):
        macro.add(change(calc, "more"))
    assert "[broken]" in repr(macro)


def test_nested_broken_state_propagates_to_parent(calc):
    inner = Macro(calc, [change(calc, "a", {"undo"}), change(calc, "b", {"do"})])
    outer = Macro(calc, [change(calc, "prefix"), inner])
    with pytest.raises(ExceptionGroup):
        outer.execute()
    assert outer.is_broken and inner.is_broken
    assert calc.log[-1] == "undo prefix"


def test_undo_compensation_failure_breaks_macro(calc):
    failures = set()
    macro = Macro(calc, [change(calc, "a", {"undo"}), change(calc, "b", failures)])
    macro.execute()
    failures.add("do")
    with pytest.raises(ExceptionGroup) as caught:
        macro.undo()
    assert [str(error) for error in caught.value.exceptions] == ["undo a", "do b"]
    assert macro.is_broken


def test_interrupt_is_preserved_and_completed_children_are_compensated(calc):
    def interrupt(ctx):
        raise KeyboardInterrupt("stop")

    child = SimpleCommandFactory(interrupt, lambda c, r: None, "interrupt")(calc)
    macro = Macro(calc, [change(calc, "a", {"undo"}), child])
    with pytest.raises(BaseExceptionGroup) as caught:
        macro.execute()
    assert isinstance(caught.value.exceptions[0], KeyboardInterrupt)
    assert macro.is_broken


def test_cycles_duplicates_and_non_commands_are_rejected(calc):
    macro = Macro(calc)
    with pytest.raises(ValueError, match="cycles"):
        macro.add(macro)
    assert macro.commands == ()
    child = change(calc, "a")
    macro.add(child)
    with pytest.raises(ValueError, match="shared"):
        macro.add(child)
    with pytest.raises(TypeError, match="BaseCommand"):
        Macro(calc, [object()])
    nested = Macro(calc, [macro])
    with pytest.raises(ValueError):
        macro.add(nested)


def test_preflight_rejects_wrong_child_state_without_side_effects(calc):
    first, second = change(calc, "a"), change(calc, "b")
    second.execute()
    macro = Macro(calc, [first, second])
    with pytest.raises(CommandStateError):
        macro.execute()
    assert first.is_ready and calc.value == 1


def test_command_reentrancy_and_macro_mutation_are_rejected(calc):
    def reenter(ctx):
        command.execute()

    command = SimpleCommandFactory(reenter, lambda c, r: None, "recursive")(calc)
    with pytest.raises(CommandStateError, match="in progress"):
        command.execute()
    assert command.is_ready
    command.do_it = lambda c: "recovered"
    assert command.execute() == "recovered"

    def mutate(ctx):
        macro.add(change(calc, "injected"))

    macro = Macro(calc, [SimpleCommandFactory(mutate, lambda c, r: None, "mutate")(calc)])
    with pytest.raises(CommandStateError, match="in progress"):
        macro.execute()
    assert len(macro.commands) == 1


def test_unrelated_direct_interfaces_survive_state_changes(calc):
    class ITagged(Interface):
        """Application-owned instance marker."""

    command = change(calc, "tagged")
    alsoProvides(command, ITagged)
    for transition in (command.execute, command.undo, command.redo):
        transition()
        assert ITagged.providedBy(command)


def test_state_subinterfaces_do_not_survive_a_transition(calc):
    from zope.interface import directlyProvides

    from komandaro import ICommand, IExecutedCommand, SimpleCommandFactory

    class IReadyExtension(ICommand):
        pass

    command = SimpleCommandFactory(lambda c: None, lambda c, result: None, "noop")(calc)
    directlyProvides(command, IReadyExtension)
    command.execute()
    assert IExecutedCommand.providedBy(command)
    assert not ICommand.providedBy(command)
    assert not IReadyExtension.providedBy(command)
