from __future__ import annotations
import os
from typing import Optional, List, Dict, Any
from langchain.tools import tool
from langchain_openai import ChatOpenAI

from tools.filesystem_retriever import (
    get_most_recent_invoice, find_invoices_in_period, find_payments_in_period
)
from tools.emailer import send_email

# ---- Tools exposed to the LLM (and also callable directly in nodes) ----

@tool("get_most_recent_invoice")
def get_most_recent_invoice_tool(account: Optional[str] = None) -> Dict[str, Any]:
    """
    Returns the most recent invoice for an account (if any).
    """
    inv = get_most_recent_invoice(account)
    if not inv:
        return {"found": False}
    return {
        "found": True,
        "invoice": {
            "account": inv.account,
            "invoice_no": inv.invoice_no,
            "date": inv.date,
            "path": str(inv.path),
        }
    }

@tool("list_invoices_in_period")
def list_invoices_in_period_tool(start_date: str, end_date: str, account: Optional[str] = None) -> Dict[str, Any]:
    """List all invoices within the provided date range for a given account."""
    hits = find_invoices_in_period(start_date, end_date, account)
    return {
        "count": len(hits),
        "invoices": [
            {"account": h.account, "invoice_no": h.invoice_no, "date": h.date, "path": str(h.path)}
            for h in hits
        ]
    }

@tool("list_payments_in_period")
def list_payments_in_period_tool(start_date: str, end_date: str, account: Optional[str] = None) -> Dict[str, Any]:
    """List all payment files in the given period for a given account."""
    hits = find_payments_in_period(start_date, end_date, account)
    return {
        "count": len(hits),
        "payments": [
            {"account": h.account, "date": h.date, "path": str(h.path)}
            for h in hits
        ]
    }

@tool("send_email_via_mock")
def send_email_via_mock_tool(to: str, subject: str, body: str, attachments: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Sends an email via mock sender (writes to JSONL outbox).
    Only call this after explicit human approval.
    """
    return send_email(to, subject, body, attachments)

# ---- LLM binding (optional; falls back to templates if no key) ----

def get_bound_llm():
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if not api_key:
        return None  # caller will fallback
    llm = ChatOpenAI(model=model, temperature=1)
    tools = [
        get_most_recent_invoice_tool,
        list_invoices_in_period_tool,
        list_payments_in_period_tool,
        send_email_via_mock_tool,
    ]
    return llm.bind_tools(tools)
