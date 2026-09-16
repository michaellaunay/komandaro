"""Stable per-registration identities, including multiple aliases."""

import pytest

from komandaro import Invoker, Registry, SimpleCommandFactory


def test_alias_is_used_by_instances_and_events_without_mutating_the_class(calc):
    cls = SimpleCommandFactory(lambda c: "ok", lambda c, r: None, "Name", id="original")
    registry = Registry()
    registry.register(cls, id="first")
    registry.register(cls, id="second")
    assert registry.create("first", calc).id == "first"
    assert registry.create("second", calc).id == "second"
    assert cls.id == "original" and cls(calc).id == "original"
    events = []
    invoker = Invoker(calc, registry)
    invoker.subscribe(events.append)
    invoker.run("first")
    invoker.undo()
    invoker.redo()
    assert [event.command.id for event in events] == ["first"] * 3


@pytest.mark.parametrize("ident", ["", "  "])
def test_empty_explicit_ids_are_rejected(ident):
    cls = SimpleCommandFactory(lambda c: None, lambda c, r: None, "Name")
    registry = Registry()
    with pytest.raises(ValueError):
        registry.register(cls, id=ident)
    assert not registry.ids


@pytest.mark.parametrize("ident", [1, False, object()])
def test_non_string_ids_are_rejected(ident):
    cls = SimpleCommandFactory(lambda c: None, lambda c, r: None, "Name")
    with pytest.raises(TypeError):
        Registry().register(cls, id=ident)
