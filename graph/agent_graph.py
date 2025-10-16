from __future__ import annotations
from typing import TypedDict, Literal, List, Optional, Dict, Any
from langgraph.graph import StateGraph, START, END

from graph.llm_tools import (
    get_bound_llm,
    get_most_recent_invoice_tool,
    list_invoices_in_period_tool,
    list_payments_in_period_tool,
    send_email_via_mock_tool
)

# ----- Agent State -----

class AgentState(TypedDict, total=False):
    # Inputs
    task: Literal["recent_invoice", "invoices_period", "payments_period"]
    account: Optional[str]
    start_date: Optional[str]
    end_date: Optional[str]
    contact_email: str
    # Working memory
    fetched: Dict[str, Any]
    draft: str
    attachments: List[str]
    # Human-in-the-loop
    awaiting_approval: bool
    approved: bool
    # UI message (optional)
    ui_msg: str

# ----- Drafting helpers (fallback if no LLM) -----

def template_draft_email(state: AgentState) -> str:
    t = state["task"]
    f = state.get("fetched", {})
    if t == "recent_invoice":
        inv = f.get("invoice", {})
        return (
            "Hello,\n\n"
            "Please find a summary of your most recent invoice:\n"
            f"- Account: {inv.get('account','')}\n"
            f"- Invoice: {inv.get('invoice_no','')}\n"
            f"- Date: {inv.get('date','')}\n\n"
            "Let us know if you have any questions.\n\nBest regards,\nBilling Team"
        )
    elif t == "invoices_period":
        lines = "\n".join(
            f"- {i['date']} / {i['account']} / {i['invoice_no']}"
            for i in f.get("invoices", [])
        )
        return f"Hello,\n\nHere are your invoices for the requested period:\n{lines}\n\nBest,\nBilling"
    else:
        lines = "\n".join(
            f"- {p['date']} / {p['account']}"
            for p in f.get("payments", [])
        )
        return f"Hello,\n\nHere are your payments for the requested period:\n{lines}\n\nBest,\nBilling"

# ----- Nodes -----

def setup(state: AgentState) -> AgentState:
    # Initialize defaults
    state.setdefault("fetched", {})
    state.setdefault("attachments", [])
    state.setdefault("approved", False)
    state["awaiting_approval"] = False
    return state

def fetch_data(state: AgentState) -> AgentState:
    # Use tools directly (deterministic). You *could* let the LLM decide tool calls,
    # but for this POC we orchestrate the tool usage explicitly here.
    task = state["task"]
    account = state.get("account")
    if task == "recent_invoice":
        res = get_most_recent_invoice_tool.invoke({"account": account})
        state["fetched"] = res
        if res.get("found"):
            state["attachments"] = [res["invoice"]["path"]]
        else:
            state["attachments"] = []
    elif task == "invoices_period":
        res = list_invoices_in_period_tool.invoke({
            "start_date": state["start_date"],
            "end_date": state["end_date"],
            "account": account
        })
        state["fetched"] = res
        state["attachments"] = []
    else:
        res = list_payments_in_period_tool.invoke({
            "start_date": state["start_date"],
            "end_date": state["end_date"],
            "account": account
        })
        state["fetched"] = res
        state["attachments"] = []
    return state

def draft_email(state: AgentState) -> AgentState:
    # Try LLM with bound tools (for richer language); fallback to template
    llm = get_bound_llm()
    if llm is None:
        state["draft"] = template_draft_email(state)
        return state

    # Build a compact system/user prompt:
    t = state["task"]
    f = state.get("fetched", {})
    user_content = {
        "task": t,
        "data": f,
        "instruction": "Draft a concise, courteous email. No hallucinations. Keep it factual."
    }
    resp = llm.invoke([{"role": "user", "content": str(user_content)}])
    state["draft"] = resp.content if hasattr(resp, "content") else template_draft_email(state)
    return state

def present_for_approval(state: AgentState) -> AgentState:
    # Pause the graph here: UI should display draft + attachments; user must approve.
    state["awaiting_approval"] = True
    state["ui_msg"] = "Draft ready. Awaiting human approval."
    return state


def router(state: AgentState):
    # If we're awaiting approval and it's not given yet, STOP the graph here.
    if state.get("awaiting_approval") and not state.get("approved"):
        return END
    # If approval has been given, go send.
    if state.get("approved"):
        return "send"
    # Default: stop
    return END

def send_email_node(state: AgentState) -> AgentState:
    res = send_email_via_mock_tool.invoke({
        "to": state.get("contact_email", "customer@example.com"),
        "subject": "Your Billing Summary",
        "body": state.get("draft", ""),
        "attachments": state.get("attachments", []),
    })
    state["ui_msg"] = f"Email sent: {res}"
    return state

# ----- Build the graph -----

def build_graph():
    g = StateGraph(AgentState)
    g.add_node("setup", setup)
    g.add_node("fetch", fetch_data)
    g.add_node("draft", draft_email)
    g.add_node("present", present_for_approval)
    g.add_node("send", send_email_node)
    g.add_edge(START, "setup")
    g.add_edge("setup", "fetch")
    g.add_edge("fetch", "draft")
    g.add_edge("draft", "present")

    # Conditional pause / send / end
    def _route(state: AgentState):
        r = router(state)
        if r == "PAUSE":
            return "present"  # remain here; UI will flip `approved=True` and call again
        elif r == "SEND":
            return "send"
        return END

    g.add_conditional_edges("present", router, {"send": "send", END: END})
    g.add_edge("send", END)
    return g.compile()
