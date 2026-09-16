"""Interfaces of the Command pattern as implemented by Komandaro.

Two orthogonal families of interfaces are used:

**Kinds** (what a command *is*), declared once on the class:

* :class:`ISimpleCommand` — a do/undo pair of functions.
* :class:`IMacro` — a composite of other commands.

**States** (where a command *is* in its life cycle), provided *directly* on
the instance and swapped at each transition:

* :class:`ICommand` — ready, can be executed once.
* :class:`IExecutedCommand` — has been executed, can be undone.
* :class:`IUndoneCommand` — has been undone, can be redone.

Keeping kinds and states separate is what allows
``zope.interface.directlyProvides`` to switch the state marker without ever
touching the interfaces declared by the class (removing a class-level
interface with ``noLongerProvides`` is not allowed and raises ``ValueError``).
"""

from __future__ import annotations

from zope.interface import Attribute, Interface

# --------------------------------------------------------------------------
# Context
# --------------------------------------------------------------------------


class IContext(Interface):
    """The execution context handed to a command.

    Komandaro makes no assumption about it: a plain object, a dict-like, a
    database session, an application root…  Front ends build it, commands
    read and mutate it.
    """


# --------------------------------------------------------------------------
# Common attributes
# --------------------------------------------------------------------------


class IBaseCommand(Interface):
    """Attributes shared by every command, whatever its kind or state."""

    name = Attribute(
        "Short human readable name.  A translatable komandaro.i18n.Message "
        "that front ends translate into the user's locale."
    )
    description = Attribute("Longer description of what the command does.  Also a Message.")
    context = Attribute("The IContext the command was bound to.")
    result = Attribute("Value returned by the last execute()/redo(), or None.")


# --------------------------------------------------------------------------
# States
# --------------------------------------------------------------------------


class ICommand(IBaseCommand):
    """A command ready to be executed, exactly once.

    After ``execute()`` the instance no longer provides ICommand and provides
    IExecutedCommand instead.  To run the same operation several times,
    instantiate the command class again for each run.
    """

    def execute():
        """Execute the command and return its result."""


class IExecutedCommand(IBaseCommand):
    """A command that has been executed and can be undone.

    After ``undo()`` the instance provides IUndoneCommand instead.
    """

    def undo():
        """Restore the context as it was before execution; return a value."""


class IUndoneCommand(IBaseCommand):
    """A command that has been undone and can be redone.

    After ``redo()`` the instance provides IExecutedCommand again.
    """

    def redo():
        """Execute again with the same context and parameters."""


# --------------------------------------------------------------------------
# Kinds
# --------------------------------------------------------------------------


class ISimpleCommand(IBaseCommand):
    """A command built from a *do* function and its inverse *undo* function."""


class IMacro(IBaseCommand):
    """A command made of sub-commands executed in order, undone in reverse.

    Execution is atomic: if a sub-command fails, the ones already executed
    are undone (in reverse order) before the exception propagates.
    """

    commands = Attribute("Tuple of the sub-commands, in execution order.")

    def add(command):
        """Append a sub-command.  Only allowed while the macro is ready."""

    def remove(command):
        """Remove a sub-command.  Only allowed while the macro is ready."""
