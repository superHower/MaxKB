# coding=utf-8
"""Call from a workflow tool node after rerank and context truncation."""
from .store import Store


def log_final_context(db_path, chat_id, chat_record_id, paragraphs):
    """paragraphs must be the exact ordered context supplied to generation, not pre-rerank candidates."""
    store = Store(db_path)
    try:
        store.log_context(str(chat_id), str(chat_record_id), paragraphs)
    finally:
        store.close()
    return {"logged": True, "count": len(paragraphs)}
