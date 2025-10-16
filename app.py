import base64
from pathlib import Path
from datetime import date, timedelta
import streamlit as st
from dotenv import load_dotenv

from graph.agent_graph import build_graph, AgentState

load_dotenv()
app = build_graph()

st.set_page_config(page_title="AgentForce Billing Demo", layout="wide")
st.title("🧾 AgentForce Billing Demo (LangGraph + Tools + HITL)")

# SIDEBAR: inputs
with st.sidebar:
    st.markdown("### Params")
    account = st.text_input("Account", value="Account123")
    contact = st.text_input("Contact Email", value="customer@example.com")
    today = date.today()
    start = st.date_input("Start date", today - timedelta(days=7))
    end = st.date_input("End date", today)

    st.markdown("### Actions")
    if st.button("Most Recent Invoice"):
        st.session_state["intent"] = ("recent_invoice", str(account), None, None, contact)
    if st.button("Invoices in Period"):
        st.session_state["intent"] = ("invoices_period", str(account), str(start), str(end), contact)
    if st.button("Payments in Period"):
        st.session_state["intent"] = ("payments_period", str(account), str(start), str(end), contact)

# Initialize chat/session state
if "state" not in st.session_state:
    st.session_state["state"] = None

# Trigger graph
if "intent" in st.session_state:
    task, acct, s, e, contact_email = st.session_state["intent"]
    base_state: AgentState = {
        "task": task,
        "account": acct,
        "start_date": s,
        "end_date": e,
        "contact_email": contact_email,
        "approved": False,
    }
    # Run graph to the pause point (awaiting approval)
    st.session_state["state"] = app.invoke(base_state)
    del st.session_state["intent"]

state = st.session_state.get("state")

# LEFT: show draft transcript
col1, col2 = st.columns([3,2])
with col1:
    st.subheader("Draft Output")
    if state:
        st.write(state.get("ui_msg") or "")
        st.text_area("Draft Email", value=state.get("draft",""), height=260, key="draft_text")
    else:
        st.info("Trigger an action from the sidebar to start.")

# RIGHT: preview & approve/send
with col2:
    st.subheader("Preview & Approval")
    if state and state.get("attachments"):
        pdf_path = Path(state["attachments"][0])
        st.caption(f"Invoice PDF: {pdf_path.name}")
        try:
            b64 = base64.b64encode(pdf_path.read_bytes()).decode("utf-8")
            st.markdown(
                f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="480px"></iframe>',
                unsafe_allow_html=True
            )
        except Exception as e:
            st.error(f"PDF preview error: {e}")
        st.download_button("Download PDF", data=pdf_path.read_bytes(), file_name=pdf_path.name)

    if state:
        # Human-in-the-loop: approve & resume
        if st.button("✅ Approve & Send"):
            state["draft"] = st.session_state["draft_text"]
            state["approved"] = True
            state["awaiting_approval"] = False
            st.session_state["state"] = app.invoke(state)
            st.success(st.session_state["state"].get("ui_msg","Sent."))
        elif st.button("🔁 Revise (stay in draft)"):
            st.info("You can edit the draft text. Approve when ready.")
