# LinkedIn Post — I Tested My AST Parser Against Graphify. Here's What Actually Happened.

This is a companion to my [GraphRAG post](linkedin-post-graphrag.md) — the build-vs-buy detail on graph extraction.

I needed a code knowledge graph for retrieval. Built my own Python AST parser over ~2 days, loaded everything into Neo4j. Then I found [Graphify](https://github.com/Graphify-Labs/graphify), an open-source tree-sitter tool that does the same thing but supports ~40 languages out of the box. Natural question: should I have just used Graphify?

I ran both on httpx:

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

Graphify found 2.7x more edges. So I plugged it into my retrieval eval to see if more edges = better recall.

**The caveat:** my retrieval pipeline (ChromaDB + Neo4j) was built around my parser's node schema. Both parsers extract methods, but with different naming — mine stores `BasicAuth.__init__`, Graphify stores `.__init__()`. My first attempt only mapped 9% of edges, which wasn't a fair test. After fixing the name matching (using Graphify's containment tree to resolve class context), I got to 89% match rate — 1,057 of 3,613 edges connected.

Results (28 queries against httpx):

| | Custom AST | Graphify |
|---|---|---|
| **Total recall** | **54.2%** | 46.4% |
| **Queries won** | **9** | 5 |

Closer than I expected. Graphify won big on redirect handling (+80%) and async client queries (+40%). My parser won on URL parsing, utility functions, and status codes.

**What I can say:**
- My parser still wins overall, but the gap is smaller than I initially thought (8pp, not 18pp)
- Graphify's finer-grained edges (`references`, `indirect_call`) do help on some query types
- The remaining 11% of unmapped edges could close the gap further — pipeline fit still matters

**What I can't say:**
- That my parser produces a definitively "better" graph than Graphify
- With a pipeline designed around Graphify's granularity from the start, results could be different

**What I liked about Graphify:**
- Fast to set up — `pip install`, one command, graph with community detection and visualization
- Leiden community detection is useful for spotting subsystems in unfamiliar codebases
- ~40 languages out of the box, incremental updates, non-code source support

**Where I hit friction:**
- I needed stable global IDs so cross-repo LLM edges could reference nodes deterministically — Graphify auto-generates IDs with no way to plug in your own scheme
- I needed Neo4j as a queryable backend for graph traversal during retrieval, not just a visualization
- These are specific to building a retrieval pipeline, not general complaints about the tool

**My take:** if you're exploring a codebase or building a single-repo prototype, start with Graphify. If you're building a multi-repo retrieval pipeline where you need to control the identity layer and query the graph programmatically, you'll probably end up writing your own parser. I don't regret building mine, but I also wouldn't build one if Graphify covered my requirements.

Code: https://github.com/onion2005/graphrag

---

#GraphRAG #RAG #KnowledgeGraph #CodeSearch #TreeSitter #Graphify #AIEngineering #GenAI
