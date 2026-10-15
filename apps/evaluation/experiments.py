# coding=utf-8
"""Stable experiment assignment helpers."""
import hashlib


def assign_variant(experiment, subject_id):
    subject = str(subject_id or "")
    digest = int(hashlib.sha256(f"{experiment.id}:{subject}".encode()).hexdigest()[:12], 16) % 10000
    cursor = 0
    for variant in experiment.variants:
        weight = int(variant.get("weight", 0))
        if weight < 0:
            continue
        cursor += weight
        if digest < cursor:
            return variant.get("key")
    return None
