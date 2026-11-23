"""Symbol handling: turn user input into a Yahoo-style ticker NeuralVest can use.

Accepted inputs (case-insensitive, spaces ignored):
    RELIANCE        -> RELIANCE.NS   (default exchange NSE)
    reliance.ns     -> RELIANCE.NS
    NSE:TCS         -> TCS.NS
    BSE:500325      -> 500325.BO
    500325          -> 500325.BO     (6-digit numbers are BSE scrip codes)
    ^NSEI           -> ^NSEI         (index, e.g. the NIFTY 50 benchmark)
"""

import json
import re
from pathlib import Path
from typing import Literal

from app.data.errors import InvalidSymbolError
from app.database.models import is_valid_symbol

Exchange = Literal["NSE", "BSE", "INDEX"]

BENCHMARK_SYMBOL = "^NSEI"  # NIFTY 50
SUFFIX_BY_EXCHANGE = {"NSE": ".NS", "BSE": ".BO"}
_EXCHANGE_PREFIX = re.compile(r"^(NSE|BSE):(.+)$")
_BSE_CODE = re.compile(r"^\d{6}$")

SEED_FILE = Path(__file__).with_name("seed_symbols.json")


def normalize_symbol(raw: str, default_exchange: Literal["NSE", "BSE"] = "NSE") -> str:
    if not isinstance(raw, str):
        raise InvalidSymbolError("symbol must be a string")
    s = re.sub(r"\s+", "", raw).upper()
    if not s:
        raise InvalidSymbolError("symbol is empty")

    if s.startswith("^"):
        candidate = s
    elif match := _EXCHANGE_PREFIX.match(s):
        exchange, base = match.groups()
        base = re.sub(r"\.(NS|BO)$", "", base)
        candidate = base + SUFFIX_BY_EXCHANGE[exchange]
    elif s.endswith((".NS", ".BO")):
        candidate = s
    elif "." in s:
        raise InvalidSymbolError(f"unsupported exchange suffix in '{raw}' (use .NS for NSE or .BO for BSE)")
    elif s.isdigit():
        if not _BSE_CODE.match(s):
            raise InvalidSymbolError(f"'{raw}' is not a 6-digit BSE scrip code")
        candidate = s + ".BO"
    else:
        candidate = s + SUFFIX_BY_EXCHANGE[default_exchange]

    if candidate.endswith(".BO") and candidate[:-3].isdigit() and not _BSE_CODE.match(candidate[:-3]):
        raise InvalidSymbolError(f"'{raw}' is not a 6-digit BSE scrip code")
    if not is_valid_symbol(candidate):
        raise InvalidSymbolError(f"'{raw}' is not a valid NSE/BSE symbol")
    return candidate


def exchange_of(symbol: str) -> Exchange:
    if symbol.startswith("^"):
        return "INDEX"
    if symbol.endswith(".NS"):
        return "NSE"
    if symbol.endswith(".BO"):
        return "BSE"
    raise InvalidSymbolError(f"cannot determine exchange of '{symbol}'")


def base_ticker(symbol: str) -> str:
    """RELIANCE.NS -> RELIANCE ; ^NSEI -> NSEI"""
    return re.sub(r"\.(NS|BO)$", "", symbol).lstrip("^")


def load_seed_symbols() -> dict:
    """The curated suggestion list (see seed_symbols.json for its source and limits)."""
    return json.loads(SEED_FILE.read_text(encoding="utf-8"))
