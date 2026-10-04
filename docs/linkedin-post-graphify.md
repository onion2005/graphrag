# LinkedIn Post — I Tested My AST Parser Against Graphify

Companion to my [GraphRAG post](linkedin-post-graphrag.md).

I built a Python AST parser for code retrieval (~2 days), then found [Graphify](https://github.com/Graphify-Labs/graphify) — open-source, tree-sitter, ~40 languages. Should I have just used it?

Ran both on httpx. Graphify found 2.7x more edges (3,613 vs 1,328) with finer-grained types like `references`, `indirect_call`, `method`.

|  | Custom AST | Graphify |
|---|---|---|
| **Nodes** | 1,192 (code only) | 1,777 (incl. tests, rationale, concepts) |
| **Edges** | 1,328 | 3,613 |
| **Languages** | Python only | ~40 |
| **Node identity** | Custom global IDs | Auto-generated |
| **Storage** | Neo4j | JSON + HTML viz |
| **Community detection** | None | Leiden algorithm |
| **Setup** | ~2 days | `pip install graphifyy` |

I plugged Graphify's graph into my retrieval eval. Both parsers extract methods but name them differently (`BasicAuth.__init__` vs `.__init__()`), so mapping took some work. After fixing it (89% match rate, 1,057 edges connected):

| | Custom AST | Graphify |
|---|---|---|
| **Total recall** | **54.2%** | 46.4% |
| **Queries won** | **9** | 5 |

Graphify won big on redirect handling (+80%) and async client (+40%). My parser won on URL parsing, utilities, status codes. Closer than I expected.

**What I liked about Graphify:**
- `pip install`, one command, done. Community detection spots subsystems nicely
- ~40 languages, incremental updates, non-code source support

**Where I hit friction:**
- No custom node IDs — I needed stable global IDs for cross-repo LLM edges
- JSON output, not a queryable graph backend — I needed Neo4j for traversal queries

**My take:** start with Graphify if you're exploring a codebase or prototyping. Build your own if you need to control the identity layer or query the graph programmatically. I don't regret building mine, but I wouldn't if Graphify covered my requirements.

Code: https://github.com/onion2005/graphrag

---

#GraphRAG #KnowledgeGraph #CodeSearch #TreeSitter #Graphify #AIEngineering #GenAI
