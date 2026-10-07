# coding=utf-8
"""Rank unique documents by first occurrence; missing labels are not zero scores."""


def retrieval_metrics(contexts, relevant_doc_ids):
    names = ("context_precision", "context_recall", "hit_rate", "mrr", "precision_at_k")
    if contexts is None or not relevant_doc_ids:
        return dict.fromkeys(names)
    relevant = set(relevant_doc_ids)
    documents = list(dict.fromkeys(str(row["document_id"]) for row in contexts))
    hits, precision_sum, reciprocal = 0, 0.0, 0.0
    for rank, doc_id in enumerate(documents, 1):
        if doc_id in relevant:
            hits += 1
            precision_sum += hits / rank
            if not reciprocal:
                reciprocal = 1 / rank
    return {
        "context_precision": precision_sum / hits if hits else 0.0,
        "context_recall": hits / len(relevant), "hit_rate": float(hits > 0), "mrr": reciprocal,
        "precision_at_k": hits / len(documents) if documents else 0.0,
    }


def total_score(scores, weights):
    if not weights or any(scores.get(key) is None for key in weights):
        return None
    return sum(scores[key] * weight for key, weight in weights.items()) / sum(weights.values())
