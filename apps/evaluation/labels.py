# coding=utf-8
"""Check that dataset retrieval labels still point at documents the application can retrieve.

A relevant_doc_ids entry that was deleted, re-imported under a new ID, or belongs to a knowledge base the
application does not use makes every retrieval metric 0 regardless of retrieval quality.
"""
import uuid

from knowledge.models import Document


def knowledge_scope(version):
    if version is None:
        return None
    ids = {str(item) for item in (version.knowledge_ids or [])}
    for node in (version.work_flow or {}).get("nodes", []) or []:
        data = (node.get("properties") or {}).get("node_data") or {}
        ids.update(str(item) for item in (data.get("knowledge_id_list") or data.get("dataset_id_list") or []))
    return ids


def label_documents(cases, version):
    """Map each labeled document ID to {id, name, knowledge_id, status: ok | missing | outside}."""
    labeled = {str(item) for case in cases for item in (case.get("relevant_doc_ids") or [])}
    valid = []
    for item in labeled:
        try:
            valid.append(str(uuid.UUID(item)))
        except ValueError:
            pass
    found = {str(doc.id): doc for doc in Document.objects.filter(id__in=valid).only("id", "name", "knowledge_id")}
    scope = knowledge_scope(version)
    documents = {}
    for item in labeled:
        doc = found.get(item)
        if doc is None:
            documents[item] = {"id": item, "name": None, "knowledge_id": None, "status": "missing"}
        else:
            outside = scope is not None and str(doc.knowledge_id) not in scope
            documents[item] = {"id": item, "name": doc.name, "knowledge_id": str(doc.knowledge_id),
                               "status": "outside" if outside else "ok"}
    return documents


def label_check(cases, version):
    documents = label_documents(cases, version)
    invalid = {key for key, value in documents.items() if value["status"] != "ok"}
    return {"documents": documents, "labeled_cases": sum(bool(case.get("relevant_doc_ids")) for case in cases),
            "invalid_cases": sum(bool(invalid.intersection(case.get("relevant_doc_ids") or [])) for case in cases)}
