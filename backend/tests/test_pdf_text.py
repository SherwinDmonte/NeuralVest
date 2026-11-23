import pytest
from reportlab.pdfgen import canvas

from app.config import Settings
from app.data.errors import DataError
from app.data.pdf_text import extract_pdf_text


@pytest.fixture
def reports_dir(tmp_path):
    pdf = canvas.Canvas(str(tmp_path / "sample_report.pdf"))
    pdf.drawString(72, 720, "Synthetic annual report: Revenue from operations")
    pdf.showPage()
    pdf.showPage()  # an empty page (like a scanned image without text)
    pdf.save()
    (tmp_path / "notes.txt").write_text("not a pdf")
    return tmp_path


def settings_for(path) -> Settings:
    return Settings(_env_file=None, financial_reports_dir=path)


def test_extracts_text_and_reports_empty_pages(reports_dir):
    result = extract_pdf_text("sample_report.pdf", settings=settings_for(reports_dir))
    assert result.page_count == 2
    assert "Revenue from operations" in result.text
    assert result.empty_pages == [2] and result.warnings


def test_max_pages(reports_dir):
    result = extract_pdf_text("sample_report.pdf", max_pages=1, settings=settings_for(reports_dir))
    assert len(result.pages) == 1 and any("first 1 of 2" in w for w in result.warnings)


@pytest.mark.parametrize("name", ["../outside.pdf", "notes.txt", "missing.pdf"])
def test_rejects_unsafe_or_invalid_files(reports_dir, name):
    with pytest.raises(DataError):
        extract_pdf_text(name, settings=settings_for(reports_dir))
