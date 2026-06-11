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
        """Strip location suffixes, numbers, and normalize whitespace."""
        upper = raw.upper().strip()
        # Remove common location noise
        patterns = [
            r"\b(BANGALORE|MUMBAI|DELHI|CHENNAI|HYDERABAD|KOLKATA|PUNE|INDIA|IN)\b",
            r"\b\d{4,}\b",
            r"[*#@/\\|]",
        ]
        for p in patterns:
            upper = re.sub(p, " ", upper)
        # Collapse whitespace
        upper = re.sub(r"\s+", " ", upper).strip()
        # Extract primary brand token (first 1-3 meaningful words)
        tokens = [t for t in upper.split() if len(t) > 2 and not t.isdigit()]
        return tokens[0] if tokens else upper

    @staticmethod
    def _parse_date(value: str, formats: list[str]) -> Optional[date]:
        from datetime import datetime
        for fmt in formats:
            try:
                return datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                continue
        return None
