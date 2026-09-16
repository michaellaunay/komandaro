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

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from komandaro.command import BaseCommand
from komandaro.i18n import Message, _
from komandaro.registry import Registry


class HistoryError(RuntimeError):
    """Nothing to undo or redo."""

    def __init__(self, message: Message) -> None:
        super().__init__(message)
        self.message = message

    def translate(self, language: str | list[str] | None = None, **kw: Any) -> str:
        return self.message.localize(language, **kw)


class EventKind(StrEnum):
    EXECUTED = "executed"
    UNDONE = "undone"
    REDONE = "redone"
    FAILED = "failed"
    CLEARED = "cleared"


@dataclass(frozen=True, slots=True)
class Event:
    """What just happened to which command."""

    kind: EventKind
    command: BaseCommand | None
    error: BaseException | None = None
    at: datetime = field(default_factory=lambda: datetime.now(UTC))


Handler = Callable[[Event], None]


class Invoker:
    """Executes commands against one context and keeps their history."""

    def __init__(
        self,
        context: Any,
        registry: Registry | None = None,
        *,
        limit: int | None = None,
    ) -> None:
        self.context = context
        self.registry = registry
        self.limit = limit
        self._undo: list[BaseCommand] = []
        self._redo: list[BaseCommand] = []
        self._handlers: list[Handler] = []

    # -- observers -----------------------------------------------------------

    def subscribe(self, handler: Handler) -> Callable[[], None]:
        """Register *handler*; returns a function that unsubscribes it."""
        self._handlers.append(handler)

        def unsubscribe() -> None:
            self._handlers.remove(handler)

        return unsubscribe

    def _emit(self, kind: EventKind, command: BaseCommand | None, error: Any = None) -> None:
        event = Event(kind, command, error)
        for handler in list(self._handlers):
            handler(event)

    # -- running -------------------------------------------------------------

    def create(self, id: str, **params: Any) -> BaseCommand:
        """Instantiate command *id* from the registry, bound to this context."""
        if self.registry is None:
            raise HistoryError(_("This invoker has no registry"))
        return self.registry.create(id, self.context, **params)

    def run(self, command: BaseCommand | str, /, **params: Any) -> Any:
        """Execute *command* (an instance or a registry id) and record it."""
        if isinstance(command, str):
            command = self.create(command, **params)
        elif params:
            raise TypeError("parameters are only accepted with a registry id")
        try:
            result = command.execute()
        except BaseException as error:
            self._emit(EventKind.FAILED, command, error)
            raise
        self._undo.append(command)
        if self.limit is not None:
            del self._undo[: max(0, len(self._undo) - self.limit)]
        self._redo.clear()
        self._emit(EventKind.EXECUTED, command)
        return result

    def undo(self) -> Any:
        if not self._undo:
            raise HistoryError(_("Nothing to undo"))
        command = self._undo[-1]
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
        if not self._redo:
            raise HistoryError(_("Nothing to redo"))
        command = self._redo[-1]
        try:
            value = command.redo()
        except BaseException as error:
            self._emit(EventKind.FAILED, command, error)
            raise
        self._redo.pop()
        self._undo.append(command)
        self._emit(EventKind.REDONE, command)
        return value

    def clear(self) -> None:
        """Forget the history (the context is left as is)."""
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
