import chromadb
from datetime import datetime

client = chromadb.HttpClient(host="localhost", port=8000)

# Collections
company = client.get_or_create_collection("company_context")
intelligence = client.get_or_create_collection("intelligence_feed")
performance = client.get_or_create_collection("performance_metrics")
grants = client.get_or_create_collection("grant_tracking")
clients = client.get_or_create_collection("client_pipeline")

# Seed company context
company.add(
    ids=["aw-001", "aw-002", "aw-003", "aw-004", "aw-005", "aw-006"],
    documents=[
        """Adventure Waggle Limited — NZ AI holding company. Founder: Derek Winer. 
        Server: Hetzner 176.9.19.86, i7-8700, 64GB RAM, no GPU. 
        Primary revenue: Waggle Logic NZD 400/800/1600 tiers.
        Email: connect@wagglelogic.com. Telegram: primary founder channel.""",

        """Waggle Logic — autonomous agent agency for NZ SMEs. 
        Signal NZD400: 3 agents (sales, researcher, social).
        Logic NZD800: 6 agents (add coder, analyst, planner).
        Department NZD1600: full stack all agents.
        Target: NZ SMEs 2-20 staff. Professional services, trades, retail.""",

        """Agent Stack — Three tier architecture:
        Tier 1 INTERFACE: orchestrator (Kimi K2), planner (Kimi K2).
        Tier 2 EXECUTION: researcher (Nemotron Super 1M context), 
        analyst (MiniMax M2.5), sales (MiniMax M2.5).
        Tier 3 GRUNT: customer-support, social-media, assistant, 
        legal-assistant, devops-lead (all qwen2.5:7b local free).""",

        """Ventures portfolio:
        1. Waggle Logic — live, revenue focus NOW
        2. Kora — AI media platform, Clip Hand operational
        3. Ledger Learn — NZ school crypto curriculum, research phase
        4. Alvearium — open source agent kernel, MIT license
        5. Synara OS — blockchain intelligence layer, 2026-2027
        6. Commodity Intelligence — signal intelligence, 2027+""",

        """NZ Government incentives — URGENT:
        IRD reclassification PENDING (still listed as florist).
        RDTI: 15% tax credit on eligible R&D spend.
        Callaghan Innovation: 40% co-funding up to NZD400k.
        Combined potential: 43% return on R&D.
        Track all R&D expenditure from incorporation date.""",

        """Infrastructure services running:
        nginx (443/80), OpenFang (4200), Ollama (11434),
        n8n (5678), PostgreSQL (5432), Redis (6379),
        ChromaDB (8000), FastAPI webhooks (8080),
        PinchTab browser (9867), waggle-webhooks systemd service.
        Cloudflare: DNS, CDN, Email Routing, WAF, Email Workers."""
    ],
    metadatas=[
        {"category": "company", "priority": "critical"},
        {"category": "product", "priority": "critical"},
        {"category": "infrastructure", "priority": "high"},
        {"category": "ventures", "priority": "high"},
        {"category": "compliance", "priority": "critical"},
        {"category": "infrastructure", "priority": "high"}
    ]
)

# Seed intelligence sources
intelligence.add(
    ids=["src-001", "src-002", "src-003", "src-004", 
         "src-005", "src-006", "src-007", "src-008", "src-009"],
    documents=[
        "arXiv AI — daily papers on agents, LLMs, reasoning, MoE architectures",
        "Hugging Face — new model releases, benchmarks, open weights",
        "GitHub trending — AI/agent repos, new tools, frameworks",
        "Reddit r/LocalLLaMA r/MachineLearning — community discoveries",
        "Substack — Karpathy, Lilian Weng, The Batch, Import AI newsletters",
        "Discord — OpenFang, LangChain, Ollama, OpenRouter servers",
        "Twitter/X — @karpathy @sama @ylecun @scaling_llm @OpenRouter",
        "ProductHunt — new AI tools, agent frameworks, automation tools",
        "Cloudflare Blog — infrastructure innovation, Workers AI, edge computing"
    ],
    metadatas=[
        {"type": "source", "frequency": "daily"},
        {"type": "source", "frequency": "daily"},
        {"type": "source", "frequency": "daily"},
        {"type": "source", "frequency": "daily"},
        {"type": "source", "frequency": "weekly"},
        {"type": "source", "frequency": "daily"},
        {"type": "source", "frequency": "daily"},
        {"type": "source", "frequency": "daily"},
        {"type": "source", "frequency": "daily"}
    ]
)

print(f"✓ company_context: {company.count()} documents")
print(f"✓ intelligence_feed: {intelligence.count()} documents")
print(f"✓ performance_metrics: {performance.count()} documents")
print(f"✓ grant_tracking: {grants.count()} documents")
print(f"✓ client_pipeline: {clients.count()} documents")
print(f"\nChromaDB seeded at {datetime.utcnow().isoformat()}")
