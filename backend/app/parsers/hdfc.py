import re
from decimal import Decimal
from pathlib import Path
import pdfplumber
import pandas as pd
from loguru import logger
from app.parsers.base import BaseParser, RawTransaction

DATE_FORMATS = ["%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%d-%b-%Y"]

# Keywords that identify summary/header rows (not transactions)
_SUMMARY_RE = re.compile(
    r"\b(total\s+dues|minimum\s+amount|opening\s+balance|closing\s+balance|"
    r"credit\s+limit|available\s+credit|cash\s+limit|finance\s+charge|"
    r"reward\s+points|statement\s+date|payment\s+due)\b",
    re.IGNORECASE,
)


class HDFCParser(BaseParser):
    BANK_NAME = "HDFC"

    def can_parse(self, content: str | bytes) -> bool:
        text = content if isinstance(content, str) else content.decode("utf-8", errors="ignore")
        return "HDFC" in text.upper()

    def parse(self, file_path: str) -> list[RawTransaction]:
        ext = Path(file_path).suffix.lower()
        if ext == ".pdf":
            return self._parse_pdf(file_path)
        elif ext == ".csv":
            return self._parse_csv(file_path)
        elif ext in (".xlsx", ".xls"):
            return self._parse_xlsx(file_path)
        return []

    # ── PDF ───────────────────────────────────────────────────────────────────

    def _parse_pdf(self, file_path: str) -> list[RawTransaction]:
        with pdfplumber.open(file_path) as pdf:
            full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)

        # Format 1: DD/MM/YYYY| HH:MM  DESCRIPTION  [+] C AMOUNT  [l/●]
        # HDFC netbanking/online statements (pdfplumber renders ₹ as "C")
        txns = self._fmt_pipe_time(full_text)
        if txns:
            logger.info(f"HDFC PDF (pipe-time format): {len(txns)} transactions")
            return txns

        # Format 2: DD/MM/YYYY  DESCRIPTION  AMOUNT  [Cr|Dr]
        # HDFC corporate / VISA Purchase Premium / physical statements
        txns = self._fmt_cr_dr_suffix(full_text)
        if txns:
            logger.info(f"HDFC PDF (Cr/Dr suffix format): {len(txns)} transactions")
            return txns

        # Format 3: table-based extraction via pdfplumber
        # Fallback for PDFs where text layout doesn't suit regex
        txns = self._fmt_table(file_path)
        if txns:
            logger.info(f"HDFC PDF (table format): {len(txns)} transactions")
            return txns

        logger.warning("HDFC PDF: no transactions matched any format")
        return []

    def _fmt_pipe_time(self, text: str) -> list[RawTransaction]:
        """DD/MM/YYYY| HH:MM DESCRIPTION [+] C AMOUNT"""
        pattern = re.compile(
            r"(\d{2}/\d{2}/\d{4})\s*\|\s*\d{2}:\d{2}\s+"
            r"(.+?)\s+"
            r"(\+\s*)?"
            r"[C₹]\s*([\d,]+\.\d{2})"
            r"(?:\s+[l●])?$",
            re.MULTILINE,
        )
        txns = []
        for m in pattern.finditer(text):
            txn_date = self._parse_date(m.group(1), DATE_FORMATS)
            if not txn_date:
                continue
            desc = m.group(2).strip()
            amount = self._clean_amount(m.group(4))
            if amount <= 0:
                continue
            is_credit = bool(m.group(3)) or bool(
                re.search(r"CREDIT CARD PAYMENT|AUTOPAY THANK YOU", desc, re.IGNORECASE)
            )
            txns.append(RawTransaction(
                date=txn_date, raw_merchant=desc, amount=amount,
                transaction_type="credit" if is_credit else "debit", description=desc,
            ))
        return txns

    def _fmt_cr_dr_suffix(self, text: str) -> list[RawTransaction]:
        """DD/MM/YYYY DESCRIPTION AMOUNT [Cr|Dr]"""
        pattern = re.compile(
            r"^(\d{2}/\d{2}/\d{4})\s+(.+?)\s+([\d,]+\.\d{2})(\s+(?:Cr|Dr))?$",
            re.MULTILINE | re.IGNORECASE,
        )
        txns = []
        for m in pattern.finditer(text):
            txn_date = self._parse_date(m.group(1), DATE_FORMATS)
            if not txn_date:
                continue
            desc = m.group(2).strip()
            # Must contain at least one letter (filters pure-number summary rows)
            if not re.search(r"[A-Za-z]", desc):
                continue
            # Skip rows where description embeds another date (header artefacts)
            if re.search(r"\d{2}/\d{2}/\d{4}", desc):
                continue
            # Skip known summary/header phrases
            if _SUMMARY_RE.search(desc):
                continue
            amount = self._clean_amount(m.group(3))
            if amount <= 0:
                continue
            suffix = (m.group(4) or "").strip().upper()
            is_credit = suffix == "CR" or bool(
                re.search(r"CREDIT CARD PAYMENT|AUTOPAY THANK YOU", desc, re.IGNORECASE)
            )
            txns.append(RawTransaction(
                date=txn_date, raw_merchant=desc, amount=amount,
                transaction_type="credit" if is_credit else "debit", description=desc,
            ))
        return txns

    def _fmt_table(self, file_path: str) -> list[RawTransaction]:
        """Extract from pdfplumber table cells — works when text layout is irregular."""
        txns = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                for table in (page.extract_tables() or []):
                    for row in table:
                        if not row or len(row) < 3:
                            continue
                        date_str = str(row[0] or "").strip()
                        desc = str(row[1] or "").strip()
                        amt_str = str(row[-1] or "").strip()  # amount is always last col

                        txn_date = self._parse_date(date_str, DATE_FORMATS)
                        if not txn_date or not desc or not re.search(r"[A-Za-z]", desc):
                            continue
                        if _SUMMARY_RE.search(desc):
                            continue
                        amount = self._clean_amount(amt_str)
                        if amount <= 0:
                            continue
                        is_credit = bool(re.search(r"Cr$", amt_str, re.IGNORECASE)) or bool(
                            re.search(r"CREDIT CARD PAYMENT|AUTOPAY THANK YOU", desc, re.IGNORECASE)
                        )
                        txns.append(RawTransaction(
                            date=txn_date, raw_merchant=desc, amount=amount,
                            transaction_type="credit" if is_credit else "debit", description=desc,
                        ))
        return txns

    # ── CSV ───────────────────────────────────────────────────────────────────

    def _parse_csv(self, file_path: str) -> list[RawTransaction]:
        """Try multiple skip-row offsets to find the data block."""
        for skip in (21, 18, 15, 12, 0):
            try:
                df = pd.read_csv(file_path, skiprows=skip, header=None, encoding="latin-1")
                txns = self._extract_from_df(df)
                if txns:
                    logger.info(f"HDFC CSV (skip={skip}): {len(txns)} transactions")
                    return txns
            except Exception:
                continue
        logger.error("HDFC CSV: could not parse with any skip-row offset")
        return []

    # ── Excel ─────────────────────────────────────────────────────────────────

    def _parse_xlsx(self, file_path: str) -> list[RawTransaction]:
        for skip in (21, 18, 15, 12, 0):
            try:
                df = pd.read_excel(file_path, skiprows=skip, header=None)
                txns = self._extract_from_df(df)
                if txns:
                    logger.info(f"HDFC XLSX (skip={skip}): {len(txns)} transactions")
                    return txns
            except Exception:
                continue
        logger.error("HDFC XLSX: could not parse with any skip-row offset")
        return []

    # ── Shared tabular helper ─────────────────────────────────────────────────

    def _extract_from_df(self, df: pd.DataFrame) -> list[RawTransaction]:
        """Parse a DataFrame where col0=date, col1=desc, col4=debit, col5=credit."""
        txns = []
        for _, row in df.iterrows():
            try:
                txn_date = self._parse_date(str(row.iloc[0]), DATE_FORMATS)
                if not txn_date:
                    continue
                desc = str(row.iloc[1]).strip()
                if not desc or desc.lower() == "nan":
                    continue

                # Try dedicated debit/credit columns first (col 4 & 5)
                if len(row) >= 6:
                    debit = self._clean_amount(str(row.iloc[4])) if pd.notna(row.iloc[4]) else Decimal("0")
                    credit = self._clean_amount(str(row.iloc[5])) if pd.notna(row.iloc[5]) else Decimal("0")
                    if debit > 0:
                        txns.append(RawTransaction(date=txn_date, raw_merchant=desc, amount=debit,
                                                    transaction_type="debit", description=desc))
                    elif credit > 0:
                        txns.append(RawTransaction(date=txn_date, raw_merchant=desc, amount=credit,
                                                    transaction_type="credit", description=desc))
                # Fallback: single amount column (col 2) with Cr/Dr suffix
                elif len(row) >= 3:
                    amt_str = str(row.iloc[2]).strip()
                    amount = self._clean_amount(amt_str)
                    if amount <= 0:
                        continue
                    is_credit = bool(re.search(r"Cr$", amt_str, re.IGNORECASE)) or bool(
                        re.search(r"CREDIT CARD PAYMENT|AUTOPAY THANK YOU", desc, re.IGNORECASE)
                    )
                    txns.append(RawTransaction(date=txn_date, raw_merchant=desc, amount=amount,
                                               transaction_type="credit" if is_credit else "debit",
                                               description=desc))
            except Exception:
                continue
        return txns
