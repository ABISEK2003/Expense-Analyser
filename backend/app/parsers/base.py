import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional


@dataclass
class RawTransaction:
    date: date
    raw_merchant: str
    amount: Decimal
    transaction_type: str  # 'debit' | 'credit'
    description: Optional[str] = None
    reference_number: Optional[str] = None


class BaseParser(ABC):
    BANK_NAME: str = "Unknown"

    @abstractmethod
    def can_parse(self, content: str | bytes) -> bool:
        """Return True if this parser can handle the file."""

    @abstractmethod
    def parse(self, file_path: str) -> list[RawTransaction]:
        """Extract transactions from the file."""

    @staticmethod
    def _clean_amount(value: str) -> Decimal:
        cleaned = re.sub(r"[^\d.]", "", str(value).strip())
        try:
            return Decimal(cleaned)
        except InvalidOperation:
            return Decimal("0")

    @staticmethod
    def _normalize_merchant(raw: str) -> str:
        """Strip location/noise tokens and return up to 3 meaningful words."""
        upper = raw.upper().strip()
        # Remove URL prefixes
        upper = re.sub(r"\bWWW\b", " ", upper)
        # Remove city/location names
        upper = re.sub(
            r"\b(BANGALORE|BENGALURU|MUMBAI|DELHI|NEW DELHI|CHENNAI|HYDERABAD|"
            r"KOLKATA|PUNE|GURGAON|NOIDA|GURUGRAM|INDIA|CENTRAL DE)\b",
            " ", upper,
        )
        # Remove standalone location abbreviation IN (not brand names like INDIGO)
        upper = re.sub(r"(?<![A-Z])\bIN\b(?![A-Z])", " ", upper)
        # Remove long reference numbers (4+ digits)
        upper = re.sub(r"\b\d{4,}\b", " ", upper)
        # Remove special characters
        upper = re.sub(r"[*#@/\\|()\[\]]", " ", upper)
        # Collapse whitespace
        upper = re.sub(r"\s+", " ", upper).strip()
        # Return up to 3 meaningful tokens (len > 2, not purely numeric)
        tokens = [t for t in upper.split() if len(t) > 2 and not t.isdigit()]
        return " ".join(tokens[:3]) if tokens else upper

    @staticmethod
    def _parse_date(value: str, formats: list[str]) -> Optional[date]:
        from datetime import datetime
        for fmt in formats:
            try:
                return datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                continue
        return None
