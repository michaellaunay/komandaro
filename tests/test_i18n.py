"""gettext integration."""

from __future__ import annotations

import pickle

import pytest

from komandaro import CommandStateError, Macro, SimpleCommandFactory, translate
from komandaro.i18n import DOMAIN, Message, _, make_gettext


def test_message_is_a_str_with_a_domain():
    msg = _("Add")
    assert isinstance(msg, str)
    assert isinstance(msg, Message)
    assert msg == "Add"
    assert msg.domain == DOMAIN
    assert {msg: 1}["Add"] == 1


def test_make_gettext_uses_custom_domain():
    my = make_gettext("myapp")
    assert my("Hello").domain == "myapp"


def test_message_survives_pickling():
    msg = pickle.loads(pickle.dumps(_("Add")))
    assert isinstance(msg, Message)
    assert msg.domain == DOMAIN


def test_plain_str_is_returned_unchanged(localedir):
    assert translate("raw", "fr", localedir) == "raw"


def test_fallback_to_msgid_when_no_catalogue(tmp_path):
    assert translate(_("Add"), "fr", tmp_path) == "Add"
    assert translate(_("Add"), "xx", tmp_path) == "Add"


@pytest.mark.parametrize(
    ("lang", "expected"),
    [
        ("fr", "La commande ${name} a déjà été exécutée"),
        ("eo", "La komando ${name} jam estis plenumita"),
        ("en", "Command ${name} has already been executed"),
        (["de", "fr"], "La commande ${name} a déjà été exécutée"),
        ("de", "Command ${name} has already been executed"),  # no catalogue: English
    ],
)
def test_library_messages_are_translated(localedir, lang, expected):
    msg = _("command_already_executed")
    assert translate(msg, lang, localedir) == expected


def test_error_translation_with_params(calc, localedir):
    cmd = SimpleCommandFactory(lambda c: 1, lambda c, r: None, _("Add"))(calc)  # plain msgid
    cmd.execute()
    with pytest.raises(CommandStateError) as info:
        cmd.execute()
    err = info.value
    assert str(err) == "Command Add has already been executed"
    assert err.translate("fr", localedir=localedir) == "La commande Add a déjà été exécutée"
    assert err.translate("eo", localedir=localedir) == "La komando Add jam estis plenumita"


def test_macro_default_name_is_translated(calc, localedir):
    assert translate(Macro(calc).name, "eo", localedir) == "Makroo"
    assert translate(Macro(calc).name, "fr", localedir) == "Macro"


def test_message_translate_helper(localedir):
    msg = _("command_already_executed")
    assert msg.localize("fr", localedir, name="X") == "La commande X a déjà été exécutée"
    assert msg.localize("fr", localedir) == "La commande ${name} a déjà été exécutée"


def test_nested_messages_are_translated_too(localedir):
    outer = _("invalid_parameter")
    assert (
        outer.localize("fr", name="n", error=_("field_too_short"))
        == "Valeur invalide pour le paramètre n : Valeur trop courte"
    )


def test_unknown_identifier_falls_back_to_itself(localedir):
    assert translate(_("no_such_identifier"), "fr") == "no_such_identifier"


def test_environment_languages(monkeypatch):
    from komandaro.i18n import environment_languages

    assert environment_languages({"LANGUAGE": "fr:eo", "LANG": "de_DE.UTF-8"}) == ["fr", "eo"]
    assert environment_languages({"LANG": "de_DE.UTF-8"}) == ["de_DE.UTF-8"]
    assert environment_languages({"LC_ALL": "C"}) == []
    assert environment_languages({}) == []
    monkeypatch.setenv("LANGUAGE", "eo")
    assert translate(_("nothing_to_undo")) == "Nenio malfarenda"
    monkeypatch.setenv("LANGUAGE", "de")
    assert translate(_("nothing_to_undo")) == "Nothing to undo"  # English fallback


def test_bind_domain_makes_localedir_optional(localedir, tmp_path):
    from examples.notebook.notebook import Add

    from komandaro.i18n import LOCALEDIRS, bind_domain

    assert LOCALEDIRS["notebook"].name == "locale"  # bound by make_gettext in the example
    assert translate(Add.name, "fr") == "Ajouter une note"
    assert translate(Add.name, "de") == "Add a note"  # the en catalogue of the application
    my = make_gettext("elsewhere", tmp_path)
    assert LOCALEDIRS["elsewhere"] == tmp_path
    assert translate(my("hello"), "fr") == "hello"
    bind_domain("elsewhere", localedir)
    assert LOCALEDIRS["elsewhere"] == localedir
