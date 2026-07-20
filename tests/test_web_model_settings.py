from __future__ import annotations

import json
import sys
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from data_analysis_agent.web.model_settings import (  # noqa: E402
    ModelSettingsInput,
    ModelSettingsStore,
    actionable_connection_error,
    test_model_connection as run_connection_test,
    validate_model_settings,
)


class WebModelSettingsTests(unittest.TestCase):
    def _settings(self, *, api_key: str | None = None) -> ModelSettingsInput:
        return ModelSettingsInput(
            model_id="demo-model",
            base_url="https://models.example.test/v1",
            api_key=api_key or f"session-{uuid.uuid4().hex}",
            timeout=30,
        )

    def test_validation_builds_runtime_config_without_changing_environment(self):
        config = validate_model_settings(self._settings())

        self.assertEqual(config.model_id, "demo-model")
        self.assertEqual(config.base_url, "https://models.example.test/v1")
        self.assertEqual(config.timeout, 30)

    def test_validation_rejects_unsafe_or_incomplete_values(self):
        invalid_inputs = [
            ModelSettingsInput("", "https://example.test/v1", "key"),
            ModelSettingsInput("model", "file:///tmp/model", "key"),
            ModelSettingsInput("model", "https://user:pass@example.test/v1", "key"),
            ModelSettingsInput("model", "https://example.test/v1?key=value", "key"),
            ModelSettingsInput("model", "https://example.test/v1", ""),
        ]

        for settings in invalid_inputs:
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                validate_model_settings(settings)

    def test_public_status_never_exposes_api_key(self):
        secret = f"secret-{uuid.uuid4().hex}"
        store = ModelSettingsStore()
        status = store.save(self._settings(api_key=secret))

        serialized = json.dumps(status)
        self.assertNotIn(secret, serialized)
        self.assertTrue(status["apiKeyConfigured"])
        self.assertEqual(status["source"], "web")

    def test_connection_test_makes_one_minimal_call(self):
        config = validate_model_settings(self._settings())
        client = MagicMock()

        with patch("data_analysis_agent.web.model_settings.build_llm", return_value=client):
            message = run_connection_test(config)

        self.assertIn("连接成功", message)
        client.invoke.assert_called_once()
        args, kwargs = client.invoke.call_args
        self.assertEqual(args[0][0]["role"], "user")
        self.assertEqual(kwargs["max_tokens"], 8)

    def test_connection_errors_are_actionable_and_redacted(self):
        secret = f"secret-{uuid.uuid4().hex}"
        error = RuntimeError(f"401 Unauthorized for token {secret}")

        message = actionable_connection_error(error, secret)

        self.assertIn("认证失败", message)
        self.assertNotIn(secret, message)

    def test_history_qa_error_redacts_web_api_key(self):
        from data_analysis_agent.history_qa import answer_history_question

        secret = f"secret-{uuid.uuid4().hex}"
        config = validate_model_settings(self._settings(api_key=secret))

        with (
            patch("data_analysis_agent.history_qa.retrieve_history_context") as retrieve,
            patch("data_analysis_agent.history_qa.build_llm") as build,
        ):
            history_slice = SimpleNamespace(
                run_id="run-demo",
                source_type="report",
                review_status="accepted",
                text="demo result",
                title="Demo",
            )
            retrieve.return_value.records = (object(),)
            retrieve.return_value.slices = (history_slice,)
            retrieve.return_value.mode = "single"
            build.side_effect = RuntimeError(f"provider rejected {secret}")
            answer = answer_history_question("demo", runtime_config_override=config)

        self.assertNotIn(secret, json.dumps(answer.warnings))
        self.assertIn("[REDACTED]", answer.warnings[0])


if __name__ == "__main__":
    unittest.main()
