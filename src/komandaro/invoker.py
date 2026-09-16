"""The invoker: runs commands, keeps the history, notifies observers.

Front ends never call ``execute()`` themselves; they hand commands (or
registry ids and parameters) to an :class:`Invoker` bound to a context::

    invoker = Invoker(context, registry)
    invoker.run("add", amount=5)      # by id, via the registry
    invoker.run(Add(context, amount=5))  # or an instance
    invoker.undo(); invoker.redo()
    invoker.subscribe(lambda event: print(event.kind, event.command))

The invoker owns two stacks (undo and redo).  Running a new command clears
the redo stack, as in every editor.  Every transition emits an
:class:`Event` to the subscribed handlers, which is how a UI refreshes,
an audit log records, or a persistence layer stores what happened.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from zope.interface import implementer

from komandaro.command import BaseCommand, walk_commands
from komandaro.i18n import Language, Message, _
from komandaro.interfaces import IEvent, IInvoker
from komandaro.permissions import PermissionDeniedError, Policy
from komandaro.registry import Registry


_LOG = logging.getLogger(__name__)


class HistoryError(RuntimeError):
    """No available history transition, or a reentrant mutation."""

    def __init__(self, message: Message) -> None:
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        return self.message.localize(None)

    def translate(self, language: Language = None, **kw: Any) -> str:
        return self.message.localize(language, **kw)


class EventKind(StrEnum):
    EXECUTED = "executed"
    UNDONE = "undone"
    REDONE = "redone"
    FAILED = "failed"
    DENIED = "denied"
    CLEARED = "cleared"


@implementer(IEvent)
@dataclass(frozen=True, slots=True)
class Event:
    """What just happened to which command."""

    kind: EventKind
    command: BaseCommand | None
    error: BaseException | None = None
    at: datetime = field(default_factory=lambda: datetime.now(UTC))


Handler = Callable[[Event], None]


@implementer(IInvoker)
class Invoker:
    """Executes commands against one context and keeps their history.

    With a *policy*, ``run``, ``undo`` and ``redo`` authorize the current
    subject against the entire command tree before executing any callback.
    Applications must isolate histories by context and security principal.
    """

    def __init__(
        self,
        context: Any,
        registry: Registry | None = None,
        *,
        limit: int | None = None,
        policy: Policy | None = None,
        subject: Any = None,
    ) -> None:
        self.context = context
        self.registry = registry
        self._busy = False
        self.limit = limit
        self.policy = policy
        self.subject = subject
        self._undo: list[BaseCommand] = []
        self._redo: list[BaseCommand] = []
        self._handlers: list[Handler] = []

    @property
    def limit(self) -> int | None:
        """Maximum retained undo entries; None is unbounded, zero disables retention."""
        return self._limit

    @limit.setter
    def limit(self, value: int | None) -> None:
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError("history limit must be an integer or None")
            if value < 0:
                raise ValueError("history limit cannot be negative")
        self._limit = value

    def _trim_history(self) -> None:
        if self.limit is not None:
            del self._undo[: max(0, len(self._undo) - self.limit)]

    @contextmanager
    def _operation(self) -> Iterator[None]:
        if self._busy:
            raise HistoryError(_("invoker_busy"))
        self._busy = True
        try:
            yield
        finally:
            self._busy = False

    # -- observers -----------------------------------------------------------

    def subscribe(self, handler: Handler) -> Callable[[], None]:
        """Register *handler* and return an idempotent unsubscribe function.

        Each registration is independent, even for the same callable.
        Ordinary observer exceptions are logged and do not change outcomes.
        """
        if not callable(handler):
            raise TypeError("event handlers must be callable")

        def registered(event: Event) -> None:
            handler(event)

        self._handlers.append(registered)
        active = True

        def unsubscribe() -> None:
            nonlocal active
            if active:
                self._handlers.remove(registered)
                active = False

        return unsubscribe

    def _emit(self, kind: EventKind, command: BaseCommand | None, error: Any = None) -> None:
        event = Event(kind, command, error)
        for handler in list(self._handlers):
            try:
                handler(event)
            except Exception:
                _LOG.exception("Observer failed while handling %s", kind)

    def _authorize(self, command: BaseCommand) -> None:
        tree = walk_commands(command)
        # Identity matters: equal-looking contexts may belong to other users.
        if any(child.context is not self.context for child in tree):
            raise ValueError("all commands must belong to the invoker context")
        if self.policy is None:
            return
        for child in tree:
            if not self.policy.permits(self.subject, child.permission, child):
                denied = PermissionDeniedError(child.id, child.permission, self.subject)
                self._emit(EventKind.DENIED, child, denied)
                raise denied

    # -- running -------------------------------------------------------------

    def create(self, id: str, **params: Any) -> BaseCommand:
        """Instantiate command *id* from the registry, bound to this context."""
        if self.registry is None:
            raise HistoryError(_("invoker_without_registry"))
        return self.registry.create(id, self.context, **params)

    def run(self, command: BaseCommand | str, /, **params: Any) -> Any:
        """Execute *command* (an instance or a registry id) and record it."""
        with self._operation():
            if isinstance(command, str):
                command = self.create(command, **params)
            elif params:
                raise TypeError("parameters are only accepted with a registry id")
            self._authorize(command)
            try:
                result = command.execute()
            except BaseException as error:
                self._emit(EventKind.FAILED, command, error)
                raise
            self._undo.append(command)
            self._trim_history()
            self._redo.clear()
            self._emit(EventKind.EXECUTED, command)
            return result

    def undo(self) -> Any:
        with self._operation():
            if not self._undo:
                raise HistoryError(_("nothing_to_undo"))
            command = self._undo[-1]
            self._authorize(command)
            try:
                value = command.undo()
            except BaseException as error:
                self._emit(EventKind.FAILED, command, error)
                raise
            self._undo.pop()
            self._redo.append(command)
            self._emit(EventKind.UNDONE, command)
            return value

    def redo(self) -> Any:
        with self._operation():
            if not self._redo:
                raise HistoryError(_("nothing_to_redo"))
            command = self._redo[-1]
            self._authorize(command)
            try:
                value = command.redo()
            except BaseException as error:
                self._emit(EventKind.FAILED, command, error)
                raise
            self._redo.pop()
            self._undo.append(command)
            self._trim_history()
            self._emit(EventKind.REDONE, command)
            return value

    def clear(self) -> None:
        """Forget the history (the context is left as is)."""
        with self._operation():
            self._undo.clear()
            self._redo.clear()
            self._emit(EventKind.CLEARED, None)

    # -- introspection -------------------------------------------------------

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    @property
    def history(self) -> tuple[BaseCommand, ...]:
        """Executed commands, oldest first."""
        return tuple(self._undo)

    @property
    def undone(self) -> tuple[BaseCommand, ...]:
        """Undone commands awaiting redo, oldest first."""
        return tuple(self._redo)

    def __iter__(self) -> Iterator[BaseCommand]:
        return iter(self.history)

    def __len__(self) -> int:
        return len(self._undo)


__all__ = ["Event", "EventKind", "Handler", "HistoryError", "Invoker"]
