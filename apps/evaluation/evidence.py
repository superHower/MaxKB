# coding=utf-8
"""Keep observable node evidence without model reasoning payloads."""


def node_evidence(value):
    if isinstance(value, dict):
        return {key: node_evidence(item) for key, item in value.items()
                if key not in {"reasoning_content", "reasoning", "thinking", "chain_of_thought"}}
    if isinstance(value, list):
        return [node_evidence(item) for item in value]
    return value
