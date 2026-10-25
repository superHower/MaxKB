# coding=utf-8
"""Judge response and reasoning-budget regressions without external model calls."""
import json
from types import SimpleNamespace
from unittest.mock import Mock

from django.test import SimpleTestCase

from .tasks import JUDGE_MAX_TOKENS, _judge
from .settings import judge_settings, retrieval_settings
from rest_framework.exceptions import ValidationError


class JudgeTests(SimpleTestCase):
    def test_custom_parameters_reach_model(self):
        model = Mock(model_name="other")
        model.invoke.return_value = SimpleNamespace(content=json.dumps({
            "answer_correctness": 1, "citation_relevance": 1,
            "no_answer_correctness": 1, "faithfulness": 1,
        }), response_metadata={})
        _judge(model, "q", "a", [], "r", settings={
            "temperature": 0.2, "max_tokens": 8192, "thinking": "enabled", "json_mode": True})
        self.assertEqual(model.invoke.call_args.kwargs, {
            "temperature": 0.2, "max_tokens": 8192, "extra_body": {"enable_thinking": True},
            "response_format": {"type": "json_object"}})

    def test_settings_reject_invalid_values(self):
        for settings in ({"max_tokens": True}, {"max_tokens": 800.5}, {"max_tokens": 1},
                         {"temperature": float("nan")}, {"temperature": 2}, {"json_mode": "false"},
                         {"thinking": []}, {"api_key": "x"}, []):
            with self.subTest(settings=settings), self.assertRaises(ValidationError):
                judge_settings(settings)

    def test_retrieval_snapshot_includes_parameters_connections_and_fallback(self):
        version = SimpleNamespace(id="version", type="WORK_FLOW", knowledge_ids=["kb"],
                                  knowledge_setting={"no_references_setting": {"status": "reply"}},
                                  work_flow={"nodes": [{"id": "search", "type": "search-knowledge-node",
                                      "properties": {"stepName": "Search", "node_data": {
                                          "knowledge_setting": {"top_n": 5, "similarity": 0.4},
                                          "knowledge_id_list": ["kb"]}}}],
                                      "edges": [{"sourceNodeId": "search", "targetNodeId": "condition"}]})
        data = retrieval_settings(version)
        self.assertEqual(data["nodes"][0]["settings"], {"top_n": 5, "similarity": 0.4})
        self.assertEqual(data["edges"], [{"source": "search", "target": "condition"}])
        self.assertEqual(data["no_references"], {"status": "reply"})

    def test_bailian_deepseek_disables_thinking_and_sets_call_budget(self):
        model = type("BaiLianChatModel", (), {})()
        model.model_name = "deepseek-v4.1-flash-1017"
        model.invoke = Mock(return_value=SimpleNamespace(content=json.dumps({
            "answer_correctness": 1, "citation_relevance": 0.5,
            "no_answer_correctness": 1, "faithfulness": 0, "reason": "partial",
        }), response_metadata={"finish_reason": "stop"}))
        scores, reason = _judge(model, "question", "answer", [], "reference")
        self.assertEqual(model.invoke.call_args.kwargs, {
            "temperature": 0, "max_tokens": JUDGE_MAX_TOKENS,
            "extra_body": {"enable_thinking": False},
        })
        self.assertEqual(scores["judge_score"], 0.625)
        self.assertEqual(reason, "partial")

    def test_response_failures_explain_truncation_and_empty_content(self):
        for content, finish, message in (
            ("", "length", "截断"),
            ('{"answer_correctness":1}', "length", "截断"),
            ("", "stop", "空正文"),
            ("no json", "stop", "未返回 JSON"),
        ):
            with self.subTest(content=content, finish=finish):
                model = Mock(model_name="other")
                model.invoke.return_value = SimpleNamespace(
                    content=content, response_metadata={"finish_reason": finish})
                with self.assertRaisesRegex(ValueError, message):
                    _judge(model, "q", "a", [], "r")
                self.assertNotIn("extra_body", model.invoke.call_args.kwargs)
