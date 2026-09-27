# AI Platform POC Roadmap — Skill Gaps → Production Case Study

> **Purpose:** One POC that closes every hands-on gap I have, and doubles as a production-ready, LinkedIn-postable case study aimed squarely at the target role (HFT/quant AI Engineer, Hong Kong).
>
> **Working principle:** Every module I build must be shippable *and* narratable — a real artifact plus a "why it matters" story. Build it once, use it as (a) skill, (b) portfolio, (c) interview material.

---

## 1. Target definition (why this exists)

- **North star:** AI Platform Architect / Senior AI Engineer — production AI, not research. Own delivery from prototype to prod.
- **Target market:** Quant/HFT firms investing in AI (e.g. the HK role). They value:
  - Production AI engineering over research
  - Agentic workflows, MCP, tool-use frameworks
  - **Self-hosted / on-prem model serving** (data-sensitive, low-latency, compliance — they do NOT send inference to Claude/GPT/Gemini APIs)
  - Financial-markets background (a plus, and I have it)
- **My differentiator:** `infra (15 yrs, cloud/K8s) + AI落地`. Most AI engineers only call APIs. I can build the infrastructure AI runs on. This is the scarce combination these firms actually need.

---

## 2. The gaps I'm closing

| Gap | Current state | Why it matters for target role |
|---|---|---|
| Agentic workflows | Touched (synapse-tools), never built one | Core requirement, listed explicitly |
| MCP | Researched, never authored a server | Listed explicitly ("MCPs, tool-use frameworks") |
| Evaluation | Have judgment, never ran a formal eval | Listed explicitly ("evaluating AI systems") |
| Self-hosted model serving | LLM Gateway on K8s is adjacent, not self-hosting | The defining trait of HFT/quant AI stacks |

---

## 3. The POC — one build that closes all four gaps

**Working title:** *Agentic GraphRAG over a self-hosted LLM, exposed via MCP, with an evaluation harness.*

A retrieval system for a codebase (or any structured corpus) that:
- runs on a **self-hosted open model** (not an external API),
- uses an **agent** to decide retrieval strategy (vector vs graph vs both, how deep to traverse),
- combines **vector search + graph traversal** (hybrid / GraphRAG),
- is **exposed as an MCP server** so any client/agent can call it as a tool,
- and ships with an **evaluation harness** proving hybrid beats naive vector search.

This is deliberately close to the real problem I already understand (the org's fragmented vector-store / Neo4j / Confluence-bridge setup), so the design judgment is genuine, not toy.

### Module breakdown → gap closed → case-study angle

| # | Module | Gap closed | LinkedIn case-study angle |
|---|---|---|---|
| A | **Self-hosted LLM serving** — serve an open model (Llama/Qwen/Mistral) on K8s with vLLM/TGI | Self-hosted serving | "Why I ran inference in-cluster instead of calling an API — latency, data control, cost. The infra reality of production AI." |
| B | **Ingestion + dual store** — parse corpus → embeddings in a vector store + relationships in a graph DB | (reinforces existing RAG) | "Ingestion is not a pipe: chunking, embedding choice, and metadata design decide downstream retrieval quality." |
| C | **Hybrid / GraphRAG retrieval** — vector recall + graph expansion, merged | (architecture depth) | "Vector search finds what's similar; graph finds what's connected. Why enterprise RAG needs both." |
| D | **Agentic layer** — LangGraph agent decides strategy (which store, how many hops, when to stop) | Agentic workflows | "Turning retrieval into an agent: letting the system reason about *how* to search, not just search." |
| E | **MCP server** — expose the whole thing as a tool any client can call | MCP | "Wrapping a capability as an MCP server so it's discoverable and reusable across the org — with the governance questions that raises." |
| F | **Evaluation harness** — golden dataset, compare hybrid vs naive vector on accuracy/relevance + latency/cost | Evaluation | "You can't ship what you can't measure: building an eval harness for a non-deterministic system, and why regex-validates-regex is a trap." |

> **Sequencing (from the AI SDLC lens — pick a thin end-to-end slice first, then deepen):**
> 1. B (thin ingestion, one small corpus) → C (basic hybrid) → get *something* returning results
> 2. F (eval from the start — don't bolt it on) — even a tiny golden set
> 3. A (move inference to self-hosted) — infra is my strength, high-signal for target role
> 4. D (agentic layer on top)
> 5. E (wrap as MCP)
> Then iterate depth on whichever module makes the best story.

---

## 4. Each module = a production-ready case study

**Rule for "prod-ready" (not a toy demo):** each posted case study must show
- a real, running artifact (repo link / screenshots / architecture diagram),
- the **decision and trade-off** (why this, not that — the architect layer),
- **evidence** (eval numbers, latency, cost, before/after),
- what I'd do differently at real scale.

**Case-study backlog (post as each module lands):**
- [ ] A — Self-hosted inference: the infra reality of production AI
- [ ] B — Ingestion as design, not plumbing
- [ ] C — Why enterprise RAG needs vector *and* graph (GraphRAG)
- [ ] D — Retrieval as an agent (agentic workflows)
- [ ] E — Exposing a capability as MCP (+ governance)
- [ ] F — Evaluation harness for non-deterministic systems
- [ ] Capstone — the whole system end-to-end, one narrative

---

## 5. Mapping to the target JD (proof of fit)

| JD requirement | Covered by |
|---|---|
| Build AI-powered apps, assistants, agentic workflows | D, E, whole POC |
| Integrations between AI and internal repos/DBs/knowledge | B, C |
| AI agents interacting with systems/APIs | D, E |
| Evaluate emerging models/frameworks | F, and A (open-model selection) |
| Production systems track record | whole POC + existing Macquarie RAG prod work |
| MCPs / tool-use frameworks | E |
| APIs, distributed systems, architecture | A (K8s serving), whole design |
| Concept → production independently | the entire self-driven POC |
| Financial markets exposure (plus) | existing background |

**Gap after POC:** essentially none on the "must-have" list. Self-hosted serving + agentic + MCP + eval all become hands-on.

---

## 6. Execution notes (anti-stall)

- **Lower the starting bar to almost zero.** First action is not code — it's one line: *"I'm building an agentic GraphRAG on a self-hosted model, exposed via MCP, with an eval harness."* Done. Then the smallest runnable step.
- **Don't wait for energy after a draining commute.** Move it forward one small step at a time; once a week counts, as long as it moves.
- **It can grow on work I'm already doing** (ingestion, MCP exposure, ACL thinking) — not a separate universe.
- **Keep a running work-log** of decisions and trade-offs as I build — that log *is* the raw material for both the case studies and interview answers.
- **Separate "done" from "posted":** a module isn't finished until it has an artifact + a decision + evidence. That's the prod-ready bar.

---

## 7. Timeline anchor

- **Now → early next year:** build the POC module by module, post case studies as they land, keep external recruiter lines warm (incl. the HK role — expressed interest, timing early next year, open to relocating).
- **Early next year:** move, targeting AI Platform / Senior AI Engineer roles, with a portfolio that hits these JDs on first read.
