# Module B + C — Implementation Brief

> Context for picking up in Claude Code. This is the implementation handoff for the GraphRAG POC (see `ai-platform-poc-roadmap.md`).

## Decisions locked

- **No graphify.** Self-written AST parser is the baseline. Cleaner id control, simpler story.
- **Baseline = Python `ast` module** → rule-based edges (CALLS, CONTAINS, IMPORTS)
- **LLM layer = same nodes, extra edges** via LLM relationship extraction, `source='llm'`
- **The comparison is:** what relationships does LLM find that static AST cannot? (SIMILAR_TO, DEPENDS_ON, semantic USES_TYPE)
- **Target corpus:** `httpx` repo (`git clone https://github.com/encode/httpx --depth=1`)
- **Graph DB:** Neo4j local, port 7687
- **Vector store:** Chroma (local persistent), `sentence-transformers` (`BAAI/bge-small-en-v1.5`)
- **LLM endpoint:** self-hosted (Module A), OpenAI-compatible at `http://localhost:8000/v1`

## ID alignment — critical, define first

```python
# ingestion/id_registry.py
import hashlib

def make_node_id(file_path: str, symbol_name: str, symbol_type: str) -> str:
    key = f"{file_path}:{symbol_name}:{symbol_type}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]
```

Same id used in both Neo4j node property and Chroma document id. This is how graph traversal results map back to vector chunks.

## Directory layout

```
graphrag-poc/
├── corpus/httpx/
├── ingestion/
│   ├── id_registry.py      # id generation — define first
│   ├── parser.py           # AST → nodes + baseline edges
│   ├── neo4j_loader.py     # write baseline graph + LLM graph to Neo4j
│   ├── llm_extractor.py    # LLM relationship extraction (pairwise, same-file)
│   └── embedder.py         # Chroma vector store build
├── retrieval/
│   ├── hybrid.py           # vector → Cypher traversal → merge
│   └── cypher_templates.py # reusable Cypher (1-hop, 2-hop, no APOC needed)
├── eval/                   # Module F, leave empty for now
└── config.py
```

## Module B — what to build

### parser.py
- Use `ast.walk()` to extract `FunctionDef`, `AsyncFunctionDef`, `ClassDef`
- Node fields: `{id, file, name, type, source_code, docstring, lineno}`
- Baseline edges from AST: `CONTAINS` (class→method), optionally `CALLS` via `ast.Call` detection
- Returns `(nodes: list[dict], edges: list[dict])`

### neo4j_loader.py
- Write nodes as `(:CodeNode {id, name, type, file, docstring, source})`
- `source='baseline'` for AST-derived, `source='llm'` label on LLM-derived edges
- Create index: `CREATE INDEX code_node_id IF NOT EXISTS FOR (n:CodeNode) ON (n.id)`
- Baseline edges: `[:RELATES {type: rel_type, source: 'baseline'}]`
- LLM edges: `[:LLM_RELATES {type, confidence, reason, source: 'llm'}]`

### llm_extractor.py
- Pairwise LLM calls: for each pair (a, b) in same file, ask LLM for relationship type + confidence
- Prompt asks for one of: CALLS, INHERITS, IMPORTS, USES_TYPE, DEPENDS_ON, SIMILAR_TO, NONE
- Only write edges with `confidence >= 0.6`
- **Pruning (O(n²) problem):** limit to same-file pairs only for first pass. `max_pairs=500` safety cap during dev.
- Temperature 0.1 (deterministic extraction)

### embedder.py
- Chunk text = `"{type}: {name}\n{docstring}\n{source_code[:300]}"`
- Chroma collection name: `"code_nodes"`
- Chroma ids = `node["id"]` (same as Neo4j)

## Module C — what to build

### hybrid.py — core logic

```
query_str
  → embed → Chroma top-k → entry_node_ids + scores
  → Cypher: MATCH neighbors within N hops from entry_ids
  → merge + dedup (vector node wins if same id)
  → return ranked list
```

### cypher_templates.py — no APOC needed

```cypher
-- 1-hop (default)
UNWIND $entry_ids AS entry_id
MATCH (start:CodeNode {id: entry_id})-[:RELATES|LLM_RELATES]-(neighbor:CodeNode)
WHERE neighbor.id NOT IN $entry_ids
RETURN DISTINCT neighbor.id, neighbor.name, neighbor.type, neighbor.file, neighbor.docstring
LIMIT $limit

-- 2-hop
UNWIND $entry_ids AS entry_id
MATCH (start:CodeNode {id: entry_id})-[:RELATES|LLM_RELATES*1..2]-(neighbor:CodeNode)
WHERE neighbor.id NOT IN $entry_ids
RETURN DISTINCT neighbor.id, neighbor.name, neighbor.type, neighbor.file, neighbor.docstring
LIMIT $limit
```

### Scoring / merge logic
- Vector nodes: keep cosine similarity score from Chroma (1 - distance)
- Graph-expanded nodes: score = 0.5 (flat, for now)
- Dedup: same id → keep vector version (higher score)
- Sort descending by score

### Default params
- `vector_top_k = 5`
- `graph_hops = 1` (default; 2 is valid but noisy — use eval data to decide)
- `max_graph_nodes = 20`

## Minimum viable smoke test

```python
result = hybrid_retrieve("HTTP client connection pooling", vector_top_k=5, graph_hops=1)
# Should return entry nodes from vector + graph-expanded neighbors
# Check: graph nodes are semantically related to entry nodes
```

## Build order (don't skip)

1. `id_registry.py` — define first, everything depends on it
2. `parser.py` — verify node/edge counts on httpx before touching Neo4j
3. `neo4j_loader.py` — baseline graph only, verify in Neo4j Browser
4. `embedder.py` — vector store, verify chunk count matches node count
5. `retrieval/hybrid.py` — smoke test with baseline graph only (no LLM edges yet)
6. `llm_extractor.py` — add LLM edges last, it's slow

## deps

```
pip install neo4j chromadb sentence-transformers
# neo4j needs Java 17+; run: neo4j start
```