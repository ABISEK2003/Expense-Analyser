import re
from decimal import Decimal
from pathlib import Path

import pdfplumber
from loguru import logger

from app.parsers.base import BaseParser, RawTransaction

DATE_FORMATS = ["%d-%m-%y", "%d-%m-%Y", "%d/%m/%Y", "%d/%m/%y"]

_TABLE_HEADER_RE = re.compile(r"\bDATE\s+PARTICULARS\b", re.IGNORECASE)
_DATE_LINE_RE = re.compile(r"^\d{2}-\d{2}-\d{2}\b")
_OPENING_BALANCE_RE = re.compile(
    r"^(?P<date>\d{2}-\d{2}-\d{2})\s+(?P<desc>B/F|BAL(?:ANCE)?\s+B/F|OPENING\s+BALANCE)\s+"
    r"(?P<balance>[\d,]+\.\d{2}(?:Cr|Dr))$",
    re.IGNORECASE,
)
_TRANSACTION_RE = re.compile(
    r"^(?P<date>\d{2}-\d{2}-\d{2})\s+"
    r"(?P<desc>.+?)\s+"
    r"(?P<amount>[\d,]+\.\d{2})\s+"
    r"(?P<balance>[\d,]+\.\d{2}(?:Cr|Dr))$",
    re.IGNORECASE,
)


class BankOfBarodaParser(BaseParser):
    BANK_NAME = "Bank of Baroda"

    def can_parse(self, content: str | bytes) -> bool:
        text = content if isinstance(content, str) else content.decode("utf-8", errors="ignore")
        upper = text.upper()
        return "BANK OF BARODA" in upper or "BARODA" in upper

    def parse(self, file_path: str) -> list[RawTransaction]:
        if Path(file_path).suffix.lower() != ".pdf":
            return []
        return self._parse_pdf(file_path)

    def _parse_pdf(self, file_path: str) -> list[RawTransaction]:
        transactions: list[RawTransaction] = []
        current_entry: dict[str, str | list[str]] | None = None
        prev_balance: Decimal | None = None
        in_transactions = False

        def flush_entry() -> None:
            nonlocal current_entry, prev_balance
            if not current_entry:
                return

            main_line = str(current_entry["line"]).strip()
            continuations = [str(part).strip() for part in current_entry["continuations"] if str(part).strip()]
            current_entry = None

            opening_match = _OPENING_BALANCE_RE.match(main_line)
            if opening_match:
                prev_balance = self._parse_signed_balance(opening_match.group("balance"))
                return

            match = _TRANSACTION_RE.match(main_line)
            if not match:
                return

            txn_date = self._parse_date(match.group("date"), DATE_FORMATS)
            if not txn_date:
                return

            amount = self._clean_amount(match.group("amount"))
            if amount <= 0:
                return

            balance = self._parse_signed_balance(match.group("balance"))
            description = " ".join([match.group("desc").strip(), *continuations]).strip()
            if not description:
                return

            txn_type = self._infer_transaction_type(prev_balance, balance, amount)
            prev_balance = balance

            transactions.append(
                RawTransaction(
                    date=txn_date,
                    raw_merchant=description,
                    amount=amount,
                    transaction_type=txn_type,
                    description=description,
                )
            )

        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                for raw_line in text.splitlines():
                    line = " ".join(raw_line.split())
                    if not line:
                        continue

                    if _TABLE_HEADER_RE.search(line):
                        in_transactions = True
                        continue

                    if not in_transactions:
                        continue

                    if self._is_ignorable_line(line):
                        continue

                    if _DATE_LINE_RE.match(line):
                        flush_entry()
                        current_entry = {"line": line, "continuations": []}
                        continue

                    if current_entry:
                        current_entry["continuations"].append(line)

        flush_entry()
        logger.info(f"Bank of Baroda PDF parsed: {len(transactions)} transactions")
        return transactions

    @staticmethod
    def _parse_signed_balance(value: str) -> Decimal:
        amount = BaseParser._clean_amount(value)
        return -amount if value.strip().lower().endswith("dr") else amount

    @staticmethod
    def _infer_transaction_type(
        previous_balance: Decimal | None, current_balance: Decimal, amount: Decimal
    ) -> str:
        if previous_balance is None:
            return "credit" if current_balance >= 0 else "debit"

        if current_balance > previous_balance:
            return "credit"
        if current_balance < previous_balance:
            return "debit"

        return "credit" if amount == 0 else "debit"

    @staticmethod
    def _is_ignorable_line(line: str) -> bool:
        upper = line.upper()
        if re.fullmatch(r"[-=]{3,}", line):
            return True
        return any(
            token in upper
            for token in (
                "TRANSACTION DETAILS",
                "STATEMENT OF ACCOUNT",
                "WITHDRAWALS",
                "DEPOSITS",
                "BALANCE",
                "DATE PARTICULARS",
                "A/C NUMBER",
                "ACCOUNT OPEN DATE",
                "PAGE NO",
            )
        )
