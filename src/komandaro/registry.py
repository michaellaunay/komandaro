"""Command registry: the catalogue a front end reads to build itself.

A :class:`Registry` maps stable identifiers to command *classes*, organises
them in groups and can be populated by hand, with a decorator, or from
``importlib.metadata`` entry points so that third-party packages can
contribute commands::

    registry = Registry()

    @registry.command(group="math")
    class Add(SimpleCommand): ...

    registry.register(Remove, id="rm", group="files")
    registry.load_entry_points("myapp.commands")

    for entry in registry:               # ordered by registration
        print(entry.id, translate(entry.command.name, "fr"), entry.group)
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from importlib.metadata import entry_points
from typing import Any

from zope.interface import implementer

from komandaro.command import BaseCommand
from komandaro.i18n import Language, Message, _
from komandaro.interfaces import IEntry, IRegistry
from komandaro.permissions import Policy
from komandaro.schema import ParameterInfo, describe


class RegistryError(LookupError):
    """Unknown identifier, or identifier already taken."""

    def __init__(self, message: Message, **params: Any) -> None:
        super().__init__(message)
        self.message = message
        self.params = params

    def __str__(self) -> str:
        return self.message.localize(None, **self.params)

    def translate(self, language: Language = None, **kw: Any) -> str:
        return self.message.localize(language, **(kw | self.params))


@implementer(IEntry)
@dataclass(frozen=True, slots=True)
class Entry:
    """A registered command class with its registry metadata."""

    id: str
    command: type[BaseCommand]
    group: str | None = None
    tags: frozenset[str] = frozenset()

    @property
    def name(self) -> str:
        return self.command.name

    @property
    def description(self) -> str:
        return self.command.description

    @property
    def permission(self) -> Any:
        return self.command.permission

    @property
    def parameters(self) -> list[ParameterInfo]:
        return describe(self.command.schema)


@implementer(IRegistry)
class Registry:
    """Ordered mapping ``id → Entry`` of command classes."""

    def __init__(self) -> None:
        self._entries: dict[str, Entry] = {}

    # -- population ----------------------------------------------------------

    def register(
        self,
        command: type[BaseCommand],
        *,
        id: str | None = None,
        group: str | None = None,
        tags: Any = (),
        replace: bool = False,
    ) -> Entry:
        """Register *command* (a class) and return its :class:`Entry`."""
        if not (isinstance(command, type) and issubclass(command, BaseCommand)):
            raise TypeError(f"expected a BaseCommand subclass, got {command!r}")
        ident = command.id if id is None else id
        if not isinstance(ident, str):
            raise TypeError("command ids must be strings")
        if not ident.strip():
            raise ValueError("command ids cannot be empty")
        if ident in self._entries and not replace:
            raise RegistryError(_("command_already_registered"), id=ident)
        entry = Entry(ident, command, group, frozenset(tags))
        self._entries[ident] = entry
        return entry

    def command(
        self, id: str | None = None, *, group: str | None = None, tags: Any = ()
    ) -> Callable[[type[BaseCommand]], type[BaseCommand]]:
        """Class decorator: ``@registry.command("add", group="math")``."""

        def decorator(cls: type[BaseCommand]) -> type[BaseCommand]:
            self.register(cls, id=id, group=group, tags=tags)
            return cls

        return decorator

    def unregister(self, id: str) -> None:
        self._entries.pop(self._require(id).id)

    def load_entry_points(self, group: str, *, registry_group: str | None = None) -> list[Entry]:
        """Register every command class exposed under entry-point *group*.

        In a contributing package's ``pyproject.toml``::

            [project.entry-points."myapp.commands"]
            add = "mypkg.commands:Add"

        The entry-point name becomes the command id.
        """
        loaded = []
        for ep in entry_points(group=group):
            loaded.append(self.register(ep.load(), id=ep.name, group=registry_group))
        return loaded

    # -- lookup --------------------------------------------------------------

    def _require(self, id: str) -> Entry:
        try:
            return self._entries[id]
        except KeyError:
            raise RegistryError(_("unknown_command"), id=id) from None

    def get(self, id: str) -> Entry:
        return self._require(id)

    def __getitem__(self, id: str) -> type[BaseCommand]:
        return self._require(id).command

    def __contains__(self, id: object) -> bool:
        return id in self._entries

    def __iter__(self) -> Iterator[Entry]:
        return iter(list(self._entries.values()))

    def __len__(self) -> int:
        return len(self._entries)

    @property
    def ids(self) -> list[str]:
        return list(self._entries)

    @property
    def groups(self) -> dict[str | None, list[Entry]]:
        """Entries grouped by ``group`` (``None`` for ungrouped), in order."""
        out: dict[str | None, list[Entry]] = {}
        for entry in self:
            out.setdefault(entry.group, []).append(entry)
        return out

    def find(self, *, group: str | None = None, tag: str | None = None) -> list[Entry]:
        return [
            e
            for e in self
            if (group is None or e.group == group) and (tag is None or tag in e.tags)
        ]

    def allowed(self, policy: Policy | None, subject: Any) -> list[Entry]:
        """Entries whose command *subject* may run under *policy* (all when None)."""
        if policy is None:
            return list(self)
        return [e for e in self if policy.permits(subject, e.permission, e.command)]

    def create(self, id: str, context: Any, **params: Any) -> BaseCommand:
        """Instantiate command *id* bound to *context* with *params*."""
        entry = self._require(id)
        command = entry.command(context, **params)
        command.id = entry.id
        return command


__all__ = ["Entry", "Registry", "RegistryError"]
