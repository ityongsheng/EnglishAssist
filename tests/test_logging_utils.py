from english_assist.logging_utils import redact


def test_redact_removes_known_secret():
    assert "sk-secret" not in redact("request failed sk-secret", ("sk-secret",))


def test_redact_masks_bearer_token():
    text = redact("Authorization: Bearer abc123")
    assert "abc123" not in text
    assert "[REDACTED]" in text
