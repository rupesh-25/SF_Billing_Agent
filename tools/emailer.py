from __future__ import annotations
from pathlib import Path
from datetime import datetime
import json

OUTBOX = Path(__file__).resolve().parent.parent / "sent_emails" / "outbox.jsonl"
OUTBOX.parent.mkdir(parents=True, exist_ok=True)

def send_email(to: str, subject: str, body: str, attachments=None):
    record = {
        "timestamp": datetime.utcnow().isoformat(),
        "from": "billing@logicmonitor.com",  # mocked
        "to": to,
        "subject": subject,
        "body": body,
        "attachments": attachments or []
    }
    with OUTBOX.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    return {"status": "ok", "id": record["timestamp"]}
