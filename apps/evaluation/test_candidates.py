# coding=utf-8
"""Candidate lifecycle tests; all model responses are mocked and production resources stay unchanged."""
import copy
import json
import uuid
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.http import Http404
from django.test import SimpleTestCase, TestCase
from rest_framework.exceptions import ValidationError

from application.models import Application, ApplicationFolder, ApplicationVersion
from common.constants.permission_constants import RoleConstants
from models_provider.models import Model
from .candidate_views import Candidates, CandidateDetail, CandidateAction, scoped_candidate
from .candidates import DEFAULT_GATES, digest, gate_report, invoke_answer, validate_candidate, build_spec
from .models import CandidateValidation, CapabilityVersion, Dataset, ImprovementCandidate, Run


def measured(score=1, safety=1, cost=1, latency=1):
    return {"answer": "verified", "score": score, "safety": safety, "cost": cost,
            "latency": latency, "tool_error": False}


class CandidateAnswerTests(SimpleTestCase):
    def test_qwen_disables_thinking_and_preserves_answer_usage(self):
        for name, expected in (("Qwen3.7-flash", {"extra_body": {"enable_thinking": False}}), ("other", {})):
            with self.subTest(model=name):
                model = Mock(model_name=name)
                model.invoke.return_value = SimpleNamespace(
                    content="先断电，再请专业电工处理。", usage_metadata={"input_tokens": 10, "output_tokens": 5})
                result = invoke_answer(model, "安全回答", {"question": "怎么接线？"}, [], {"input": 1, "output": 1})
                self.assertEqual(model.invoke.call_args.kwargs, expected)
                self.assertEqual(result["answer"], "先断电，再请专业电工处理。")
                self.assertAlmostEqual(result["cost"], .000015)


class CandidateLifecycleTests(TestCase):
    def setUp(self):
        self.actor = uuid.uuid4()
        folder = ApplicationFolder.objects.create(id=str(uuid.uuid4()), name="candidate tests")
        self.app = Application.objects.create(name="candidate tests", folder=folder)
        self.model = Model.objects.create(name="candidate model", model_type="LLM", model_name="test",
                                          provider="test", credential="not-a-real-secret")
        self.version = ApplicationVersion.objects.create(application=self.app, application_name=self.app.name,
                                                         model_id=self.model.id,
                                                         model_setting={"system": "old", "prompt": "{question}"})
        cases = [{"id": "one", "question": "test", "ground_truth": "verified", "category": "returns"}]
        dataset = Dataset.objects.create(application_id=self.app.id, workspace_id="default", name="candidate tests",
                                          version="1", cases=cases)
        self.run = Run.objects.create(application_id=self.app.id, workspace_id="default", user_id=self.actor,
                                      dataset=dataset, status="completed", results=[{"id": "one", "contexts": []}],
                                      config={"application_version": str(self.version.id),
                                              "dataset_snapshot": {"name": dataset.name, "cases": cases}})
        self.payload = {"title": "proposal", "kind": "prompt_patch", "baseline_id": str(self.run.id),
                        "judge_model_id": str(self.model.id), "risk": "needs review",
                        "patch": {"field": "system", "content": "new"}, "pricing": {"input": 0, "output": 0}}
        self.kw = {"workspace_id": "default", "application_id": str(self.app.id)}

    def request(self, data):
        role = RoleConstants.WORKSPACE_MANAGE.get_workspace_role()(None, self.kw)
        return SimpleNamespace(user=SimpleNamespace(id=self.actor), data=data,
                               auth=SimpleNamespace(role_list=[str(role)], permission_list=[]))

    def create(self):
        response = Candidates().post(self.request(self.payload), **self.kw)
        return ImprovementCandidate.objects.get(id=json.loads(response.content)["data"]["id"])

    def test_edit_draft_needs_no_judge_pricing_or_gates_and_preserves_original(self):
        payload = {k: v for k, v in self.payload.items() if k not in {"judge_model_id", "pricing", "gates"}}
        payload["draft_only"] = True
        spec = build_spec(payload, self.run, [])
        self.assertTrue(spec["draft_only"])
        self.assertEqual(spec["patch"]["before"], "old")
        self.assertEqual(spec["patch"]["content"], "new")
        self.assertNotIn("pricing", spec)
        self.assertNotIn("gates", spec)

    def test_workflow_draft_preserves_intent_node_configuration(self):
        self.version.type = "WORK_FLOW"
        self.version.work_flow = {"nodes": [{"id": "intent", "type": "intent-node", "properties": {
            "stepName": "Intent", "node_data": {"branch": [{"id": "knowledge", "name": "Knowledge"}]}}}]}
        self.version.save()
        payload = {**self.payload, "draft_only": True, "kind": "workflow_patch", "patch": {
            "node_id": "intent", "field": "node_data", "content": '{"branch": []}'}}
        spec = build_spec(payload, self.run, [])
        self.assertEqual(json.loads(spec["patch"]["before"])["branch"][0]["id"], "knowledge")
        self.assertEqual(json.loads(spec["patch"]["content"]), {"branch": []})

    def action(self, item, action, **extra):
        return CandidateAction().post(self.request({"action": action, "revision": item.revision, **extra}),
                                      candidate_id=item.id, **self.kw)

    def validation(self, item, rows):
        item.status = "pending_review"
        item.save()
        return CandidateValidation.objects.create(candidate=item, revision=item.revision, created_by=self.actor,
                                                   status="passed", snapshot={"sha256": digest(item.spec)},
                                                   report=gate_report(rows, DEFAULT_GATES))

    def test_approval_is_separate_immutable_artifact(self):
        item = self.create()
        self.validation(item, [{"before": measured(), "after": measured()}])
        self.action(item, "approve", impact_scope="customer service only", rollback_version_id=str(self.version.id))
        capability = CapabilityVersion.objects.get(candidate=item)
        self.assertEqual(capability.status, "pending_release")
        self.assertEqual(capability.manifest["artifact"]["base_version"]["model_setting"]["system"], "new")
        self.assertEqual(capability.manifest["approved_by"], str(self.actor))
        self.assertIn("diff", capability.manifest["spec"])
        self.version.refresh_from_db()
        self.assertEqual(self.version.model_setting["system"], "old")
        self.assertEqual(ApplicationVersion.objects.filter(application=self.app).count(), 1)
        with self.assertRaises(ValidationError):
            self.action(item, "approve", impact_scope="again", rollback_version_id=str(self.version.id))

    def test_hard_gate_and_missing_metrics_cannot_be_waived(self):
        for metric, value in (("score", .2), ("safety", 0), ("latency", 20), ("cost", None)):
            with self.subTest(metric=metric):
                item = self.create()
                after = measured()
                after[metric] = value
                self.validation(item, [{"before": measured(), "after": after}])
                with self.assertRaises(ValidationError):
                    self.action(item, "approve", impact_scope="test", rollback_version_id=str(self.version.id))
                self.assertFalse(item.capability_versions.exists())

    def test_category_regression_requires_reason(self):
        item = self.create()
        rows = [{"category": "returns", "before": measured(.95), "after": measured(.94)}]
        self.validation(item, rows)
        data = {"impact_scope": "returns", "rollback_version_id": str(self.version.id)}
        with self.assertRaises(ValidationError):
            self.action(item, "approve", **data)
        self.action(item, "approve", waivers={"category:returns": "Reviewed sample; acceptable wording change"}, **data)
        self.assertTrue(item.capability_versions.exists())

    def test_revision_reject_and_audit(self):
        item = self.create()
        self.validation(item, [{"before": measured(), "after": measured()}])
        self.action(item, "reject", reason="Revise wording")
        payload = {**self.payload, "revision": 1, "patch": {"field": "system", "content": "revised"}}
        CandidateDetail().put(self.request(payload), candidate_id=item.id, **self.kw)
        item.refresh_from_db()
        self.assertEqual((item.revision, item.status), (2, "draft"))
        with self.assertRaises(ValidationError):
            self.action(item, "approve", impact_scope="test", rollback_version_id=str(self.version.id))
        with self.assertRaises(ValidationError):
            CandidateDetail().put(self.request(payload), candidate_id=item.id, **self.kw)
        self.assertEqual(list(item.audits.order_by("created_at").values_list("action", flat=True)),
                         ["saved", "reject", "saved"])

    def test_scoping_and_malformed_ids(self):
        item = self.create()
        with self.assertRaises(Http404):
            scoped_candidate("elsewhere", str(self.app.id), item.id)
        with self.assertRaises(Http404):
            scoped_candidate("default", str(uuid.uuid4()), item.id)
        for field in ("baseline_id", "judge_model_id"):
            with self.assertRaises(ValidationError):
                Candidates().post(self.request({**self.payload, field: "invalid"}), **self.kw)
        with self.assertRaises(ValidationError):
            Candidates().post(self.request({**self.payload, "badcase_ids": [str(uuid.uuid4())]}), **self.kw)

    @patch("evaluation.candidates.get_model_instance_by_model_workspace_id")
    @patch("evaluation.candidates.judge_answer", return_value={"score": 1, "safety": 1, "reason": "OK"})
    @patch("evaluation.candidates.invoke_answer", return_value=measured(cost=0))
    def test_worker_duplicate_delivery_and_production_isolation(self, answer, judge, model):
        item = self.create()
        with patch("evaluation.candidate_views.validate_candidate.delay"):
            self.action(item, "validate")
        validation = item.validations.get()
        snapshot = copy.deepcopy(validation.snapshot)
        validate_candidate.run(str(validation.id))
        validate_candidate.run(str(validation.id))
        validation.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual((validation.status, item.status), ("passed", "pending_review"))
        self.assertEqual(answer.call_count, 2)
        self.assertEqual(validation.snapshot, snapshot)
        self.version.refresh_from_db()
        self.assertEqual(self.version.model_setting["system"], "old")
        self.assertEqual(ApplicationVersion.objects.count(), 1)

    def test_cancelled_job_does_not_run(self):
        item = self.create()
        with patch("evaluation.candidate_views.validate_candidate.delay"):
            self.action(item, "validate")
        self.action(item, "cancel_validation", reason="Stop")
        with patch("evaluation.candidates.invoke_answer") as answer:
            validate_candidate.run(str(item.validations.get().id))
            answer.assert_not_called()
        self.assertEqual(item.validations.get().status, "cancelled")

    def test_safety_is_per_case_and_empty_report_blocks(self):
        report = gate_report([], DEFAULT_GATES)
        self.assertFalse(report["passed"])
        rows = [{"before": measured(safety=1), "after": measured(safety=1)},
                {"before": measured(safety=1), "after": measured(safety=.5)}]
        safety = next(c for c in gate_report(rows, DEFAULT_GATES)["checks"] if c["key"] == "safety")
        self.assertFalse(safety["passed"])
        self.assertEqual(safety["value"], .5)

    def test_all_candidate_kinds_and_category_policy(self):
        self.version.knowledge_ids = [str(uuid.uuid4())]
        self.version.save()
        for kind, content in (("skill_version", "# Customer service\nAnswer from verified facts and protect private data."),
                              ("knowledge_task", "Verified maintenance fixture")):
            self.payload.update(kind=kind, patch={"content": content, "knowledge_id": self.version.knowledge_ids[0]})
            self.assertEqual(self.create().kind, kind)
        with self.assertRaises(ValidationError):
            Candidates().post(self.request({**self.payload, "gates": {"max_category_drop": .1}}), **self.kw)
