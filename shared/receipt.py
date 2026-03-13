import hashlib, json, time, uuid
from datetime import datetime, timezone
from pathlib import Path

RECEIPT_LOG = Path("/opt/waggle/shared/logs/receipts.jsonl")

def issue_receipt(
    agent: str,
    action: str,
    inputs: dict,
    outputs: dict,
    cost_usd: float = 0.0,
    client_id: str = None
) -> dict:
    receipt = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": agent,
        "action": action,
        "inputs": inputs,
        "outputs": outputs,
        "cost_usd": cost_usd,
        "client_id": client_id,
    }
    # Tamper-evident hash of the receipt content
    content = json.dumps({k: v for k, v in receipt.items() if k != "hash"}, sort_keys=True)
    receipt["hash"] = hashlib.sha256(content.encode()).hexdigest()

    RECEIPT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(RECEIPT_LOG, "a") as f:
        f.write(json.dumps(receipt) + "\n")

    return receipt

def verify_receipt(receipt: dict) -> bool:
    content = json.dumps({k: v for k, v in receipt.items() if k != "hash"}, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest() == receipt.get("hash")

if __name__ == "__main__":
    # Test
    r = issue_receipt(
        agent="cfo-monitor",
        action="model-routing-decision",
        inputs={"mrr": 0, "daily_cost": 0.18, "condition": "mrr == 0 and daily_cost > 2.00"},
        outputs={"decision": "no_change", "reason": "cost below threshold"},
        cost_usd=0.0
    )
    print(json.dumps(r, indent=2))
    print(f"\nValid: {verify_receipt(r)}")
