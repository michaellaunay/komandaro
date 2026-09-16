"""Reference implementation of the Komandaro interfaces."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from zope.interface import directlyProvides, implementer

from komandaro.i18n import Message, _
from komandaro.interfaces import (
    ICommand,
    IExecutedCommand,
    IMacro,
    ISimpleCommand,
    IUndoneCommand,
)

DoFunction = Callable[[Any], Any]
UndoFunction = Callable[[Any, Any], Any]


class CommandStateError(RuntimeError):
    """Raised when a life-cycle method is called in the wrong state.

    The message is a lazy :class:`~komandaro.i18n.Message`; ``str(error)``
    gives the untranslated text, :meth:`translate` gives the localised one.
    """

    def __init__(self, message: Message, **params: Any) -> None:
        super().__init__(message)
        self.message = message
        self.params = params

    def __str__(self) -> str:
        return str(self.message) % self.params if self.params else str(self.message)

    def translate(self, language: str | Iterable[str] | None = None, **kw: Any) -> str:
        """Return the error message in *language*."""
        return self.message.localize(language, **kw, **self.params)


class BaseCommand:
    """State machine shared by every command implementation.

    Subclasses implement :meth:`_do`, :meth:`_undo` and :meth:`_redo`; the
    public ``execute``/``undo``/``redo`` check the state, delegate, then
    move the instance to its next state.
    """

    name: str = _("Unnamed command")
    description: str = ""

    def __init__(self, context: Any) -> None:
        self.context = context
        self.result: Any = None
        directlyProvides(self, ICommand)

    # -- public life cycle ---------------------------------------------------

    def execute(self) -> Any:
        self._require(ICommand, _("Command %(name)s has already been executed"))
        self.result = self._do()
        directlyProvides(self, IExecutedCommand)
        return self.result

    def undo(self) -> Any:
        self._require(IExecutedCommand, _("Command %(name)s cannot be undone in its current state"))
        value = self._undo()
        directlyProvides(self, IUndoneCommand)
        return value

    def redo(self) -> Any:
        self._require(IUndoneCommand, _("Command %(name)s cannot be redone in its current state"))
        self.result = self._redo()
        directlyProvides(self, IExecutedCommand)
        return self.result

    # -- state helpers -------------------------------------------------------

    @property
    def is_ready(self) -> bool:
        return bool(ICommand.providedBy(self))

    @property
    def is_executed(self) -> bool:
        return bool(IExecutedCommand.providedBy(self))

    @property
    def is_undone(self) -> bool:
        return bool(IUndoneCommand.providedBy(self))

    def _require(self, state: Any, message: Message) -> None:
        if not state.providedBy(self):
            raise CommandStateError(message, name=str(self.name))

    # -- to be implemented by subclasses -------------------------------------

    def _do(self) -> Any:
        raise NotImplementedError

    def _undo(self) -> Any:
        raise NotImplementedError

    def _redo(self) -> Any:
        return self._do()

    def __repr__(self) -> str:
        state = "ready" if self.is_ready else "executed" if self.is_executed else "undone"
        return f"<{type(self).__name__} {self.name!s} [{state}]>"


# --------------------------------------------------------------------------
# Simple command
# --------------------------------------------------------------------------


@implementer(ISimpleCommand)
class SimpleCommand(BaseCommand):
    """A command whose behaviour is given by two functions.

    ``do_it(context)`` performs the operation and returns a result;
    ``undo_it(context, result)`` reverts it.  Both are stored as static
    methods so that they are *not* bound to the instance when called.
    """

    do_it: Callable[..., Any] = staticmethod(lambda context: None)
    undo_it: Callable[..., Any] = staticmethod(lambda context, result: None)

    def _do(self) -> Any:
        return self.do_it(self.context)

    def _undo(self) -> Any:
        return self.undo_it(self.context, self.result)


def SimpleCommandFactory(  # noqa: N802 — historical name kept on purpose
    do_function: DoFunction,
    undo_function: UndoFunction,
    name: str | Message,
    description: str | Message = "",
    class_name: str | None = None,
) -> type[SimpleCommand]:
    """Build a :class:`SimpleCommand` subclass from a do/undo pair.

    The returned *class* is instantiated once per execution with the
    context: ``cmd = MyCommand(context); cmd.execute()``.

    *name* and *description* should be :class:`~komandaro.i18n.Message`
    objects (``_("Add")``) so that front ends can translate them.
    """
    attrs = {
        "name": name,
        "description": description,
        "do_it": staticmethod(do_function),
        "undo_it": staticmethod(undo_function),
        "__doc__": str(description) or str(name),
    }
    cls_name = class_name or "".join(part.capitalize() for part in str(name).split()) or "Command"
    return type(cls_name + "Command", (SimpleCommand,), attrs)


# --------------------------------------------------------------------------
# Macro
# --------------------------------------------------------------------------


@implementer(IMacro)
class Macro(BaseCommand):
    """A composite command: executes its children in order, undoes in reverse.

    Children are command *instances* already bound to a context (usually the
    same one).  If a child raises during ``execute``, the children already
    executed are undone in reverse order and the exception is re-raised, so
    the macro is atomic.
    """

    def __init__(
        self,
        context: Any,
        commands: Iterable[BaseCommand] = (),
        name: str | Message | None = None,
        description: str | Message | None = None,
    ) -> None:
        super().__init__(context)
        self._commands: list[BaseCommand] = list(commands)
        if name is not None:
            self.name = name
        if description is not None:
            self.description = description

    name: str = _("Macro")
    description: str = _("A sequence of commands executed as one")

    @property
    def commands(self) -> tuple[BaseCommand, ...]:
        return tuple(self._commands)

    def add(self, command: BaseCommand) -> None:
        self._require(ICommand, _("Macro %(name)s cannot be modified once executed"))
        self._commands.append(command)

    def remove(self, command: BaseCommand) -> None:
        self._require(ICommand, _("Macro %(name)s cannot be modified once executed"))
        self._commands.remove(command)

    def _run(self, step: Callable[[BaseCommand], Any]) -> list[Any]:
        done: list[BaseCommand] = []
        results: list[Any] = []
        try:
            for command in self._commands:
                results.append(step(command))
                done.append(command)
        except BaseException:
            for command in reversed(done):
                command.undo()
            raise
        return results

    def _do(self) -> list[Any]:
        return self._run(lambda c: c.execute())

    def _redo(self) -> list[Any]:
        return self._run(lambda c: c.redo())

    def _undo(self) -> list[Any]:
        return [command.undo() for command in reversed(self._commands)]
