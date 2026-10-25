# coding=utf-8
"""Trace normalization, trajectory assertions and closure verdicts without database or model calls."""
import json

from django.test import SimpleTestCase

from .closure import _node_value, _same, _target, case_verdict
from .trace import build_trace, trace_scores

WORKFLOW = {"nodes": [
    {"id": "intent", "type": "intent-node", "properties": {"stepName": "意图分流", "node_data": {
        "branch": [{"id": "b-stock", "content": "库存"}, {"id": "b-product", "content": "商品知识"}]}}},
    {"id": "search", "type": "search-knowledge-node", "properties": {"stepName": "知识库检索", "node_data": {
        "knowledge_id_list": ["k1"], "knowledge_setting": {"top_n": 3, "similarity": 0.6, "search_mode": "embedding"}}}},
    {"id": "tool", "type": "tool-lib-node", "properties": {"stepName": "查订单", "node_data": {"tool_lib_id": "t-1"}}},
]}
DETAILS = {
    "r2": {"node_id": "search", "index": 1, "type": "search-knowledge-node", "status": 200, "question": "q",
           "paragraph_list": [{"content": "c"}]},
    "r1": {"node_id": "intent", "index": 0, "type": "intent-node", "status": 200, "branch_id": "b-stock",
           "category": "库存"},
    "r3": {"node_id": "tool", "index": 2, "type": "tool-lib-node", "status": 500, "err_message": "timeout",
           "params": {"order": "1"}},
}


class TraceTests(SimpleTestCase):
    def test_steps_are_ordered_and_located(self):
        trace = build_trace(DETAILS, WORKFLOW, {"index": 1})
        self.assertEqual([s["node_id"] for s in trace["steps"]], ["intent", "search", "tool"])
        self.assertEqual(trace["branches"][0]["name"], "库存")
        self.assertEqual(trace["steps"][1]["retrieval"]["top_n"], 3)
        self.assertEqual(trace["steps"][1]["retrieval"]["knowledge_ids"], ["k1"])
        self.assertEqual(trace["steps"][1]["retrieval"]["hit_count"], 1)
        self.assertEqual(trace["failed_step"], 2)
        self.assertEqual(trace["tool_calls"][0]["id"], "t-1")

    def test_assertions_only_when_declared(self):
        trace = build_trace(DETAILS, WORKFLOW)
        self.assertEqual(trace_scores(trace, {}), {})
        scores = trace_scores(trace, {"expected_tools": ["查订单"], "expected_branch": "商品知识"})
        self.assertEqual(scores["tool_call_accuracy"], 1.0)
        self.assertEqual(scores["tool_order_correct"], 1.0)
        self.assertEqual(scores["tool_error_rate"], 1.0)
        self.assertEqual(scores["branch_correct"], 0.0)
        self.assertEqual(trace_scores(trace, {"expected_tools": []})["tool_call_accuracy"], 0.0)

    def test_tool_order(self):
        details = {"a": {"node_id": "x", "index": 0, "type": "mcp-node", "mcp_tool": "b"},
                   "b": {"node_id": "y", "index": 1, "type": "mcp-node", "mcp_tool": "a"}}
        scores = trace_scores(build_trace(details), {"expected_tools": ["a", "b"]})
        self.assertEqual(scores["tool_call_accuracy"], 1.0)
        self.assertEqual(scores["tool_order_correct"], 0.0)


class ClosureTests(SimpleTestCase):
    def test_verdicts(self):
        ok = {"ground_truth": "g", "scores": {"answer_correctness": 0.9}, "trace": {"failed_step": None}}
        self.assertEqual(case_verdict(ok), "passed")
        self.assertEqual(case_verdict({**ok, "scores": {"answer_correctness": 0.2}}), "failed")
        self.assertEqual(case_verdict({**ok, "trace": {"failed_step": 0}}), "failed")
        self.assertEqual(case_verdict({**ok, "scores": {"answer_correctness": 0.9, "branch_correct": 0.0}}), "failed")
        self.assertEqual(case_verdict({"ground_truth": "", "scores": {}}), "needs_review")
        self.assertEqual(case_verdict({"ground_truth": "", "scores": {"faithfulness": 0.8,
                                                                     "no_answer_correctness": 1}}), "passed")

    def test_patch_comparison(self):
        data = _target("WORK_FLOW", json.loads(json.dumps(WORKFLOW)), "search")
        self.assertTrue(_same("workflow_patch", _node_value("workflow_patch", "node_data", data),
                              json.dumps(data, ensure_ascii=False, indent=2)))
        self.assertFalse(_same("prompt_patch", _node_value("prompt_patch", "system", data), "new"))
