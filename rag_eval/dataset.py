# coding=utf-8
"""Validated datasets with immutable SHA256 versions."""
import csv
import hashlib
import json
from pathlib import Path

CATEGORIES = {"frequent", "boundary", "multi_hop", "negative", "terminology"}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def version(cases):
    return hashlib.sha256(canonical(cases).encode()).hexdigest()


def load_cases(path):
    path = Path(path)
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as source:
            rows = list(csv.DictReader(source))
        for row in rows:
            for key in ("relevant_doc_ids", "knowledge_ids", "document_tags", "expected_tools", "history"):
                if row.get(key):
                    row[key] = json.loads(row[key])
                else:
                    row.pop(key, None)
    elif path.suffix.lower() == ".json":
        rows = json.loads(path.read_text(encoding="utf-8-sig"))
    else:
        raise ValueError("Dataset must be JSON or CSV")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Dataset must be a nonempty array")
    cases, ids = [], set()
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise TypeError(f"Case {index}: expected object")
        case = dict(row)
        for key in ("question", "ground_truth"):
            if not isinstance(case.get(key), str) or not case[key].strip():
                raise ValueError(f"Case {index}: {key} must be nonempty text")
        case["id"] = str(case.get("id") or hashlib.sha256(case["question"].encode()).hexdigest()[:24])
        if case["id"] in ids:
            raise ValueError(f"Duplicate case ID {case['id']}; supply explicit IDs for duplicate questions")
        ids.add(case["id"])
        for key in ("relevant_doc_ids", "knowledge_ids", "document_tags"):
            if key in case and (not isinstance(case[key], list) or
                                any(not isinstance(item, str) or not item for item in case[key])):
                raise ValueError(f"Case {index}: {key} must be an array of nonempty strings")
        # Trajectory assertions: expected_tools (ordered, [] means no tool call) and expected_branch.
        if "expected_tools" in case and (not isinstance(case["expected_tools"], list) or any(
                not isinstance(item, str) or not item.strip() for item in case["expected_tools"])):
            raise ValueError(f"Case {index}: expected_tools must be an array of tool names or IDs")
        if not case.get("expected_branch"):
            case.pop("expected_branch", None)
        elif not isinstance(case["expected_branch"], str):
            raise ValueError(f"Case {index}: expected_branch must be text")
        # Multi-turn: prior user messages sent in the same chat before the scored question.
        if "history" in case and (not isinstance(case["history"], list) or len(case["history"]) > 20 or any(
                not isinstance(item, str) or not item.strip() for item in case["history"])):
            raise ValueError(f"Case {index}: history must be at most 20 nonempty messages")
        if case.get("category") and case["category"] not in CATEGORIES:
            raise ValueError(f"Case {index}: invalid category")
        cases.append(case)
    return cases
