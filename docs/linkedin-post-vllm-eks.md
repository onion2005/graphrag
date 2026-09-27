# LinkedIn Post — Self-Hosted LLM on EKS

![Architecture & Load Test Results](../loadtest/hero_linkedin.png)

"Self-hosting is cheaper than APIs." I built it, load-tested it, and ran the numbers. The answer is: it depends on volume, and the APIs are much faster.

**Setup:** Qwen 2.5 7B on EKS → Karpenter GPU autoscaling → vLLM → OpenAI-compatible API. Single g5.xlarge (A10G GPU).

**Latency (Locust, 5 concurrent users, realistic workloads):**

| Workload | Self-hosted P50 | Claude Haiku (est.) | GPT-4o-mini (est.) |
|---|---|---|---|
| Tool call | 1.6s | ~0.5s | ~0.3s |
| JSON extraction | 2.5s | ~0.8s | ~0.5s |
| Simple QA | 6.4s | ~1.2s | ~0.8s |
| RAG (long context) | 21s | ~3s | ~2s |
| Agent multi-turn | 25s | ~4s | ~3s |

APIs are 5-10x faster. A10G running a 7B model can't match H100 clusters behind frontier APIs. That's expected.

**But cost tells a different story. Monthly cost — single g5.xlarge (1x A10G GPU), always on:**

| Daily requests | Self-hosted (on-demand) | Self-hosted (spot) | Claude Haiku | GPT-4o-mini |
|---|---|---|---|---|
| 1K | $724 | $252 | $36 | $6 |
| 10K | $724 | $252 | $357 | $57 |
| 50K | $724 | $252 | $1,784 | $284 |
| 100K | $724 | $252 | $3,569 | $568 |

![Cost Crossover Analysis](../loadtest/cost_crossover.png)

**Crossover points:** Self-hosted (spot) beats Claude Haiku at ~7K daily requests. Beats GPT-4o-mini at ~44K daily. On-demand: ~20K and ~128K respectively.

**The trade-off is clear:**

1. APIs win on latency — not close
2. APIs win on cost at low volume (<7K req/day)
3. Self-hosted wins on cost at scale (>20K req/day even on-demand)
4. Self-hosted wins on data sovereignty — tokens never leave your VPC
5. Self-hosted loses on ops burden — 6-min cold start, GPU quota requests, Karpenter tuning, driver compat, K8s sharp edges
6. Quality gap — 7B tool calling works, but isn't frontier-model quality

**Self-host when:** sustained high throughput (>10K req/day), data stays in your VPC, you have infra engineers. **Use APIs when:** latency matters, volume is low, you need frontier quality.

Code + infra manifests on GitHub.

---

#MLOps #LLMOps #Kubernetes #vLLM #AWS #EKS #GPU #SelfHostedAI #GenAI #CostOptimization #Karpenter
