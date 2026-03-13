import json, re
from datetime import datetime, timezone
from pathlib import Path
import sys
sys.path.insert(0, "/opt/waggle/shared")
from receipt import issue_receipt

SUSPICIOUS_PATTERNS = [
    r"ignore.{0,20}(previous|above|prior|all).{0,20}(instructions|prompts|rules)",
    r"you are now",
    r"new persona",
    r"disregard",
    r"override",
    r"system prompt",
    r"forget.{0,20}(everything|instructions|rules)",
    r"act as",
    r"jailbreak",
    r"DAN",
    r"developer mode",
]

REQUIRED_FIELDS = [
    "business_name", "industry", "primary_pain",
    "channels", "tone", "recommended_tier"
]

WHITELIST = [
    "business_name", "industry", "team_size", "primary_pain",
    "channels", "tone", "products", "ideal_customer",
    "success_metric", "current_tools", "assets",
    "recommended_tier", "recommended_agents",
    "key_automations", "onboarding_notes"
]

def validate_intake(raw):
    profile = raw.get("client_profile", {})
    missing = [f for f in REQUIRED_FIELDS if not profile.get(f)]
    if missing:
        return False, f"Missing fields: {missing}", {}
    all_text = json.dumps(profile).lower()
    for pattern in SUSPICIOUS_PATTERNS:
        if re.search(pattern, all_text, re.IGNORECASE):
            return False, f"Injection attempt detected", {}
    tier = str(profile.get("recommended_tier", ""))
    if tier not in ["400", "800", "1600"]:
        profile["recommended_tier"] = "400"
    clean = {k: v for k, v in profile.items() if k in WHITELIST}
    return True, "valid", clean

def process_intake(raw_json):
    try:
        raw = json.loads(raw_json)
    except json.JSONDecodeError as e:
        return {"status": "error", "reason": str(e)}
    valid, reason, clean = validate_intake(raw)
    receipt = issue_receipt(
        agent="waggle-intake-validator",
        action="intake-validation",
        inputs={"raw_keys": list(raw.get("client_profile", {}).keys())},
        outputs={"valid": valid, "reason": reason},
        cost_usd=0.0
    )
    if not valid:
        with open("/opt/waggle/shared/logs/intake_rejected.jsonl", "a") as f:
            f.write(json.dumps({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "reason": reason,
                "receipt_id": receipt["id"]
            }) + "\n")
        return {"status": "rejected", "reason": reason}
    queue_file = f"/opt/waggle/intake/queue/{receipt['id']}.json"
    with open(queue_file, "w") as f:
        json.dump({
            "status": "pending",
            "profile": clean,
            "receipt_id": receipt["id"],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, f, indent=2)
    return {"status": "queued", "receipt_id": receipt["id"], "profile": clean}

if __name__ == "__main__":
    test = json.dumps({"client_profile": {
        "business_name": "Test Co",
        "industry": "retail",
        "primary_pain": "too much admin",
        "channels": ["email"],
        "tone": "casual",
        "recommended_tier": "400"
    }})
    result = process_intake(test)
    print(json.dumps(result, indent=2))
