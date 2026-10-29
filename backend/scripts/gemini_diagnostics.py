"""Discover models or run one explicitly authorized minimal Gemini request."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

from google.genai import types

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_gemini_model
from app.services.translation import (
    GEMINI_REQUEST_TIMEOUT_MS,
    _create_gemini_client,
    _provider_status,
    safe_provider_error,
)


def _error_result(error: Exception, model: str | None) -> dict[str, object]:
    safe_error = safe_provider_error(error, model=model or "(not selected)")
    return {
        "success": False,
        "http_status": safe_error.status_code or _provider_status(error),
        "error_category": safe_error.category,
        "provider_reason": safe_error.provider_reason,
        "safe_message": str(safe_error),
        "model": model,
    }


def discover_models() -> dict[str, object]:
    client = None
    selected_model = None
    try:
        selected_model = get_gemini_model()
        client = _create_gemini_client()
        models = []
        for item in client.models.list():
            actions = getattr(item, "supported_actions", None) or ()
            name = getattr(item, "name", "") or ""
            model_id = name.removeprefix("models/")
            if "generateContent" in actions and model_id:
                models.append(model_id)
        return {
            "success": True,
            "configured_model": selected_model,
            "generate_content_models": sorted(set(models)),
        }
    except Exception as error:
        return _error_result(error, selected_model)
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()


def test_model(model: str) -> dict[str, object]:
    started = time.perf_counter()
    client: Any = None
    if re.fullmatch(r"[A-Za-z0-9._/-]{1,100}", model) is None:
        return {
            "success": False,
            "http_status": None,
            "error_category": "permanent",
            "provider_reason": None,
            "safe_message": "The selected model identifier has an invalid format.",
            "elapsed_ms": 0,
            "model": None,
            "structured_output_requested": False,
            "request_timeout_ms": GEMINI_REQUEST_TIMEOUT_MS,
        }
    try:
        client = _create_gemini_client()
        response = client.models.generate_content(
            model=model,
            contents="Reply with the single word OK.",
            config=types.GenerateContentConfig(
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    disable=True
                )
            ),
        )
        text = getattr(response, "text", None)
        return {
            "success": isinstance(text, str) and bool(text.strip()),
            "http_status": None,
            "error_category": None,
            "provider_reason": None,
            "safe_message": None if isinstance(text, str) and text.strip() else "Gemini returned an empty response.",
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "model": model,
            "structured_output_requested": False,
            "request_timeout_ms": GEMINI_REQUEST_TIMEOUT_MS,
        }
    except Exception as error:
        result = _error_result(error, model)
        result.update({
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "structured_output_requested": False,
            "request_timeout_ms": GEMINI_REQUEST_TIMEOUT_MS,
        })
        return result
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="List accessible models supporting generateContent.")
    probe = subparsers.add_parser("test", help="Send one minimal request to a selected model.")
    probe.add_argument("--model", default=None, help="Model ID; defaults to GEMINI_MODEL.")
    probe.add_argument("--confirm-live", action="store_true", help="Authorize one provider generation request.")
    args = parser.parse_args()

    if args.command == "list":
        result = discover_models()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["success"] else 1

    if not args.confirm_live:
        print(json.dumps({
            "success": False,
            "live_generation_call_made": False,
            "message": "Refusing to generate content without --confirm-live.",
        }, indent=2))
        return 2
    try:
        selected_model = args.model or get_gemini_model()
    except Exception as error:
        print(json.dumps(_error_result(error, None), ensure_ascii=False, indent=2))
        return 1
    result = test_model(selected_model)
    result["live_generation_call_made"] = True
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
