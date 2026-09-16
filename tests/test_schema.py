"""Parameter schemas, validation and the memento hook."""

from __future__ import annotations

import pytest
from zope.interface import Interface
from zope.schema import Choice, Int, TextLine

from komandaro import ParameterError, SimpleCommandFactory, describe, validate
from komandaro.i18n import _


class IAddParameters(Interface):
    amount = Int(title=_("Amount"), description=_("Value to add"), required=True, min=1)
    label = TextLine(title=_("Label"), required=False, default="add")
    mode = Choice(title=_("Mode"), values=["fast", "safe"], required=False, default="safe")


def add(ctx, amount, label="add", mode="safe"):
    ctx.value += amount
    ctx.log.append(f"{label}:{mode}")
    return ctx.value


def undo_add(ctx, result, amount, **_):
    ctx.value -= amount
    return ctx.value


Add = SimpleCommandFactory(add, undo_add, _("Add"), schema=IAddParameters, id="add")


def test_describe_lists_fields_in_declaration_order():
    infos = describe(IAddParameters)
    assert [i.name for i in infos] == ["amount", "label", "mode"]
    amount, label, mode = infos
    assert amount.type == "Int"
    assert amount.title == "Amount"
    assert amount.description == "Value to add"
    assert amount.required and amount.default is None
    assert amount.python_type is int
    assert label.required is False and label.default == "add"
    assert mode.choices == ("fast", "safe")
    assert describe(None) == []


def test_validate_fills_defaults(calc):
    assert validate(IAddParameters, {"amount": 3}) == {"amount": 3, "label": "add", "mode": "safe"}
    cmd = Add(calc, amount=3)
    assert cmd.params == {"amount": 3, "label": "add", "mode": "safe"}
    assert cmd.execute() == 3
    assert calc.log == ["add:safe"]
    assert cmd.undo() == 0


def test_validate_without_schema_accepts_anything():
    assert validate(None, {"x": 1}) == {"x": 1}


def test_validate_reports_every_issue_at_once(calc):
    with pytest.raises(ParameterError) as info:
        Add(calc, amount=0, mode="wrong", extra=1)
    issues = {i.name: str(i) for i in info.value.issues}
    assert set(issues) == {"amount", "mode", "extra"}
    assert issues["extra"] == "Unknown parameter extra"
    assert issues["amount"].startswith("Invalid value for parameter amount:")
    assert "mode" in str(info.value)


def test_missing_required_parameter(calc, localedir):
    with pytest.raises(ParameterError) as info:
        Add(calc)
    (issue,) = info.value.issues
    assert str(issue) == "Missing required parameter amount"
    assert info.value.translate("fr", localedir=localedir) == {
        "amount": "Paramètre obligatoire manquant : amount"
    }


def test_field_errors_are_translated_by_identifier(calc, localedir):
    with pytest.raises(ParameterError) as info:
        Add(calc, amount=0, mode="wrong")
    by_name = {i.name: i for i in info.value.issues}
    assert by_name["amount"].params["error"] == "field_too_small"
    assert str(by_name["amount"]) == "Invalid value for parameter amount: Value is too small"
    assert (
        by_name["amount"].translate("fr")
        == "Valeur invalide pour le paramètre amount : Valeur trop petite"
    )
    assert by_name["mode"].translate("eo").endswith("Limigo ne plenumita")


def test_command_id_defaults_and_overrides():
    assert Add.id == "add"
    Plain = SimpleCommandFactory(add, undo_add, "Add stuff")
    assert Plain.__name__ == "AddStuffCommand"
    assert Plain.id == "addstuff"


def test_snapshot_memento_is_given_to_undo(calc):
    calc.value = 10

    def overwrite(ctx, value):
        ctx.value = value
        return "done"

    def restore(ctx, memento, value):
        ctx.value = memento

    def snapshot(ctx, value):
        return ctx.value

    Set = SimpleCommandFactory(overwrite, restore, "Set", snapshot=snapshot)
    cmd = Set(calc, value=42)
    assert cmd.memento is None
    assert cmd.execute() == "done"
    assert cmd.memento == 10
    assert calc.value == 42
    cmd.undo()
    assert calc.value == 10
    cmd.redo()
    assert calc.value == 42
    assert cmd.memento == 10  # snapshot is taken once, on first execution


def test_legacy_signature_without_parameters_still_works(calc):
    Legacy = SimpleCommandFactory(lambda c: 1, lambda c, r: None, "legacy")
    assert Legacy(calc).execute() == 1
