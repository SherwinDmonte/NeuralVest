"""Text extraction from MANUALLY downloaded annual-report PDFs (decision D1: pypdf, BSD).

Only files inside data/financial_reports/ are read (no arbitrary paths). Scanned PDFs
(images without a text layer) yield little or no text; OCR is out of scope and such
pages are reported, not guessed.
"""

from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.config import Settings, get_settings
from app.data.errors import DataError

MAX_PDF_BYTES = 50 * 1024 * 1024


@dataclass
class PdfText:
    file: str
    page_count: int
    pages: list[str]
    empty_pages: list[int] = field(default_factory=list)  # 1-based page numbers
    warnings: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n\n".join(self.pages)


def _resolve_inside(base_dir: Path, filename: str) -> Path:
    base = base_dir.resolve()
    path = (base / filename).resolve()
    if base not in path.parents:
        raise DataError("PDF must be inside data/financial_reports/")
    if path.suffix.lower() != ".pdf":
        raise DataError("only .pdf files are supported")
    if not path.is_file():
        raise DataError(f"file not found: {filename}")
    if path.stat().st_size > MAX_PDF_BYTES:
        raise DataError("PDF is larger than 50 MB")
    return path


def extract_pdf_text(filename: str, max_pages: int | None = None, settings: Settings | None = None) -> PdfText:
    """Extract text page by page from data/financial_reports/<filename>."""
    settings = settings or get_settings()
    path = _resolve_inside(Path(settings.financial_reports_dir), filename)
    try:
        reader = PdfReader(str(path), strict=False)
        if reader.is_encrypted and not reader.decrypt(""):
            raise DataError("PDF is password-protected")
        pages_to_read = reader.pages[: max_pages] if max_pages else reader.pages
        pages = [(page.extract_text() or "").strip() for page in pages_to_read]
    except PdfReadError as exc:
        raise DataError(f"could not read PDF: {exc.__class__.__name__}") from exc

    result = PdfText(file=path.name, page_count=len(reader.pages), pages=pages)
    result.empty_pages = [i + 1 for i, text in enumerate(pages) if not text]
    if result.empty_pages:
        result.warnings.append(
            f"{len(result.empty_pages)} page(s) have no extractable text (possibly scanned images; OCR not supported)."
        )
    if max_pages and result.page_count > max_pages:
        result.warnings.append(f"Only the first {max_pages} of {result.page_count} pages were read.")
    return result
