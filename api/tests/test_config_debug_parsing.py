import pytest
from pydantic_core import ValidationError

from config import Settings


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("release", False),
        ("production", False),
        ("0", False),
        ("debug", True),
        ("development", True),
        ("1", True),
    ],
)
def test_debug_accepts_common_environment_labels(raw_value, expected):
    assert Settings(DEBUG=raw_value).DEBUG is expected


def test_debug_rejects_unknown_text():
    with pytest.raises(ValidationError):
        Settings(DEBUG="definitely-not-a-bool")
