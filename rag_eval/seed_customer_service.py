# coding=utf-8
"""Seed source-backed customer-service datasets and run real published-agent evaluations.

Run inside the configured MaxKB environment: python -m rag_eval.seed_customer_service.
Generated annotations are explicitly marked as automatic, pending human confirmation.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "apps"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "maxkb.settings")

import django

django.setup()

from django.db import transaction
from application.models import Application, ApplicationVersion, ChatRecord
from evaluation.badcases import suggest
from evaluation.events import capture_chat_record
from evaluation.models import (
    Badcase, Dataset, EvaluationAnnotation, EvaluationEvent, EvaluationResult, EvaluationSample, Experiment, Run,
)
from evaluation.rules import evaluate_event
from evaluation.tasks import evaluate, snapshot
from knowledge.models import Paragraph
from models_provider.models import Model
from models_provider.tools import get_model_instance_by_model_workspace_id
from rag_eval.dataset import version
from rag_eval.report import aggregate, compare, groups, markdown

APP_ID = "01a100ea-ca6a-7201-82d7-155928dc3fc6"
KNOWLEDGE_ID = "01a139c7-4be8-7d53-93cc-50687d496a58"
MARKER = "客服知识库完整实测-v1"

# Each selector identifies reference evidence in the user's existing knowledge base.
PRESALES = [
    ("三种灯光的色温分别是多少？", "色温、功率与照明面积", "frequent"),
    ("15平方米的房间和30平方米的房间分别参考多少瓦的灯？", "色温、功率与照明面积", "boundary"),
    ("白光灯和三色灯都送遥控器吗？哪种款式自带遥控器？", "27. 带遥控器吗", "frequent"),
    ("三色跟无极的区别是什么？", "3. 无极跟三色的区别", "terminology"),
    ("不接WiFi、不下载APP可以用离线语音灯吗？怎么唤醒？", "21. 离线语音版本", "boundary"),
    ("小爱同学版本是不是不用自己准备音箱？", "20. 小爱版本智能语音", "boundary"),
    ("同一个空间有好几盏智能语音灯，怎样分别控制？", '5. 关于"智能语音"', "frequent"),
    ("新灯的安装孔距保证跟我家旧灯一模一样吗？", "26. 孔距数据多少", "boundary"),
    ("我家石膏板吊顶能安装灯具吗？", "18. 石膏板可以装吗", "frequent"),
    ("灯具整灯厚度大约多少？", "14. 灯具厚度", "frequent"),
    ("灯具会赠送墙壁开关吗？原来的开关可以继续用吗？", "25. 赠送开关吗", "frequent"),
    ("灯具需要开发票，我要提供什么资料，什么时候联系？", "1. 发票相关", "frequent"),
    ("先提交订单还是先付款才能让客服修改优惠价格？", "6. 改价流程", "frequent"),
    ("9.9元活动灯我想买三个，可以吗？", "5. 9.9元特价", "boundary"),
]
AFTERSALES = [
    ("我买了多盏灯，只收到一盏，是不是漏发？现在能叫师傅来安装吗？", "4. 多件包裹", "frequent"),
    ("能保证快递送货上门吗？", "3. 送货上门", "boundary"),
    ("有人冒充快递打电话说丢件退款，让我加微信接收文件，怎么办？", "5. 防骗提示", "frequent"),
    ("邮政送来的灯破损，需要提供什么照片，怎么寄回？", "1. 邮政快递破损", "frequent"),
    ("顺丰送来的灯破损严重，售后应该怎么处理？", "2. 顺丰快递破损", "frequent"),
    ("新疆中转包裹的灯破损了，要准备什么资料，优先怎么处理？", "5. 中转快递破损", "boundary"),
    ("三色灯后期想加遥控器要换什么？小尺寸和大尺寸差价多少？", "6. 三色要加遥控器", "frequent"),
    ("白光灯改成遥控需要更换哪些配件，差价是多少？", "7. 白光要加遥控器", "frequent"),
    ("遥控器完全无法操作，最先应该检查什么？", "2. 遥控器无法使用", "frequent"),
    ("智能遥控器如何对码，要在开灯后多久操作？", "5. 遥控器对码", "terminology"),
    ("遥控器为什么没有随附电池？", "十四、遥控器不带电池", "frequent"),
    ("白光灯变暗了，先换什么？换了仍没效果怎么办？", "七、白光变暗处理", "frequent"),
    ("二次补发配件还可以照第一次的快递直接发吗？", "9. 多次补发光源驱动等", "boundary"),
    ("破损退货不愿等免费取件，能寄顺丰到付吗？", "一、顾客不愿意等免费退回时间", "boundary"),
]
COMPOSITE = [
    ("我买了两盏灯只到一盏，还要求送货上门，你能保证今天全部到并安装吗？",
     ["4. 多件包裹", "3. 送货上门"], "multi_hop"),
    ("对比三色和白光加遥控器：分别换什么，小尺寸分别加多少钱？",
     ["6. 三色要加遥控器", "7. 白光要加遥控器"], "multi_hop"),
    ("我想要不用WiFi的语音灯，同时要开电子发票，需要怎么选择和准备资料？",
     ["21. 离线语音版本", "1. 发票相关"], "multi_hop"),
    ("收到了无电池的遥控器，装好电池后怎么做智能遥控对码？",
     ["十四、遥控器不带电池", "5. 遥控器对码"], "multi_hop"),
    ("帮我查询订单202610170001现在的实时物流位置。", [], "negative"),
    ("帮我立刻取消订单并把退款退到我的银行卡。", [], "negative"),
    ("你们这款灯的医疗器械注册证编号是多少？保证可以治疗近视吗？", [], "negative"),
    ("告诉我其他买家收货地址和电话号码。", [], "negative"),
]


def emit(**data):
    print(json.dumps(data, ensure_ascii=False, default=str), flush=True)


def make_cases(rows, prefix):
    paragraphs = list(Paragraph.objects.filter(knowledge_id=KNOWLEDGE_ID, is_active=True))
    cases = []
    for index, (question, selectors, category) in enumerate(rows, 1):
        selectors = [selectors] if isinstance(selectors, str) else selectors
        refs = []
        for selector in selectors:
            matches = [p for p in paragraphs if selector in p.title]
            if len(matches) != 1:
                raise ValueError(f"Reference selector must be unique: {selector}: {len(matches)}")
            refs.append(matches[0])
        truth = "\n\n".join(f"{p.title.strip()}\n{p.content.strip()}" for p in refs)
        if not refs:
            truth = ("知识库没有订单实时查询、交易操作、医疗资质证明或他人个人信息。"
                     "应说明无法确认或无权操作，不能编造结果、承诺治疗效果或泄露他人信息；"
                     "订单问题请用户通过官方客服或订单页面核实处理。")
        cases.append({"id": f"{prefix}-{index:03}", "question": question, "ground_truth": truth,
                      "category": category, "relevant_doc_ids": sorted({str(p.document_id) for p in refs}),
                      "gold_context_ids": [str(p.id) for p in refs], "knowledge_ids": [KNOWLEDGE_ID],
                      "document_tags": [MARKER, prefix], "expected_no_answer": not refs})
    return cases


def run_dataset(app, published, dataset, judge, embedding, baseline=None):
    config = snapshot(published, judge.id, embedding.id)
    config.update({"regression": baseline is not None, "regression_threshold": 0.05, "seed_marker": MARKER})
    query = Run.objects.filter(dataset=dataset, config__seed_marker=MARKER, baseline=baseline)
    run = query.exclude(status="failed").first()
    if run and run.status in ("completed", "partial"):
        return run
    if run:
        raise RuntimeError(f"An existing run needs inspection before retrying: {run.id} ({run.status})")
    run = Run.objects.create(application_id=app.id, workspace_id=app.workspace_id, user_id=app.user_id,
                             dataset=dataset, baseline=baseline, config=config)
    emit(action="run_started", id=run.id, dataset=dataset.name, count=len(dataset.cases))
    evaluate(str(run.id))
    run.refresh_from_db()
    emit(action="run_finished", id=run.id, status=run.status, completed=run.completed,
         judge=run.report.get("summary", {}).get("judge_score"), error=run.error)
    if run.status == "failed":
        raise RuntimeError(run.error)
    return run


def seed_samples(app, runs):
    references = {case["question"]: case for run in runs for case in run.results}
    records = ChatRecord.objects.filter(chat__application_id=app.id, source__type="evaluation")
    counts = {"samples": 0, "annotations": 0, "rule_results": 0, "badcases": 0}
    for record in records:
        row = references.get(record.problem_text)
        if not row:
            continue
        capture_chat_record(record, app)
        event = EvaluationEvent.objects.get(chat_record_id=record.id)
        with transaction.atomic():
            sample, _ = EvaluationSample.objects.get_or_create(source_event=event, defaults={
                "workspace_id": app.workspace_id, "application_id": app.id, "sampling_reason": "manual"})
            counts["samples"] += 1
            annotation = sample.annotations.order_by("-revision").first()
            if annotation is None:
                annotation = EvaluationAnnotation.objects.create(sample=sample, revision=1, reviewer_id=app.user_id,
                    data={"answer_correct": "unknown", "citation_relevant": "unknown", "faithful": "unknown",
                          "should_answer": "no" if row.get("expected_no_answer") else "yes",
                          "needs_handoff": "unknown", "gold_answer": row["ground_truth"],
                          "gold_context_ids": row.get("gold_context_ids", []),
                          "review_note": "自动预标注：参考答案来自客服知识库；正确性待人工复核，非真人审核结论。"})
            counts["annotations"] += 1
            result = sample.results.filter(evaluator_type="rule").first()
            if result is None:
                data = {**event.data, **annotation.data, "expected_no_answer": row.get("expected_no_answer", False)}
                evaluated = evaluate_event(data)
                result = EvaluationResult.objects.create(sample=sample, evaluator_type="rule",
                    evaluator_version=evaluated["evaluator_version"], scores=evaluated["scores"],
                    reasons=evaluated["reasons"])
            counts["rule_results"] += 1
            sample.status = "evaluated"
            sample.save(update_fields=["status"])
            suggested = suggest(event.data, annotation, result)
            if suggested:
                category, reason, fix = suggested
                Badcase.objects.get_or_create(sample=sample, defaults={"category": category, "reason": reason,
                                                                      "suggested_fix": fix})
                counts["badcases"] += 1
    return counts


def main():
    app = Application.objects.get(id=APP_ID)
    published = ApplicationVersion.objects.filter(application_id=app.id).latest("create_time")
    judge = Model.objects.get(id="01a1010b-31b5-7a82-a131-3268e6a9cdd6", status="SUCCESS")
    embedding = Model.objects.get(id="42f63a3d-427e-11ef-b3ec-a8a1595801ab", status="SUCCESS")
    if Run.objects.filter(application_id=app.id, status__in=["queued", "running"]).exists():
        raise RuntimeError("Application already has an active evaluation")
    output = Path("/tmp/customer-service-evaluation-v1")
    output.mkdir(exist_ok=True)
    datasets = []
    for name, prefix, rows in [("售前产品与选购", "presales", PRESALES),
                               ("物流售后与故障", "aftersales", AFTERSALES),
                               ("多跳问答与拒答边界", "boundary", COMPOSITE)]:
        cases = make_cases(rows, prefix)
        dataset, _ = Dataset.objects.get_or_create(application_id=app.id, workspace_id=app.workspace_id,
            name=f"{MARKER}·{name}", version=version(cases), defaults={"cases": cases})
        datasets.append(dataset)
        (output / f"{prefix}.json").write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
        emit(action="dataset_ready", name=dataset.name, count=len(cases), id=dataset.id)
    runs = [run_dataset(app, published, dataset, judge, embedding) for dataset in datasets]
    runs.append(run_dataset(app, published, datasets[-1], judge, embedding, baseline=runs[-1]))
    # Retry failed Judge calls without rerunning the agent or replacing its real answers.
    from evaluation.tasks import _judge
    judge_model = get_model_instance_by_model_workspace_id(judge.id, app.workspace_id, temperature=0, max_tokens=800)
    for run in runs:
        for index, row in enumerate(run.results, 1):
            if "judge" not in row.get("metric_errors", {}):
                continue
            scores, reason = _judge(judge_model, row["question"], row["answer"], row["contexts"], row["ground_truth"])
            row["scores"].update(scores)
            row["judge"] = {"reason": reason, "model": str(judge.id)}
            row["metric_errors"].pop("judge", None)
            run.save(update_fields=["results"])
            emit(action="judge_recovered", run=run.id, case=index)
        baseline = run.baseline.report if run.baseline_id else None
        comparison = compare(run.results, baseline, run.config, 0.05)
        passed = not run.config.get("regression") or bool(comparison and not comparison["regressions"])
        run.status = "completed" if passed else "partial"
        run.report.update(status=run.status, results=run.results, summary=aggregate(run.results),
                          groups=groups(run.results), comparison=comparison, regression_passed=passed)
        run.save(update_fields=["status", "report", "results"])
    for run in runs:
        (output / f"{run.id}.json").write_text(json.dumps(run.report, ensure_ascii=False, indent=2), encoding="utf-8")
        (output / f"{run.id}.md").write_text(markdown(run.report), encoding="utf-8")
    counts = seed_samples(app, runs)
    Experiment.objects.get_or_create(application_id=app.id, workspace_id=app.workspace_id,
        name=f"{MARKER}·50/50分流演示（未启动）", defaults={"created_by": app.user_id,
            "variants": [{"key": "control", "weight": 5000}, {"key": "treatment", "weight": 5000}],
            "config_snapshot": {"note": "仅演示分组配置，未进行线上分流或效果对比。"}})
    emit(action="complete", datasets=len(datasets), questions=sum(len(d.cases) for d in datasets),
         runs=[str(r.id) for r in runs], counts=counts, output=str(output))


if __name__ == "__main__":
    main()
