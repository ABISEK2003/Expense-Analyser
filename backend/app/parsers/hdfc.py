import re
from decimal import Decimal
from pathlib import Path
import pdfplumber
import pandas as pd
from loguru import logger
from app.parsers.base import BaseParser, RawTransaction

DATE_FORMATS = ["%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%d-%b-%Y"]


class HDFCParser(BaseParser):
    BANK_NAME = "HDFC"

    def can_parse(self, content: str | bytes) -> bool:
        text = content if isinstance(content, str) else content.decode("utf-8", errors="ignore")
        return "HDFC" in text.upper() or "HDFC BANK" in text.upper()

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

        # HDFC statement format:
        #   DD/MM/YYYY| HH:MM  DESCRIPTION  [+] C AMOUNT  [l/●]
        # pdfplumber renders ₹ as "C"; "+" prefix means credit.
        row_pattern = re.compile(
            r"(\d{2}/\d{2}/\d{4})\s*\|\s*\d{2}:\d{2}\s+"   # date | time
            r"(.+?)\s+"                                        # description
            r"(\+\s*)?"                                        # optional + = credit
            r"[C₹]\s*([\d,]+\.\d{2})"                        # C/₹ + amount
            r"(?:\s+[l●])?$",                                  # optional PI marker
            re.MULTILINE,
        )

        with pdfplumber.open(file_path) as pdf:
            full_text = "\n".join(
                page.extract_text() or "" for page in pdf.pages
            )

        for match in row_pattern.finditer(full_text):
            txn_date = self._parse_date(match.group(1), DATE_FORMATS)
            if not txn_date:
                continue

            desc = match.group(2).strip()

            # Skip GST/tax lines
            if re.search(r"\b(CGST|SGST|IGST)-", desc, re.IGNORECASE):
                continue

            amount = self._clean_amount(match.group(4))
            if amount <= 0:
                continue

            # + prefix OR well-known credit keywords → credit
            is_credit = bool(match.group(3)) or bool(
                re.search(r"(CREDIT CARD PAYMENT|AUTOPAY THANK YOU)", desc, re.IGNORECASE)
            )

            transactions.append(
                RawTransaction(
                    date=txn_date,
                    raw_merchant=desc,
                    amount=amount,
                    transaction_type="credit" if is_credit else "debit",
                    description=desc,
                )
            )

        logger.info(f"HDFC PDF parsed: {len(transactions)} transactions")
        return transactions

    def _parse_csv(self, file_path: str) -> list[RawTransaction]:
        transactions = []
        try:
            df = pd.read_csv(file_path, skiprows=21, header=None, encoding="latin-1")
            for _, row in df.iterrows():
                try:
                    txn_date = self._parse_date(str(row.iloc[0]), DATE_FORMATS)
                    if not txn_date:
                        continue
                    desc = str(row.iloc[1]).strip()
                    debit = self._clean_amount(str(row.iloc[4])) if str(row.iloc[4]).strip() else Decimal("0")
                    credit = self._clean_amount(str(row.iloc[5])) if str(row.iloc[5]).strip() else Decimal("0")
                    if debit > 0:
                        transactions.append(RawTransaction(date=txn_date, raw_merchant=desc, amount=debit, transaction_type="debit", description=desc))
                    elif credit > 0:
                        transactions.append(RawTransaction(date=txn_date, raw_merchant=desc, amount=credit, transaction_type="credit", description=desc))
                except Exception:
                    continue
        except Exception as e:
            logger.error(f"HDFC CSV parse error: {e}")
        return transactions

    def _parse_xlsx(self, file_path: str) -> list[RawTransaction]:
        transactions = []
        try:
            df = pd.read_excel(file_path, skiprows=21, header=None)
            for _, row in df.iterrows():
                try:
                    txn_date = self._parse_date(str(row.iloc[0]), DATE_FORMATS)
                    if not txn_date:
                        continue
                    desc = str(row.iloc[1]).strip()
                    debit = self._clean_amount(str(row.iloc[4])) if pd.notna(row.iloc[4]) else Decimal("0")
                    credit = self._clean_amount(str(row.iloc[5])) if pd.notna(row.iloc[5]) else Decimal("0")
                    if debit > 0:
                        transactions.append(RawTransaction(date=txn_date, raw_merchant=desc, amount=debit, transaction_type="debit", description=desc))
                    elif credit > 0:
                        transactions.append(RawTransaction(date=txn_date, raw_merchant=desc, amount=credit, transaction_type="credit", description=desc))
                except Exception:
                    continue
        except Exception as e:
            logger.error(f"HDFC XLSX parse error: {e}")
        return transactions
