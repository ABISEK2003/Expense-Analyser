import re
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pdfplumber
from loguru import logger

from app.parsers.base import BaseParser, RawTransaction

DATE_FORMATS = [
    "%d-%m-%Y",
    "%d-%m-%y",
    "%d/%m/%Y",
    "%d/%m/%y",
    "%d %b %Y",
    "%d-%b-%Y",
    "%Y-%m-%d",
]

_DATE_AT_START_RE = re.compile(r"^\d{2}[-/]\d{2}[-/]\d{2,4}\b|^\d{2}\s+\w{3}\s+\d{4}\b")
_AMOUNT_RE = re.compile(r"[\d,]+\.\d{2}")
_BALANCE_SUFFIX_RE = re.compile(r"(Cr|Dr)\.?$", re.IGNORECASE)
_HEADER_KEYWORDS = {
    "date": ("date", "txn date", "transaction date", "value date"),
    "desc": ("description", "narration", "particulars", "remarks", "details", "transaction details"),
    "debit": ("debit", "withdrawal", "withdrawals", "debits"),
    "credit": ("credit", "deposit", "deposits", "credits"),
    "amount": ("amount", "txn amount", "transaction amount"),
    "balance": ("balance", "running balance", "closing balance"),
}


class GenericStatementParser(BaseParser):
    BANK_NAME = "Generic Statement"

    def can_parse(self, content: str | bytes) -> bool:
        return False

    def parse(self, file_path: str) -> list[RawTransaction]:
        ext = Path(file_path).suffix.lower()
        if ext == ".pdf":
            return self._parse_pdf(file_path)
        if ext in (".csv", ".xlsx", ".xls"):
            return self._parse_tabular(file_path, ext)
        return []

    def _parse_pdf(self, file_path: str) -> list[RawTransaction]:
        txns = self._parse_pdf_tables(file_path)
        if txns:
            logger.info(f"Generic PDF (table format): {len(txns)} transactions")
            return txns

        txns = self._parse_pdf_lines(file_path)
        if txns:
            logger.info(f"Generic PDF (line format): {len(txns)} transactions")
            return txns

        logger.warning("Generic PDF parser found no transactions")
        return []

    def _parse_pdf_tables(self, file_path: str) -> list[RawTransaction]:
        transactions: list[RawTransaction] = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables() or []:
                    if not table or len(table) < 2:
                        continue
                    df = pd.DataFrame(table)
                    parsed = self._extract_from_df(df)
                    if parsed:
                        transactions.extend(parsed)
        return self._dedupe(transactions)

    def _parse_pdf_lines(self, file_path: str) -> list[RawTransaction]:
        transactions: list[RawTransaction] = []
        current_entry: dict[str, str | list[str]] | None = None
        previous_balance: Decimal | None = None

        def flush() -> None:
            nonlocal current_entry, previous_balance
            if not current_entry:
                return

            line = str(current_entry["line"]).strip()
            continuations = [str(part).strip() for part in current_entry["continuations"] if str(part).strip()]
            current_entry = None

            parts = line.rsplit(" ", 2)
            if len(parts) < 3:
                return

            date_str, desc, tail = parts
            txn_date = self._parse_date(date_str, DATE_FORMATS)
            if not txn_date:
                return

            amount_match = _AMOUNT_RE.search(tail)
            if not amount_match:
                return

            amount = self._clean_amount(amount_match.group(0))
            if amount <= 0:
                return

            full_desc = " ".join([desc.strip(), *continuations]).strip()
            if not full_desc or full_desc.lower() == "nan":
                return

            txn_type = "debit"
            if _BALANCE_SUFFIX_RE.search(tail):
                current_balance = self._parse_signed_amount(tail)
                txn_type = self._infer_transaction_type(previous_balance, current_balance)
                previous_balance = current_balance
            elif re.search(r"\b(cr|credit|deposit)\b", tail, re.IGNORECASE):
                txn_type = "credit"

            transactions.append(
                RawTransaction(
                    date=txn_date,
                    raw_merchant=full_desc,
                    amount=amount,
                    transaction_type=txn_type,
                    description=full_desc,
                )
            )

        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                for raw_line in (page.extract_text() or "").splitlines():
                    line = " ".join(raw_line.split())
                    if not line or self._looks_like_header(line):
                        continue

                    if _DATE_AT_START_RE.match(line):
                        flush()
                        current_entry = {"line": line, "continuations": []}
                    elif current_entry:
                        current_entry["continuations"].append(line)

        flush()
        return self._dedupe(transactions)

    def _parse_tabular(self, file_path: str, ext: str) -> list[RawTransaction]:
        try:
            if ext == ".csv":
                raw_df = pd.read_csv(file_path, header=None, encoding="latin-1")
            else:
                raw_df = pd.read_excel(file_path, header=None)
        except Exception as e:
            logger.error(f"Generic tabular parse error: {e}")
            return []

        txns = self._extract_from_df(raw_df)
        if txns:
            logger.info(f"Generic tabular parser: {len(txns)} transactions")
        return txns

    def _extract_from_df(self, raw_df: pd.DataFrame) -> list[RawTransaction]:
        header_idx = self._find_header_row(raw_df)
        if header_idx is None:
            return []

        header = [self._normalize_header(cell) for cell in raw_df.iloc[header_idx].tolist()]
        df = raw_df.iloc[header_idx + 1 :].copy()
        df.columns = header

        date_col = self._find_column(df.columns, "date")
        desc_col = self._find_column(df.columns, "desc")
        if not date_col or not desc_col:
            return []

        debit_col = self._find_column(df.columns, "debit")
        credit_col = self._find_column(df.columns, "credit")
        amount_col = self._find_column(df.columns, "amount")
        balance_col = self._find_column(df.columns, "balance")

        transactions: list[RawTransaction] = []
        previous_balance: Decimal | None = None

        for _, row in df.iterrows():
            txn_date = self._parse_date(str(row.get(date_col, "")).strip(), DATE_FORMATS)
            if not txn_date:
                continue

            desc = str(row.get(desc_col, "")).strip()
            if not desc or desc.lower() == "nan":
                continue

            debit = self._cell_amount(row.get(debit_col)) if debit_col else Decimal("0")
            credit = self._cell_amount(row.get(credit_col)) if credit_col else Decimal("0")
            amount = self._cell_amount(row.get(amount_col)) if amount_col else Decimal("0")

            if debit > 0:
                txn_amount = debit
                txn_type = "debit"
            elif credit > 0:
                txn_amount = credit
                txn_type = "credit"
            elif amount > 0:
                txn_amount = amount
                txn_type = self._infer_type_from_row(desc, row, balance_col, previous_balance)
            else:
                continue

            if balance_col:
                balance_value = str(row.get(balance_col, "")).strip()
                if balance_value and balance_value.lower() != "nan":
                    previous_balance = self._parse_signed_amount(balance_value)

            transactions.append(
                RawTransaction(
                    date=txn_date,
                    raw_merchant=desc,
                    amount=txn_amount,
                    transaction_type=txn_type,
                    description=desc,
                )
            )

        return self._dedupe(transactions)

    @staticmethod
    def _normalize_header(value: object) -> str:
        return " ".join(str(value or "").strip().lower().split())

    @staticmethod
    def _find_header_row(df: pd.DataFrame) -> int | None:
        max_rows = min(len(df), 25)
        for idx in range(max_rows):
            cells = [GenericStatementParser._normalize_header(cell) for cell in df.iloc[idx].tolist()]
            joined = " | ".join(cells)
            has_date = any(keyword in joined for keyword in _HEADER_KEYWORDS["date"])
            has_desc = any(keyword in joined for keyword in _HEADER_KEYWORDS["desc"])
            has_amount = any(
                keyword in joined
                for group in ("debit", "credit", "amount", "balance")
                for keyword in _HEADER_KEYWORDS[group]
            )
            if has_date and has_desc and has_amount:
                return idx
        return None

    @staticmethod
    def _find_column(columns, group: str) -> str | None:
        for col in columns:
            normalized = str(col).strip().lower()
            if any(keyword in normalized for keyword in _HEADER_KEYWORDS[group]):
                return col
        return None

    @staticmethod
    def _cell_amount(value: object) -> Decimal:
        if value is None:
            return Decimal("0")
        text = str(value).strip()
        if not text or text.lower() == "nan":
            return Decimal("0")
        return BaseParser._clean_amount(text)

    @staticmethod
    def _parse_signed_amount(value: str) -> Decimal:
        amount = BaseParser._clean_amount(value)
        return -amount if re.search(r"\bdr\b", value, re.IGNORECASE) else amount

    def _infer_type_from_row(
        self,
        description: str,
        row: pd.Series,
        balance_col: str | None,
        previous_balance: Decimal | None,
    ) -> str:
        if balance_col:
            balance_value = str(row.get(balance_col, "")).strip()
            if balance_value and balance_value.lower() != "nan":
                current_balance = self._parse_signed_amount(balance_value)
                return self._infer_transaction_type(previous_balance, current_balance)

        if re.search(r"\b(cr|credit|deposit|refund|reversal|received)\b", description, re.IGNORECASE):
            return "credit"
        return "debit"

    @staticmethod
    def _infer_transaction_type(previous_balance: Decimal | None, current_balance: Decimal) -> str:
        if previous_balance is None:
            return "credit" if current_balance >= 0 else "debit"
        if current_balance > previous_balance:
            return "credit"
        if current_balance < previous_balance:
            return "debit"
        return "debit"

    @staticmethod
    def _looks_like_header(line: str) -> bool:
        upper = line.upper()
        if re.fullmatch(r"[-=]{3,}", line):
            return True
        return any(
            token in upper
            for token in (
                "TRANSACTION DETAILS",
                "STATEMENT OF ACCOUNT",
                "DATE PARTICULARS",
                "DATE DESCRIPTION",
                "WITHDRAWAL",
                "DEPOSIT",
                "BALANCE",
                "OPENING BALANCE",
                "CLOSING BALANCE",
                "PAGE NO",
                "ACCOUNT NUMBER",
            )
        )

    @staticmethod
    def _dedupe(transactions: list[RawTransaction]) -> list[RawTransaction]:
        seen: set[tuple[str, str, str, str]] = set()
        unique: list[RawTransaction] = []
        for txn in transactions:
            key = (str(txn.date), txn.raw_merchant, str(txn.amount), txn.transaction_type)
            if key in seen:
                continue
            seen.add(key)
            unique.append(txn)
        return unique
