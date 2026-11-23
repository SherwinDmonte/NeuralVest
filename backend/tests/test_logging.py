from app.utils.logging_config import redact


def test_redacts_mongodb_credentials():
    text = "connecting to mongodb+srv://alice:Sup3r$ecret@cluster0.abc.mongodb.net/?x=1"
    out = redact(text)
    assert "Sup3r$ecret" not in out
    assert "mongodb+srv://alice:***@cluster0.abc.mongodb.net" in out


def test_redacts_secret_key_value_pairs():
    out = redact("password=hunter2 token: abc123 api_key=xyz")
    assert "hunter2" not in out and "abc123" not in out and "xyz" not in out


def test_leaves_normal_text_alone():
    assert redact("GET /api/health -> 200") == "GET /api/health -> 200"
