import json, os, time, httpx, asyncio
from pathlib import Path
from datetime import datetime, timezone
import sys
sys.path.insert(0, "/opt/waggle/shared")
from receipt import issue_receipt

QUEUE_DIR = Path("/opt/waggle/intake/queue")
PROCESSED_DIR = Path("/opt/waggle/intake/processed")
ORCHESTRATOR_ID = "5369a40d-4ca0-4deb-8d1d-2976b61cd6d8"
OPENFANG_API = "http://127.0.0.1:50051/api"

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

async def process_queued_profile(filepath: Path):
    with open(filepath) as f:
        item = json.load(f)

    profile = item["profile"]
    business = profile.get("business_name", "Unknown")
    tier = profile.get("recommended_tier", "400")
    pain = profile.get("primary_pain", "")
    agents = profile.get("recommended_agents", [])
    automations = profile.get("key_automations", [])

    message = f"""NEW CLIENT INTAKE QUEUED

Business: {business}
Tier: NZD {tier}/mo
Primary pain: {pain}
Recommended agents: {', '.join(agents) if agents else 'TBD'}
Key automations: {', '.join(automations) if automations else 'TBD'}
Tone: {profile.get('tone', 'professional')}
Industry: {profile.get('industry', 'unknown')}

ACTION REQUIRED:
1. Review this profile
2. Draft welcome email to {business}
3. Confirm NZD {tier}/mo trial activation
4. Note any questions for follow-up call

Receipt ID: {item['receipt_id']}"""

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{OPENFANG_API}/agents/{ORCHESTRATOR_ID}/message",
                json={"message": message}
            )
            success = r.status_code == 200
    except Exception as e:
        print(f"Orchestrator notify failed: {e}")
        success = False

    issue_receipt(
        agent="queue-processor",
        action="intake-dispatched",
        inputs={"business": business, "tier": tier},
        outputs={"orchestrator_notified": success},
        cost_usd=0.0,
        client_id=item["receipt_id"]
    )

    # Move to processed
    processed_file = PROCESSED_DIR / filepath.name
    filepath.rename(processed_file)
    print(f"Processed: {business} (NZD {tier}/mo) -> {processed_file.name}")

async def watch_queue():
    print("Queue processor watching /opt/waggle/intake/queue/")
    while True:
        pending = list(QUEUE_DIR.glob("*.json"))
        for f in pending:
            await process_queued_profile(f)
        await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(watch_queue())
