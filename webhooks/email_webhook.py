from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import httpx
import json
import os

app = FastAPI()

OPENFANG_API = "http://127.0.0.1:4200/api"

AGENT_IDS = {
    "orchestrator": "5369a40d-4ca0-4deb-8d1d-2976b61cd6d8",
    "sales-assistant": "8e453b66-c00a-442c-9410-5416022b769f",
    "analyst": "4460936b-286b-4ba0-a184-5aee215cac28",
    "customer-support": "17e8e06d-b661-4398-8da9-e8b59ab514e1"
}

@app.post("/webhooks/email")
async def receive_email(request: Request):
    data = await request.json()
    
    route_to = data.get("route_to", "orchestrator")
    from_addr = data.get("from", "")
    subject = data.get("subject", "No subject")
    raw = data.get("raw", "")
    
    agent_id = AGENT_IDS.get(route_to, AGENT_IDS["orchestrator"])
    
    message = f"""INBOUND EMAIL
From: {from_addr}
Subject: {subject}

{raw[:2000]}

---
Handle this email. If it's a lead, qualify them and draft a response. 
If it's a client, action their request.
If urgent, flag to founder via Telegram.
"""
    
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{OPENFANG_API}/agents/{agent_id}/message",
            json={"content": message}
        )
    
    return JSONResponse({"status": "received", "routed_to": route_to})

@app.get("/webhooks/health")
async def health():
    return {"status": "ok"}
