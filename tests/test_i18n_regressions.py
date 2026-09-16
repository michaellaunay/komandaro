"""Fallback and iterator regressions, using real compiled catalogues."""

import pytest

from komandaro import CommandStateError, PermissionDeniedError, RegistryError, translate
from komandaro.i18n import _, environment_languages


@pytest.mark.parametrize("language", ["C", "POSIX", "C.UTF-8", "POSIX.UTF-8", "", ["C", "fr"]])
def test_no_preference_locale_does_not_stop_fallback(language):
    expected = "Rien à annuler" if language == ["C", "fr"] else "Nothing to undo"
    assert translate(_("nothing_to_undo"), language) == expected


@pytest.mark.parametrize("variable", ["LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"])
def test_encoded_c_locale_is_filtered_from_environment(variable):
    assert environment_languages({variable: "C.UTF-8"}) == []


def test_generator_is_reused_for_nested_message_parameters():
    result = _("invalid_parameter").localize(
        iter(["fr"]), name="n", error=_("field_too_short")
    )
    assert result == "Valeur invalide pour le paramètre n : Valeur trop courte"


def test_language_preferences_are_not_modified():
    languages = ["fr"]
    translate(_("nothing_to_undo"), languages)
    assert languages == ["fr"]


def test_stored_error_parameters_override_duplicate_formatting_keys():
    command = CommandStateError(_("command_already_executed"), name="actual")
    registry = RegistryError(_("unknown_command"), id="actual")
    denied = PermissionDeniedError("actual", "edit")
    assert "actual" in command.translate("en", name="ignored")
    assert "actual" in registry.translate("en", id="ignored")
    assert "actual" in denied.translate("en", id="ignored")
