"""Every implementation must satisfy its interface — no more drift."""

from __future__ import annotations

import pytest
from zope.interface.verify import verifyClass, verifyObject

from komandaro import (
    AllowAll,
    Event,
    EventKind,
    IBaseCommand,
    ICommand,
    IEntry,
    IEvent,
    IExecutedCommand,
    IInvoker,
    IMacro,
    Invoker,
    IPermissionPolicy,
    IRegistry,
    ISimpleCommand,
    IUndoneCommand,
    Macro,
    Registry,
    SimpleCommand,
    SimpleCommandFactory,
    SubjectPermissionsPolicy,
)
from komandaro.i18n import _

Noop = SimpleCommandFactory(lambda c: None, lambda c, r: None, _("noop"), id="noop")


@pytest.mark.parametrize(
    ("interface", "cls"),
    [
        (ISimpleCommand, SimpleCommand),
        (ISimpleCommand, Noop),
        (IMacro, Macro),
        (IRegistry, Registry),
        (IInvoker, Invoker),
        (IPermissionPolicy, SubjectPermissionsPolicy),
        (IPermissionPolicy, AllowAll),
    ],
)
def test_classes_implement_their_interface(interface, cls):
    assert interface.implementedBy(cls)
    verifyClass(interface, cls)


def test_command_instances_provide_kind_and_state(calc):
    cmd = Noop(calc)
    verifyObject(ISimpleCommand, cmd)
    verifyObject(IBaseCommand, cmd)
    verifyObject(ICommand, cmd)
    cmd.execute()
    verifyObject(IExecutedCommand, cmd)
    cmd.undo()
    verifyObject(IUndoneCommand, cmd)
    for name in ("id", "name", "description", "schema", "permission", "context", "params"):
        assert hasattr(cmd, name), name
    assert hasattr(cmd, "result") and hasattr(cmd, "memento")


def test_macro_instance(calc):
    macro = Macro(calc, [Noop(calc)])
    verifyObject(IMacro, macro)
    verifyObject(ICommand, macro)


def test_registry_entry_invoker_event_instances(calc):
    registry = Registry()
    entry = registry.register(Noop)
    verifyObject(IRegistry, registry)
    verifyObject(IEntry, entry)
    invoker = Invoker(calc, registry, policy=AllowAll())
    verifyObject(IInvoker, invoker)
    verifyObject(IEvent, Event(EventKind.CLEARED, None))
    verifyObject(IPermissionPolicy, SubjectPermissionsPolicy())


def test_entry_exposes_permission():
    class Guarded(SimpleCommand):
        permission = "admin"

    entry = Registry().register(Guarded, id="g")
    assert entry.permission == "admin"
    assert Registry().register(Noop).permission is None
