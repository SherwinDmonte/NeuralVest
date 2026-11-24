"""PDF export of a finished report (tasks 11.4.1 and 11.4.2), built with ReportLab.

Rules:
  * The PDF shows the stored report (`analysis_reports.final_summary`, Phase 10) and nothing
    else: Python only formats the stored numbers (thousand separators, 2 decimals) and never
    recalculates or adds any. Missing values are printed as "n/a".
  * Charts are drawn server-side with ReportLab's own graphics (no browser, no matplotlib):
    the closing price over the analysis window (from the stored `market_data`), the portfolio
    allocation, and the backtest equity curve (from the stored agent result).
  * Every external link is re-validated (utils/urls.safe_http_url) before it is written.
  * Disclaimers appear on the first page and in every page footer.
"""

import io
from datetime import date, datetime
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from reportlab.graphics.charts.barcharts import HorizontalBarChart
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (KeepTogether, ListFlowable, ListItem, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

from app.utils.urls import safe_http_url

GENERAL_DISCLAIMER = ("NeuralVest is an educational project, not a SEBI-registered investment adviser. This report "
                      "describes past data and is not investment advice or a forecast.")
FOOTER = "NeuralVest · educational use only · not investment advice"
# Dataviz palette (docs: categorical order) - readable on white paper
SERIES = [colors.HexColor(c) for c in ("#3987e5", "#d95926", "#199e70", "#c98500")]
INK, MUTED, LINE, PANEL = (colors.HexColor(c) for c in ("#0f1b33", "#5b6478", "#d5d9e2", "#f3f5f9"))
MAX_CHART_POINTS = 260
WINDOWS_FONTS = Path("C:/Windows/Fonts")
ACRONYMS = {"pe": "P/E", "pb": "P/B", "eps": "EPS", "roe": "ROE", "roa": "ROA", "yoy": "YoY", "cagr": "CAGR",
            "hhi": "HHI"}


# ---------------------------------------------------------------- fonts (the rupee sign)
def _register_fonts() -> tuple[str, str, bool]:
    """(regular, bold, has_rupee). Arial on Windows has the ₹ glyph; the built-in Helvetica
    does not, so without Arial "₹" is printed as "Rs "."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    regular, bold = WINDOWS_FONTS / "arial.ttf", WINDOWS_FONTS / "arialbd.ttf"
    if regular.exists() and bold.exists():
        try:
            if "NV-Regular" not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont("NV-Regular", str(regular)))
                pdfmetrics.registerFont(TTFont("NV-Bold", str(bold)))
            face = pdfmetrics.getFont("NV-Regular").face
            return "NV-Regular", "NV-Bold", 0x20B9 in face.charToGlyph
        except Exception:  # unreadable font file: fall back to the built-in font
            pass
    return "Helvetica", "Helvetica-Bold", False


class _Fmt:
    def __init__(self, has_rupee: bool) -> None:
        self.has_rupee = has_rupee

    def text(self, value: Any) -> str:
        """Escaped text for a Paragraph (user/AI/source text can contain < & >)."""
        s = "n/a" if value is None or value == "" else str(value)
        if not self.has_rupee:
            s = s.replace("₹", "Rs ")
        return escape(s)

    @staticmethod
    def num(value: Any, digits: int = 2, suffix: str = "") -> str:
        if value is None or isinstance(value, bool):
            return "n/a"
        if isinstance(value, (int, float)):
            return f"{value:,.{digits}f}{suffix}"
        return str(value)

    def inr(self, value: Any) -> str:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return "n/a"
        return ("₹" if self.has_rupee else "Rs ") + f"{value:,.2f}"

    @staticmethod
    def label(key: str) -> str:
        words = key.replace("_pct", "").split("_")
        text = " ".join(ACRONYMS.get(w, w) for w in words)
        return text[0].upper() + text[1:] + (" (%)" if key.endswith("_pct") else "")


# ---------------------------------------------------------------- styles
def _styles(regular: str, bold: str) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    body = ParagraphStyle("nv-body", parent=base["BodyText"], fontName=regular, fontSize=9, leading=12.5,
                          textColor=INK, alignment=TA_LEFT)
    return {
        "title": ParagraphStyle("nv-title", parent=body, fontName=bold, fontSize=18, leading=22, spaceAfter=4),
        "h1": ParagraphStyle("nv-h1", parent=body, fontName=bold, fontSize=13, leading=16, spaceBefore=10,
                             spaceAfter=5, textColor=INK),
        "h2": ParagraphStyle("nv-h2", parent=body, fontName=bold, fontSize=10.5, leading=13, spaceBefore=7,
                             spaceAfter=3),
        "body": body,
        "small": ParagraphStyle("nv-small", parent=body, fontSize=7.5, leading=10, textColor=MUTED),
        "cell": ParagraphStyle("nv-cell", parent=body, fontSize=8, leading=10),
        "cellb": ParagraphStyle("nv-cellb", parent=body, fontName=bold, fontSize=8, leading=10),
        "box": ParagraphStyle("nv-box", parent=body, fontSize=8, leading=11, backColor=PANEL, borderColor=LINE,
                              borderWidth=0.5, borderPadding=6, spaceBefore=12, spaceAfter=12),
    }


class _Builder:
    def __init__(self, report: dict[str, Any], extras: dict[str, Any]) -> None:
        regular, bold, has_rupee = _register_fonts()
        self.font, self.bold = regular, bold
        self.f = _Fmt(has_rupee)
        self.st = _styles(regular, bold)
        self.r = report
        self.x = extras
        self.story: list = []

    # -------------------------------------------------- primitives
    def p(self, text: str, style: str = "body") -> None:
        self.story.append(Paragraph(text, self.st[style]))

    def h1(self, text: str) -> None:
        self.p(self.f.text(text), "h1")

    def h2(self, text: str) -> None:
        self.p(self.f.text(text), "h2")

    def bullets(self, items: list[str], style: str = "body") -> None:
        if not items:
            return
        self.story.append(ListFlowable([ListItem(Paragraph(self.f.text(i), self.st[style]), leftIndent=10)
                                        for i in items], bulletType="bullet", start="•", leftIndent=10,
                                       bulletFontName=self.font, bulletFontSize=8, bulletOffsetY=-2))

    def table(self, rows: list[list[Any]], widths: list[float] | None = None, header: bool = True) -> None:
        if not rows:
            return
        cells = [[c if not isinstance(c, str) else
                  Paragraph(self.f.text(c), self.st["cellb" if header and i == 0 else "cell"]) for c in row]
                 for i, row in enumerate(rows)]
        t = Table(cells, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
        style = [("GRID", (0, 0), (-1, -1), 0.4, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                 ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                 ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]
        if header:
            style.append(("BACKGROUND", (0, 0), (-1, 0), PANEL))
        t.setStyle(TableStyle(style))
        self.story.append(t)
        self.story.append(Spacer(1, 5))

    def kv(self, pairs: list[tuple[str, str]]) -> None:
        self.table([[k, v] for k, v in pairs], widths=[55 * mm, 115 * mm], header=False)

    # -------------------------------------------------- charts
    def _line_chart(self, title: str, series: list[tuple[str, list[tuple[date, float]]]],
                    y_label: str) -> Drawing | None:
        series = [(name, pts) for name, pts in series if len(pts) >= 2]
        if not series:
            return None
        origin = min(pts[0][0] for _, pts in series)
        width, height = 170 * mm, 62 * mm
        d = Drawing(width, height)
        d.add(String(0, height - 10, f"{title} ({y_label})", fontName=self.bold, fontSize=9, fillColor=INK))
        lp = LinePlot()
        lp.x, lp.y, lp.width, lp.height = 38, 26, width - 50, height - 52
        lp.data = [[((dt - origin).days, v) for dt, v in pts] for _, pts in series]
        for i, _ in enumerate(series):
            lp.lines[i].strokeColor = SERIES[i % len(SERIES)]
            lp.lines[i].strokeWidth = 1.4
            if i:  # later series dashed, so identical curves (e.g. equal weights) stay visible
                lp.lines[i].strokeDashArray = (4, 2)
        lp.xValueAxis.labelTextFormat = lambda days: date.fromordinal(origin.toordinal() + int(days)).strftime("%b %y")
        for axis in (lp.xValueAxis, lp.yValueAxis):
            axis.labels.fontName, axis.labels.fontSize = self.font, 7
            axis.labels.fillColor = MUTED
            axis.strokeColor = LINE
        lp.yValueAxis.labelTextFormat = lambda v: f"{v:,.0f}"
        lp.yValueAxis.visibleGrid, lp.yValueAxis.gridStrokeColor = True, LINE
        d.add(lp)
        if len(series) > 1:
            legend = Legend()
            legend.x, legend.y = width - 78 * len(series), height - 6
            legend.alignment, legend.columnMaximum = "right", 1
            legend.fontName, legend.fontSize = self.font, 7
            legend.dx = legend.dy = 6
            legend.deltax = 70
            legend.colorNamePairs = [(SERIES[i % len(SERIES)], name) for i, (name, _) in enumerate(series)]
            d.add(legend)
        return d

    def _allocation_chart(self, allocations: list[dict]) -> Drawing | None:
        rows = [(a.get("symbol"), a.get("weight_pct")) for a in allocations if isinstance(a.get("weight_pct"), (int, float))]
        if not rows:
            return None
        bar_h = 14
        height = 30 + bar_h * len(rows) * 1.6
        d = Drawing(170 * mm, height)
        d.add(String(0, height - 10, "Target weights (%)", fontName=self.bold, fontSize=9, fillColor=INK))
        ch = HorizontalBarChart()
        ch.x, ch.y, ch.width, ch.height = 80, 10, 170 * mm - 110, height - 28
        ch.data = [[w for _, w in rows][::-1]]
        ch.categoryAxis.categoryNames = [s for s, _ in rows][::-1]
        ch.valueAxis.valueMin, ch.valueAxis.valueMax = 0, 100
        ch.bars[0].fillColor = SERIES[0]
        ch.bars[0].strokeColor = None
        ch.barLabelFormat = lambda v: f"{v:.2f}%"
        ch.barLabels.fontName, ch.barLabels.fontSize, ch.barLabels.boxAnchor = self.font, 7, "w"
        ch.barLabels.dx = 3
        for axis in (ch.categoryAxis, ch.valueAxis):
            axis.labels.fontName, axis.labels.fontSize = self.font, 7
            axis.strokeColor = LINE
        d.add(ch)
        return d

    def add_drawing(self, drawing: Drawing | None, caption: str | None = None) -> None:
        if drawing is None:
            return
        block = [drawing]
        if caption:
            block.append(Paragraph(self.f.text(caption), self.st["small"]))
        block.append(Spacer(1, 6))
        self.story.append(KeepTogether(block))

    # -------------------------------------------------- sections
    def cover(self) -> None:
        req = self.r.get("request") or {}
        self.p(self.f.text("NeuralVest financial intelligence report"), "title")
        self.p(self.f.text(", ".join(req.get("symbols") or [])), "h2")
        pairs = [("Generated", _when(self.r.get("generated_at"))), ("Status", self.r.get("status")),
                 ("Request ID", self.r.get("request_id")), ("Report version", self.r.get("report_version"))]
        if req.get("investment_amount") is not None:
            pairs += [("Investment amount", self.f.inr(req.get("investment_amount"))),
                      ("Risk preference", req.get("risk_preference"))]
        self.kv([(k, str(v) if v is not None else "n/a") for k, v in pairs])
        self.p(self.f.text(GENERAL_DISCLAIMER + " " + " ".join(self.r.get("disclaimers") or [])), "box")

        obs = self.r.get("key_observations") or {}
        self.h1("Key observations")
        if obs.get("source") == "llm":
            self.p(self.f.text(f"Written by the local AI model ({obs.get('model')}) from the rule-based readings and "
                               "checked against them."), "small")
        else:
            self.p(self.f.text("Rule-based readings" + (f" ({obs['reason']})" if obs.get("reason") else "")), "small")
        self.bullets(obs.get("items") or [])
        trace, execution = self.r.get("traceability") or {}, self.r.get("execution") or {}
        checks = [f"Traceability: {'all' if trace.get('ok') else 'NOT all'} {trace.get('numbers_checked', 'n/a')} "
                  "numbers traced to agent results.",
                  f"Output validation: {execution.get('validation_issue_count', 0)} issue(s)."]
        self.p(self.f.text(" ".join(checks)), "small")
        if self.r.get("unavailable_sections"):
            self.p(self.f.text("Unavailable: " + "; ".join(self.r["unavailable_sections"])), "small")

    def stock(self, sym: str) -> None:
        s = self.r.get("sections") or {}
        f = self.f
        co = (s.get("company_overview") or {}).get(sym) or {}
        self.story.append(PageBreak())
        self.h1(f"{sym} · {co.get('company_name') or ''}")
        self.kv([("Exchange", f.text(co.get("exchange"))), ("Sector / industry",
                 f"{co.get('sector') or 'n/a'} / {co.get('industry') or 'n/a'}"),
                 ("Last close", f"{f.num(co.get('last_close'))} ({co.get('last_close_date') or 'n/a'})")])

        ms = (s.get("market_summary") or {}).get(sym) or {}
        self.h2("Market summary")
        if ms.get("available") is False:
            self.p(f.text(f"Unavailable: {ms.get('reason')}"), "small")
        else:
            bc, vol = ms.get("benchmark_comparison") or {}, ms.get("volume") or {}
            self.table([["Measure", "Value"],
                        ["1-year price change", f.num(ms.get("period_return_pct"), suffix="%")],
                        ["NIFTY 50 over the same period", f.num(bc.get("benchmark_return_pct"), suffix="%")],
                        ["Difference (stock - NIFTY 50)", f.num(bc.get("relative_pct"), suffix=" points")],
                        ["Last volume vs 20-day average", f.num(vol.get("last_vs_avg_ratio"), suffix="x")]],
                       widths=[85 * mm, 85 * mm])
            if ms.get("last_bar_may_be_incomplete"):
                self.p(f.text("The last price bar may be incomplete (market still open when fetched)."), "small")
        prices = (self.x.get("prices") or {}).get(sym) or []
        self.add_drawing(self._line_chart(f"{sym} closing price", [(sym, prices)], "INR per share"),
                         "Source: Yahoo Finance via yfinance (stored in NeuralVest). End-of-day prices.")

        ta = (s.get("technical_analysis") or {}).get(sym) or {}
        if ta.get("available") is not False and ta:
            self.h2("Technical analysis")
            ind = ta.get("indicators") or {}
            macd = ind.get("macd") or {}
            self.table([["Indicator", "Value"], ["Trend", ta.get("trend") or "n/a"],
                        ["SMA 20 / 50 / 200", " / ".join(f.num(ind.get(k)) for k in ("sma_20", "sma_50", "sma_200"))],
                        ["RSI (14)", f"{f.num(ind.get('rsi_14'))} ({ta.get('rsi_zone') or 'n/a'})"],
                        ["MACD / signal / histogram", " / ".join(f.num(macd.get(k), 3) for k in
                                                                 ("macd", "signal", "histogram"))]],
                       widths=[85 * mm, 85 * mm])
            self.bullets(list((ta.get("readings") or {}).values()), "cell")
            self._explanation(ta)

        self._news(sym, s)
        self._fundamentals(sym, s)
        self._risk(sym, s)

    def _explanation(self, section: dict) -> None:
        if section.get("explanation"):
            who = "AI explanation (local model, checked)" if section.get("explanation_source") == "llm" else \
                "Explanation (rule-based template)"
            self.p(f"<i>{self.f.text(who)}:</i> {self.f.text(section['explanation'])}", "cell")

    def _news(self, sym: str, s: dict) -> None:
        f = self.f
        news, sent = (s.get("news_summary") or {}).get(sym) or {}, (s.get("sentiment") or {}).get(sym) or {}
        self.h2("News and sentiment")
        if news.get("available") is False:
            self.p(f.text(f"Unavailable: {news.get('reason')}"), "small")
            return
        breakdown = ", ".join(f"{k} {v}" for k, v in (sent.get("breakdown") or {}).items()) or "n/a"
        self.p(f.text(f"Overall sentiment: {sent.get('overall_sentiment')} ({breakdown}); "
                      f"{news.get('articles_analyzed', 'n/a')} articles analysed from the last "
                      f"{news.get('lookback_days', 'n/a')} days."), "cell")
        if news.get("digest"):
            self.p(f.text(news["digest"]), "cell")
        rows = [["Headline", "Publisher", "Sentiment"]]
        for a in news.get("top_headlines") or []:
            url = safe_http_url(a.get("url"))
            title = f.text(a.get("headline"))
            head = Paragraph(f'<a href="{escape(url, {chr(34): "&quot;"})}" color="#1f5fbf">{title}</a>' if url
                             else title, self.st["cell"])
            rows.append([head, a.get("publisher") or "n/a", a.get("sentiment") or "n/a"])
        if len(rows) > 1:
            self.table(rows, widths=[110 * mm, 35 * mm, 25 * mm])
        if sent.get("disclaimer"):
            self.p(f.text(sent["disclaimer"]), "small")

    def _fundamentals(self, sym: str, s: dict) -> None:
        f = self.f
        fu, fh = (s.get("fundamentals") or {}).get(sym) or {}, (s.get("financial_health") or {}).get(sym) or {}
        self.h2("Fundamentals and financial health")
        if fu.get("available") is False:
            self.p(f.text(f"Unavailable: {fu.get('reason')}"), "small")
            return
        periods = fu.get("statement_periods") or {}
        self.p(f.text(f"Annual statements: income {periods.get('income_statement') or 'n/a'}, balance sheet "
                      f"{periods.get('balance_sheet') or 'n/a'}. Price used: {f.num(fu.get('price_used'))}."
                      + (" Bank: assessed with bank-specific rules." if fu.get("is_bank") else "")), "small")
        metrics = list((fu.get("metrics") or {}).items())
        rows = [["Metric", "Value", "Metric", "Value"]]
        for i in range(0, len(metrics), 2):
            pair = metrics[i:i + 2] + [("", None)] * (2 - len(metrics[i:i + 2]))
            rows.append([x for k, v in pair for x in (f.label(k) if k else "", f.num(v) if k else "")])
        self.table(rows, widths=[50 * mm, 35 * mm, 50 * mm, 35 * mm])
        if fu.get("unavailable_metrics"):
            self.p(f.text("Not computable: " + ", ".join(fu["unavailable_metrics"])), "small")
        if fh.get("available") is not False and fh:
            assess = ", ".join(f"{k} {v}" for k, v in (fh.get("assessments") or {}).items())
            self.p(f.text(f"Overall: {fh.get('overall')} ({assess})"), "cell")
            if fh.get("strengths"):
                self.p("<b>Strengths</b>", "cell")
                self.bullets(fh["strengths"], "cell")
            if fh.get("weaknesses"):
                self.p("<b>Weaknesses</b>", "cell")
                self.bullets(fh["weaknesses"], "cell")
        self._explanation(fu)

    def _risk(self, sym: str, s: dict) -> None:
        f = self.f
        rk = ((s.get("risk") or {}).get("per_symbol") or {}).get(sym)
        if not rk:
            return
        self.h2("Risk")
        if rk.get("available") is False:
            self.p(f.text(f"Unavailable: {rk.get('reason')}"), "small")
            return
        w = rk.get("window") or {}
        self.table([["Measure", "Value"],
                    ["Risk class", rk.get("risk_classification") or "n/a"],
                    ["Annualised volatility", f.num(rk.get("annualized_volatility_pct"), suffix="%")],
                    ["Annualised return", f.num(rk.get("annualized_return_pct"), suffix="%")],
                    ["Beta vs NIFTY 50", f"{f.num(rk.get('beta'), 3)} ({rk.get('market_sensitivity') or 'n/a'})"],
                    ["Maximum drawdown", f.num(rk.get("max_drawdown_pct"), suffix="%")],
                    ["Sharpe ratio", f.num(rk.get("sharpe"), 3) if rk.get("sharpe") is not None
                     else f"n/a ({rk.get('sharpe_reason') or 'not available'})"],
                    ["Window", f"{w.get('from', 'n/a')} to {w.get('to', 'n/a')} ({w.get('observations', 'n/a')} days)"]],
                   widths=[85 * mm, 85 * mm])
        self.bullets(list((rk.get("readings") or {}).values()), "cell")
        if rk.get("explanation"):
            self.p(f"<i>Explanation:</i> {f.text(rk['explanation'])}", "cell")

    def portfolio_risk(self) -> None:
        f = self.f
        risk = (self.r.get("sections") or {}).get("risk") or {}
        pr = risk.get("portfolio")
        if not pr:
            return
        self.story.append(PageBreak())
        self.h1("Risk across the stocks")
        matrix = pr.get("correlation") or {}
        if matrix:
            names = list(matrix)
            rows = [["Correlation"] + names] + [[a] + [f.num((matrix.get(a) or {}).get(b), 2) for b in names]
                                                for a in names]
            width = min(30 * mm, 140 * mm / max(1, len(names)))
            self.table(rows, widths=[30 * mm] + [width] * len(names))
        div, conc = pr.get("diversification") or {}, pr.get("concentration") or {}
        pairs = [(f.label(k), f.num(v) if isinstance(v, (int, float)) else str(v)) for k, v in div.items()
                 if not isinstance(v, (dict, list))]
        pairs += [(f.label(k), f.num(v) if isinstance(v, (int, float)) else str(v)) for k, v in conc.items()
                  if not isinstance(v, (dict, list))]
        if pairs:
            self.kv(list(dict(pairs).items()))  # the same measure can appear in both groups
        if pr.get("weights_assumption"):
            self.p(f.text(f"Weights assumed: {pr['weights_assumption']}"), "small")

    def portfolio(self) -> None:
        f = self.f
        po = (self.r.get("sections") or {}).get("portfolio")
        if not po:
            return
        if not ((self.r.get("sections") or {}).get("risk") or {}).get("portfolio"):
            self.story.append(PageBreak())  # otherwise it follows "Risk across the stocks" on the same page
        self.h1("Illustrative portfolio")
        if po.get("available") is False:
            self.p(f.text(f"Unavailable: {po.get('reason')}"), "small")
            return
        cons = po.get("constraints") or {}
        self.kv([("Investment amount", f.inr(po.get("investment_amount"))),
                 ("Risk preference", f.text(po.get("risk_preference"))),
                 ("Method used", f.text(po.get("method_label") or po.get("method"))),
                 ("Weight limits", f"{f.num(cons.get('min_weight_pct'))}% to {f.num(cons.get('max_weight_pct'))}% "
                                   "per stock, no short selling"),
                 ("Invested / cash left", f"{f.inr(po.get('invested_inr'))} / {f.inr(po.get('leftover_cash_inr'))}")])
        if po.get("fallback_reason"):
            self.p(f.text(f"Fallback: {po['fallback_reason']}"), "small")
        for note in cons.get("notes") or []:
            self.p(f.text(note), "small")
        rows = [["Stock", "Target weight", "Actual weight", "Amount", "Shares", "Last price"]]
        for a in po.get("allocations") or []:
            rows.append([a.get("symbol") or "n/a", f.num(a.get("weight_pct"), suffix="%"),
                         f.num(a.get("actual_weight_pct"), suffix="%"), f.inr(a.get("amount_inr")),
                         f.num(a.get("shares"), 0), f"{f.num(a.get('last_price'))} ({a.get('last_price_date') or 'n/a'})"])
        self.table(rows, widths=[28 * mm, 24 * mm, 24 * mm, 32 * mm, 16 * mm, 46 * mm])
        self.add_drawing(self._allocation_chart(po.get("allocations") or []))

        em = po.get("expected_metrics") or {}
        self.h2("Expected figures (from past data)")
        self.table([["Measure", "Value"], ["Annual return", f.num(em.get("annual_return_pct"), suffix="%")],
                    ["Annual volatility", f.num(em.get("annual_volatility_pct"), suffix="%")],
                    ["Sharpe ratio", f.num(em.get("sharpe_ratio"), 3)]], widths=[85 * mm, 85 * mm])
        if em.get("basis"):
            self.p(f.text(f"Basis: {em['basis']}"), "small")

        bk = po.get("backtest")
        self.h2("Backtest")
        if not bk:
            self.p(f.text(po.get("backtest_reason") or "No backtest."), "small")
        else:
            period = bk.get("period") or {}
            self.table([["Measure", "Strategy"],
                        ["Test period", f"{period.get('from', 'n/a')} to {period.get('to', 'n/a')}"],
                        ["CAGR", f.num(bk.get("cagr_pct"), suffix="%")],
                        ["Equal-weight CAGR", f.num(bk.get("equal_weight_cagr_pct"), suffix="%")],
                        ["NIFTY 50 CAGR", f.num(bk.get("nifty50_cagr_pct"), suffix="%")],
                        ["Volatility", f.num(bk.get("volatility_pct"), suffix="%")],
                        ["Sharpe ratio", f.num(bk.get("sharpe"), 3)],
                        ["Maximum drawdown", f.num(bk.get("max_drawdown_pct"), suffix="%")],
                        ["Trading costs", f.inr(bk.get("total_costs_inr"))]], widths=[85 * mm, 85 * mm])
            curve = self.x.get("equity_curve") or []
            self.add_drawing(self._line_chart("Backtest: value of the investment", [
                ("Strategy", _points(curve, "strategy")), ("Equal weight", _points(curve, "equal_weight")),
                ("NIFTY 50", _points(curve, "nifty50"))], "INR"),
                "Walk-forward backtest: weights on each rebalance date use only earlier prices; costs included.")
            self.bullets(bk.get("limitations") or [], "small")
        if po.get("explanation"):
            self.p(f"<i>Explanation:</i> {f.text(po['explanation'])}", "cell")
        self.p(f.text(po.get("disclaimer")), "box")

    def appendix(self) -> None:
        f = self.f
        self.story.append(PageBreak())
        self.h1("Data limitations")
        self.bullets(self.r.get("data_limitations") or [], "cell")
        self.h1("Sources")
        rows = [["Source", "Detail", "Stock", "Data as of"]]
        for s in self.r.get("source_references") or []:
            rows.append([s.get("source") or "n/a", s.get("detail") or "", s.get("symbol") or "",
                         s.get("data_as_of") or ""])
        self.table(rows, widths=[50 * mm, 60 * mm, 28 * mm, 32 * mm])
        if self.r.get("glossary"):
            self.h1("Glossary")
            self.bullets(list(self.r["glossary"].values()), "cell")
        self.h1("Disclaimers")
        for d in [GENERAL_DISCLAIMER, *(self.r.get("disclaimers") or [])]:
            self.p(f.text(d), "cell")

    def build(self) -> bytes:
        self.cover()
        for sym in (self.r.get("request") or {}).get("symbols") or []:
            self.stock(sym)
        self.portfolio_risk()
        self.portfolio()
        self.appendix()
        buf = io.BytesIO()
        request_id = self.r.get("request_id") or ""
        font = self.font

        def footer(canvas, doc) -> None:
            canvas.saveState()
            canvas.setFont(font, 7)
            canvas.setFillColor(MUTED)
            canvas.drawString(18 * mm, 10 * mm, FOOTER)
            canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"{request_id[:8]} · page {doc.page}")
            canvas.restoreState()

        doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                                bottomMargin=18 * mm, title="NeuralVest report",
                                author="NeuralVest", subject=", ".join((self.r.get("request") or {}).get("symbols") or []),
                                creator="NeuralVest (ReportLab)")
        doc.build(self.story, onFirstPage=footer, onLaterPages=footer)
        return buf.getvalue()


# ---------------------------------------------------------------- helpers
def _when(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M UTC")
    if isinstance(value, str) and len(value) >= 16:
        return value[:16].replace("T", " ") + " UTC"
    return str(value) if value else "n/a"


def _to_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _thin(points: list[tuple[date, float]]) -> list[tuple[date, float]]:
    """At most MAX_CHART_POINTS points (keeps the first and last) so the PDF stays small."""
    if len(points) <= MAX_CHART_POINTS:
        return points
    step = len(points) / (MAX_CHART_POINTS - 1)
    picked = [points[int(i * step)] for i in range(MAX_CHART_POINTS - 1)]
    return picked + [points[-1]]


def _points(curve: list[dict], key: str) -> list[tuple[date, float]]:
    pts = [(d, row[key]) for row in curve if (d := _to_date(row.get("date"))) is not None
           and isinstance(row.get(key), (int, float))]
    return _thin(pts)


def price_points(docs: list[dict]) -> list[tuple[date, float]]:
    """market_data documents -> (date, close) points for the price chart."""
    pts = [(d, doc["close"]) for doc in docs if (d := _to_date(doc.get("date"))) is not None
           and isinstance(doc.get("close"), (int, float))]
    return _thin(sorted(pts))


def build_pdf(report: dict[str, Any], prices: dict[str, list[tuple[date, float]]] | None = None,
              equity_curve: list[dict] | None = None) -> bytes:
    """PDF bytes for a stored report. `prices` and `equity_curve` only add charts."""
    return _Builder(report, {"prices": prices or {}, "equity_curve": equity_curve or []}).build()
