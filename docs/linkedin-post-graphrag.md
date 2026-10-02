# LinkedIn Post — GraphRAG: When Vector Search Isn't Enough

Vector search on code has a blind spot. It finds what's similar, not what's connected.

You ask "how does httpx handle authentication?" Vector search returns `BasicAuth`, `DigestAuth`, `NetRCAuth` — semantically similar to your query. But it completely misses the `Auth` base class they inherit from, the `Client._build_auth()` that wires them in, and the `_auth_flow` generator that orchestrates the challenge-response cycle. Those are structurally connected, not semantically similar.

When an AI coding assistant misses the base class, it generates code that bypasses the auth flow. That's not a search quality problem — it's a correctness problem. At scale, this means more hallucinated code, more review cycles, more incidents from generated code that looks right but ignores the architecture.

**The insight: code already has the graph. You just have to use it.**

Code has a formal, parseable structure — an AST. Every class, function, and method is a node. Every CALL, IMPORT, INHERIT is an edge. I built a GraphRAG system: vector search finds entry points, then graph expansion walks structural edges to pull in related symbols the embeddings missed.

![Neo4j Knowledge Graph — 2,080 nodes, 2,940 relationships across httpx, requests, urllib3](../docs/neo4j-graph.png)

**What the data actually says — and what it doesn't:**

![Evaluation Summary](../eval/eval_summary.png)

AST graph expansion more than doubled total recall (25.6% to 59.9%). But it didn't improve Recall@10 or NDCG@10 at all. This is the critical nuance that changes how you architect the system:

**1. Graph is a recall expander, not a ranker.** Graph-discovered symbols rank below vector hits. If your application only consumes top-10 results, graph adds nothing. If it can use 20-30 results — an agent with tool calls, a context window that tolerates more code — graph is a 2.3x recall multiplier. The architectural implication: graph expansion only pays off downstream of an agent or re-ranker that can handle a larger candidate set.

**2. The build-vs-buy decision for graph extraction is unintuitive.** I spent 500 LLM calls extracting SIMILAR_TO / DEPENDS_ON edges within a single repo (478 edges). Zero recall improvement. The AST parser — which runs in seconds, costs nothing, and requires no prompt engineering — produced all the signal. **Within a single codebase, structural relationships dominate semantic ones.** CALLS and INHERITS edges encode architecture. LLM-inferred edges just rediscover what the import graph already knows.

You also have a choice in how you build the AST graph. Tools like [Graphify](https://github.com/Graphify-Labs/graphify) give you tree-sitter parsing across 40 languages out of the box — zero custom code, community detection, visualization included. But you trade control: I needed stable global IDs across repos so cross-repo LLM edges could reference nodes deterministically. With a hand-rolled parser, I control the ID scheme, the edge types, the Neo4j schema. With an off-the-shelf tool, you get speed but lose that flexibility. The principal's calculus: if you're building a one-repo prototype, use Graphify. If you're designing a multi-repo retrieval system where node identity matters across pipelines, you'll end up owning the parser anyway.

**3. But this breaks down across repo boundaries.**

AST edges can't cross repos. There's no IMPORT from `httpx.BasicAuth` to `requests.HTTPBasicAuth`. So I ran a second experiment: 3 repos (httpx, requests, urllib3), 2,080 nodes, 12 cross-repo queries.

The hard part is pair selection. 2,080 nodes means 4.3M possible pairs. Brute-forcing LLM calls is economically insane. Instead: embed all symbols, compute cosine similarity across repos only (skip same-repo), take the top 500 pairs, LLM-validate each. 500 calls, not 4.3M. Result: 538 cross-repo edges.

AST alone: 45.4% total recall. AST + cross-repo LLM: 48.8%. The +3.4pp came from symbols that are structurally invisible but semantically equivalent — `urllib3/GzipDecoder` connected to `httpx/GZipDecoder`, `urllib3/encode_multipart_formdata` linked to `httpx/MultipartStream`.

**What this means for production systems:**

The real question isn't "AST vs LLM." It's about where each extraction method has an information advantage:

- **Within a repo:** AST wins. It's free, fast, complete, and deterministic. LLM edges are expensive noise. Don't use them.
- **Across repos:** LLM is the only option. AST has zero cross-repo signal. The embedding-pruned approach (embed → rank → validate) makes the cost tractable.
- **Across languages:** AST parsers need per-language rules. At 10,000 repos in 15 languages, that's a maintenance nightmare. LLM extraction is language-agnostic. This is where the cost curve flips.

The uncomfortable truth for the "just use LLM for everything" crowd: within a single repo, a `tree-sitter` parse gives you a better knowledge graph in 2 seconds than 500 LLM calls costing $2. But the "just use AST" crowd hits a wall at org-wide code search, where the relationships that matter most — shared interfaces, alternative implementations, dependency patterns — exist only in developers' heads.

**If I were building this for production**, the architecture would be: AST graph per repo (batch, cheap, deterministic), cross-repo LLM edges on a schedule (embedding-pruned, incremental), vector search as the entry point, and a re-ranker downstream to handle the larger candidate set from graph expansion.

Stack: Python, Neo4j, ChromaDB, LangGraph agent, BGE embeddings, Claude Haiku. Code: https://github.com/onion2005/graphrag

---

#GraphRAG #RAG #KnowledgeGraph #Neo4j #CodeSearch #InformationRetrieval #AIEngineering #GenAI
