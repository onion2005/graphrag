# LinkedIn Post — GraphRAG: When Vector Search Isn't Enough

Vector search on code has a blind spot. It finds what's similar, not what's connected.

I asked "how does httpx handle authentication?" and vector search returned `BasicAuth`, `DigestAuth`, `NetRCAuth` — all semantically similar to my query. But it missed `Client._build_auth()` that wires them into the request lifecycle, and the `_auth_flow` generator that orchestrates the challenge-response cycle. These symbols don't appear in the same chunks as the auth classes — they live in `_client.py`, not `_auth.py`. Embeddings work on text proximity. The AST knows they're connected through call graphs.

Miss that wiring, and your AI coding assistant generates code that calls `BasicAuth` directly but bypasses the auth flow. That's not a search quality problem — it's a correctness problem.

So I built a GraphRAG system. The idea is simple: code already has a graph — the AST. Classes, functions, methods are nodes. CALL, IMPORT, INHERIT are edges. Vector search finds entry points, then graph expansion walks those edges to pull in related symbols the embeddings missed.

![Neo4j Knowledge Graph — 2,080 nodes, 2,940 relationships across httpx, requests, urllib3](../docs/neo4j-graph.png)

Here's what I found, and what surprised me:

![Evaluation Summary](../eval/eval_summary.png)

**Experiment 1: single-repo (httpx, 28 queries)**

1. **Graph is a recall expander, not a ranker.** Graph expansion more than doubled total recall (22.9% to 53.5% across all returned results). But it didn't improve Recall@10 or NDCG@10 at all. Graph-discovered symbols always rank below the original vector hits. Why? It's not a tuning problem. Graph finds symbols that are structurally important but semantically distant from the query — `_build_auth()` doesn't score high against "how does authentication work?" even though it's the method that wires auth in. You could boost graph scores, but then you'd push irrelevant neighbors above relevant vector hits. The real fix is downstream: a re-ranker or agent that can work with 20-30 candidates instead of 10. That's where graph becomes a 2.3x total recall multiplier.

2. **LLM-extracted edges added zero recall within a single repo.** 500 LLM calls, 478 SIMILAR_TO/DEPENDS_ON edges, no improvement. The AST parser — seconds to run, zero cost — already had all the signal. CALLS and INHERITS encode the architecture. LLM edges just rediscovered what the import graph already knew.

3. **More edges ≠ better retrieval.** Separately, I benchmarked my parser against [Graphify](https://github.com/Graphify-Labs/graphify), an open-source tree-sitter tool. Graphify found 2.7x more edges but scored lower on total recall (35.2% vs 53.5%). Different reason from point 2 though — Graphify extracts methods as separate nodes while my parser doesn't, so only 333 of its 3,613 edges mapped to my node schema. It's a pipeline integration comparison, not a pure graph quality one. Details [here](linkedin-post-graphify.md).

**Experiment 2: cross-repo (httpx + requests + urllib3, 12 queries)**

4. **AST breaks down across repo boundaries — and that's where LLM edges actually help.** There's no IMPORT edge from `httpx.BasicAuth` to `requests.HTTPBasicAuth`. So I ran a separate experiment: 3 repos, 2,080 nodes total (same graph as the Neo4j screenshot above). The problem is pair selection — 2,080 nodes means 4.3M possible pairs, and you can't LLM-call all of them. I embedded everything, computed cosine similarity across repos only, took the top 500 pairs, and had Claude Haiku validate each one. 500 calls instead of 4.3M. Got 538 cross-repo edges.

Result: AST alone gave 45.4% total recall on the cross-repo queries. Adding LLM edges pushed it to 48.8%. The +3.4pp came from things like `urllib3/GzipDecoder` → `httpx/GZipDecoder` and `urllib3/encode_multipart_formdata` → `httpx/MultipartStream`. Symbols that are structurally invisible but doing the same thing.

So where does this leave things? After running all these experiments, my take is:

- **Within a repo:** just use AST. It's free, fast, and got better recall than 500 LLM calls. Don't overthink it.
- **Across repos:** LLM is the only option since AST stops at the repo boundary. The embed-then-validate approach keeps costs sane.
- **Across languages:** I only tested Python, but I'd expect AST to get painful at scale. Per-language parsers at 10,000 repos in 15 languages is a maintenance problem. LLM extraction doesn't care what language it's reading — though I haven't validated that yet.
- **Build vs buy:** off-the-shelf tools like Graphify get you up fast (~40 languages, community detection, visualization). But if you need stable node IDs across repos or a queryable graph backend, you'll end up owning the parser.

If I were building this for production: AST graph per repo (batch job, cheap), cross-repo LLM edges on a schedule (embedding-pruned, incremental), vector search as the entry point, re-ranker downstream.

Stack: Python, Neo4j, ChromaDB, LangGraph agent, BGE embeddings, Claude Haiku. Code: https://github.com/onion2005/graphrag

---

#GraphRAG #RAG #KnowledgeGraph #Neo4j #CodeSearch #InformationRetrieval #AIEngineering #GenAI
