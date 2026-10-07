# coding=utf-8
"""Optional dependency integration tests; no provider requests are made."""
import asyncio
import json
import os
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


class RagasTests(unittest.TestCase):
    def test_real_adapters_and_scoring_contract(self):
        try:
            import ragas  # noqa: F401
        except ImportError:
            self.skipTest("Install rag_eval/requirements.txt to verify RAGAS adapters")
        from rag_eval.judge import Judge

        config = json.loads((Path(__file__).parents[1] / "examples/config.json").read_text(encoding="utf-8-sig"))
        with patch.dict(os.environ, {"JUDGE_API_KEY": "test", "EMBEDDING_API_KEY": "test"}):
            judge = Judge(config["judge"])
        case = {"question": "q", "ground_truth": "a"}
        with patch.object(judge.faithfulness, "single_turn_ascore", AsyncMock(return_value=0.8)), \
                patch.object(judge.relevancy, "single_turn_ascore", AsyncMock(return_value=0.9)), \
                patch.object(judge.completeness, "single_turn_ascore", AsyncMock(return_value=1.0)), \
                patch.object(judge, "rubric", return_value=(0.7, "covers key points")):
            scores, reasons, errors = asyncio.run(judge.score(case, "a", [{"content": "a"}]))
        self.assertEqual(errors, {})
        self.assertEqual(scores["faithfulness"], 0.8)
        self.assertEqual(scores["completeness"], 1)
        self.assertEqual(scores["keypoint_coverage"], 0.7)
        self.assertIn("keypoint_coverage", reasons)
        with patch.object(judge.relevancy, "single_turn_ascore", AsyncMock(side_effect=TimeoutError)), \
                patch.object(judge.completeness, "single_turn_ascore", AsyncMock(return_value=1.0)), \
                patch.object(judge, "rubric", return_value=(0.7, "reason")):
            scores, _, errors = asyncio.run(judge.score(case, "a", None))
        self.assertIsNone(scores["faithfulness"])
        self.assertIsNone(scores["answer_relevancy"])
        self.assertIn("answer_relevancy", errors)
