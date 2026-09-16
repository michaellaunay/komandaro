"""Static container defaults must not leak between commands or descriptions."""

from zope.interface import Interface
from zope.schema import Choice, Dict, Int, List, TextLine

from komandaro import SimpleCommandFactory, describe, validate


class IDefaults(Interface):
    labels = List(value_type=TextLine(), required=False, default=[])
    data = Dict(
        key_type=TextLine(), value_type=List(value_type=Int()),
        required=False, default={"nested": [1]},
    )


def test_static_container_defaults_are_deeply_isolated(calc):
    cls = SimpleCommandFactory(lambda c, **kw: None, lambda c, r, **kw: None, "defaults", schema=IDefaults)
    first, second = cls(calc), cls(calc)
    first.params["labels"].append("changed")
    first.params["data"]["nested"].append(2)
    assert second.params == {"labels": [], "data": {"nested": [1]}}
    assert IDefaults["labels"].default == []
    assert IDefaults["data"].default == {"nested": [1]}


def test_descriptions_do_not_expose_static_container_defaults():
    infos = describe(IDefaults)
    infos[0].default.append("UI change")
    infos[1].default["nested"].append(9)
    assert validate(IDefaults, {}) == {"labels": [], "data": {"nested": [1]}}


def test_explicit_parameters_keep_their_identity():
    labels = ["explicit"]
    assert validate(IDefaults, {"labels": labels})["labels"] is labels


def test_application_object_defaults_preserve_choice_identity():
    token = object()

    class IChoiceDefault(Interface):
        choice = Choice(values=[token], required=False, default=token)

    assert validate(IChoiceDefault, {})["choice"] is token
    assert describe(IChoiceDefault)[0].default is token


def test_factory_owns_its_default_creation_policy():
    created = []

    def factory():
        value = []
        created.append(value)
        return value

    class IFactory(Interface):
        labels = List(value_type=TextLine(), required=False, defaultFactory=factory)

    result = validate(IFactory, {})
    assert result["labels"] is created[-1]


def test_choice_container_default_keeps_vocabulary_identity():
    token = (object(),)

    class IChoiceContainer(Interface):
        choice = Choice(values=[token], required=False, default=token)

    assert validate(IChoiceContainer, {})["choice"] is token
    assert describe(IChoiceContainer)[0].default is token
