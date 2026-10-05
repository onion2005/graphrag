# LinkedIn Article — Self-Hosted LLM on EKS

![Architecture & Load Test Results](../loadtest/hero_linkedin.png)

"Self-hosting is cheaper than APIs." I built it, load-tested it, and ran the numbers. Short answer: it depends on volume *and* whether a 7B model is good enough for your use case.

## What I Built

This wasn't just deploying a model — it was building the full serving stack and wiring it into an existing system.

**Infrastructure (from scratch):**
- EKS cluster with a system node group (m5.large, no GPU) and Karpenter managing GPU nodes separately
- Karpenter NodePool configured for g5.xlarge spot instances with GPU taint, scale-to-zero (`consolidateAfter: 5m`), and a 2-GPU cost guardrail
- NVIDIA device plugin for GPU scheduling, vLLM deployment with readiness probes (120s initial delay for model loading)

**Code migration:**
- Swapped the entire codebase from Anthropic SDK to OpenAI-compatible SDK — the LangGraph agent, LLM relationship extractor, eval judge, and golden dataset generator all needed to go through the self-hosted endpoint. This wasn't a demo hitting curl; the model runs the same agent pipeline I evaluated in my [GraphRAG experiments](linkedin-post-graphrag.md)

**Load test design:**
- 5 workload categories that mirror real production patterns: tool calls, structured JSON extraction, simple QA, long-context RAG, and multi-turn agent reasoning. Each hits different bottlenecks (decode speed, context length, multi-round latency)

**Setup:** Qwen 2.5 7B, g5.xlarge (1x A10G), vLLM v0.8.4 with OpenAI-compatible API.

## What I Measured

**Latency (Locust, 5 concurrent users, 79 requests, 0 failures):**

| Workload | P50 | P95 |
|---|---|---|
| Tool call | 1.6s | 2.3s |
| JSON extraction | 2.5s | 8.0s |
| Simple QA | 6.4s | 6.8s |
| RAG (long context) | 21s | 21s |
| Agent multi-turn | 25s | 32s |

A 7B model on a single A10G won't compete with frontier APIs on H100 clusters. I didn't benchmark APIs head-to-head, but latency-sensitive workloads should stay on APIs.

**Cost** — with a caveat: this compares a 7B open model against much more capable APIs (Claude Haiku, GPT-4o-mini). The crossover only matters if 7B quality is good enough for your task. Monthly cost assuming always-on, single model:

| Daily requests | Self-hosted (on-demand) | Self-hosted (spot) | Claude Haiku | GPT-4o-mini |
|---|---|---|---|---|
| 1K | $724 | $252 | $36 | $6 |
| 10K | $724 | $252 | $357 | $57 |
| 50K | $724 | $252 | $1,784 | $284 |
| 100K | $724 | $252 | $3,569 | $568 |

API costs assume ~590 tokens/request (my test mix: 28K prompt + 18K completion over 79 requests). Heavier workloads shift these crossover points.

![Cost Crossover Analysis](../loadtest/cost_crossover.png)

**Crossover for this workload mix:** spot beats Claude Haiku at ~7K req/day, GPT-4o-mini at ~44K/day.

Important: this is one model on one GPU. If your deployment needs 2-3 models, self-hosted cost doubles or triples and the crossover shifts accordingly.

## What I Learned Building This

**Operational:**
- GPU quota was the first blocker. AWS defaults to 0 vCPUs for G-instances in new accounts — took a support request and a few days
- Karpenter spot provisioning works, but NVIDIA device plugin + AMI driver compatibility tripped me up twice
- 5 concurrent users is a light test. 10 users roughly doubled P50 on heavier workloads

**Architectural:**
- A single A10G is a bottleneck at real concurrency. Production needs a larger instance (g5.2xlarge+) or request batching
- vLLM serves one model per process. A 7B model at fp16 takes ~14GB of the A10G's 24GB VRAM. Most production setups run multiple vLLM instances behind a router (like [LiteLLM Gateway](https://github.com/onion2005/LLM-Gateway)), each on its own GPU. If your models are fine-tuned variants of the same base, vLLM can hot-swap LoRA adapters per request on a single GPU instead — but I didn't test this
- In production you'd keep at least 1 replica warm. I built Karpenter scale-to-zero for dev to avoid paying for idle GPU — cold start is ~3-4 min (model loading), fine for POC but not production
- Tool calling with Qwen 7B works (Hermes format) but isn't frontier quality. Simple calls are fine, complex multi-step reasoning breaks down. The right next step would be running the same eval queries through both Qwen 7B and Claude Haiku and comparing tool-call success rates — I didn't do that, which is a gap in this analysis

## What I'd Optimize Next

Quantization. My deployment runs Qwen 7B at FP16 (~14GB VRAM on a 24GB A10G). Switching to INT8 (AWQ or GPTQ) would roughly halve that to ~7GB — enough to fit a second model on the same GPU, or free headroom for longer contexts and higher concurrency. vLLM supports this with a single flag (`--quantization awq`). Quality loss on INT8 is minimal for most tasks; INT4 is more aggressive and would need testing, especially for tool calling where the model is already borderline.

This is probably the highest-leverage change I didn't make. The cost table above assumes one model per GPU — quantization could change that math significantly.

## When Does Self-Hosting Make Sense?

No general rule — depends on your workload, model count, and quality requirements.

**Self-host when:** sustained high volume (for this setup: >7K req/day vs Haiku, >44K vs GPT-4o-mini), data must stay in your VPC, and you have K8s expertise on the team.

**Use APIs when:** latency matters, volume is bursty or low, you need frontier-model quality, or you'd need multiple models (which multiplies GPU cost).

Code + infra manifests: https://github.com/onion2005/graphrag
LiteLLM Gateway (router for multiple vLLM instances): https://github.com/onion2005/LLM-Gateway

---

#MLOps #LLMOps #Kubernetes #vLLM #AWS #EKS #GPU #SelfHostedAI #GenAI #CostOptimization #Karpenter
