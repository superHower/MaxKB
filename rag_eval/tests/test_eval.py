# coding=utf-8
import asyncio
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rag_eval.__main__ import execute, export, validate_config
from rag_eval.client import APIError, MaxKBClient, read_answer
from rag_eval.dataset import load_cases, version
from rag_eval.metrics import retrieval_metrics, total_score
from rag_eval.report import compare
from rag_eval.store import Store


class Response(io.BytesIO):
    def __init__(self, text, content_type="text/event-stream"):
        super().__init__(text.encode())
        self.headers = {"Content-Type": content_type}


class EvalTests(unittest.TestCase):
    def test_document_ranking_and_missing_labels(self):
        result = retrieval_metrics([{"document_id": key} for key in ["noise", "a", "a", "b"]], ["a", "b", "c"])
        self.assertAlmostEqual(result["context_precision"], (1 / 2 + 2 / 3) / 2)
        self.assertAlmostEqual(result["context_recall"], 2 / 3)
        self.assertEqual(result["mrr"], 0.5)
        self.assertEqual(retrieval_metrics([], ["a"])["hit_rate"], 0)
        self.assertIsNone(retrieval_metrics([], [])["context_recall"])
        self.assertIsNone(total_score({"a": 1, "b": None}, {"a": 1, "b": 1}))

    def test_sse_and_truncation(self):
        response = Response(': ping\r\ndata: {"content":"你","chat_record_id":"r","is_end":false}\r\n\r\n'
                            'data: {"content":"好","is_end":false}\n\n'
                            'data: {"content":"","is_end":true,"usage":{"total_tokens":4}}\n\n')
        result = read_answer(response)
        self.assertEqual(result["answer"], "你好")
        self.assertEqual(result["token_usage"]["total_tokens"], 4)
        self.assertEqual(result["chat_record_id"], "r")
        with self.assertRaises(APIError):
            read_answer(Response('data: {"content":"partial","is_end":false}\n\n'))

    def test_dataset_json_csv_versions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "qa.json").write_text(json.dumps([
                {"question": "q", "ground_truth": "a", "relevant_doc_ids": ["d"]}]), encoding="utf-8")
            (root / "qa.csv").write_text('question,ground_truth,relevant_doc_ids\nq,a,"[""d""]"\n', encoding="utf-8")
            self.assertEqual(load_cases(root / "qa.json"), load_cases(root / "qa.csv"))
            cases = load_cases(root / "qa.json")
            digest = version(cases)
            cases[0]["ground_truth"] = "new"
            self.assertNotEqual(digest, version(cases))

    def test_retry_opens_new_conversation(self):
        cfg = {"base_url": "http://local/chat/api", "retries": 1}
        def fake(url, payload, token, timeout):
            if url.endswith("/open"):
                return Response('{"code":200,"data":"chat"}', "application/json")
            fake.calls += 1
            if fake.calls == 1:
                return Response('data: {"content":"partial"}\n\n')
            return Response('data: {"content":"ok","is_end":true}\n\n')
        fake.calls = 0
        with patch.dict("os.environ", {"MAXKB_API_KEY": "test"}), patch("rag_eval.client.request", fake), \
                patch("rag_eval.client.time.sleep"):
            result = MaxKBClient(cfg).ask("q")
        self.assertEqual(result["answer"], "ok")
        self.assertEqual(result["attempts"], 2)

    def test_run_persistence_regression_export(self):
        cases = [{"id": "a", "question": "q", "ground_truth": "a", "relevant_doc_ids": ["d"],
                  "knowledge_ids": ["kb"], "document_tags": ["guide"]}]
        config = {"maxkb": {"base_url": "http://local"}, "concurrency": 2, "retrieval_source": "response",
                  "snapshot": {"embedding_model": "e", "llm_model": "l", "top_k": 5,
                               "similarity_threshold": 0.5, "rerank": False, "knowledge_version": "1",
                               "model_version": "1", "rag_config_version": "1"},
                  "weights": {"context_recall": 1}}
        def fake(question):
            return {"question": question, "answer": "a", "response_time": 0.1, "timestamp": "t",
                    "contexts": [{"document_id": "d", "content": "a"}], "token_usage": None}
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "eval.db")
            try:
                digest = store.import_dataset("qa", cases)
                self.assertEqual(store.dataset("qa", digest)[1], cases)
                store.log_context("c", "r", [{"paragraph_id": "p", "document_id": "d", "content": "a"}])
                self.assertEqual(store.contexts("c", "r")[0]["document_id"], "d")
                with patch("rag_eval.__main__.MaxKBClient") as client:
                    client.return_value.ask.side_effect = fake
                    report = asyncio.run(execute(store, "qa", digest, cases, config))
                self.assertEqual(report["status"], "completed")
                self.assertEqual(store.baseline("qa", digest)["id"], report["id"])
                self.assertIn("knowledge_ids:kb", report["groups"])
                export(report, Path(directory) / "reports")
                self.assertTrue((Path(directory) / "reports" / f"{report['id']}.md").exists())
                current = json.loads(json.dumps(report["results"]))
                current[0]["scores"]["context_recall"] = 0
                current[0]["total_score"] = 0
                comparison = compare(current, report, report["config"], 0.05)
                self.assertEqual(comparison["dimensions"]["context_recall"]["delta"], -1)
                self.assertEqual(len(comparison["regressions"]), 1)
                current[0]["ground_truth"] = "changed"
                self.assertEqual(compare(current, report, report["config"], 0.05)["matched_cases"], 0)
                config["concurrency"] = 0
                with self.assertRaises(ValueError):
                    validate_config(config)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
