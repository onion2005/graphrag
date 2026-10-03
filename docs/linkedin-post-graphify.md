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

**The caveat:** my retrieval pipeline (ChromaDB + Neo4j) was built around my parser's node schema. Both parsers extract methods, but with different naming — mine stores `BasicAuth.__init__`, Graphify stores `.__init__()`. The ID mapping only connected 333 of Graphify's 3,613 edges (9%). So this measures pipeline fit, not graph quality in the abstract.

Results (28 queries against httpx):

| | Custom AST | Graphify |
|---|---|---|
| **Total recall** | **53.5%** | 35.2% |
| **Queries won** | **13** | 2 |

**What I can say:**
- If you build a retrieval pipeline around a specific node schema, swapping in a different parser's graph without adapting the pipeline doesn't work well
- The 91% of unmapped edges aren't "wrong" — they just don't connect to anything in my vector store
- Pipeline fit matters as much as graph quality

**What I can't say:**
- That my parser produces a "better" graph than Graphify
- With a pipeline designed around Graphify's granularity and naming, results could be different — I didn't test that

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
