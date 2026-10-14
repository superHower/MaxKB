# coding=utf-8
"""Business quality metrics calculated from persisted evaluation events."""
from collections import Counter, defaultdict


def percentile(values, ratio):
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((len(ordered) - 1) * ratio)))
    return ordered[index]


def summarize(events):
    rows = [item.data if hasattr(item, "data") else (item.get("data", item) if isinstance(item, dict) else item)
            for item in events]
    total = len(rows)
    votes = Counter((row.get("feedback") or {}).get("vote", "-1") for row in rows)
    latencies = [float(row["latency_ms"]) for row in rows if isinstance(row.get("latency_ms"), (int, float))]
    costs = [float(row["estimated_cost"]) for row in rows if isinstance(row.get("estimated_cost"), (int, float))]
    input_tokens = [float((row.get("token_usage") or {}).get("input", 0)) for row in rows]
    output_tokens = [float((row.get("token_usage") or {}).get("output", 0)) for row in rows]
    resolved = [row for row in rows if (row.get("feedback") or {}).get("vote") == "0"
                and row.get("human_handoff") is not True]
    no_answer = [row for row in rows if not row.get("retrieval_candidates")]
    evaluable = [row for row in rows if row.get("evaluable")]
    conversations = defaultdict(int)
    for row in rows:
        if row.get("chat_id"):
            conversations[str(row["chat_id"])] += 1
    one_turn = sum(value == 1 for value in conversations.values())
    def rate(value, denominator=total):
        return value / denominator if denominator else None
    return {
        "sample_count": total, "effective_count": len(rows),
        "resolved_rate": rate(len(resolved)), "one_turn_resolution_rate": rate(one_turn),
        "human_handoff_rate": rate(sum(row.get("human_handoff") is True for row in rows)),
        "like_rate": rate(votes.get("0", 0)), "dislike_rate": rate(votes.get("1", 0)),
        "no_answer_rate": rate(len(no_answer)), "citation_evaluable_rate": rate(len(evaluable)),
        "latency_ms": {"mean": sum(latencies) / len(latencies) if latencies else None,
                       "p50": percentile(latencies, .5), "p95": percentile(latencies, .95),
                       "p99": percentile(latencies, .99), "count": len(latencies)},
        "tokens": {"input": sum(input_tokens), "output": sum(output_tokens)},
        "estimated_cost": sum(costs),
    }
