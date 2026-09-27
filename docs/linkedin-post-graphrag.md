# LinkedIn Post — GraphRAG: When Vector Search Isn't Enough

RAG doesn't work well on code. Here's why, and what I built instead.

The failure mode is subtle. You ask "how does httpx handle authentication?" Vector search returns `BasicAuth`, `DigestAuth`, `NetRCAuth` — semantically similar to your query. Looks good. But it completely misses the `Auth` base class they inherit from, the `Client._build_auth()` that wires them in, and the `_auth_flow` generator that orchestrates the challenge-response cycle. Those are structurally connected, not semantically similar. Embeddings can't see inheritance hierarchies or call graphs.

**The fix: use the structure that's already there.**

Code isn't a document. It has a formal, parseable structure — an AST. Every class, function, and method is a node. Every CALL, IMPORT, INHERIT is an edge. This graph already exists in the source code. You just have to extract it.

So I built a GraphRAG system: vector search finds the entry points, then graph expansion walks structural edges to pull in related symbols the embeddings missed. Hop-decay scoring (0.8 per hop) keeps distant neighbors from diluting relevance.

**The results that changed my assumptions:**

Vector + AST graph found **77% more relevant symbols** than vector alone (10.8 vs 6.1 per query). But here's what I didn't expect:

1. **LLM-extracted edges added zero value over AST edges.** I spent tokens having an LLM classify SIMILAR_TO / DEPENDS_ON relationships between symbols. The AST edges (CALLS, INHERITS, IMPORTS) already captured the useful structure. The semantic edges were either redundant or noise. This surprised me — I expected the LLM to find patterns the parser couldn't.

2. **Graph without vector is useless.** Pure graph traversal without good seed nodes returns noise. The vector search IS the entry point — you need both, but in a specific order.

3. **The real win is cross-file discovery.** Authentication in httpx spans `_auth.py`, `_client.py`, and `_config.py`. Vector search finds one file. The graph finds all three. This is the problem GraphRAG actually solves for code: following dependencies across file boundaries.

**The uncomfortable conclusion:**

For code, the knowledge graph you need is the one your parser already gives you for free. The expensive LLM extraction step that papers recommend? I ran a controlled eval and it didn't move the needle. CALLS and INHERITS edges did all the work.

This doesn't mean LLM-extracted edges are useless for all domains — unstructured documents don't have ASTs. But if your corpus has formal structure (code, schemas, APIs, configs), extract the graph from the structure first. Only add LLM edges if the eval shows a gap.

Stack: Python, Neo4j, ChromaDB, LangGraph agent, BGE embeddings. Code on GitHub.

---

#GraphRAG #RAG #KnowledgeGraph #Neo4j #CodeSearch #InformationRetrieval #AIEngineering #GenAI #NLP
