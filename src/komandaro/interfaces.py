"""Interfaces of the Command pattern as implemented by Komandaro.

Two orthogonal families of interfaces describe a command:

**Kinds** (what a command *is*), declared once on the class:

* :class:`ISimpleCommand` — a do/undo pair of functions.
* :class:`IMacro` — a composite of other commands.

**States** (where a command *is* in its life cycle), provided *directly* on
the instance and swapped at each transition:

* :class:`ICommand` — ready, can be executed once.
* :class:`IExecutedCommand` — has been executed, can be undone.
* :class:`IUndoneCommand` — has been undone, can be redone.
* :class:`IBrokenCommand` — compensation failed; application recovery required.

Keeping kinds and states separate is what allows
``zope.interface.directlyProvides`` to switch the state marker without ever
touching the interfaces declared by the class (removing a class-level
interface with ``noLongerProvides`` is not allowed and raises ``ValueError``).

The other contracts — :class:`IRegistry`, :class:`IEntry`, :class:`IInvoker`,
:class:`IEvent`, :class:`IPermissionPolicy` — describe the objects a front
end talks to.  ``tests/test_interfaces.py`` verifies every implementation
against its interface so that the two cannot drift apart.
"""

from __future__ import annotations

from zope.interface import Attribute, Interface

# --------------------------------------------------------------------------
# Context
# --------------------------------------------------------------------------


class IContext(Interface):
    """Optional marker for the execution context handed to a command.

    Komandaro never checks it: a plain object, a dict-like, a database
    session, an application root… all work.  Applications that want to
    register commands as adapters of their context in a component registry
    may make it provide this interface.
    """


# --------------------------------------------------------------------------
# Common attributes
# --------------------------------------------------------------------------


class IBaseCommand(Interface):
    """Attributes shared by every command, whatever its kind or state."""

    id = Attribute("Stable identifier used by registries and front ends.")
    name = Attribute("Short human readable name (a translatable komandaro.i18n.Message).")
    description = Attribute("Longer description of what the command does (a Message).")
    schema = Attribute("Interface of zope.schema fields describing the parameters, or None.")
    permission = Attribute("Permission required to run the command, or None (public).")
    context = Attribute("The context the command was bound to.")
    params = Attribute("The validated parameters of this execution (dict).")
    result = Attribute("Value returned by the last execute()/redo(), or None.")
    memento = Attribute("Value captured by _snapshot() before the first execution.")


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


class IBrokenCommand(IBaseCommand):
    """A failed compensation left the command unusable until application recovery."""


# --------------------------------------------------------------------------
# Kinds
# --------------------------------------------------------------------------


class ISimpleCommand(IBaseCommand):
    """A command built from a *do* function and its inverse *undo* function."""

    do_it = Attribute("Static ``do_it(context, **params) -> result``.")
    undo_it = Attribute(
        "Static ``undo_it(context, state, **params)``; *state* is the memento when "
        "``snapshot_it`` is defined, the result otherwise."
    )
    snapshot_it = Attribute("Static ``snapshot_it(context, **params) -> memento``, or None.")


class IMacro(IBaseCommand):
    """A command made of sub-commands executed in order, undone in reverse.

    Completed steps are compensated before a failure propagates. Failed
    compensation marks the macro broken; business callbacks must themselves
    be atomic on failure. This interface does not guarantee database atomicity.
    """

    commands = Attribute("Tuple of the sub-commands, in execution order.")

    def add(command):
        """Append a sub-command.  Only allowed while the macro is ready."""

    def remove(command):
        """Remove a sub-command.  Only allowed while the macro is ready."""


# --------------------------------------------------------------------------
# Permissions
# --------------------------------------------------------------------------


class IPermissionPolicy(Interface):
    """Decides whether a *subject* may run a command requiring a *permission*.

    Komandaro treats permissions as opaque values: strings, flags of an
    ``IntFlag`` enum, classes of a permission hierarchy… the policy alone
    gives them meaning, which is what makes the model replaceable.
    """

    def implies(held, required):
        """True when holding *held* grants *required*."""

    def permits(subject, required, command=None):
        """True when *subject* may run *command*, which requires *required*."""


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------


class IEntry(Interface):
    """A registered command class with its registry metadata."""

    id = Attribute("Identifier under which the command is registered.")
    command = Attribute("The command class.")
    group = Attribute("Optional group name.")
    tags = Attribute("Frozen set of tags.")
    name = Attribute("The command's translatable name.")
    description = Attribute("The command's translatable description.")
    permission = Attribute("The command's required permission, or None.")
    parameters = Attribute("List of ParameterInfo describing the command's schema.")


class IRegistry(Interface):
    """Ordered mapping ``id -> IEntry`` of command classes."""

    ids = Attribute("Registered identifiers, in registration order.")
    groups = Attribute("Entries grouped by group name (None for ungrouped).")

    def register(command, *, id=None, group=None, tags=(), replace=False):
        """Register a command class; return its IEntry."""

    def command(id=None, *, group=None, tags=()):
        """Class decorator doing the same."""

    def unregister(id):
        """Remove an entry."""

    def load_entry_points(group, *, registry_group=None):
        """Register the command classes exposed under an entry-point group."""

    def get(id):
        """Return the IEntry for *id* (RegistryError when unknown)."""

    def find(*, group=None, tag=None):
        """Entries matching a group and/or a tag."""

    def allowed(policy, subject):
        """Entries whose command *subject* may run under *policy*."""

    def create(id, context, **params):
        """Instantiate command *id* bound to *context*."""


# --------------------------------------------------------------------------
# Invoker
# --------------------------------------------------------------------------


class IEvent(Interface):
    """What just happened to which command."""

    kind = Attribute("An EventKind.")
    command = Attribute("The command concerned, or None.")
    error = Attribute("The exception for failed/denied events, else None.")
    at = Attribute("UTC timestamp.")


class IInvoker(Interface):
    """Executes commands against one context and keeps their history."""

    context = Attribute("The context commands are bound to.")
    registry = Attribute("Optional IRegistry used to create commands by id.")
    policy = Attribute("Optional policy consulted before run, undo and redo.")
    subject = Attribute("Who is running the commands (opaque, for the policy).")
    limit = Attribute("Maximum size of the undo stack, or None.")
    history = Attribute("Executed commands, oldest first.")
    undone = Attribute("Undone commands awaiting redo, oldest first.")
    can_undo = Attribute(
        "Whether the undo stack is nonempty; not a permission or success guarantee."
    )
    can_redo = Attribute(
        "Whether the redo stack is nonempty; not a permission or success guarantee."
    )

    def create(id, **params):
        """Instantiate command *id* via the registry, bound to this context."""

    def run(command, /, **params):
        """Execute a command (instance or registry id) and record it."""

    def undo():
        """Undo the last executed command."""

    def redo():
        """Redo the last undone command."""

    def clear():
        """Forget the history."""

    def subscribe(handler):
        """Register an IEvent handler; return the function that unsubscribes it."""
