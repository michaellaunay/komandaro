"""Reference implementation of the Komandaro interfaces."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from typing import Any

from zope.interface import directlyProvidedBy, directlyProvides, implementer

from komandaro.i18n import Language, Message, _
from komandaro.interfaces import (
    IBrokenCommand,
    ICommand,
    IExecutedCommand,
    IMacro,
    ISimpleCommand,
    IUndoneCommand,
)
from komandaro.schema import validate

DoFunction = Callable[..., Any]
UndoFunction = Callable[..., Any]
SnapshotFunction = Callable[..., Any]


class CommandStateError(RuntimeError):
    """Raised when a life-cycle method is called in the wrong state.

    The message is lazy; ``str(error)`` uses the process language and
    :meth:`translate` selects an explicit language.
    """

    def __init__(self, message: Message, **params: Any) -> None:
        super().__init__(message)
        self.message = message
        self.params = params

    def __str__(self) -> str:
        """The message in the process language (see ``komandaro.i18n``)."""
        return self.message.localize(None, **self.params)

    def translate(self, language: Language = None, **kw: Any) -> str:
        """Return the error message in *language*."""
        return self.message.localize(language, **kw, **self.params)


class BaseCommand:
    """State machine shared by every command implementation.

    Subclasses implement :meth:`_do`, :meth:`_undo` and :meth:`_redo`; the
    public ``execute``/``undo``/``redo`` check the state, delegate, then
    move the instance to its next state.

    Class attributes describing the command (what a registry exposes):

    * ``id`` — stable identifier used by registries and front ends
      (defaults to the lower-cased class name without ``Command``);
    * ``name`` / ``description`` — translatable labels;
    * ``schema`` — an interface of ``zope.schema`` fields describing the
      accepted keyword parameters, or ``None`` to accept anything;
    * ``permission`` — what a subject must hold to run the command, or
      ``None`` for a public command (see ``komandaro.permissions``).

    Instances are created with the context and the parameters:
    ``cmd = Add(context, amount=5)``.  Parameters are validated against
    ``schema`` at that moment (:class:`~komandaro.schema.ParameterError`)
    and exposed as ``cmd.params``.

    Before ``_do()`` runs, :meth:`_snapshot` is called and its value kept
    in ``self.memento`` so that ``_undo()`` can restore state that cannot
    be derived from the result alone.
    """

    id: str = ""
    name: str = _("unnamed_command")
    description: str = ""
    schema: Any = None
    permission: Any = None

    def __init__(self, context: Any, **params: Any) -> None:
        self.context = context
        self.params: dict[str, Any] = validate(self.schema, params)
        self.result: Any = None
        self.memento: Any = None
        self._busy = False
        directlyProvides(self, ICommand)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not cls.__dict__.get("id"):
            base = cls.__name__.removesuffix("Command") or cls.__name__
            cls.id = base.lower()

    # -- public life cycle ---------------------------------------------------

    def execute(self) -> Any:
        with self._transition(ICommand, _("command_already_executed")):
            self.memento = self._snapshot()
            self.result = self._do()
            self._set_state(IExecutedCommand)
            return self.result

    def undo(self) -> Any:
        with self._transition(IExecutedCommand, _("command_not_undoable")):
            value = self._undo()
            self._set_state(IUndoneCommand)
            return value

    def redo(self) -> Any:
        with self._transition(IUndoneCommand, _("command_not_redoable")):
            self.result = self._redo()
            self._set_state(IExecutedCommand)
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

    @property
    def is_broken(self) -> bool:
        """True after compensation could not restore a consistent macro."""
        return bool(IBrokenCommand.providedBy(self))

    def _set_state(self, state: Any) -> None:
        markers = (ICommand, IExecutedCommand, IUndoneCommand, IBrokenCommand)
        others = [
            iface
            for iface in directlyProvidedBy(self)
            if not any(iface.isOrExtends(marker) for marker in markers)
        ]
        directlyProvides(self, *others, state)

    def _require(self, state: Any, message: Message) -> None:
        if self._busy:
            raise CommandStateError(_("command_busy"), name=self.name)
        if self.is_broken:
            raise CommandStateError(_("command_broken"), name=self.name)
        if not state.providedBy(self):
            raise CommandStateError(message, name=self.name)

    @contextmanager
    def _transition(self, state: Any, message: Message) -> Iterator[None]:
        self._require(state, message)
        self._busy = True
        try:
            yield
        finally:
            self._busy = False

    def _reset_ready(self) -> None:
        """Reset only an internally compensated, previously ready command."""
        self.result = None
        self.memento = None
        self._set_state(ICommand)

    # -- to be implemented by subclasses -------------------------------------

    def _snapshot(self) -> Any:
        """Capture whatever ``_undo`` will need; called before ``_do``."""
        return None

    def _do(self) -> Any:
        raise NotImplementedError

    def _undo(self) -> Any:
        raise NotImplementedError

    def _redo(self) -> Any:
        return self._do()

    def __repr__(self) -> str:
        state = (
            "broken" if self.is_broken else
            "ready" if self.is_ready else
            "executed" if self.is_executed else "undone"
        )
        return f"<{type(self).__name__} {self.name!s} [{state}]>"


# --------------------------------------------------------------------------
# Simple command
# --------------------------------------------------------------------------


@implementer(ISimpleCommand)
class SimpleCommand(BaseCommand):
    """A command whose behaviour is given by plain functions.

    * ``do_it(context, **params)`` performs the operation and returns a result;
    * ``undo_it(context, state, **params)`` reverts it, where *state* is the
      memento returned by ``snapshot_it`` when one is defined, and the
      result of ``do_it`` otherwise;
    * ``snapshot_it(context, **params)`` (optional) captures state before
      execution, for operations whose inverse cannot be derived from the
      result.

    All three are stored as static methods so that they are *not* bound to
    the instance when called.
    """

    do_it: Callable[..., Any] = staticmethod(lambda context, **params: None)
    undo_it: Callable[..., Any] = staticmethod(lambda context, state, **params: None)
    snapshot_it: Callable[..., Any] | None = None

    def _snapshot(self) -> Any:
        if self.snapshot_it is None:
            return None
        return self.snapshot_it(self.context, **self.params)

    def _do(self) -> Any:
        return self.do_it(self.context, **self.params)

    def _undo(self) -> Any:
        state = self.result if self.snapshot_it is None else self.memento
        return self.undo_it(self.context, state, **self.params)


def SimpleCommandFactory(  # noqa: N802 — historical name kept on purpose
    do_function: DoFunction,
    undo_function: UndoFunction,
    name: str | Message,
    description: str | Message = "",
    class_name: str | None = None,
    *,
    schema: Any = None,
    snapshot: SnapshotFunction | None = None,
    id: str | None = None,
) -> type[SimpleCommand]:
    """Build a :class:`SimpleCommand` subclass from a do/undo pair.

    The returned *class* is instantiated once per execution with the
    context and the parameters: ``cmd = MyCommand(context, amount=5)``.

    *name* and *description* should be :class:`~komandaro.i18n.Message`
    objects (``_("Add")``) so that front ends can translate them.
    *schema* is an interface of ``zope.schema`` fields; *snapshot* an
    optional ``snapshot(context, **params)`` memento function; *id* the
    registry identifier (derived from the class name by default).
    """
    attrs: dict[str, Any] = {
        "name": name,
        "description": description,
        "schema": schema,
        "do_it": staticmethod(do_function),
        "undo_it": staticmethod(undo_function),
        "snapshot_it": staticmethod(snapshot) if snapshot is not None else None,
        "__doc__": str(description) or str(name),
    }
    if id:
        attrs["id"] = id
    cls_name = class_name or "".join(part.capitalize() for part in str(name).split()) or "Command"
    return type(cls_name + "Command", (SimpleCommand,), attrs)


# --------------------------------------------------------------------------
# Macro
# --------------------------------------------------------------------------


@implementer(IMacro)
class Macro(BaseCommand):
    """A composite command: executes its children in order, undoes in reverse.

    Children are distinct command instances, organized as an acyclic tree.
    Completed steps are compensated when a transition fails. A successful
    compensation restores a retryable lifecycle; a failed compensation
    marks the macro broken and raises a BaseExceptionGroup containing the
    original error and every compensation error. Callbacks must be atomic
    on their own failures: this is not a database transaction.

    Subclasses may declare a ``schema`` and build their children from
    ``self.params`` in ``__init__``; the keyword names ``commands``, ``name``
    and ``description`` are reserved and cannot be parameters.
    """

    def __init__(
        self,
        context: Any,
        commands: Iterable[BaseCommand] = (),
        name: str | Message | None = None,
        description: str | Message | None = None,
        **params: Any,
    ) -> None:
        super().__init__(context, **params)
        self._commands: list[BaseCommand] = list(commands)
        walk_commands(self)
        if name is not None:
            self.name = name
        if description is not None:
            self.description = description

    name: str = _("macro_label")
    description: str = _("macro_description")

    @property
    def commands(self) -> tuple[BaseCommand, ...]:
        return tuple(self._commands)

    def add(self, command: BaseCommand) -> None:
        self._require(ICommand, _("macro_frozen"))
        previous = self._commands
        self._commands = [*previous, command]
        try:
            walk_commands(self)
        except BaseException:
            self._commands = previous
            raise

    def remove(self, command: BaseCommand) -> None:
        self._require(ICommand, _("macro_frozen"))
        self._commands.remove(command)

    def _run(self, action: str, inverse: str, *, reverse: bool = False) -> list[Any]:
        # Preflight the whole tree, including descendants, before any effect.
        expected = {
            "execute": ICommand,
            "undo": IExecutedCommand,
            "redo": IUndoneCommand,
        }[action]
        for child in walk_commands(self)[1:]:
            child._require(expected, _("macro_child_state"))
        children = tuple(reversed(self.commands)) if reverse else self.commands
        done: list[BaseCommand] = []
        results: list[Any] = []
        try:
            for command in children:
                results.append(getattr(command, action)())
                done.append(command)
        except BaseException as original:
            errors: list[BaseException] = []
            for command in reversed(done):
                try:
                    getattr(command, inverse)()
                    if action == "execute":
                        command._reset_ready()
                except BaseException as error:
                    errors.append(error)
            if errors or any(child.is_broken for child in children):
                self._set_state(IBrokenCommand)
            if errors:
                raise BaseExceptionGroup(
                    _("macro_compensation_failed").localize(), [original, *errors]
                ) from None
            raise
        return results

    def _reset_ready(self) -> None:
        for command in self.commands:
            command._reset_ready()
        super()._reset_ready()

    def _do(self) -> list[Any]:
        return self._run("execute", "undo")

    def _redo(self) -> list[Any]:
        return self._run("redo", "undo")

    def _undo(self) -> list[Any]:
        return self._run("undo", "redo", reverse=True)


def walk_commands(command: BaseCommand) -> tuple[BaseCommand, ...]:
    """Snapshot a command tree, rejecting cycles and shared instances.

    A command instance has one lifecycle and cannot occupy two positions in
    the same macro tree. The iterative traversal also avoids recursive loops
    during authorization, before any business callback is invoked.
    """
    pending = [command]
    seen: set[int] = set()
    commands: list[BaseCommand] = []
    while pending:
        current = pending.pop()
        if not isinstance(current, BaseCommand):
            raise TypeError("macro children must be BaseCommand instances")
        if id(current) in seen:
            raise ValueError("command trees cannot contain cycles or shared instances")
        seen.add(id(current))
        commands.append(current)
        if isinstance(current, Macro):
            pending.extend(reversed(current.commands))
    return tuple(commands)
