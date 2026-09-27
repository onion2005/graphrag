# GraphRAG POC — Code Retrieval with Knowledge Graphs

A proof-of-concept AI platform that combines vector search with graph-based code retrieval, served via a self-hosted LLM on EKS.

## What This Does

Traditional RAG retrieves code by semantic similarity — but misses structural relationships like inheritance, function calls, and cross-file dependencies. This project builds a **GraphRAG** system that:

1. **Parses** a Python codebase (httpx) into an AST-based knowledge graph (Neo4j)
2. **Embeds** code symbols into a vector store (ChromaDB + BGE embeddings)
3. **Retrieves** using hybrid search: vector finds entry points, graph expansion walks structural edges (CALLS, INHERITS, IMPORTS) to discover related symbols
4. **Reasons** via a LangGraph agent with tool-calling capabilities

## Architecture

```
                    ┌─────────────────────────────────────────┐
                    │            EKS Cluster                  │
 Locust/Client      │  ┌───────────────────────────────────┐  │
     │              │  │   GPU Node (g5.xlarge, 1x A10G)   │  │
     ▼              │  │                                   │  │
 kubectl            │  │   vLLM v0.8.4                     │  │
 port-forward ──────┤  │     │                             │  │
                    │  │     ▼                             │  │
                    │  │   Qwen 2.5 7B Instruct            │  │
                    │  └───────────────────────────────────┘  │
                    │         ▲ Karpenter (spot autoscaling)  │
                    └─────────────────────────────────────────┘
```

## Knowledge Graph

![Neo4j Graph — 2,080 nodes, 2,940 relationships across httpx, requests, urllib3](docs/neo4j-graph.png)

## Key Results

### Single-Repo GraphRAG (httpx)

- AST graph expansion **more than doubles total recall** (27.4% → 70.3%) — finds symbols embeddings miss entirely
- Graph is a **pure recall expander**: top-k ranking (Recall@10, NDCG@10) is identical with or without graph — graph nodes rank below vector hits
- Within-repo LLM edges (478 SIMILAR_TO/DEPENDS_ON) added only **+1.3pp recall** — AST parser edges did all the work
- Graph without vector entry points is useless — you need both, in sequence

### Cross-Repo GraphRAG (httpx + requests + urllib3)

- **LLM edges add unique value across repo boundaries** — where AST edges can't reach
- 538 cross-repo LLM edges extracted via Claude Haiku across 3 repos (2,080 nodes)
- AST alone: 45.4% total recall → AST + cross-repo LLM: **48.7%** (+3.3pp)
- LLM edges found symbols AST couldn't: `urllib3/GzipDecoder`, `requests/request`, `urllib3/encode_multipart_formdata` — connected by semantic similarity, not imports
- **Conclusion:** within a single repo, AST is king. Across repos at scale, LLM edges fill the gap AST can't cover

### Self-Hosted LLM Load Test

Tested with Locust against Qwen 2.5 7B on vLLM (g5.xlarge):

| Workload | P50 | P95 |
|---|---|---|
| Tool call | 1.6s | 2.3s |
| JSON extraction | 2.5s | 8.0s |
| Simple QA | 6.4s | 6.8s |
| RAG (long context) | 21s | 21s |
| Agent multi-turn | 25s | 32s |

**Cost:** $724/mo on-demand, $252/mo spot — beats Claude Haiku API above ~7K daily requests (spot).

## Project Structure

```
├── agent/              # LangGraph agent with tool-calling
├── ingestion/          # AST parser, embedder, Neo4j loader, LLM extractor
├── retrieval/          # Hybrid search (vector + graph), Cypher templates
├── eval/               # Golden datasets (single + cross-repo), metrics (NDCG, MRR, P@K)
├── loadtest/           # Locust load tests, cost analysis, reports
├── infra/
│   ├── eks/            # EKS cluster config (eksctl)
│   ├── karpenter/      # GPU NodePool + EC2NodeClass
│   └── k8s/            # vLLM deployment, service, secrets
└── docs/               # LinkedIn posts
```

## Stack

- **LLM Serving:** vLLM on EKS with Karpenter GPU autoscaling (spot instances)
- **Model:** Qwen 2.5 7B Instruct (Hermes tool-call format)
- **Graph DB:** Neo4j (AST-based code knowledge graph)
- **Vector DB:** ChromaDB with BGE-small-en-v1.5 embeddings
- **Agent:** LangGraph with OpenAI-compatible tool calling
- **Load Testing:** Locust with 5 realistic workload categories
- **Infra:** EKS, Karpenter, kubectl port-forward

## Setup

```bash
# Install dependencies
pip install -r requirements.txt  # or: pip install openai langchain-openai chromadb neo4j

# Set environment variables
export NEO4J_PASSWORD=your_password
export LLM_BASE_URL=http://localhost:8000/v1
export LLM_API_KEY=your_key

# Run the agent
python -m agent.run "How does httpx handle authentication?"
```

## Related Posts

- [Self-Hosted LLM on EKS — Cost & Latency Analysis](docs/linkedin-post-vllm-eks.md)
- [GraphRAG: When Vector Search Isn't Enough](docs/linkedin-post-graphrag.md)
