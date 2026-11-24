"""PDF export (tasks 11.4.1-11.4.2): built from a report produced by the real offline workflow."""

import io
from datetime import UTC, date, datetime

import pytest
from pypdf import PdfReader

from app.data import news_data as nd
from app.orchestration import graph as graph_module
from app.services import pdf_export as pe
from app.services.report_generator import build_report
from tests.agent_fakes import FakeLLM, patch_benchmark
from tests.test_workflow import run


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(nd, "utc_now", lambda: datetime(2026, 11, 22, tzinfo=UTC))
    patch_benchmark(monkeypatch, graph_module)


@pytest.fixture
def portfolio_state(tmp_path, monkeypatch):
    return run(tmp_path, monkeypatch, ["RELIANCE", "TCS"], investment_amount=100000, risk_preference="conservative")


def text_of(pdf: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf))
    return "\n".join(page.extract_text() for page in reader.pages)


def test_pdf_contains_every_section_and_the_disclaimers(portfolio_state):
    report = portfolio_state["final_report"]
    # the synthetic history is too short for a backtest; a small curve exercises the chart
    curve = [{"date": f"2025-01-{d:02d}", "strategy": 100000 + d, "equal_weight": 100000 - d, "nifty50": None}
             for d in range(1, 21)]
    prices = {"RELIANCE.NS": [(date(2025, 1, 1 + i), 1000.0 + i) for i in range(20)]}
    pdf = pe.build_pdf(report, prices=prices, equity_curve=curve)
    assert pdf.startswith(b"%PDF") and len(pdf) < 2_000_000
    text = text_of(pdf)
    for heading in ("Key observations", "Market summary", "Technical analysis", "News and sentiment",
                    "Fundamentals and financial health", "Risk", "Risk across the stocks", "Illustrative portfolio",
                    "Data limitations", "Sources", "Glossary", "Disclaimers"):
        assert heading in text, heading
    assert "not a SEBI-registered" in text and "not investment advice" in text
    assert "RELIANCE.NS" in text and "TCS.NS" in text


def test_pdf_shows_stored_numbers_unchanged(portfolio_state):
    report = portfolio_state["final_report"]
    text = text_of(pe.build_pdf(report)).replace("\n", " ")
    ms = report["sections"]["market_summary"]["RELIANCE.NS"]
    assert f"{ms['period_return_pct']:,.2f}%" in text
    for a in report["sections"]["portfolio"]["allocations"]:
        assert f"{a['weight_pct']:,.2f}%" in text and f"{a['shares']:,.0f}" in text


def test_pdf_escapes_text_and_drops_unsafe_links(portfolio_state):
    report = portfolio_state["final_report"]
    report["key_observations"]["items"] = ["<b>bold?</b> & <script>alert(1)</script>"]
    news = report["sections"]["news_summary"]["RELIANCE.NS"]
    news["top_headlines"] = [{"headline": "Evil link", "publisher": "X", "url": "javascript:alert(1)",
                              "sentiment": "neutral"},
                             {"headline": "Good link", "publisher": "Y", "url": "https://example.com/a",
                              "sentiment": "positive"}]
    pdf = pe.build_pdf(report)
    text = text_of(pdf)
    assert "<script>alert(1)</script>" in text  # shown as text, not interpreted
    assert b"javascript:" not in pdf and b"https://example.com/a" in pdf


def test_pdf_with_missing_sections(tmp_path, monkeypatch):
    state = run(tmp_path, monkeypatch, ["RELIANCE"], fundamentals_fail=True)
    text = text_of(pe.build_pdf(state["final_report"]))
    assert "Unavailable" in text and "Illustrative portfolio" not in text


def test_minimal_report_does_not_crash():
    pdf = pe.build_pdf({"request": {"symbols": ["X.NS"]}, "sections": {}})
    assert "n/a" in text_of(pdf)


def test_rupee_fallback_without_a_font_that_has_it():
    f = pe._Fmt(has_rupee=False)
    assert f.inr(1234.5) == "Rs 1,234.50" and f.text("₹500") == "Rs 500"
    assert pe._Fmt(has_rupee=True).inr(1234.5) == "₹1,234.50"
    assert f.num(None) == "n/a" and f.num(True) == "n/a"


def test_labels_and_thinning():
    assert pe._Fmt.label("roe_pct") == "ROE (%)" and pe._Fmt.label("pe") == "P/E"
    assert pe._Fmt.label("revenue_growth_yoy_pct") == "Revenue growth YoY (%)"
    points = [(date.fromordinal(738000 + i), float(i)) for i in range(1000)]
    thin = pe._thin(points)
    assert len(thin) == pe.MAX_CHART_POINTS and thin[0] == points[0] and thin[-1] == points[-1]


def test_report_build_is_reused_not_recalculated(portfolio_state):
    """The PDF takes the stored report as is: rebuilding it gives the same sections."""
    again = build_report(portfolio_state, llm=FakeLLM(), use_llm=False)
    assert again["sections"]["portfolio"]["allocations"] == portfolio_state["final_report"]["sections"]["portfolio"]["allocations"]
