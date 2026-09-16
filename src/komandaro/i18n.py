"""Internationalisation support for Komandaro.

Commands carry *lazy* messages: a :class:`Message` is a plain ``str``
subclass that remembers it is a gettext message id.  Nothing is translated
until a front end (CLI, HTML, TUI…) calls :func:`translate` with the locale
of the current user.  This keeps the core free of any global "current
language" state, which matters when the same process serves several users
(a web server) or several sessions.

Usage in library or application code::

    from komandaro.i18n import _

    name = _("Add")

Usage in a front end::

    from komandaro.i18n import translate

    label = translate(command.name, "fr")

Catalogues live in ``komandaro/locale/<lang>/LC_MESSAGES/komandaro.mo``.
They are compiled from the ``.po`` files with ``pybabel compile``.
"""

from __future__ import annotations

import gettext
from collections.abc import Iterable
from pathlib import Path
from typing import Any

#: Default gettext domain used by the library itself.
DOMAIN = "komandaro"

#: Directory holding the compiled catalogues shipped with the package.
DEFAULT_LOCALEDIR = Path(__file__).parent / "locale"


class Message(str):
    """A lazily translatable string.

    Behaves exactly like ``str`` (so it can be printed, compared, used as a
    dict key…) but records the gettext *domain* it belongs to.  The value of
    the string is the message id (the untranslated text).
    """

    __slots__ = ("domain",)

    domain: str

    def __new__(cls, msgid: str, domain: str = DOMAIN) -> Message:
        obj = super().__new__(cls, msgid)
        obj.domain = domain
        return obj

    def localize(
        self,
        language: str | Iterable[str] | None = None,
        localedir: str | Path | None = None,
        **params: Any,
    ) -> str:
        """Translate this message and, if *params* are given, ``%``-format it.

        (Named ``localize`` because ``str.translate`` already exists.)
        """
        text = translate(self, language, localedir)
        return text % params if params else text

    def __reduce__(self) -> tuple[Any, ...]:  # pickling keeps the domain
        return (Message, (str(self), self.domain))


def make_gettext(domain: str = DOMAIN) -> Any:
    """Return a ``_`` function producing :class:`Message` objects for *domain*.

    Applications built on Komandaro should create their own::

        _ = make_gettext("myapp")
    """

    def _(msgid: str) -> Message:
        return Message(msgid, domain)

    return _


#: The library's own marker function, recognised by ``pybabel extract``.
_ = make_gettext(DOMAIN)


def translate(
    message: str,
    language: str | Iterable[str] | None = None,
    localedir: str | Path | None = None,
) -> str:
    """Translate *message* for *language*.

    * A plain ``str`` is returned unchanged.
    * A :class:`Message` is looked up in the catalogue of its domain.
    * *language* may be a single code (``"fr"``), a preference list
      (``["fr_FR", "fr", "en"]``) or ``None`` to use the process environment
      (``LANGUAGE``, ``LC_ALL``, ``LC_MESSAGES``, ``LANG``).
    * When no catalogue is found, the message id is returned (gettext
      fallback), so the library never fails because of a missing translation.
    """
    if not isinstance(message, Message) or message == "":
        # an empty msgid would return the catalogue header
        return str(message)
    languages: list[str] | None
    if language is None:
        languages = None
    elif isinstance(language, str):
        languages = [language]
    else:
        languages = list(language)
    catalogue = gettext.translation(
        message.domain,
        localedir=str(localedir or DEFAULT_LOCALEDIR),
        languages=languages,
        fallback=True,
    )
    return catalogue.gettext(str(message))
