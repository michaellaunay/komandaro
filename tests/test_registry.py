"""Command registry."""

from __future__ import annotations

import pytest
from zope.interface import Interface
from zope.schema import Int

from komandaro import Registry, RegistryError, SimpleCommand, SimpleCommandFactory
from komandaro.i18n import _


class IAmount(Interface):
    amount = Int(title=_("Amount"))


Add = SimpleCommandFactory(
    lambda c, amount: amount, lambda c, r, amount: None, _("Add"), schema=IAmount, id="add"
)
Noop = SimpleCommandFactory(lambda c: None, lambda c, r: None, _("Noop"))


@pytest.fixture
def registry():
    reg = Registry()
    reg.register(Add, group="math", tags=["arith", "safe"])
    reg.register(Noop)
    return reg


def test_register_and_lookup(registry):
    assert len(registry) == 2
    assert registry.ids == ["add", "noop"]
    assert "add" in registry and "nope" not in registry
    assert registry["add"] is Add
    entry = registry.get("add")
    assert entry.name == "Add"
    assert entry.group == "math"
    assert entry.tags == {"arith", "safe"}
    assert [p.name for p in entry.parameters] == ["amount"]
    assert registry.get("noop").parameters == []


def test_duplicate_id_is_refused_unless_replace(registry, localedir):
    with pytest.raises(RegistryError) as info:
        registry.register(Noop, id="add")
    assert str(info.value) == "Command add is already registered"
    assert info.value.translate("eo", localedir=localedir) == "La komando add jam estas registrita"
    registry.register(Noop, id="add", replace=True)
    assert registry["add"] is Noop


def test_unknown_id(registry):
    with pytest.raises(RegistryError, match="Unknown command nope"):
        registry.get("nope")
    with pytest.raises(RegistryError):
        registry.unregister("nope")


def test_unregister(registry):
    registry.unregister("noop")
    assert registry.ids == ["add"]


def test_only_command_classes_are_accepted(registry, calc):
    with pytest.raises(TypeError):
        registry.register(Add(calc, amount=1))  # an instance
    with pytest.raises(TypeError):
        registry.register(int)


def test_decorator_registration():
    reg = Registry()

    @reg.command("twice", group="math")
    class Twice(SimpleCommand):
        name = _("Twice")

    assert reg["twice"] is Twice
    assert reg.groups == {"math": [reg.get("twice")]}


def test_groups_and_find(registry):
    groups = registry.groups
    assert list(groups) == ["math", None]
    assert [e.id for e in registry.find(group="math")] == ["add"]
    assert [e.id for e in registry.find(tag="safe")] == ["add"]
    assert registry.find(group="math", tag="none") == []
    assert [e.id for e in registry] == ["add", "noop"]


def test_create_binds_context_and_params(registry, calc):
    cmd = registry.create("add", calc, amount=7)
    assert cmd.context is calc
    assert cmd.params == {"amount": 7}
    assert cmd.execute() == 7


def test_load_entry_points(monkeypatch):
    from importlib.metadata import EntryPoint

    fake = [EntryPoint(name="plus", value="tests.test_registry:Add", group="x.commands")]
    monkeypatch.setattr("komandaro.registry.entry_points", lambda group: fake)
    reg = Registry()
    loaded = reg.load_entry_points("x.commands", registry_group="ext")
    assert [e.id for e in loaded] == ["plus"]
    assert reg["plus"] is Add
    assert reg.get("plus").group == "ext"
