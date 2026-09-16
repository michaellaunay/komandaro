"""Authorization must cover every transition and every command in a tree."""

from enum import Flag, IntFlag

import pytest

from komandaro import (
    EventKind,
    Invoker,
    Macro,
    PermissionDeniedError,
    SimpleCommandFactory,
    SubjectPermissionsPolicy,
)
from komandaro.permissions import default_implies


class Account(IntFlag):
    READ = 1
    WRITE = 2


class Unrelated(IntFlag):
    ADMIN = 1
    OTHER = 2


class Feature(Flag):
    ENABLED = 1


@pytest.mark.parametrize(
    ("held", "required"),
    [
        (Account.READ, Unrelated.ADMIN),
        (Unrelated.OTHER, Account.WRITE),
        (1, Account.READ),
        (Account.READ, 1),
        (True, Account.READ),
        (Feature.ENABLED, Account.READ),
        (Account.READ, Feature.ENABLED),
    ],
)
def test_flag_domains_never_grant_each_other(held, required):
    assert default_implies(held, required) is False


def make_change(context, permission=None):
    def do(ctx):
        ctx.value += 1
        return ctx.value

    def undo(ctx, result):
        ctx.value -= 1
        return ctx.value

    cls = SimpleCommandFactory(do, undo, "Change", id="change")
    cls.permission = permission
    return cls(context)


@pytest.mark.parametrize("action", ["undo", "redo"])
def test_revocation_blocks_history_transitions(calc, action):
    invoker = Invoker(calc, policy=SubjectPermissionsPolicy(), subject={"edit"})
    command = make_change(calc, "edit")
    invoker.run(command)
    if action == "redo":
        invoker.undo()
    before = (calc.value, invoker.history, invoker.undone)
    seen = []
    invoker.subscribe(seen.append)
    invoker.subject = set()
    with pytest.raises(PermissionDeniedError):
        getattr(invoker, action)()
    assert (calc.value, invoker.history, invoker.undone) == before
    assert [event.kind for event in seen] == [EventKind.DENIED]
    invoker.subject = {"edit"}
    getattr(invoker, action)()


@pytest.mark.parametrize("action", ["run", "undo", "redo"])
def test_nested_macros_authorize_all_children_before_any_mutation(calc, action):
    child = make_change(calc, "edit")
    macro = Macro(calc, [make_change(calc), Macro(calc, [child])])
    invoker = Invoker(calc, policy=SubjectPermissionsPolicy(), subject={"edit"})
    if action != "run":
        invoker.run(macro)
    if action == "redo":
        invoker.undo()
    before = (calc.value, invoker.history, invoker.undone)
    invoker.subject = set()
    with pytest.raises(PermissionDeniedError) as caught:
        invoker.run(macro) if action == "run" else getattr(invoker, action)()
    assert caught.value.command_id == child.id
    assert (calc.value, invoker.history, invoker.undone) == before


@pytest.mark.parametrize("nested", [False, True])
def test_foreign_context_is_rejected_before_execution(calc, nested):
    other = type(calc)()
    command = make_change(other)
    if nested:
        command = Macro(calc, [make_change(calc), command])
    with pytest.raises(ValueError, match="context"):
        Invoker(calc).run(command)
    assert (calc.value, other.value) == (0, 0)


def test_duplicate_children_are_rejected_before_execution(calc):
    child = make_change(calc)
    with pytest.raises(ValueError, match="shared"):
        Invoker(calc).run(Macro(calc, [child, child]))
    assert calc.value == 0
