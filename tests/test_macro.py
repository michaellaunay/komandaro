"""Composite commands."""

from __future__ import annotations

import pytest
from zope.interface.verify import verifyObject

from komandaro import (
    CommandStateError,
    ICommand,
    IExecutedCommand,
    IMacro,
    Macro,
    SimpleCommandFactory,
)


def step(label: str, fail: bool = False):
    def do(ctx):
        if fail:
            raise ValueError(f"{label} failed")
        ctx.log.append(f"do {label}")
        return label

    def undo(ctx, result):
        ctx.log.append(f"undo {label}")

    return SimpleCommandFactory(do, undo, label)


def test_macro_executes_in_order_and_undoes_in_reverse(calc):
    macro = Macro(calc, [step("a")(calc), step("b")(calc), step("c")(calc)])
    assert IMacro.providedBy(macro)
    verifyObject(IMacro, macro)
    verifyObject(ICommand, macro)

    assert macro.execute() == ["a", "b", "c"]
    assert calc.log == ["do a", "do b", "do c"]
    assert all(c.is_executed for c in macro.commands)
    verifyObject(IExecutedCommand, macro)

    macro.undo()
    assert calc.log[3:] == ["undo c", "undo b", "undo a"]
    assert all(c.is_undone for c in macro.commands)

    macro.redo()
    assert calc.log[6:] == ["do a", "do b", "do c"]


def test_macro_is_atomic_on_failure(calc):
    macro = Macro(calc, [step("a")(calc), step("b")(calc), step("boom", fail=True)(calc)])
    with pytest.raises(ValueError, match="boom failed"):
        macro.execute()
    assert calc.log == ["do a", "do b", "undo b", "undo a"]
    # the macro stays ready: it never reached the executed state
    assert macro.is_ready
    with pytest.raises(CommandStateError):
        macro.undo()


def test_macro_add_remove_only_while_ready(calc):
    a, b = step("a")(calc), step("b")(calc)
    macro = Macro(calc)
    macro.add(a)
    macro.add(b)
    macro.remove(a)
    assert macro.commands == (b,)
    macro.execute()
    with pytest.raises(CommandStateError, match="cannot be modified"):
        macro.add(a)
    with pytest.raises(CommandStateError, match="cannot be modified"):
        macro.remove(b)


def test_macro_custom_name_and_description(calc):
    macro = Macro(calc, name="Batch", description="Do everything")
    assert macro.name == "Batch"
    assert macro.description == "Do everything"
    assert Macro.name == "Macro"  # class default untouched


def test_nested_macros(calc):
    inner = Macro(calc, [step("x")(calc), step("y")(calc)])
    outer = Macro(calc, [step("a")(calc), inner])
    assert outer.execute() == ["a", ["x", "y"]]
    outer.undo()
    assert calc.log == ["do a", "do x", "do y", "undo y", "undo x", "undo a"]
