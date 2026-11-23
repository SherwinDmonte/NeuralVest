import pytest
from pydantic import ValidationError

from app.config import Settings


def make(**kwargs) -> Settings:
    # _env_file=None: ignore backend/.env so tests are deterministic.
    return Settings(_env_file=None, **kwargs)


def test_defaults_and_cors_list():
    s = make(cors_origins="http://localhost:5173, http://127.0.0.1:5173 ,")
    assert s.cors_origin_list == ["http://localhost:5173", "http://127.0.0.1:5173"]
    assert s.mongodb_db_name == "neuralvest_db"
    assert s.market_data_max_years == 5


@pytest.mark.parametrize(
    "uri, expected",
    [
        (None, False),
        ("", False),
        ("mongodb+srv://user:<password>@cluster0.example.mongodb.net/", False),
        ("mongodb+srv://user:s3cret@cluster0.example.mongodb.net/", True),
    ],
)
def test_mongodb_configured(uri, expected):
    assert make(mongodb_uri=uri).mongodb_configured is expected


def test_uri_is_secret_in_repr():
    s = make(mongodb_uri="mongodb+srv://user:s3cret@cluster0.example.mongodb.net/")
    assert "s3cret" not in repr(s)
    assert "s3cret" not in str(s.model_dump())


def test_warn_must_be_below_block():
    with pytest.raises(ValidationError):
        make(storage_warn_pct=90, storage_block_pct=85)


def test_database_names_must_differ():
    with pytest.raises(ValidationError):
        make(mongodb_db_name="same", mongodb_test_db_name="same")


def test_active_db_name_uses_test_db_in_test_env():
    assert make(app_env="test").active_db_name == "neuralvest_db_test"
    assert make(app_env="development").active_db_name == "neuralvest_db"


def test_retention_years_is_bounded():
    with pytest.raises(ValidationError):
        make(market_data_max_years=0)
