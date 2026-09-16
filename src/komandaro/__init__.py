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
from komandaro.i18n import Message, make_gettext, translate
from komandaro.interfaces import (
    IBaseCommand,
    ICommand,
    IContext,
    IExecutedCommand,
    IMacro,
    ISimpleCommand,
    IUndoneCommand,
)
from komandaro.invoker import Event, EventKind, HistoryError, Invoker
from komandaro.registry import Entry, Registry, RegistryError
from komandaro.schema import ParameterError, ParameterInfo, ParameterIssue, describe, validate

__version__ = "0.2.1"

__all__ = [
    "BaseCommand",
    "CommandStateError",
    "Entry",
    "Event",
    "EventKind",
    "HistoryError",
    "IBaseCommand",
    "ICommand",
    "IContext",
    "IExecutedCommand",
    "IMacro",
    "ISimpleCommand",
    "IUndoneCommand",
    "Invoker",
    "Macro",
    "Message",
    "ParameterError",
    "ParameterInfo",
    "ParameterIssue",
    "Registry",
    "RegistryError",
    "SimpleCommand",
    "SimpleCommandFactory",
    "__version__",
    "describe",
    "make_gettext",
    "translate",
    "validate",
]
