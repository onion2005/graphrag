# LinkedIn Post — GraphRAG: When Vector Search Isn't Enough

Vector search on code has a blind spot. It finds what's similar, not what's connected.

The failure mode is subtle. You ask "how does httpx handle authentication?" Vector search returns `BasicAuth`, `DigestAuth`, `NetRCAuth` — semantically similar to your query. Looks good. But it completely misses the `Auth` base class they inherit from, the `Client._build_auth()` that wires them in, and the `_auth_flow` generator that orchestrates the challenge-response cycle. Those are structurally connected, not semantically similar. Embeddings can't see inheritance hierarchies or call graphs.

**The fix: use the structure that's already there.**

Code isn't a document. It has a formal, parseable structure — an AST. Every class, function, and method is a node. Every CALL, IMPORT, INHERIT is an edge. This graph already exists in the source code. You just have to extract it.

So I built a GraphRAG system: vector search finds the entry points, then graph expansion walks structural edges to pull in related symbols the embeddings missed. Hop-decay scoring (0.8 per hop) keeps distant neighbors from diluting relevance.

![Recall Comparison: Vector vs Hybrid](../eval/recall_comparison.png)

**The results that changed my assumptions:**

AST graph expansion **more than doubled total recall** — from 25.6% to 59.9%. But it didn't improve top-k ranking. Recall@5, Recall@10, NDCG@10 were identical with or without the graph. Here's what that means:

1. **Graph is a pure recall expander, not a ranker.** It finds relevant symbols that embeddings miss entirely — but those symbols rank below the vector hits. The graph fills in the long tail, not the top of the list. This matters: if your application only looks at top-10 results, graph adds nothing. If it can use 20-30 results (like an agent with tool calls), graph is a 2.6x recall win.

2. **LLM-extracted edges added zero value within a single repo.** I spent 500 LLM calls extracting SIMILAR_TO / DEPENDS_ON relationships (478 edges). Total recall didn't budge — still 25.6%. AST edges alone got +34pp. The parser gives you the graph for free.

3. **Graph without vector is useless.** Pure graph traversal without good seed nodes returns noise. The vector search IS the entry point — you need both, but in a specific order.

4. **The real win is cross-file discovery.** Authentication in httpx spans `_auth.py`, `_client.py`, and `_config.py`. Vector search finds one file. The graph finds all three. This is the problem GraphRAG actually solves for code: following dependencies across file boundaries.

![Ranking Quality by Retrieval Mode](../eval/ranking_quality.png)

![Recall by Category](../eval/recall_by_category.png)

**But wait — what about multiple repos?**

AST edges can't cross repo boundaries. There's no IMPORT edge from `httpx.BasicAuth` to `requests.HTTPBasicAuth` — they're independent codebases. So I ran a second experiment: 3 repos (httpx, requests, urllib3), 2,080 nodes, 12 cross-repo queries.

I used Claude Haiku to extract 538 semantic edges across repo boundaries — SIMILAR_TO, ALTERNATIVE_TO, IMPLEMENTS_SAME_INTERFACE. Things like "httpx's GZipDecoder is equivalent to urllib3's GzipDecoder."

| Mode | Total Recall |
|------|-------------|
| Vector only | 23.3% |
| Vector + AST | 45.4% |
| Vector + cross-repo LLM | 31.4% |
| **Vector + AST + cross-repo LLM** | **48.7%** |

Cross-repo LLM edges found 3 symbols that AST couldn't reach — `urllib3/GzipDecoder`, `requests/request`, `urllib3/encode_multipart_formdata` — connected by semantic similarity, not imports.

**The nuanced conclusion:**

Within a single repo, the AST graph is free and does all the work. LLM edges add noise. But across repos at scale? AST can't see cross-boundary relationships. LLM edges fill exactly that gap — +3.3pp recall on top of AST, finding symbols that are structurally invisible but semantically related.

The real question for production: who writes AST rules for 10,000 repos in different languages? LLM extraction scales where hand-written parsers don't.

Stack: Python, Neo4j, ChromaDB, LangGraph agent, BGE embeddings, Claude Haiku. Code on GitHub.

---

#GraphRAG #RAG #KnowledgeGraph #Neo4j #CodeSearch #InformationRetrieval #AIEngineering #GenAI #NLP
