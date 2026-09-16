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
        ("fr", "La commande %(name)s a déjà été exécutée"),
        ("eo", "La komando %(name)s jam estis plenumita"),
        ("en", "Command %(name)s has already been executed"),
        (["de", "fr"], "La commande %(name)s a déjà été exécutée"),
    ],
)
def test_library_messages_are_translated(localedir, lang, expected):
    msg = _("Command %(name)s has already been executed")
    assert translate(msg, lang, localedir) == expected


def test_error_translation_with_params(calc, localedir):
    cmd = SimpleCommandFactory(lambda c: 1, lambda c, r: None, _("Add"))(calc)
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
    msg = _("Command %(name)s has already been executed")
    assert msg.localize("fr", localedir, name="X") == "La commande X a déjà été exécutée"
