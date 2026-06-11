from pathlib import Path
import pdfplumber
from loguru import logger
from app.parsers.base import BaseParser, RawTransaction
from app.parsers.hdfc import HDFCParser
from app.parsers.icici import ICICIParser
from app.parsers.sbi import SBIParser
from app.parsers.axis import AxisParser

PARSERS: list[BaseParser] = [
    HDFCParser(),
    ICICIParser(),
    SBIParser(),
    AxisParser(),
]


def _extract_text_sample(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        with pdfplumber.open(file_path) as pdf:
            print(f"Extracting text sample from PDF: {file_path}")
            print(f"Number of pages in PDF: {len(pdf.pages)}")
            print(f"Extracted text from first page: {(pdf.pages[0].extract_text() or '')[:500]}")  # Print first 500 chars
            return (pdf.pages[0].extract_text() or "") if pdf.pages else ""
    elif ext in (".csv", ".xlsx"):
        with open(file_path, "rb") as f:
            return f.read(2048).decode("utf-8", errors="ignore")
    return ""


def get_parser(file_path: str) -> tuple[BaseParser, str]:
    """Return the appropriate parser and bank name for the given file."""
    sample = _extract_text_sample(file_path)
    for parser in PARSERS:
        if parser.can_parse(sample):
            logger.info(f"Auto-selected parser: {parser.BANK_NAME} for {file_path}")
            return parser, parser.BANK_NAME

    logger.warning(f"No specific parser matched for {file_path}, using generic CSV/XLSX fallback")
    return HDFCParser(), "Unknown"


def parse_statement(file_path: str) -> tuple[list[RawTransaction], str]:
    parser, bank_name = get_parser(file_path)
    transactions = parser.parse(file_path)
    return transactions, bank_name
