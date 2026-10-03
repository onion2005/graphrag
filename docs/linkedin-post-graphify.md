# LinkedIn Post — Custom AST Parser vs Graphify: More Edges ≠ Better Retrieval

This is a companion to my [GraphRAG post](linkedin-post-graphrag.md) — the build-vs-buy deep dive on graph extraction.

I compared my hand-rolled Python AST parser against [Graphify](https://github.com/Graphify-Labs/graphify), an open-source tool that uses tree-sitter for deterministic code graph extraction. I ran both on httpx:

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

Graphify finds 2.7x more edges — finer-grained types like `references`, `indirect_call`, `imports_from`. More edges should mean better recall, right?

I tested it. Mapped Graphify's graph into my eval pipeline and ran the same 28 queries. Only 333 of Graphify's 3,613 edges mapped to my node schema — Graphify extracts methods as separate nodes while my parser doesn't — so this comparison reflects how each graph integrates into the same retrieval pipeline, not a pure graph-quality comparison.

| | Custom AST | Graphify |
|---|---|---|
| **Total recall** | **53.5%** | 35.2% |
| **Queries won** | **13** | 2 |

The custom parser's `CONTAINS` edges (class→methods, module→functions) are the recall workhorse — they connect parent symbols to children, which is exactly what graph expansion needs. Graphify's finer-grained edges (`uses`, `references`) connect at the method level, but those methods aren't in the vector store as separate entry points, so graph expansion can't reach them.

**The trade-off is control vs. speed-to-value.** Graphify gives you 40 languages, community detection, incremental updates, and a visualization out of the box. But I needed stable global IDs across repos so cross-repo LLM edges could reference nodes deterministically, custom Neo4j indexes for graph traversal queries, and full control over edge types for the retrieval pipeline. With an off-the-shelf tool, you can't own the identity layer — and as the eval shows, graph structure choices directly impact recall.

If you're building a single-repo prototype or want fast architectural insight, use Graphify — it's genuinely good. If you're designing a multi-repo retrieval system where node identity matters across pipelines and you need the graph as a queryable backend, you'll end up owning the parser anyway.

Code: https://github.com/onion2005/graphrag

---

#GraphRAG #RAG #KnowledgeGraph #CodeSearch #TreeSitter #Graphify #AIEngineering #GenAI
