"""Production release guards do not rely on the UI's default branch choice."""

import pytest
from tools.check_release import validate_release


@pytest.mark.parametrize("ref", ["refs/heads/main", "refs/heads/topic", "refs/tags/v9.0.0"])
def test_pypi_rejects_every_reference_except_the_matching_tag(ref):
    with pytest.raises(ValueError):
        validate_release(ref, "pypi", "0.3.0")


@pytest.mark.parametrize("target", ["pypi", "testpypi"])
def test_matching_version_tag_is_valid(target):
    validate_release("refs/tags/v0.3.0", target, "0.3.0")


def test_testpypi_accepts_a_branch_but_not_a_mismatched_version_tag():
    validate_release("refs/heads/main", "testpypi", "0.3.0")
    with pytest.raises(ValueError):
        validate_release("refs/tags/v0.2.0", "testpypi", "0.3.0")


def test_unknown_target_is_rejected():
    with pytest.raises(ValueError):
        validate_release("refs/heads/main", "elsewhere", "0.3.0")
