import re
from decimal import Decimal
from pathlib import Path
import pdfplumber
import pandas as pd
from loguru import logger
from app.parsers.base import BaseParser, RawTransaction

DATE_FORMATS = ["%d-%m-%Y", "%d/%m/%Y", "%d %b %Y", "%d-%b-%Y", "%d/%m/%y"]


class ICICIParser(BaseParser):
    BANK_NAME = "ICICI"

    def can_parse(self, content: str | bytes) -> bool:
        text = content if isinstance(content, str) else content.decode("utf-8", errors="ignore")
        return "ICICI" in text.upper()

    def parse(self, file_path: str) -> list[RawTransaction]:
        ext = Path(file_path).suffix.lower()
        if ext == ".pdf":
            return self._parse_pdf(file_path)
        elif ext == ".csv":
            return self._parse_csv(file_path)
        elif ext == ".xlsx":
            return self._parse_xlsx(file_path)
        return []

    def _parse_pdf(self, file_path: str) -> list[RawTransaction]:
        transactions = []
        row_pattern = re.compile(
            r"(\d{2}-\d{2}-\d{4})\s+(.+?)\s+([\d,]+\.\d{2})\s*(Dr|Cr)",
            re.IGNORECASE,
        )
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                for match in row_pattern.finditer(text):
                    txn_date = self._parse_date(match.group(1), DATE_FORMATS)
                    if not txn_date:
                        continue
                    desc = match.group(2).strip()
                    amount = self._clean_amount(match.group(3))
                    txn_type = "debit" if match.group(4).upper() == "DR" else "credit"
                    transactions.append(RawTransaction(date=txn_date, raw_merchant=desc, amount=amount, transaction_type=txn_type, description=desc))
        logger.info(f"ICICI PDF parsed: {len(transactions)} transactions")
        return transactions

    def _parse_csv(self, file_path: str) -> list[RawTransaction]:
        transactions = []
        try:
            df = pd.read_csv(file_path, encoding="latin-1")
            df.columns = [c.strip().lower() for c in df.columns]
            for _, row in df.iterrows():
                try:
                    date_col = next((c for c in df.columns if "date" in c), None)
                    desc_col = next((c for c in df.columns if "description" in c or "particulars" in c), None)
                    if not date_col or not desc_col:
                        break
                    txn_date = self._parse_date(str(row[date_col]), DATE_FORMATS)
                    if not txn_date:
                        continue
                    desc = str(row[desc_col]).strip()
                    debit_col = next((c for c in df.columns if "debit" in c or "withdrawal" in c), None)
                    credit_col = next((c for c in df.columns if "credit" in c or "deposit" in c), None)
                    debit = self._clean_amount(str(row[debit_col])) if debit_col and pd.notna(row[debit_col]) else Decimal("0")
                    credit = self._clean_amount(str(row[credit_col])) if credit_col and pd.notna(row[credit_col]) else Decimal("0")
                    if debit > 0:
                        transactions.append(RawTransaction(date=txn_date, raw_merchant=desc, amount=debit, transaction_type="debit", description=desc))
                    elif credit > 0:
                        transactions.append(RawTransaction(date=txn_date, raw_merchant=desc, amount=credit, transaction_type="credit", description=desc))
                except Exception:
                    continue
        except Exception as e:
            logger.error(f"ICICI CSV parse error: {e}")
        return transactions

    def _parse_xlsx(self, file_path: str) -> list[RawTransaction]:
        transactions = []
        try:
            df = pd.read_excel(file_path)
            df.columns = [str(c).strip().lower() for c in df.columns]
            for _, row in df.iterrows():
                try:
                    date_col = next((c for c in df.columns if "date" in c), None)
                    desc_col = next((c for c in df.columns if "description" in c or "particulars" in c), None)
                    if not date_col or not desc_col:
                        break
                    txn_date = self._parse_date(str(row[date_col]), DATE_FORMATS)
                    if not txn_date:
                        continue
                    desc = str(row[desc_col]).strip()
                    debit_col = next((c for c in df.columns if "debit" in c), None)
                    credit_col = next((c for c in df.columns if "credit" in c), None)
                    debit = self._clean_amount(str(row[debit_col])) if debit_col and pd.notna(row[debit_col]) else Decimal("0")
                    credit = self._clean_amount(str(row[credit_col])) if credit_col and pd.notna(row[credit_col]) else Decimal("0")
                    if debit > 0:
                        transactions.append(RawTransaction(date=txn_date, raw_merchant=desc, amount=debit, transaction_type="debit", description=desc))
                    elif credit > 0:
                        transactions.append(RawTransaction(date=txn_date, raw_merchant=desc, amount=credit, transaction_type="credit", description=desc))
                except Exception:
                    continue
        except Exception as e:
            logger.error(f"ICICI XLSX parse error: {e}")
        return transactions
