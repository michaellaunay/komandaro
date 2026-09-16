"""The detachable permission model."""

from __future__ import annotations

from enum import IntFlag

import pytest

from komandaro import (
    AllowAll,
    EventKind,
    Invoker,
    PermissionDeniedError,
    Registry,
    SimpleCommand,
    SimpleCommandFactory,
    SubjectPermissionsPolicy,
)
from komandaro.i18n import _
from komandaro.permissions import default_held, default_implies, describe_permission


def make(cmd_id, permission=None):
    cls = SimpleCommandFactory(lambda c: cmd_id, lambda c, r: None, _(cmd_id), id=cmd_id)
    cls.permission = permission
    return cls


# --- three permission models, one policy -----------------------------------


class Perm(IntFlag):
    """The AlirPunkto model: bit flags."""

    NONE = 0
    READ = 1
    WRITE = 2
    ADMIN = 4


class Read:
    """A permission class graph: holding a subclass grants the base classes."""


class Write(Read):
    pass


class Delete(Read):
    pass


class Admin(Write, Delete):  # diamond inheritance
    pass


@pytest.mark.parametrize(
    ("held", "required", "expected"),
    [
        (None, None, True),
        ("read", "read", True),
        ("read", "write", False),
        ("anything", None, True),
        (Perm.READ | Perm.WRITE, Perm.WRITE, True),
        (Perm.READ, Perm.WRITE, False),
        (Perm.ADMIN, Perm.READ | Perm.WRITE, False),
        (Admin, Read, True),
        (Admin, Delete, True),
        (Write, Delete, False),
        (Read, Admin, False),
        (Admin(), Read, True),  # an instance of a permission class
        ("read", Perm.READ, False),  # models do not mix
    ],
)
def test_default_implies(held, required, expected):
    assert default_implies(held, required) is expected


def test_default_held():
    class User:
        permissions = frozenset({"read", "write"})

    class Flagged:
        permissions = Perm.READ | Perm.WRITE

    assert list(default_held(None)) == []
    assert default_held(User()) == frozenset({"read", "write"})
    assert list(default_held(Flagged())) == [Perm.READ | Perm.WRITE]
    assert list(default_held(["a", "b"])) == ["a", "b"]
    assert list(default_held(Perm.ADMIN)) == [Perm.ADMIN]
    assert list(default_held(Admin)) == [Admin]
    assert list(default_held(42)) == []


def test_subject_policy_with_each_model():
    policy = SubjectPermissionsPolicy()
    assert policy.permits({"read"}, "read")
    assert not policy.permits({"read"}, "write")
    assert policy.permits(None, None)  # public command
    assert not policy.permits(None, "read")
    assert policy.permits(Perm.READ | Perm.ADMIN, Perm.ADMIN)
    assert not policy.permits(Perm.READ, Perm.ADMIN)
    assert policy.permits([Admin], Delete)
    assert not policy.permits([Write], Delete)


def test_policy_ingredients_are_replaceable():
    # roles -> permissions resolved by the application
    roles = {"editor": {"read", "write"}, "viewer": {"read"}}
    policy = SubjectPermissionsPolicy(held=lambda user: roles[user["role"]])
    assert policy.permits({"role": "editor"}, "write")
    assert not policy.permits({"role": "viewer"}, "write")
    # a completely different meaning of "implies"
    policy = SubjectPermissionsPolicy(implies=lambda held, required: held >= required)
    assert policy.permits([3], 2)
    assert not policy.permits([1], 2)
    assert policy.implies(5, 5)


def test_invoker_enforces_the_policy(calc):
    registry = Registry()
    registry.register(make("public"))
    registry.register(make("edit", "write"))
    registry.register(make("wipe", "admin"))
    events = []
    invoker = Invoker(calc, registry, policy=SubjectPermissionsPolicy(), subject={"read", "write"})
    invoker.subscribe(events.append)

    assert invoker.run("public") == "public"
    assert invoker.run("edit") == "edit"
    with pytest.raises(PermissionDeniedError) as info:
        invoker.run("wipe")
    assert str(info.value) == "Permission admin is required to run wipe"
    assert info.value.translate("fr") == "La permission admin est requise pour exécuter wipe"
    assert info.value.subject == {"read", "write"}
    assert [e.kind for e in events] == [EventKind.EXECUTED, EventKind.EXECUTED, EventKind.DENIED]
    assert isinstance(events[-1].error, PermissionDeniedError)
    assert len(invoker) == 2  # the denied command was never executed nor recorded

    invoker.subject = {"admin"}  # per request / per session
    assert invoker.run("wipe") == "wipe"

    # Revocation applies to instances and to history transitions.
    invoker.subject = set()
    with pytest.raises(PermissionDeniedError):
        invoker.run(make("edit", "write")(calc))
    with pytest.raises(PermissionDeniedError):
        invoker.undo()
    invoker.subject = {"admin"}
    invoker.undo()
    invoker.subject = set()
    with pytest.raises(PermissionDeniedError):
        invoker.redo()
    invoker.subject = {"admin"}
    invoker.redo()


def test_no_policy_or_allow_all_means_everything_is_permitted(calc):
    registry = Registry()
    registry.register(make("wipe", "admin"))
    assert Invoker(calc, registry).run("wipe") == "wipe"
    assert Invoker(calc, registry, policy=AllowAll(), subject=None).run("wipe") == "wipe"


def test_registry_allowed_builds_a_menu():
    registry = Registry()
    registry.register(make("public"))
    registry.register(make("edit", Perm.WRITE))
    registry.register(make("wipe", Perm.ADMIN))
    policy = SubjectPermissionsPolicy()
    assert [e.id for e in registry.allowed(policy, Perm.READ | Perm.WRITE)] == ["public", "edit"]
    assert [e.id for e in registry.allowed(policy, None)] == ["public"]
    assert [e.id for e in registry.allowed(None, None)] == ["public", "edit", "wipe"]


def test_describe_permission():
    assert describe_permission(None) == ""
    assert describe_permission("read") == "read"
    assert describe_permission(Perm.WRITE) == "WRITE"
    assert describe_permission(Perm.READ | Perm.WRITE) in {"READ|WRITE", "3"}
    assert describe_permission(Admin) == "Admin"


def test_permission_is_a_plain_class_attribute(calc):
    class Guarded(SimpleCommand):
        permission = Write

    assert Guarded.permission is Write
    assert Guarded(calc).permission is Write
