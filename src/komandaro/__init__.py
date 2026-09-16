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

__version__ = "0.1.0"

__all__ = [
    "BaseCommand",
    "CommandStateError",
    "IBaseCommand",
    "ICommand",
    "IContext",
    "IExecutedCommand",
    "IMacro",
    "ISimpleCommand",
    "IUndoneCommand",
    "Macro",
    "Message",
    "SimpleCommand",
    "SimpleCommandFactory",
    "__version__",
    "make_gettext",
    "translate",
]
