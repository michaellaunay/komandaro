"""Internationalisation support for Komandaro.

Conventions (the same as the AlirPunkto application):

* A user-facing string is a **message identifier** in ``snake_case`` —
  ``_("nothing_to_undo")`` — never an English sentence.  The English text
  lives in the ``en`` catalogue like any other language, so wording can be
  fixed without touching code.
* Placeholders use the ``${name}`` syntax (``string.Template``): the message
  ``command_already_executed`` is ``"Command ${name} has already been
  executed"`` in English.
* A :class:`Message` is *lazy*: a ``str`` subclass carrying the identifier
  and its gettext *domain*.  Nothing is translated until a front end calls
  :func:`translate` with the locale of the current user, so one process
  can serve many users.  When the requested language has no catalogue (or
  no entry), English is used, and failing that the identifier itself.

Library code::

    from komandaro.i18n import _
    name = _("macro_label")

Application code, binding its own catalogues once::

    _ = make_gettext("myapp", Path(__file__).parent / "locale")

Front end::

    translate(command.name, "fr")
"""

from __future__ import annotations

import gettext
import os
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from string import Template
from typing import Any

#: Default gettext domain used by the library itself.
DOMAIN = "komandaro"

#: Language used when the requested one has no catalogue or no entry.
FALLBACK_LANGUAGE = "en"

#: Directory holding the compiled catalogues shipped with the package.
DEFAULT_LOCALEDIR = Path(__file__).parent / "locale"

#: Where the catalogues of each domain live (:func:`bind_domain` adds entries).
LOCALEDIRS: dict[str, Path] = {DOMAIN: DEFAULT_LOCALEDIR}

Language = str | Iterable[str] | None


class Message(str):
    """A lazily translatable message identifier.

    Behaves exactly like ``str`` (printing, comparing, hashing) with the
    value of the identifier, and records the gettext *domain* it belongs to.
    """

    __slots__ = ("domain",)

    domain: str

    def __new__(cls, msgid: str, domain: str = DOMAIN) -> Message:
        obj = super().__new__(cls, msgid)
        obj.domain = domain
        return obj

    def localize(
        self, language: Language = None, localedir: str | Path | None = None, **params: Any
    ) -> str:
        """Translate this message and substitute ``${name}`` placeholders.

        Parameters that are themselves :class:`Message` objects are
        translated first, in the same language.  (Named ``localize`` because
        ``str.translate`` already exists.)
        """
        text = translate(self, language, localedir)
        if not params:
            return text
        values = {
            key: translate(value, language, localedir) if isinstance(value, Message) else value
            for key, value in params.items()
        }
        return Template(text).safe_substitute(values)

    def __reduce__(self) -> tuple[Any, ...]:  # pickling keeps the domain
        return (Message, (str(self), self.domain))


def bind_domain(domain: str, localedir: str | Path) -> None:
    """Declare where the catalogues of *domain* are, like ``gettext.bindtextdomain``.

    Once bound, :func:`translate` finds the domain's catalogues without a
    ``localedir`` argument, so a front end translates library and application
    messages alike with one call.
    """
    LOCALEDIRS[domain] = Path(localedir)


def make_gettext(
    domain: str = DOMAIN, localedir: str | Path | None = None
) -> Callable[[str], Message]:
    """Return a ``_`` function producing :class:`Message` objects for *domain*.

    Applications built on Komandaro create their own, binding the directory
    of their compiled catalogues at the same time::

        _ = make_gettext("myapp", Path(__file__).parent / "locale")
    """
    if localedir is not None:
        bind_domain(domain, localedir)

    def _(msgid: str) -> Message:
        return Message(msgid, domain)

    return _


#: The library's own marker function, recognised by ``pybabel extract``.
_ = make_gettext(DOMAIN)


def environment_languages(environ: Mapping[str, str] | None = None) -> list[str]:
    """The languages of the process, as gettext reads them from the environment.

    ``LANGUAGE`` (colon-separated) wins, then ``LC_ALL``, ``LC_MESSAGES``,
    ``LANG``; ``C``/``POSIX`` mean "no preference".
    """
    env = os.environ if environ is None else environ
    for name in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = env.get(name)
        if value:
            return [lang for lang in value.split(":") if lang and lang not in ("C", "POSIX")]
    return []


def _languages(language: Language) -> list[str]:
    if language is None:
        languages = environment_languages()
    elif isinstance(language, str):
        languages = [language]
    else:
        languages = list(language)
    if FALLBACK_LANGUAGE not in languages:
        languages.append(FALLBACK_LANGUAGE)
    return languages


def translate(message: str, language: Language = None, localedir: str | Path | None = None) -> str:
    """Translate *message* for *language*.

    * A plain ``str`` is returned unchanged; a :class:`Message` is looked up
      in the catalogue of its domain.
    * *language* may be a code (``"fr"``), a preference list
      (``["fr_FR", "fr", "de"]``) or ``None`` for the process environment
      (``LANGUAGE``, ``LC_ALL``, ``LC_MESSAGES``, ``LANG``).  English is
      always tried last, then the identifier itself is returned: the library
      never fails because of a missing translation.
    * *localedir* overrides the directory bound to the message's domain
      (see :func:`bind_domain`).
    """
    if not isinstance(message, Message) or message == "":
        # an empty msgid would return the catalogue header
        return str(message)
    directory = localedir or LOCALEDIRS.get(message.domain, DEFAULT_LOCALEDIR)
    catalogue = gettext.translation(
        message.domain, localedir=str(directory), languages=_languages(language), fallback=True
    )
    return catalogue.gettext(str(message))


__all__ = [
    "DEFAULT_LOCALEDIR",
    "DOMAIN",
    "FALLBACK_LANGUAGE",
    "LOCALEDIRS",
    "Language",
    "Message",
    "_",
    "bind_domain",
    "environment_languages",
    "make_gettext",
    "translate",
]
