"""
Generate a latency/throughput/cost report from Locust CSV output
and vLLM Prometheus metrics.

Usage:
    python loadtest/report.py [--csv-prefix loadtest/results] [--metrics-url http://localhost:8000/metrics]
"""
import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


G5_XLARGE_HOURLY = 1.006  # us-east-1 on-demand


def parse_locust_stats(csv_prefix: str) -> dict:
    """Parse Locust CSV stats files."""
    stats_file = Path(f"{csv_prefix}_stats.csv")
    if not stats_file.exists():
        raise FileNotFoundError(f"{stats_file} not found. Run locust with --csv first.")

    rows = []
    with open(stats_file) as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    # Find the chat completion rows (not Aggregated, not TOKENS)
    chat_rows = [r for r in rows if "/v1/chat/completions" in r.get("Name", "")]
    agg_row = next((r for r in rows if r.get("Name") == "Aggregated"), None)

    # Token rows
    token_rows = [r for r in rows if r.get("Type") == "TOKENS"]
    prompt_token_row = next((r for r in token_rows if "prompt" in r.get("Name", "")), None)
    completion_token_row = next((r for r in token_rows if "completion" in r.get("Name", "")), None)

    result = {"per_endpoint": [], "aggregated": None, "tokens": {}}

    for row in chat_rows:
        result["per_endpoint"].append({
            "name": row["Name"],
            "requests": int(row.get("Request Count", 0)),
            "failures": int(row.get("Failure Count", 0)),
            "median_ms": float(row.get("Median Response Time", 0)),
            "p95_ms": float(row.get("95%", 0)),
            "p99_ms": float(row.get("99%", 0)),
            "avg_ms": float(row.get("Average Response Time", 0)),
            "min_ms": float(row.get("Min Response Time", 0)),
            "max_ms": float(row.get("Max Response Time", 0)),
            "rps": float(row.get("Requests/s", 0)),
        })

    if agg_row:
        result["aggregated"] = {
            "total_requests": int(agg_row.get("Request Count", 0)),
            "total_failures": int(agg_row.get("Failure Count", 0)),
            "median_ms": float(agg_row.get("Median Response Time", 0)),
            "p95_ms": float(agg_row.get("95%", 0)),
            "p99_ms": float(agg_row.get("99%", 0)),
            "avg_ms": float(agg_row.get("Average Response Time", 0)),
            "rps": float(agg_row.get("Requests/s", 0)),
        }

    # Read token counts from file saved by locustfile.py
    token_file = Path(csv_prefix).parent / "token_counts.json"
    if token_file.exists():
        with open(token_file) as f:
            tokens = json.load(f)
        result["tokens"]["total_prompt"] = tokens.get("prompt", 0)
        result["tokens"]["total_completion"] = tokens.get("completion", 0)

    return result


def fetch_vllm_metrics(metrics_url: str) -> dict:
    """Fetch and parse vLLM Prometheus metrics."""
    req = Request(metrics_url)
    with urlopen(req, timeout=10) as resp:
        text = resp.read().decode()

    metrics = {}

    def get_gauge(name: str) -> float | None:
        m = re.search(rf'^{re.escape(name)}\s+([\d.e+-]+)', text, re.MULTILINE)
        return float(m.group(1)) if m else None

    def get_counter(name: str) -> float | None:
        pattern = rf'^{re.escape(name)}_total\s+([\d.e+-]+)'
        m = re.search(pattern, text, re.MULTILINE)
        return float(m.group(1)) if m else None

    def get_histogram_stats(name: str) -> dict | None:
        count_m = re.search(rf'^{re.escape(name)}_count\s+([\d.e+-]+)', text, re.MULTILINE)
        sum_m = re.search(rf'^{re.escape(name)}_sum\s+([\d.e+-]+)', text, re.MULTILINE)
        if count_m and sum_m:
            count = float(count_m.group(1))
            total = float(sum_m.group(1))
            return {"count": int(count), "sum_s": round(total, 3), "avg_s": round(total / count, 3) if count > 0 else 0}
        return None

    metrics["gpu_cache_usage_pct"] = get_gauge("vllm:gpu_cache_usage_perc")
    metrics["requests_running"] = get_gauge("vllm:num_requests_running")
    metrics["requests_waiting"] = get_gauge("vllm:num_requests_waiting")
    metrics["total_prompt_tokens"] = get_counter("vllm:prompt_tokens")
    metrics["total_generation_tokens"] = get_counter("vllm:generation_tokens")
    metrics["total_requests_success"] = get_counter("vllm:request_success")

    metrics["e2e_latency"] = get_histogram_stats("vllm:e2e_request_latency_seconds")
    metrics["ttft"] = get_histogram_stats("vllm:time_to_first_token_seconds")
    metrics["tpot"] = get_histogram_stats("vllm:time_per_output_token_seconds")
    metrics["prefill_time"] = get_histogram_stats("vllm:request_prefill_time_seconds")
    metrics["decode_time"] = get_histogram_stats("vllm:request_decode_time_seconds")
    metrics["queue_time"] = get_histogram_stats("vllm:request_queue_time_seconds")

    return metrics


def compute_cost(locust_stats: dict, duration_s: float) -> dict:
    """Compute cost metrics."""
    total_tokens = (
        locust_stats["tokens"].get("total_prompt", 0)
        + locust_stats["tokens"].get("total_completion", 0)
    )
    duration_h = duration_s / 3600
    instance_cost = G5_XLARGE_HOURLY * duration_h

    cost_per_1k = (instance_cost / total_tokens * 1000) if total_tokens > 0 else 0
    tokens_per_dollar = (total_tokens / instance_cost) if instance_cost > 0 else 0

    return {
        "instance_type": "g5.xlarge",
        "hourly_rate": G5_XLARGE_HOURLY,
        "test_duration_s": round(duration_s, 1),
        "instance_cost_during_test": round(instance_cost, 4),
        "total_tokens": total_tokens,
        "cost_per_1k_tokens": round(cost_per_1k, 6),
        "tokens_per_dollar": round(tokens_per_dollar, 0),
    }


def print_report(locust_stats: dict, vllm_metrics: dict, cost: dict):
    """Print formatted report."""
    print("=" * 70)
    print("  vLLM LOAD TEST REPORT")
    print("=" * 70)

    agg = locust_stats.get("aggregated", {})
    print(f"\n--- Locust Results ---")
    print(f"Total requests:    {agg.get('total_requests', 0)}")
    print(f"Failures:          {agg.get('total_failures', 0)}")
    print(f"RPS:               {agg.get('rps', 0):.2f}")
    print(f"Median latency:    {agg.get('median_ms', 0):.0f} ms")
    print(f"P95 latency:       {agg.get('p95_ms', 0):.0f} ms")
    print(f"P99 latency:       {agg.get('p99_ms', 0):.0f} ms")

    for ep in locust_stats.get("per_endpoint", []):
        print(f"\n  {ep['name']}")
        print(f"    Requests: {ep['requests']}  |  Median: {ep['median_ms']:.0f}ms  |  P95: {ep['p95_ms']:.0f}ms  |  P99: {ep['p99_ms']:.0f}ms")

    print(f"\n--- vLLM Server Metrics ---")
    print(f"GPU KV cache usage:     {(vllm_metrics.get('gpu_cache_usage_pct') or 0) * 100:.1f}%")
    print(f"Total prompt tokens:    {vllm_metrics.get('total_prompt_tokens') or 0:.0f}")
    print(f"Total gen tokens:       {vllm_metrics.get('total_generation_tokens') or 0:.0f}")
    print(f"Successful requests:    {vllm_metrics.get('total_requests_success') or 0:.0f}")

    if vllm_metrics.get("e2e_latency"):
        e2e = vllm_metrics["e2e_latency"]
        print(f"Avg E2E latency:        {e2e['avg_s'] * 1000:.0f} ms  (over {e2e['count']} requests)")
    if vllm_metrics.get("ttft"):
        ttft = vllm_metrics["ttft"]
        print(f"Avg TTFT:               {ttft['avg_s'] * 1000:.0f} ms")
    if vllm_metrics.get("tpot"):
        tpot = vllm_metrics["tpot"]
        print(f"Avg time/output token:  {tpot['avg_s'] * 1000:.1f} ms")
    if vllm_metrics.get("queue_time"):
        qt = vllm_metrics["queue_time"]
        print(f"Avg queue time:         {qt['avg_s'] * 1000:.1f} ms")

    print(f"\n--- Cost Analysis ---")
    print(f"Instance:               {cost['instance_type']} @ ${cost['hourly_rate']}/hr")
    print(f"Test duration:          {cost['test_duration_s']:.0f}s")
    print(f"Total tokens:           {cost['total_tokens']:,}")
    print(f"Cost per 1K tokens:     ${cost['cost_per_1k_tokens']:.4f}")
    print(f"Tokens per $1:          {cost['tokens_per_dollar']:,.0f}")

    # Compare to API pricing
    print(f"\n--- Cost Comparison ---")
    api_prices = {
        "Claude Haiku (input)":  0.00025,
        "Claude Haiku (output)": 0.00125,
        "GPT-4o-mini (input)":   0.00015,
        "GPT-4o-mini (output)":  0.00060,
    }
    print(f"  Self-hosted (blended): ${cost['cost_per_1k_tokens']:.4f} / 1K tokens")
    for name, price in api_prices.items():
        ratio = price / cost['cost_per_1k_tokens'] if cost['cost_per_1k_tokens'] > 0 else 0
        print(f"  {name:<25s}: ${price:.5f} / 1K tokens  ({ratio:.1f}x self-hosted)")


def save_report(locust_stats: dict, vllm_metrics: dict, cost: dict, output_path: str):
    """Save structured report as JSON."""
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "locust": locust_stats,
        "vllm_metrics": vllm_metrics,
        "cost": cost,
    }
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nJSON report saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate load test report")
    parser.add_argument("--csv-prefix", default="loadtest/results", help="Locust CSV prefix")
    parser.add_argument("--metrics-url", default="http://localhost:8000/metrics", help="vLLM metrics URL")
    parser.add_argument("--duration", type=float, default=60, help="Test duration in seconds")
    parser.add_argument("--output", default="loadtest/report.json", help="Output JSON path")
    args = parser.parse_args()

    print("Parsing Locust results...")
    locust_stats = parse_locust_stats(args.csv_prefix)

    print("Fetching vLLM metrics...")
    try:
        vllm_metrics = fetch_vllm_metrics(args.metrics_url)
    except Exception as e:
        print(f"  Warning: could not fetch vLLM metrics ({e}), using empty metrics")
        vllm_metrics = {}

    cost = compute_cost(locust_stats, args.duration)

    print_report(locust_stats, vllm_metrics, cost)
    save_report(locust_stats, vllm_metrics, cost, args.output)


if __name__ == "__main__":
    main()
