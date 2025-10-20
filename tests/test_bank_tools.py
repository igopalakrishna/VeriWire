from veriwire.bank_tools import _normalize_pid


def test_normalize_pid_lower_and_strip():
    assert _normalize_pid("10sf-917 264") == "10sf917264"
    assert _normalize_pid(" wire2025  ") == "wire2025"


