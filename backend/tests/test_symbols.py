import pytest

from app.data.errors import InvalidSymbolError
from app.data.symbols import base_ticker, exchange_of, load_seed_symbols, normalize_symbol
from app.database.models import is_valid_symbol


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("RELIANCE", "RELIANCE.NS"),
        ("  reliance.ns ", "RELIANCE.NS"),
        ("NSE:TCS", "TCS.NS"),
        ("nse : infy", "INFY.NS"),
        ("BSE:500325", "500325.BO"),
        ("500325", "500325.BO"),
        ("500325.bo", "500325.BO"),
        ("^nsei", "^NSEI"),
        ("M&M", "M&M.NS"),
        ("bajaj-auto", "BAJAJ-AUTO.NS"),
    ],
)
def test_normalize_symbol(raw, expected):
    assert normalize_symbol(raw) == expected


def test_default_exchange_bse():
    assert normalize_symbol("RELIANCE", default_exchange="BSE") == "RELIANCE.BO"


@pytest.mark.parametrize("raw", ["", "   ", "RELIANCE.L", "12345", "1234567", "REL;DROP", None, "AAPL.XX"])
def test_invalid_symbols_raise(raw):
    with pytest.raises(InvalidSymbolError):
        normalize_symbol(raw)


def test_exchange_and_base():
    assert exchange_of("TCS.NS") == "NSE" and exchange_of("500325.BO") == "BSE" and exchange_of("^NSEI") == "INDEX"
    assert base_ticker("RELIANCE.NS") == "RELIANCE" and base_ticker("^NSEI") == "NSEI"


def test_seed_list_is_documented_and_valid():
    seed = load_seed_symbols()
    assert {"source", "limitations", "curated_on", "symbols"} <= set(seed)
    assert "NOT an official" in seed["limitations"]
    assert len(seed["symbols"]) == len(set(seed["symbols"])) == 30
    assert all(is_valid_symbol(s) and s.endswith(".NS") for s in seed["symbols"])
