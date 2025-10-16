from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
import re

DATA_ROOT = Path(__file__).resolve().parent.parent / "data"

@dataclass
class InvoiceHit:
    path: Path
    account: str
    invoice_no: str
    date: str  # YYYY-MM-DD

@dataclass
class PaymentHit:
    path: Path
    account: str
    date: str  # YYYY-MM-DD

def _iter_date_dirs(base: Path):
    if not base.exists():
        return
    for d in sorted(base.iterdir()):
        if d.is_dir():
            yield d

def _parse_invoice_filename(name: str):
    # Invoice_Account123_INV001.pdf
    m = re.match(r"Invoice_(?P<account>[^_]+)_(?P<inv>[^.]+)\.pdf", name, re.I)
    return (m.group('account'), m.group('inv')) if m else (None, None)

def _parse_payments_filename(name: str):
    # Payments_Account123.xlsx
    m = re.match(r"Payments_(?P<account>[^.]+)\.xlsx", name, re.I)
    return m.group('account') if m else None

def get_most_recent_invoice(account: Optional[str]=None) -> Optional[InvoiceHit]:
    base = DATA_ROOT / "invoices"
    latest = None
    for d in _iter_date_dirs(base):
        for f in d.glob("*.pdf"):
            acc, inv = _parse_invoice_filename(f.name)
            if not acc: continue
            if account and acc.lower() != account.lower(): continue
            latest = InvoiceHit(path=f, account=acc, invoice_no=inv, date=d.name)
    return latest

def find_invoices_in_period(start_date: str, end_date: str, account: Optional[str]=None) -> List[InvoiceHit]:
    base = DATA_ROOT / "invoices"
    sdt = datetime.fromisoformat(start_date).date()
    edt = datetime.fromisoformat(end_date).date()
    hits: List[InvoiceHit] = []
    for d in _iter_date_dirs(base):
        ddate = datetime.fromisoformat(d.name).date()
        if not (sdt <= ddate <= edt): continue
        for f in d.glob("*.pdf"):
            acc, inv = _parse_invoice_filename(f.name)
            if not acc: continue
            if account and acc.lower() != account.lower(): continue
            hits.append(InvoiceHit(path=f, account=acc, invoice_no=inv, date=d.name))
    return hits

def find_payments_in_period(start_date: str, end_date: str, account: Optional[str]=None) -> List[PaymentHit]:
    base = DATA_ROOT / "payments"
    sdt = datetime.fromisoformat(start_date).date()
    edt = datetime.fromisoformat(end_date).date()
    hits: List[PaymentHit] = []
    for d in _iter_date_dirs(base):
        ddate = datetime.fromisoformat(d.name).date()
        if not (sdt <= ddate <= edt): continue
        for f in d.glob("*.xlsx"):
            acc = _parse_payments_filename(f.name)
            if not acc: continue
            if account and acc.lower() != account.lower(): continue
            hits.append(PaymentHit(path=f, account=acc, date=d.name))
    return hits
