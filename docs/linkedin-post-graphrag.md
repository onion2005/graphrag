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

You also have a choice in *how* you build the AST graph. I compared my hand-rolled Python AST parser against [Graphify](https://github.com/Graphify-Labs/graphify), an open-source tool that uses tree-sitter for the same deterministic extraction. I ran both on httpx:

|  | Custom AST Parser | Graphify |
|---|---|---|
| **Nodes (httpx)** | 1,192 (code only) | 1,777 (incl. 799 test, 267 rationale, 62 concept) |
| **Edges (httpx)** | 1,328 | 3,613 |
| **Languages** | Python only | ~40 (tree-sitter grammars) |
| **Edge types** | CALLS, IMPORTS, INHERITS, USES_TYPE | calls, imports, inherits, references, uses, indirect_call, method, + 5 more |
| **Node identity** | Custom global IDs (hash-based, repo-scoped) | Auto-generated, no custom ID scheme |
| **Graph storage** | Neo4j (queryable, supports Cypher) | JSON + HTML viz (Neo4j export via Cypher dump) |
| **Schema control** | Full — custom properties, edge types, indexes | Fixed schema |
| **Community detection** | None | Leiden algorithm, auto-labels subsystems |
| **Visualization** | Neo4j Browser | Built-in interactive force-directed graph |
| **Incremental updates** | Full re-parse | `--update` rescans only changed files |
| **Non-code sources** | None | Docs, PDFs, images, SQL schemas |
| **Setup time** | ~2 days to build | `pip install graphifyy` |

Graphify finds 2.7x more edges — finer-grained types like `references`, `indirect_call`, `imports_from`. More edges should mean better recall, right? I tested it. Mapped Graphify's graph into my eval pipeline (333 edges that matched my node schema) and ran the same 28 queries:

| | Custom AST | Graphify |
|---|---|---|
| **Total recall** | **53.5%** | 35.2% |
| **Queries won** | **13** | 2 |

More edges ≠ better retrieval. The custom parser's `CONTAINS` edges (class→methods, module→functions) are the recall workhorse — they connect parent symbols to children, which is exactly what graph expansion needs. Graphify's finer-grained edges (`uses`, `references`) connect at the method level, but those methods aren't in the vector store as separate entry points, so graph expansion can't reach them.

The trade-off is control vs. speed-to-value. Graphify gives you 40 languages, community detection, incremental updates, and a visualization out of the box. But I needed stable global IDs across repos so cross-repo LLM edges could reference nodes deterministically, custom Neo4j indexes for graph traversal queries, and full control over edge types for the retrieval pipeline. With an off-the-shelf tool, you can't own the identity layer — and as the eval shows, graph structure choices directly impact recall.

The principal's calculus: if you're building a single-repo prototype or want fast architectural insight, use Graphify — it's genuinely good. If you're designing a multi-repo retrieval system where node identity matters across pipelines and you need the graph as a queryable backend (not just a visualization), you'll end up owning the parser anyway.

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
