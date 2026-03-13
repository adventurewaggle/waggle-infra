import subprocess, httpx, json, time, asyncio, chromadb
import sys; sys.path.insert(0, "/opt/waggle/shared")
from receipt import issue_receipt
from datetime import datetime, timezone

OPENFANG_API = "http://127.0.0.1:50051/api"
ORCHESTRATOR_ID = "5369a40d-4ca0-4deb-8d1d-2976b61cd6d8"
ANALYST_ID = "4460936b-286b-4ba0-a184-5aee215cac28"
SALES_ID = "8e453b66-c00a-442c-9410-5416022b769f"

chroma = chromadb.HttpClient(host="localhost", port=8000)
perf_col = chroma.get_or_create_collection("performance_metrics")

AGENT_IDS = {
    "orchestrator":     "5369a40d-4ca0-4deb-8d1d-2976b61cd6d8",
    "researcher":       "c0265b59-6868-4fc5-93f1-319585d0aa9e",
    "analyst":          "4460936b-286b-4ba0-a184-5aee215cac28",
    "sales":            "8e453b66-c00a-442c-9410-5416022b769f",
    "customer-support": "17e8e06d-b661-4398-8da9-e8b59ab514e1",
    "social-media":     "edb85ad1-5f2e-4493-9eab-703ed8159e66",
    "planner":          "848f0d44-aee9-492e-97eb-5f526a150bf3"
}

ROUTING_RULES = [
    {
        "condition": "mrr == 0 and daily_cost > 2.00",
        "action": "downgrade",
        "agents": ["customer-support", "social-media"],
        "to_model": "ollama/qwen2.5:7b",
        "reason": "Zero revenue — cost gate active"
    },
    {
        "condition": "mrr >= 400 and grunt_response > 120",
        "action": "upgrade",
        "agents": ["customer-support"],
        "to_model": "openrouter/minimax/minimax-m2.5",
        "reason": "Client paying — upgrade support quality"
    },
    {
        "condition": "mrr >= 2400",
        "action": "upgrade",
        "agents": ["customer-support", "social-media"],
        "to_model": "openrouter/moonshotai/kimi-k2",
        "reason": "3+ clients — full API stack justified"
    },
]

def get_daily_api_cost() -> float:
    try:
        key = subprocess.getoutput(
            "grep OPENROUTER_API_KEY /opt/waggle/shared/configs/.env | cut -d= -f2"
        ).strip()
        r = httpx.get(
            "https://openrouter.ai/api/v1/auth/key",
            headers={"Authorization": f"Bearer {key}"},
            timeout=10
        )
        return float(r.json().get("data", {}).get("usage_daily", 0))
    except:
        return 0.0

def get_mrr() -> float:
    try:
        import psycopg2
        conn = psycopg2.connect("dbname=waggle user=postgres host=localhost")
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(SUM(monthly_value_nzd), 0) FROM clients WHERE status='active'")
        mrr = float(cur.fetchone()[0])
        conn.close()
        return mrr
    except:
        return 0.0

async def ping_agent(name: str, agent_id: str) -> dict:
    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                f"{OPENFANG_API}/agents/{agent_id}/message",
                json={"message": "ping"}
            )
            elapsed = round(time.time() - start, 2)
            data = r.json()
            return {
                "response_time_s": elapsed,
                "status": "ok",
                "cost_usd": data.get("cost_usd", 0),
                "tokens": data.get("output_tokens", 0)
            }
    except Exception as e:
        return {"response_time_s": round(time.time() - start, 2), "status": f"error: {e}"}

async def apply_routing_rule(rule: dict, context: dict):
    for agent_name in rule["agents"]:
        agent_id = AGENT_IDS.get(agent_name)
        if not agent_id:
            continue
        subprocess.run([
            "/root/.openfang/bin/openfang", "agent", "set",
            agent_id, "model", rule["to_model"]
        ], capture_output=True)

    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": rule["action"],
        "agents": rule["agents"],
        "model": rule["to_model"],
        "reason": rule["reason"],
        "context": context
    }
    with open("/opt/waggle/shared/logs/routing_decisions.log", "a") as f:
        f.write(json.dumps(log_entry) + "\n")
    issue_receipt(
        agent="cfo-monitor",
        action="model-routing-decision",
        inputs=context,
        outputs={"agents": rule["agents"], "model": rule["to_model"]},
        cost_usd=0.0
    )

    async with httpx.AsyncClient(timeout=30) as client:
        await client.post(
            f"{OPENFANG_API}/agents/{ORCHESTRATOR_ID}/message",
            json={"message": f"AUTO-ROUTING: {rule['reason']} — {rule['agents']} → {rule['to_model']}"}
        )

async def run_cfo_monitor():
    now = datetime.now(timezone.utc)
    metrics = {
        "timestamp": now.isoformat(),
        "financial": {},
        "performance": {},
        "system": {},
        "decisions": []
    }

    mrr = get_mrr()
    daily_cost = get_daily_api_cost()
    metrics["financial"] = {
        "mrr_nzd": mrr,
        "daily_api_cost_usd": daily_cost,
        "monthly_projected_usd": round(daily_cost * 30, 4),
        "cost_revenue_ratio": round((daily_cost * 30 * 1.6) / mrr, 3) if mrr > 0 else 999
    }

    metrics["system"] = {
        "cpu": subprocess.getoutput("top -bn1 | grep 'Cpu(s)' | awk '{print $2}'").strip(),
        "mem_pct": subprocess.getoutput("free -m | awk 'NR==2{printf \"%.1f\", $3*100/$2}'").strip(),
        "load": subprocess.getoutput("cat /proc/loadavg").split()[:3],
        "disk_pct": subprocess.getoutput("df / | awk 'NR==2{print $5}'").strip()
    }

    grunt_agents = {
        "customer-support": "17e8e06d-b661-4398-8da9-e8b59ab514e1",
        "social-media": "edb85ad1-5f2e-4493-9eab-703ed8159e66"
    }
    tasks = [ping_agent(n, i) for n, i in grunt_agents.items()]
    results = await asyncio.gather(*tasks)
    metrics["performance"] = dict(zip(grunt_agents.keys(), results))

    grunt_response = max(r.get("response_time_s", 0) for r in results)

    context = {"mrr": mrr, "daily_cost": daily_cost, "grunt_response": grunt_response}
    for rule in ROUTING_RULES:
        try:
            if eval(rule["condition"], {}, context):
                await apply_routing_rule(rule, context)
                metrics["decisions"].append(rule["reason"])
        except:
            pass

    try:
        perf_col.add(
            ids=[f"perf-{now.strftime('%Y%m%d%H%M%S')}"],
            documents=[json.dumps(metrics)],
            metadatas={
                "mrr": float(mrr),
                "daily_cost": float(daily_cost),
                "grunt_response": float(grunt_response),
                "timestamp": now.isoformat()
            }
        )
    except Exception as e:
        print(f"ChromaDB write warning: {e}")

    report = f"""📊 SYSTEM REPORT {datetime.now().strftime('%d %b %H:%M')}

💰 FINANCIAL
MRR: NZD {mrr:.0f}
Daily API cost: USD ${daily_cost:.4f}
Projected monthly: USD ${daily_cost*30:.2f}

⚡ PERFORMANCE
Grunt layer response: {grunt_response:.1f}s
CPU: {metrics['system']['cpu']}%
Memory: {metrics['system']['mem_pct']}%
Load: {' '.join(metrics['system']['load'])}

🔄 AUTO-DECISIONS
{chr(10).join(f'→ {d}' for d in metrics['decisions']) if metrics['decisions'] else '→ No changes required'}"""

    print(report)

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            await client.post(
                f"{OPENFANG_API}/agents/{ORCHESTRATOR_ID}/message",
                json={"message": report}
            )
    except Exception as e:
        print(f"Orchestrator notify warning: {e}")

    return metrics

if __name__ == "__main__":
    asyncio.run(run_cfo_monitor())
