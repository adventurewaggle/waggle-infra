from fastapi import FastAPI, Request
import sys; sys.path.insert(0, "/opt/waggle/shared")
from receipt import issue_receipt
from fastapi.responses import JSONResponse
import httpx
import os
import logging
import email as emaillib
import base64

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI()

OPENFANG_API = "http://127.0.0.1:50051/api"
RESEND_API_KEY = os.getenv("RESEND_API_KEY")

AGENT_IDS = {
    "orchestrator":     "5369a40d-4ca0-4deb-8d1d-2976b61cd6d8",
    "sales-assistant":  "8e453b66-c00a-442c-9410-5416022b769f",
    "analyst":          "4460936b-286b-4ba0-a184-5aee215cac28",
    "customer-support": "17e8e06d-b661-4398-8da9-e8b59ab514e1",
    "researcher":       "c0265b59-6868-4fc5-93f1-319585d0aa9e"
}

def extract_body(raw: str) -> str:
    """Extract clean plain text from raw MIME email."""
    try:
        msg = emaillib.message_from_string(raw)
        body = ""

        if msg.is_multipart():
            for part in msg.walk():
                ct = part.get_content_type()
                cte = part.get("Content-Transfer-Encoding", "")
                if ct == "text/plain":
                    payload = part.get_payload()
                    if cte.lower() == "base64":
                        payload = base64.b64decode(payload).decode("utf-8", errors="replace")
                    body += payload
        else:
            payload = msg.get_payload()
            cte = msg.get("Content-Transfer-Encoding", "")
            if cte.lower() == "base64":
                payload = base64.b64decode(payload).decode("utf-8", errors="replace")
            body = payload

        # Clean up
        body = body.strip()
        # Remove Proton Mail footer noise
        lines = [l for l in body.splitlines() 
                 if "proton.me" not in l.lower() 
                 and "sent from" not in l.lower()]
        return "\n".join(lines).strip()

    except Exception as e:
        logger.error(f"MIME parse error: {e}")
        return raw[:500]

def classify_route(subject: str, body: str) -> str:
    """Route email to correct agent based on content."""
    text = (subject + " " + body).lower()

    if any(w in text for w in ["invoice", "payment", "billing", "cost", "price", "quote", "pricing"]):
        return "analyst"

    if any(w in text for w in ["interested", "demo", "trial", "sign up", "get started", 
                                "your service", "waggle logic", "automat"]):
        return "sales-assistant"

    if any(w in text for w in ["support", "help", "issue", "problem", "broken", 
                                "not working", "error", "question"]):
        return "customer-support"

    if any(w in text for w in ["research", "report", "data", "analysis", "market"]):
        return "researcher"

    # Default — orchestrator handles anything ambiguous
    return "orchestrator"

async def send_reply(to: str, subject: str, body: str, from_domain: str):
    logger.info(f"Sending reply to {to}")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
            json={
                "from": f"Waggle Logic <connect@{from_domain}>",
                "to": [to],
                "subject": f"Re: {subject}",
                "text": body
            }
        )
        logger.info(f"Resend: {resp.status_code} | {resp.text}")
        return resp

@app.post("/webhooks/email")
async def receive_email(request: Request):
    data = await request.json()

    from_addr  = data.get("from", "")
    to_addr    = data.get("to", "")
    subject    = data.get("subject", "No subject")
    raw        = data.get("raw", "")

    # Parse clean body from MIME
    body = extract_body(raw)
    logger.info(f"Clean body: {body[:200]}")

    # Smart routing
    route_to = classify_route(subject, body)
    logger.info(f"From: {from_addr} | Subject: {subject} | Route: {route_to}")

    from_domain = "connect.adventurewaggle.nz" if "adventurewaggle" in to_addr else "connect.wagglelogic.com"
    agent_id = AGENT_IDS.get(route_to, AGENT_IDS["orchestrator"])

    message = f"""INBOUND EMAIL — ACTION REQUIRED
From: {from_addr}
Subject: {subject}

{body}

---
Instructions:
1. Understand what this person needs
2. Draft a professional reply under 200 words
3. Be warm, direct, and helpful
4. Start your response with REPLY: on its own line
5. Everything after REPLY: will be sent to {from_addr}
"""

    try:
        logger.info(f"Calling agent: {route_to} ({agent_id})")
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(
                f"{OPENFANG_API}/agents/{agent_id}/message",
                json={"message": message}
            )
            logger.info(f"Agent status: {resp.status_code}")
            result = resp.json()

        agent_text = result.get("response", "")
        logger.info(f"Agent response: {agent_text[:300]}")

        if "REPLY:" in agent_text:
            reply_body = agent_text.split("REPLY:", 1)[1].strip()
            await send_reply(from_addr, subject, reply_body, from_domain)
            await create_chatwoot_conversation(from_addr, from_addr, subject, body)
            action = f"replied via {route_to}"
        else:
            logger.warning(f"No REPLY: marker. Response: {agent_text[:200]}")
            action = "no reply — missing REPLY: marker"

    except Exception as e:
        logger.error(f"EXCEPTION: {e}")
        action = f"error: {e}"

    return JSONResponse({
        "status": "received",
        "routed_to": route_to,
        "action": action,
        "from": from_addr,
        "subject": subject
    })

@app.get("/webhooks/health")
async def health():
    return {"status": "ok"}

@app.post("/webhooks/chatwoot")
async def chatwoot_webhook(request: Request):
    data = await request.json()
    event = data.get("event")
    if event != "message_created":
        return {"status": "ignored"}
    msg = data.get("content", "")
    conv_id = data.get("conversation", {}).get("id")
    if not msg or data.get("message_type") != "incoming":
        return {"status": "ignored"}
    agent_id = "8414ea82-5e9b-4fb0-8030-d47d0e2126e6"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{OPENFANG_API}/agents/{agent_id}/message",
            json={"message": msg}
        )
        reply = r.json().get("response", "")
        if reply:
            await client.post(
                f"http://127.0.0.1:3000/api/v1/accounts/1/conversations/{conv_id}/messages",
                headers={"api_access_token": "4ASfXK964jmk5V1oDHQ7Hvbb"},
                json={"content": reply, "message_type": "outgoing", "private": False}
            )
    return {"status": "ok"}
