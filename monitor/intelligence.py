import httpx, json, asyncio, chromadb
from datetime import datetime
import subprocess

OPENFANG_API = "http://127.0.0.1:4200/api"
RESEARCHER_ID = "c0265b59-6868-4fc5-93f1-319585d0aa9e"
ORCHESTRATOR_ID = "5369a40d-4ca0-4deb-8d1d-2976b61cd6d8"
ANALYST_ID = "4460936b-286b-4ba0-a184-5aee215cac28"
SALES_ID = "8e453b66-c00a-442c-9410-5416022b769f"

chroma = chromadb.HttpClient(host="localhost", port=8000)
intel_col = chroma.get_or_create_collection("intelligence_feed")
perf_col = chroma.get_or_create_collection("performance_metrics")

SOURCES = [
    {"name": "arxiv_ai", "url": "https://arxiv.org/list/cs.AI/recent", "type": "research"},
    {"name": "arxiv_lg", "url": "https://arxiv.org/list/cs.LG/recent", "type": "research"},
    {"name": "hf_models", "url": "https://huggingface.co/models?sort=trending", "type": "models"},
    {"name": "github_trending", "url": "https://github.com/trending?since=daily&spoken_language_code=en", "type": "tools"},
    {"name": "openrouter_models", "url": "https://openrouter.ai/api/v1/models", "type": "models"},
    {"name": "cloudflare_blog", "url": "https://blog.cloudflare.com/tag/workers-ai/", "type": "infrastructure"},
    {"name": "producthunt", "url": "https://www.producthunt.com/topics/artificial-intelligence", "type": "tools"},
]

async def scrape_source(source: dict) -> str:
    """Use PinchTab to scrape a source."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # Navigate
            nav = await client.post(
                "http://localhost:9867/instances",
                json={"profile": f"intel-{source['name']}"}
            )
            instance_id = nav.json().get("id")

            await client.post(
                f"http://localhost:9867/instances/{instance_id}/navigate",
                json={"url": source["url"]}
            )

            # Extract text
            text_r = await client.get(
                f"http://localhost:9867/instances/{instance_id}/text"
            )
            return text_r.text[:3000]
    except Exception as e:
        return f"Scrape error: {e}"

async def analyse_discovery(content: str, source_name: str) -> dict:
    """Nemotron analyses content for relevance to Adventure Waggle stack."""
    prompt = f"""You are the Intelligence Analyst for Adventure Waggle Limited, an NZ AI company.

Source: {source_name}
Content: {content[:2000]}

Analyse this for relevance to our stack:
- Agent orchestration (OpenFang)
- LLM models and routing (Kimi K2, Nemotron, MiniMax, qwen)
- Browser automation (PinchTab)
- NZ SME automation (Waggle Logic clients)
- Cost optimisation
- Open source tools we could integrate

Respond in JSON only:
{{
  "relevance_score": 1-10,
  "summary": "one sentence",
  "opportunity": "specific action we should take",
  "routes_to": "cto|cfo|cmo|archive",
  "priority": "immediate|weekly|archive",
  "tags": ["tag1", "tag2"]
}}"""

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{OPENFANG_API}/agents/{RESEARCHER_ID}/message",
            json={"message": prompt}
        )
        try:
            text = r.json().get("response", "{}")
            # Extract JSON from response
            start = text.find("{")
            end = text.rfind("}") + 1
            return json.loads(text[start:end])
        except:
            return {"relevance_score": 0, "routes_to": "archive", "priority": "archive"}

async def route_discovery(discovery: dict, source: dict, analysis: dict):
    """Route high-value discoveries to correct agent."""
    if analysis.get("relevance_score", 0) < 5:
        return

    # Store in ChromaDB
    doc_id = f"{source['name']}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    intel_col.add(
        ids=[doc_id],
        documents=[f"{analysis.get('summary', '')} — {analysis.get('opportunity', '')}"],
        metadatas={
            "source": source["name"],
            "score": analysis.get("relevance_score", 0),
            "priority": analysis.get("priority", "archive"),
            "routes_to": analysis.get("routes_to", "archive"),
            "timestamp": datetime.utcnow().isoformat()
        }
    )

    score = analysis.get("relevance_score", 0)
    if score < 7:
        return  # Archive only, no agent notification

    # Route to correct agent
    routes = {
        "cto": ORCHESTRATOR_ID,  # orchestrator delegates to devops
        "cfo": ANALYST_ID,
        "cmo": SALES_ID,
    }

    route = analysis.get("routes_to", "archive")
    agent_id = routes.get(route, ORCHESTRATOR_ID)

    message = f"""INTELLIGENCE FEED — Score {score}/10
Source: {source['name']}
Summary: {analysis.get('summary')}
Opportunity: {analysis.get('opportunity')}
Priority: {analysis.get('priority')}
Action required: Evaluate and implement if viable."""

    async with httpx.AsyncClient(timeout=30) as client:
        await client.post(
            f"{OPENFANG_API}/agents/{agent_id}/message",
            json={"message": message}
        )

async def generate_daily_digest():
    """Compile daily digest for Derek via orchestrator."""
    # Query ChromaDB for today's high-value discoveries
    results = intel_col.query(
        query_texts=["high priority AI agent tools and models"],
        n_results=10,
        where={"score": {"$gte": 7}}
    )

    discoveries = results.get("documents", [[]])[0]
    if not discoveries:
        return

    digest_prompt = f"""Generate Derek's daily intelligence digest.

Today's high-value discoveries:
{chr(10).join(f'- {d}' for d in discoveries[:5])}

Format as:
🔍 INTELLIGENCE DIGEST — {datetime.now().strftime('%d %b %Y')}

TOP DISCOVERIES (scored 7+/10):
[list them]

RECOMMENDED ACTIONS:
[specific next steps]

STACK IMPACT:
[how this affects Adventure Waggle]"""

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{OPENFANG_API}/agents/{ORCHESTRATOR_ID}/message",
            json={"message": digest_prompt}
        )
        digest = r.json().get("response", "")
        print(f"\n{'='*50}\n{digest}\n{'='*50}")

async def run_intelligence_cycle():
    """Full intelligence collection cycle."""
    print(f"Intelligence cycle starting: {datetime.utcnow().isoformat()}")
    
    high_value = 0
    for source in SOURCES:
        print(f"Scraping {source['name']}...")
        content = await scrape_source(source)
        analysis = await analyse_discovery(content, source["name"])
        await route_discovery(content, source, analysis)
        
        score = analysis.get("relevance_score", 0)
        print(f"  Score: {score}/10 — {analysis.get('summary', 'no summary')[:80]}")
        if score >= 7:
            high_value += 1
        
        await asyncio.sleep(2)  # Rate limit

    print(f"\nCycle complete. {high_value} high-value discoveries.")
    await generate_daily_digest()

if __name__ == "__main__":
    asyncio.run(run_intelligence_cycle())
