# GraphRAG Edge Extraction — Design Decision

## Problem

Code relationship extraction can use static analysis (AST) or LLM. Each has strengths and costs. Running LLM on all possible relationships is expensive and redundant. How should we split the work?

## Decision: AST for structure, LLM for semantics

### AST-extracted edges (deterministic)

| Edge Type | Source | What it captures | Why AST |
|-----------|--------|-----------------|---------|
| CONTAINS | `ast.ClassDef` → child `FunctionDef` | class→method, module→symbol hierarchy | Directly in syntax tree, 100% precision |
| CALLS | `ast.Call` nodes | function A invokes function B | Call sites are explicit in AST |
| IMPORTS | `ast.Import` / `ast.ImportFrom` | module-level dependencies | Import statements are literal |
| INHERITS | `ast.ClassDef.bases` | class B extends class A | Base classes listed in class definition |
| USES_TYPE | `ast.arg.annotation`, `ast.FunctionDef.returns` | function uses type X in signature | Type annotations are syntactic |

These relationships are **visible in the source code structure**. AST extraction is fast, free, and never wrong about what it finds.

### LLM-extracted edges (semantic)

| Edge Type | What it captures | Why LLM |
|-----------|-----------------|---------|
| SIMILAR_TO | Two functions serve a similar purpose or implement similar logic | Requires understanding intent, not just syntax. `BasicAuth.auth_flow` and `NetRCAuth.auth_flow` have different implementations but the same purpose. AST sees different code; LLM sees the same pattern. |
| DEPENDS_ON | Implicit runtime dependency between symbols (shared state, initialization order, configuration) | `auth_flow` depends on `__init__` because it reads `self._auth_header` set during init. AST can see the attribute access but cannot reason about initialization order or shared mutable state. |

These relationships require **understanding what the code does**, not just what it looks like.

## Why not LLM for everything?

We tested this. Results from 500 LLM calls on the httpx codebase:

- **CALLS**: AST found 136 edges. LLM found 58, with only 5 overlapping. AST is more complete and reliable for direct invocations.
- **INHERITS**: AST extracts from `class Foo(Bar)` with zero ambiguity. LLM found 39 but sometimes incorrectly labeled method-to-class relationships as inheritance.
- **USES_TYPE**: AST reads annotations directly. LLM found 19 but occasionally confused type usage with general dependencies.
- **SIMILAR_TO**: 548 edges. AST cannot detect this at all. This is where LLM adds the most value.
- **DEPENDS_ON**: 31 edges. AST cannot reason about runtime dependencies.

LLM is expensive, rate-limited, and non-deterministic. Using it for relationships AST already handles perfectly is waste.

## Pruning: making LLM extraction practical

Naive pairwise LLM extraction is O(n^2). For 1,144 symbols, that's 654,000+ pairs.

**Solution**: embed all symbols once, compute cosine similarity, only send top-k most similar pairs to the LLM.

| Approach | Pairs processed | Edges found | Hit rate | File coverage |
|----------|----------------|-------------|----------|---------------|
| Brute-force (same-file, alphabetical) | 500 | 210 | 42% | 2 files |
| Embedding-pruned (top-5 per node) | 500 | 490 | 98% | 45 files |

Same budget, 2.3x more edges, full repo coverage. The embedding pre-filter ensures LLM only evaluates pairs likely to have relationships.

## Final architecture

```
Source code
  │
  ├── AST parser ──→ CONTAINS, CALLS, IMPORTS, INHERITS, USES_TYPE
  │                   (deterministic, fast, complete)
  │
  └── Embedding ──→ top-k similar pairs ──→ LLM ──→ SIMILAR_TO, DEPENDS_ON
                     (pruning)                        (semantic, expensive, targeted)
  │
  └──→ Neo4j graph ──→ hybrid retrieval
         RELATES (AST)
         LLM_RELATES (LLM)
```

---

# Evaluation Results

## Method 1: Golden dataset (28 queries, 161 expected symbols)

LLM-generated queries across 4 categories (structural navigation, semantic similarity, cross-file dependency, API surface), human-reviewable. Metrics computed against fixed expected symbols.

### Recall — does the mode find the right symbols?

| Mode | R@5 | R@10 | R@20 | R@all |
|------|-----|------|------|-------|
| Vector Only | 0.169 | 0.321 | 0.321 | **0.321** |
| Vector + AST Graph | 0.154 | 0.294 | 0.530 | **0.663** |
| Vector + Graph (LLM) | 0.088 | 0.220 | 0.339 | **0.339** |
| Vector + Graph (AST+LLM) | 0.107 | 0.245 | 0.516 | **0.674** |

### Ranking quality — are the right symbols ranked high?

| Mode | MRR | nDCG@5 | nDCG@10 | nDCG@20 |
|------|-----|--------|---------|---------|
| Vector Only | **0.380** | **0.205** | **0.275** | 0.275 |
| Vector + AST Graph | 0.321 | 0.153 | 0.218 | **0.321** |
| Vector + Graph (LLM) | 0.172 | 0.085 | 0.152 | 0.204 |
| Vector + Graph (AST+LLM) | 0.269 | 0.113 | 0.177 | 0.293 |

### Per-category R@all

| Category | Vector Only | +AST Graph | +LLM Graph | +AST+LLM |
|----------|-------------|------------|------------|-----------|
| Structural navigation | 0.452 | 0.714 | 0.500 | **0.762** |
| Semantic similarity | 0.100 | **0.721** | 0.100 | **0.721** |
| Cross-file dependency | 0.398 | **0.626** | 0.421 | **0.626** |
| API surface | 0.333 | **0.588** | 0.333 | **0.588** |

## Method 2: LLM-as-judge (same 28 queries, judge grades each retrieved symbol 0-3)

Independent of golden dataset — the LLM judge evaluates what was *actually retrieved*, catching relevant symbols the golden set missed.

### Aggregate

| Mode | Avg Relevance | Relevant found (≥2) | P@10 | nDCG@10 | nDCG@20 | MRR |
|------|--------------|---------------------|------|---------|---------|-----|
| Vector Only | **1.81** | 6.1 | **0.614** | **0.916** | **0.916** | **0.929** |
| Vector + AST Graph | 1.54 | 11.2 | 0.514 | 0.584 | 0.727 | 0.631 |
| Vector + Graph (LLM) | 1.69 | 7.8 | 0.554 | 0.708 | 0.812 | 0.649 |
| Vector + Graph (AST+LLM) | 1.55 | **12.0** | 0.507 | 0.563 | 0.702 | 0.608 |

### Relevance grade distribution

| Mode | Irrelevant (0) | Peripheral (1) | Important (2) | Essential (3) |
|------|---------------|----------------|---------------|---------------|
| Vector Only | **9.6%** | 28.9% | 32.5% | 28.9% |
| Vector + AST Graph | 21.0% | 29.5% | 26.2% | 23.3% |
| Vector + Graph (LLM) | 12.9% | 31.1% | 30.1% | 26.0% |
| Vector + Graph (AST+LLM) | 21.2% | 28.5% | 25.8% | 24.5% |

## Conclusions from both evaluations (before damping)

Both methods agree:

1. **Graph expansion doubles recall**: AST+LLM finds 67% of expected symbols vs 32% for vector-only (golden dataset). LLM judge confirms: 12.0 relevant symbols found vs 6.1.

2. **Graph expansion hurts ranking**: Vector-only achieves MRR 0.929 and nDCG@10 0.916 (judge) — its results are almost perfectly ranked. Graph modes drop to MRR 0.608-0.631 because graph-expanded nodes flood the top positions with 21% irrelevant results.

3. **AST graph dominates LLM graph**: AST edges (CONTAINS, CALLS) contribute nearly all the recall gain. LLM edges (SIMILAR_TO, DEPENDS_ON) add only +1.8pp total recall in golden dataset eval. LLM graph's value shows more in the judge eval (+1.7 relevant symbols), but AST graph alone gets +5.1.

4. **The gap closes at higher k**: nDCG@20 for AST graph (0.727) is much closer to vector-only (0.916) than nDCG@10 (0.584 vs 0.916). The relevant nodes are found — they're just ranked too low.

5. **Semantic similarity is where graph shines most**: R@all jumps from 0.100 to 0.721 with AST graph — a 7x improvement. CONTAINS edges pull in sibling methods within the same class.

---

# Decision: Graph Node Score Damping

## Problem

Graph expansion finds 2x more relevant symbols but ranks them poorly. Graph-expanded nodes are scored by embedding similarity to the query (reranking), but they compete equally with vector search results in the merged ranking. This pushes high-quality vector hits out of the top positions.

## Solution: hop-based decay

Apply `score *= 0.8 ^ hops` to graph nodes before merging. Nodes found via 1 hop get score × 0.8, 2-hop nodes get × 0.64, etc.

### Parameter sweep (AST+LLM graph, 28 queries)

| Config | MRR | nDCG@10 | R@all |
|--------|-----|---------|-------|
| No damping (before) | 0.269 | 0.177 | 0.674 |
| **Decay 0.8** | **0.426** | **0.268** | **0.674** |
| Decay 0.6 | 0.395 | 0.271 | 0.674 |
| Threshold 0.4 | 0.269 | 0.177 | 0.674 |
| Threshold 0.5 | 0.269 | 0.177 | 0.674 |
| Decay 0.8 + Thresh 0.4 | 0.426 | 0.268 | 0.674 |
| Decay 0.8 + Thresh 0.5 | 0.426 | 0.268 | 0.635 |
| Decay 0.7 + Thresh 0.4 | 0.405 | 0.271 | 0.660 |
| Vector Only (reference) | 0.380 | 0.275 | 0.321 |

**Decay 0.8 wins**: MRR jumps +0.157 (0.269→0.426), R@all fully preserved. Threshold alone has no effect because all reranked scores are already above 0.5.

### Results after damping (golden dataset)

| Mode | MRR | nDCG@10 | R@5 | R@10 | R@all |
|------|-----|---------|-----|------|-------|
| Vector Only | 0.380 | 0.275 | 0.169 | 0.321 | 0.321 |
| **Vector + AST Graph** | **0.441** | **0.294** | **0.210** | **0.334** | **0.663** |
| Vector + Graph (LLM) | 0.330 | 0.203 | 0.116 | 0.214 | 0.339 |
| Vector + Graph (AST+LLM) | 0.426 | 0.268 | 0.172 | 0.304 | 0.674 |

**AST Graph now beats vector-only on every metric** while retaining 2x the recall.

---

# Decision: LLM Graph Is Not Worth the Cost

## Evidence

After damping, comparing AST-only graph vs AST+LLM:

| Metric | Vector Only | +AST Graph | +LLM Graph | +AST+LLM |
|--------|-------------|------------|------------|-----------|
| MRR | 0.380 | **0.441** | 0.330 | 0.426 |
| nDCG@10 | 0.275 | **0.294** | 0.203 | 0.268 |
| R@all | 0.321 | 0.663 | 0.339 | 0.674 |

1. **LLM graph alone hurts ranking**: MRR 0.330 is *below* vector-only (0.380). SIMILAR_TO/DEPENDS_ON edges expand to nodes that aren't relevant to the query.

2. **Adding LLM to AST is marginal at best**: R@all gains +1.1pp (0.663→0.674) but MRR drops -0.015 (0.441→0.426). The extra recall isn't worth the ranking degradation.

3. **AST graph alone is the sweet spot**: Best MRR (0.441), best nDCG@10 (0.294), strong recall (0.663). It beats vector-only on every metric.

4. **Cost asymmetry**: AST extraction is instant, deterministic, and free. LLM extraction requires 500 API calls ($), embedding pre-filtering, and produces non-deterministic results.

## Why LLM edges don't help

The SIMILAR_TO edges connect symbols with similar purpose (e.g., `BasicAuth.auth_flow` ↔ `NetRCAuth.auth_flow`). But for retrieval, these symbols are already reachable: they share a parent class (`Auth`) connected by CONTAINS edges, and vector search already finds some of them by embedding similarity.

DEPENDS_ON edges capture implicit runtime dependencies, but these are rare (31 edges) and don't align with what users query for.

## Decision

**Drop LLM graph for retrieval.** Use AST-only graph (CONTAINS, CALLS, INHERITS, USES_TYPE) with hop-based decay (0.8).

The LLM extraction code (`llm_extractor.py`) and Neo4j LLM_RELATES edges remain available for analysis and exploration — they're valuable for understanding code relationships, just not for improving retrieval quality in this setup.

## Caveat

This conclusion is specific to:
- The httpx codebase (well-structured, clear class hierarchies)
- The query types tested (code understanding, API discovery)
- 1-hop graph expansion

LLM edges might add value for:
- Codebases with less clear structure (no class hierarchies to traverse)
- Queries specifically targeting similar implementations across unrelated modules
- Multi-hop traversal where AST edges alone create too much noise
