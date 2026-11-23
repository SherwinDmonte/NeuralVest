"""INDEPENDENT reference implementations of the indicators, written as plain Python loops
from the textbook definitions (no pandas rolling/ewm). Used by the unit tests and by
scripts/verify_indicators.py to check the production code on real data (task 6.3.2)."""


def ref_sma(values, n):
    return [None if i + 1 < n else sum(values[i + 1 - n:i + 1]) / n for i in range(len(values))]


def ref_ema(values, span):
    """EMA seeded with the first value; reported once `span` values have been seen."""
    alpha, out, prev = 2 / (span + 1), [], None
    for i, v in enumerate(values):
        prev = v if prev is None else alpha * v + (1 - alpha) * prev
        out.append(prev if i + 1 >= span else None)
    return out


def ref_rsi(values, n=14):
    """Wilder's RSI: simple average of the first n changes, then Wilder smoothing."""
    gains = [max(values[i] - values[i - 1], 0) for i in range(1, len(values))]
    losses = [max(values[i - 1] - values[i], 0) for i in range(1, len(values))]
    out = [None] * len(values)
    ag, al = sum(gains[:n]) / n, sum(losses[:n]) / n

    def value(g, lo):
        if lo == 0:
            return 50.0 if g == 0 else 100.0
        return 100 - 100 / (1 + g / lo)

    out[n] = value(ag, al)
    for i in range(n + 1, len(values)):
        ag = (ag * (n - 1) + gains[i - 1]) / n
        al = (al * (n - 1) + losses[i - 1]) / n
        out[i] = value(ag, al)
    return out


def ref_macd(values, fast=12, slow=26, signal=9):
    """MACD line = EMA(fast) - EMA(slow) (unseeded part excluded); signal = EMA of the line."""
    alpha_f, alpha_s = 2 / (fast + 1), 2 / (slow + 1)
    ema_f = ema_s = None
    line = []
    for i, v in enumerate(values):
        ema_f = v if ema_f is None else alpha_f * v + (1 - alpha_f) * ema_f
        ema_s = v if ema_s is None else alpha_s * v + (1 - alpha_s) * ema_s
        line.append(ema_f - ema_s if i + 1 >= slow else None)
    first = next(i for i, x in enumerate(line) if x is not None)
    sig = [None] * first + ref_ema(line[first:], signal)
    return line, sig
