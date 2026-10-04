# LinkedIn Post — GraphRAG: When Vector Search Isn't Enough

Vector search on code has a blind spot. It finds what's similar, not what's connected.

I asked "how does httpx handle authentication?" and vector search returned `BasicAuth`, `DigestAuth`, `NetRCAuth`. But it missed `Client._build_auth()` that wires them into the request lifecycle — that lives in `_client.py`, not `_auth.py`. Embeddings work on text proximity. The AST knows they're connected through call graphs.

So I built a GraphRAG system: vector search finds entry points, then graph expansion walks AST edges (CALL, IMPORT, INHERIT) to pull in related symbols the embeddings missed. Tested it on 3 Python repos (httpx, requests, urllib3), 2,080 nodes, 28 queries.

![Evaluation Summary](../eval/eval_summary.png)

What I found:

1. **Graph more than doubled recall (22.9% → 54.2%), but doesn't help ranking.** Graph-discovered symbols always rank below vector hits. `_build_auth()` is structurally important but doesn't score high against "how does authentication work?" You can't just boost graph scores — that pushes irrelevant neighbors up. You need a re-ranker or agent downstream that can work with 20-30 candidates instead of 10.

2. **Within a single repo, LLM-extracted edges are a waste.** 500 LLM calls, 478 edges, zero recall improvement. The AST parser — seconds to run, zero cost — already had all the signal.

3. **Across repos, LLM edges are the only option.** AST can't cross repo boundaries. I used embedding similarity to prune 4.3M possible pairs down to 500, then had Claude Haiku validate each. 538 cross-repo edges, +3.4pp recall.

4. **I benchmarked against Graphify (open-source, tree-sitter).** With fair node mapping (89% match rate), my parser still won: 54.2% vs 46.4%. But Graphify won 5 of 28 queries. Details in a [separate post](linkedin-post-graphify.md).

My take: AST graph per repo (cheap, deterministic), LLM edges across repos (embedding-pruned), vector search as entry point, re-ranker downstream. Full methodology and eval results in the repo.

Stack: Python, Neo4j, ChromaDB, LangGraph, BGE embeddings, Claude Haiku.
Code: https://github.com/onion2005/graphrag

---

#GraphRAG #RAG #KnowledgeGraph #Neo4j #CodeSearch #AIEngineering #GenAI
