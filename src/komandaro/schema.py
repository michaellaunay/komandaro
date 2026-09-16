"""Parameter schemas: what a command needs, declared once, consumed by every front end.

A command class declares its parameters as a ``zope.interface.Interface``
whose attributes are ``zope.schema`` fields::

    from zope.interface import Interface
    from zope.schema import Int

    class IAddParameters(Interface):
        amount = Int(title=_("Amount"), description=_("Value to add"), required=True)

    Add = SimpleCommandFactory(add, undo_add, _("Add"), schema=IAddParameters)

The schema serves two purposes:

* **validation** at instantiation (:func:`validate`), so a command is never
  built with missing or ill-typed parameters, whatever the front end;
* **description** (:func:`describe`), a neutral, ordered list of
  :class:`ParameterInfo` that a CLI turns into options, an HTML front end
  into form fields and an API into a JSON schema.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from zope.interface.interface import InterfaceClass
from zope.schema import getFieldsInOrder
from zope.schema.interfaces import (
    ConstraintNotSatisfied,
    IChoice,
    IField,
    InvalidValue,
    NotUnique,
    RequiredMissing,
    TooBig,
    TooLong,
    TooShort,
    TooSmall,
    ValidationError,
    WrongContainedType,
    WrongType,
)

from komandaro.i18n import Language, Message, _

#: Message identifiers for the usual ``zope.schema`` validation errors, most
#: specific first (``isinstance`` walk).  Unknown errors get ``field_invalid``.
FIELD_ERRORS: tuple[tuple[type[ValidationError], Message], ...] = (
    (TooShort, _("field_too_short")),
    (TooLong, _("field_too_long")),
    (TooSmall, _("field_too_small")),
    (TooBig, _("field_too_big")),
    (WrongContainedType, _("field_wrong_contained_type")),
    (WrongType, _("field_wrong_type")),
    (RequiredMissing, _("field_required_missing")),
    (ConstraintNotSatisfied, _("field_constraint_not_satisfied")),
    (NotUnique, _("field_not_unique")),
    (InvalidValue, _("field_invalid_value")),
)


@dataclass(frozen=True, slots=True)
class ParameterIssue:
    """One validation problem: which parameter, and a translatable message."""

    name: str
    message: Message
    params: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.message.localize(None, **self.params)

    def translate(self, language: Language = None, **kw: Any) -> str:
        return self.message.localize(language, **kw, **self.params)


class ParameterError(ValueError):
    """Raised when parameters do not satisfy the command's schema.

    ``issues`` lists every problem found (missing, unknown or invalid
    parameters) so that a front end can report them all at once.
    """

    def __init__(self, issues: list[ParameterIssue]) -> None:
        self.issues = list(issues)
        super().__init__(str(self))

    def __str__(self) -> str:
        return "; ".join(f"{issue.name}: {issue}" for issue in self.issues)

    def translate(self, language: Language = None, **kw: Any) -> dict[str, str]:
        """Return ``{parameter: localised message}``."""
        return {issue.name: issue.translate(language, **kw) for issue in self.issues}


@dataclass(frozen=True, slots=True)
class ParameterInfo:
    """Front-end neutral description of one parameter."""

    name: str
    type: str
    title: str
    description: str = ""
    required: bool = True
    default: Any = None
    choices: tuple[Any, ...] | None = None
    field: Any = field(default=None, repr=False, compare=False)

    @property
    def python_type(self) -> Any:
        """Best-effort Python type (``int``, ``str``…) for the field, or None."""
        return getattr(self.field, "_type", None)


def fields(schema: InterfaceClass | None) -> list[tuple[str, Any]]:
    """Ordered ``(name, field)`` pairs of *schema* (empty when ``None``)."""
    if schema is None:
        return []
    return list(getFieldsInOrder(schema))


def describe(schema: InterfaceClass | None) -> list[ParameterInfo]:
    """Describe *schema* as an ordered list of :class:`ParameterInfo`."""
    infos: list[ParameterInfo] = []
    for name, fld in fields(schema):
        choices: tuple[Any, ...] | None = None
        if IChoice.providedBy(fld) and getattr(fld, "vocabulary", None) is not None:
            choices = tuple(term.value for term in fld.vocabulary)
        infos.append(
            ParameterInfo(
                name=name,
                type=type(fld).__name__,
                title=fld.title or name,
                description=fld.description or "",
                required=bool(fld.required),
                default=fld.default,
                choices=choices,
                field=fld,
            )
        )
    return infos


def validate(schema: InterfaceClass | None, params: Mapping[str, Any]) -> dict[str, Any]:
    """Validate *params* against *schema* and return the completed mapping.

    * unknown names are rejected,
    * missing optional parameters take the field's default,
    * missing required parameters and invalid values are reported together,
      one message per parameter, in a :class:`ParameterError`.

    With ``schema=None`` any parameters are accepted unchanged.
    """
    if schema is None:
        return dict(params)

    issues: list[ParameterIssue] = []
    known = dict(fields(schema))
    for name in params:
        if name not in known:
            issues.append(ParameterIssue(name, _("unknown_parameter"), {"name": name}))
    result: dict[str, Any] = {}
    for name, fld in known.items():
        if name in params:
            value = params[name]
        elif fld.required:
            issues.append(ParameterIssue(name, _("missing_parameter"), {"name": name}))
            continue
        else:
            value = fld.default
        if value is None and not fld.required:
            result[name] = None
            continue
        try:
            fld.validate(value)
        except ValidationError as error:
            issues.append(
                ParameterIssue(
                    name,
                    _("invalid_parameter"),
                    {"name": name, "error": describe_error(error)},
                )
            )
            continue
        result[name] = value
    if issues:
        raise ParameterError(issues)
    return result


def describe_error(error: ValidationError) -> Message:
    """The translatable message identifier for a ``zope.schema`` error."""
    for cls, message in FIELD_ERRORS:
        if isinstance(error, cls):
            return message
    return _("field_invalid")


def is_schema(obj: Any) -> bool:
    """True when *obj* is an interface usable as a parameter schema."""
    return isinstance(obj, InterfaceClass)


__all__ = [
    "FIELD_ERRORS",
    "IField",
    "ParameterError",
    "ParameterInfo",
    "ParameterIssue",
    "describe",
    "describe_error",
    "fields",
    "is_schema",
    "validate",
]
