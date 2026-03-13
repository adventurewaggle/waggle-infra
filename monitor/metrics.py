import subprocess, httpx, json, time, asyncio
from datetime import datetime

OPENFANG_API = "http://127.0.0.1:4200/api"
LOG_FILE = "/opt/waggle/shared/logs/metrics.log"

AGENTS = {
    "orchestrator":     "5369a40d-4ca0-4deb-8d1d-2976b61cd6d8",
    "researcher":       "c0265b59-6868-4fc5-93f1-319585d0aa9e",
    "analyst":          "4460936b-286b-4ba0-a184-5aee215cac28",
    "sales":            "8e453b66-c00a-442c-9410-5416022b769f",
    "customer-support": "17e8e06d-b661-4398-8da9-e8b59ab514e1",
    "social-media":     "edb85ad1-5f2e-4493-9eab-703ed8159e66"
}

SLOW_THRESHOLD = 120  # seconds — alert if grunt layer exceeds this

async def ping_agent(name, agent_id):
    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=180) as client:
            r = await client.post(
                f"{OPENFANG_API}/agents/{agent_id}/message",
                json={"message": "ping — reply with one word: pong"}
            )
            elapsed = round(time.time() - start, 2)
            data = r.json()
            return {
                "response_time_s": elapsed,
                "status": "ok" if r.status_code == 200 else "error",
                "cost_usd": data.get("cost_usd", 0),
                "output_tokens": data.get("output_tokens", 0),
                "model": data.get("model", "unknown")
            }
    except Exception as e:
        return {
            "response_time_s": round(time.time() - start, 2),
            "status": f"error: {e}"
        }

async def collect():
    metrics = {"timestamp": datetime.utcnow().isoformat(), "agents": {}, "system": {}, "ollama": {}}

    # System
    metrics["system"] = {
        "cpu": subprocess.getoutput("top -bn1 | grep 'Cpu(s)' | awk '{print $2}'").strip(),
        "mem_pct": subprocess.getoutput("free -m | awk 'NR==2{printf \"%.1f\", $3*100/$2}'").strip(),
        "load": subprocess.getoutput("cat /proc/loadavg").split()[:3],
        "disk_pct": subprocess.getoutput("df / | awk 'NR==2{print $5}'").strip()
    }

    # Ollama running models
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get("http://127.0.0.1:11434/api/ps")
            models = r.json().get("models", [])
            metrics["ollama"] = {
                "active": len(models),
                "models": [m.get("name") for m in models]
            }
    except:
        metrics["ollama"] = {"active": 0}

    # Ping all agents concurrently
    tasks = {name: ping_agent(name, aid) for name, aid in AGENTS.items()}
    results = await asyncio.gather(*tasks.values())
    metrics["agents"] = dict(zip(tasks.keys(), results))

    # Log
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(metrics) + "\n")

    # Alert on slow grunt layer
    for name in ["customer-support", "social-media"]:
        t = metrics["agents"].get(name, {}).get("response_time_s", 0)
        if t > SLOW_THRESHOLD:
            async with httpx.AsyncClient(timeout=30) as client:
                await client.post(
                    f"{OPENFANG_API}/agents/5369a40d-4ca0-4deb-8d1d-2976b61cd6d8/message",
                    json={"message": f"PERFORMANCE ALERT: {name} response time {t}s exceeds {SLOW_THRESHOLD}s threshold. Grunt layer congested — consider escalating to API model or queuing requests."}
                )

    return metrics

if __name__ == "__main__":
    m = asyncio.run(collect())
    print(json.dumps(m, indent=2))
