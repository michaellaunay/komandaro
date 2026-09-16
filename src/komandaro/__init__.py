"""Komandaro — a small, undoable Command pattern toolkit.

Write your application logic once as commands; expose it through a CLI,
an HTML UI, a TUI or an API without touching the logic.
"""

from komandaro.command import (
    BaseCommand,
    CommandStateError,
    Macro,
    SimpleCommand,
    SimpleCommandFactory,
)
from komandaro.i18n import Message, bind_domain, make_gettext, translate
from komandaro.interfaces import (
    IBaseCommand,
    ICommand,
    IContext,
    IEntry,
    IEvent,
    IExecutedCommand,
    IInvoker,
    IMacro,
    IPermissionPolicy,
    IRegistry,
    ISimpleCommand,
    IUndoneCommand,
)
from komandaro.invoker import Event, EventKind, HistoryError, Invoker
from komandaro.permissions import AllowAll, PermissionDeniedError, SubjectPermissionsPolicy
from komandaro.registry import Entry, Registry, RegistryError
from komandaro.schema import ParameterError, ParameterInfo, ParameterIssue, describe, validate

__version__ = "0.3.0"

__all__ = [
    "AllowAll",
    "BaseCommand",
    "CommandStateError",
    "Entry",
    "Event",
    "EventKind",
    "HistoryError",
    "IBaseCommand",
    "ICommand",
    "IContext",
    "IEntry",
    "IEvent",
    "IExecutedCommand",
    "IInvoker",
    "IMacro",
    "IPermissionPolicy",
    "IRegistry",
    "ISimpleCommand",
    "IUndoneCommand",
    "Invoker",
    "Macro",
    "Message",
    "ParameterError",
    "ParameterInfo",
    "ParameterIssue",
    "PermissionDeniedError",
    "Registry",
    "RegistryError",
    "SimpleCommand",
    "SimpleCommandFactory",
    "SubjectPermissionsPolicy",
    "__version__",
    "bind_domain",
    "describe",
    "make_gettext",
    "translate",
    "validate",
]
