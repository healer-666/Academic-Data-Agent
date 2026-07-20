from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from data_analysis_agent.agent_runner import _should_enable_search, _should_request_search  # noqa: E402
from data_analysis_agent.config import RuntimeConfig  # noqa: E402
from data_analysis_agent.reporting import ReportTelemetry  # noqa: E402
from data_analysis_agent.runtime_models import AgentStepTrace  # noqa: E402
from data_analysis_agent.tooling_service import (  # noqa: E402
    append_search_disclosure,
    collect_search_sources,
    determine_search_status,
)
from data_analysis_agent.tools.tavily_search import TavilySearchTool  # noqa: E402


class WebSearchFlowTests(unittest.TestCase):
    def _search_trace(self) -> AgentStepTrace:
        observation = json.dumps(
            {
                "status": "success",
                "text": "Search results",
                "data": {
                    "query": "current benchmark",
                    "results": [
                        {
                            "title": "Primary source",
                            "url": "https://example.test/source",
                            "content": "A concise source summary.",
                        },
                        {
                            "title": "Duplicate",
                            "url": "https://example.test/source",
                            "content": "Duplicate URL.",
                        },
                        {
                            "title": "Unsafe",
                            "url": "javascript:alert(1)",
                            "content": "Ignored.",
                        },
                    ],
                },
            }
        )
        return AgentStepTrace(
            step_index=1,
            raw_response="{}",
            action="call_tool",
            tool_name="TavilySearchTool",
            tool_input="current benchmark",
            tool_status="success",
            observation=observation,
        )

    def test_search_need_is_driven_by_task_content_not_quality_mode(self):
        data_context = SimpleNamespace(columns=("value", "group"))

        self.assertTrue(
            _should_request_search(
                data_context=data_context,
                query="请查找现行行业标准并解释差异",
                task_type="general_analysis",
            )
        )
        self.assertTrue(
            _should_request_search(
                data_context=data_context,
                query="完成赛题",
                task_type="mathematical_modeling",
            )
        )
        self.assertFalse(
            _should_request_search(
                data_context=data_context,
                query="计算各组均值",
                task_type="general_analysis",
            )
        )

        runtime_config = RuntimeConfig(
            model_id="demo",
            api_key="model-key",
            base_url="https://models.example.test/v1",
            tavily_api_key="search-key",
        )
        self.assertTrue(
            _should_enable_search(
                runtime_config=runtime_config,
                data_context=data_context,
                query="查找最新政策",
                quality_mode="draft",
                latency_mode="fast",
            )
        )
        self.assertFalse(
            _should_enable_search(
                runtime_config=runtime_config,
                data_context=data_context,
                query="计算各组均值",
                quality_mode="publication",
                latency_mode="quality",
            )
        )

    def test_missing_search_service_is_explicit_and_non_blocking(self):
        status, notes = determine_search_status(
            (),
            ReportTelemetry(),
            search_requested=True,
            search_configured=False,
        )

        self.assertEqual(status, "unavailable")
        self.assertIn("继续", notes)
        report = append_search_disclosure(
            "# Report",
            search_status=status,
            search_notes=notes,
            search_sources=(),
        )
        self.assertIn("联网搜索与外部来源", report)
        self.assertIn("未使用外部搜索结果", report)

    def test_search_sources_are_deduplicated_and_written_to_report(self):
        sources = collect_search_sources((self._search_trace(),))

        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["url"], "https://example.test/source")
        report = append_search_disclosure(
            "# Report",
            search_status="used",
            search_notes="Used external context.",
            search_sources=sources,
        )
        self.assertIn("[Primary source](<https://example.test/source>)", report)
        self.assertIn("当前任务结论仍来自本次上传的数据", report)

    def test_runtime_tavily_key_is_injected_without_global_environment_mutation(self):
        captured: dict[str, str] = {}

        class FakeTavilyClient:
            def __init__(self, api_key: str):
                captured["api_key"] = api_key

            def search(self, **kwargs):
                return {"results": []}

        fake_module = SimpleNamespace(TavilyClient=FakeTavilyClient)
        with patch.dict(os.environ, {}, clear=True), patch.dict(sys.modules, {"tavily": fake_module}):
            result = TavilySearchTool(api_key="runtime-search-key").execute({"query": "demo"})
            self.assertNotIn("TAVILY_API_KEY", os.environ)

        self.assertEqual(result.status.value, "success")
        self.assertEqual(captured["api_key"], "runtime-search-key")


if __name__ == "__main__":
    unittest.main()
