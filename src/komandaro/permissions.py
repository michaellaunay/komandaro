"""A detachable permission model.

Komandaro does not define what a permission *is*.  A command declares the
permission it requires (``permission = ...``, any object); an
:class:`~komandaro.interfaces.IPermissionPolicy` decides whether a
*subject* — the user, the session, the request… also any object — may run
it.  Replace the policy and you replace the model: the default one below
handles flat permission sets, ``IntFlag`` enumerations (the AlirPunkto
model) and class hierarchies (a permission graph with multiple inheritance)
without knowing which one is in use.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from enum import Flag
from typing import Any, Protocol

from zope.interface import implementer

from komandaro.i18n import Language, Message, _
from komandaro.interfaces import IPermissionPolicy


class Policy(Protocol):
    """Static shape of an ``IPermissionPolicy``, for type checkers."""

    def implies(self, held: Any, required: Any) -> bool: ...

    def permits(self, subject: Any, required: Any, command: Any = None) -> bool: ...


class PermissionDeniedError(RuntimeError):
    """Raised by the invoker when the policy refuses a command."""

    def __init__(self, command_id: str, permission: Any, subject: Any = None) -> None:
        self.message: Message = _("permission_denied")
        self.command_id = command_id
        self.permission = permission
        self.subject = subject
        super().__init__(self.message)

    @property
    def params(self) -> dict[str, Any]:
        return {"id": self.command_id, "permission": describe_permission(self.permission)}

    def __str__(self) -> str:
        return self.message.localize(None, **self.params)

    def translate(self, language: Language = None, **kw: Any) -> str:
        return self.message.localize(language, **kw, **self.params)


def describe_permission(permission: Any) -> str:
    """A short, readable name for a permission value of any model."""
    if permission is None:
        return ""
    if isinstance(permission, type):
        return permission.__name__
    if isinstance(permission, Flag):
        return permission.name or str(permission.value)
    return str(permission)


def default_held(subject: Any) -> Iterable[Any]:
    """The permissions *subject* holds.

    ``None`` holds nothing; an object with a ``permissions`` attribute holds
    those; a bare iterable (set, list, tuple, ``IntFlag`` value…) holds
    itself.  Applications with another convention pass their own ``held``
    function to :class:`SubjectPermissionsPolicy`.
    """
    if subject is None:
        return ()
    held = getattr(subject, "permissions", None)
    if held is not None:
        return (held,) if isinstance(held, Flag | str | type) else held
    if isinstance(subject, Flag | str | type):
        return (subject,)
    if isinstance(subject, Iterable):
        return subject
    return ()


def default_implies(held: Any, required: Any) -> bool:
    """The three usual meanings of "holding *held* grants *required*".

    * equality — flat permission names;
    * ``held & required == required`` — ``IntFlag`` enumerations, as in
      AlirPunkto's ``Permissions``;
    * ``issubclass(held, required)`` — a hierarchy of permission classes,
      diamond inheritance included, where a more specific permission grants
      the more general ones it derives from.
    """
    if required is None:
        return True
    if held == required:
        return True
    if isinstance(held, Flag) and isinstance(required, Flag):
        return (held & required) == required
    if isinstance(held, type) and isinstance(required, type):
        return issubclass(held, required)
    return isinstance(required, type) and isinstance(held, required)


@implementer(IPermissionPolicy)
class SubjectPermissionsPolicy:
    """The default policy: *subject* may run a command when one of the
    permissions it holds implies the required one.

    Both ingredients are replaceable: ``held(subject)`` lists what the
    subject holds, ``implies(held, required)`` says what grants what.
    """

    def __init__(
        self,
        held: Callable[[Any], Iterable[Any]] = default_held,
        implies: Callable[[Any, Any], bool] = default_implies,
    ) -> None:
        self._held = held
        self._implies = implies

    def implies(self, held: Any, required: Any) -> bool:
        return self._implies(held, required)

    def permits(self, subject: Any, required: Any, command: Any = None) -> bool:
        if required is None:
            return True
        return any(self._implies(held, required) for held in self._held(subject))


@implementer(IPermissionPolicy)
class AllowAll:
    """A policy that permits everything (the behaviour without a policy)."""

    def implies(self, held: Any, required: Any) -> bool:
        return True

    def permits(self, subject: Any, required: Any, command: Any = None) -> bool:
        return True


__all__ = [
    "AllowAll",
    "PermissionDeniedError",
    "Policy",
    "SubjectPermissionsPolicy",
    "default_held",
    "default_implies",
    "describe_permission",
]
