from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.core import config
from scripts import gemini_diagnostics


class GeminiConfigurationTests(unittest.TestCase):
    def test_only_repository_root_dotenv_is_loaded_and_process_values_win(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".env").write_text(
                "GEMINI_API_KEY=file-secret\nGEMINI_MODEL=file-model\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {
                "GEMINI_API_KEY": "process-secret",
                "GEMINI_MODEL": "process-model",
            }, clear=True), patch("app.core.config.get_repository_root", return_value=root):
                config.load_local_environment()
                self.assertEqual(config.get_gemini_model(), "process-model")
                self.assertEqual(config.get_gemini_api_key(), "process-secret")

    def test_root_dotenv_supplies_model_when_process_override_is_absent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".env").write_text("GEMINI_API_KEY=file-secret\nGEMINI_MODEL=file-model\n", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True), patch(
                "app.core.config.get_repository_root", return_value=root
            ):
                config.load_local_environment()
                self.assertEqual(config.get_gemini_model(), "file-model")


class GeminiDiagnosticTests(unittest.TestCase):
    def test_model_discovery_filters_generate_content_models(self) -> None:
        class Models:
            @staticmethod
            def list():
                return [
                    type("Item", (), {"name": "models/a", "supported_actions": ["generateContent"]})(),
                    type("Item", (), {"name": "models/b", "supported_actions": ["embedContent"]})(),
                ]

        class Client:
            models = Models()

            @staticmethod
            def close():
                pass

        with patch.object(gemini_diagnostics, "_create_gemini_client", return_value=Client()), patch(
            "app.core.config.get_gemini_model", return_value="a"
        ):
            result = gemini_diagnostics.discover_models()
        self.assertTrue(result["success"])
        self.assertEqual(result["generate_content_models"], ["a"])

    def test_selected_model_probe_sends_one_minimal_unstructured_request(self) -> None:
        class Models:
            calls = []

            def generate_content(self, **kwargs):
                self.calls.append(kwargs)
                return type("Response", (), {"text": "OK"})()

        class Client:
            models = Models()

            @staticmethod
            def close():
                pass

        client = Client()
        with patch.object(gemini_diagnostics, "_create_gemini_client", return_value=client):
            result = gemini_diagnostics.test_model("selected-model")
        self.assertTrue(result["success"])
        self.assertEqual(result["model"], "selected-model")
        self.assertFalse(result["structured_output_requested"])
        self.assertEqual(len(client.models.calls), 1)
        self.assertEqual(client.models.calls[0]["model"], "selected-model")
        config = client.models.calls[0]["config"]
        self.assertFalse(config.tools)
        self.assertTrue(config.automatic_function_calling.disable)

    def test_sdk_afc_warning_is_suppressed_without_tools(self) -> None:
        from google.genai import types
        from google.genai.models import Models, _GenerateContentConfig_to_mldev

        sdk_models = Models(Mock())
        response = types.GenerateContentResponse()
        with (
            patch.object(sdk_models, "_generate_content", return_value=response) as send,
            patch("google.genai.models.logger.warning") as warning,
        ):
            actual = sdk_models.generate_content(
                model="test-model",
                contents="Reply OK",
                config=types.GenerateContentConfig(
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(
                        disable=True
                    )
                ),
            )
        self.assertIs(actual, response)
        send.assert_called_once()
        warning.assert_not_called()
        api_client = Mock()
        api_client.vertexai = False
        wire_config = _GenerateContentConfig_to_mldev(
            api_client,
            types.GenerateContentConfig(
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    disable=True
                )
            ),
        )
        self.assertEqual(wire_config, {})


if __name__ == "__main__":
    unittest.main()
