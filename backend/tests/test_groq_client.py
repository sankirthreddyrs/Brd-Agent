"""Unit tests for the Groq-powered GeminiClient structured generation and retry mechanics."""

import json
from unittest.mock import MagicMock, patch

from groq import APIConnectionError, RateLimitError
from pydantic import BaseModel
import pytest

from app.llm.gemini_client import GeminiClient


class SampleSchema(BaseModel):
    name: str
    count: int
    is_active: bool


def _mock_completion_choice(content: str) -> MagicMock:
    """Helper creating mock chat completion response with specified content."""
    mock_choice = MagicMock()
    mock_choice.message.content = content
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    return mock_response


def test_clean_json_text():
    """Verify markdown code fence stripping and whitespace handling."""
    assert GeminiClient._clean_json_text('{"a": 1}') == '{"a": 1}'
    assert GeminiClient._clean_json_text('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert GeminiClient._clean_json_text('```\n{"a": 1}\n```') == '{"a": 1}'
    assert GeminiClient._clean_json_text('  ```json\n{"a": 1}```  ') == '{"a": 1}'


def test_generate_structured_success():
    """Verify standard single-attempt structured generation."""
    client = GeminiClient(api_key="mock-key", model_name="llama-3.3-70b-versatile")

    mock_json = json.dumps({"name": "Test Project", "count": 42, "is_active": True})
    mock_response = _mock_completion_choice(f"```json\n{mock_json}\n```")

    with patch.object(client.client.chat.completions, "create", return_value=mock_response) as mock_create:
        result = client.generate_structured("Extract project data", SampleSchema)

        assert isinstance(result, SampleSchema)
        assert result.name == "Test Project"
        assert result.count == 42
        assert result.is_active is True

        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["model"] == "llama-3.3-70b-versatile"
        assert call_kwargs["response_format"] == {"type": "json_object"}
        assert len(call_kwargs["messages"]) == 2
        assert "EXPECTED JSON SCHEMA:" in call_kwargs["messages"][1]["content"]


def test_generate_structured_validation_retry_success():
    """Verify corrective retry when initial response fails validation."""
    client = GeminiClient(api_key="mock-key", model_name="llama-3.3-70b-versatile")

    # Attempt 1 returns invalid schema (missing count and is_active)
    bad_json = json.dumps({"name": "Bad Payload"})
    # Attempt 2 returns valid schema
    good_json = json.dumps({"name": "Good Payload", "count": 10, "is_active": False})

    mock_resp1 = _mock_completion_choice(bad_json)
    mock_resp2 = _mock_completion_choice(good_json)

    with patch.object(
        client.client.chat.completions, "create", side_effect=[mock_resp1, mock_resp2]
    ) as mock_create:
        result = client.generate_structured("Generate sample", SampleSchema)

        assert isinstance(result, SampleSchema)
        assert result.name == "Good Payload"
        assert result.count == 10
        assert mock_create.call_count == 2

        # Verify conversation history in second call includes corrective message
        second_call_messages = mock_create.call_args_list[1][1]["messages"]
        assert len(second_call_messages) == 4
        assert second_call_messages[2]["role"] == "assistant"
        assert second_call_messages[3]["role"] == "user"
        assert "CRITICAL VALIDATION ERROR" in second_call_messages[3]["content"]


def test_generate_structured_retry_failure_raises_runtime_error():
    """Verify that multiple consecutive validation failures raise RuntimeError with raw text."""
    client = GeminiClient(api_key="mock-key", model_name="llama-3.3-70b-versatile")

    bad_json = json.dumps({"name": "Still Bad"})
    mock_resp = _mock_completion_choice(bad_json)

    with patch.object(
        client.client.chat.completions, "create", return_value=mock_resp
    ):
        with pytest.raises(RuntimeError) as exc_info:
            client.generate_structured("Generate sample", SampleSchema)

        assert "Failed to generate valid SampleSchema" in str(exc_info.value)
        assert "Still Bad" in str(exc_info.value)


def test_api_level_exponential_backoff_retry():
    """Verify RateLimitError or APIConnectionError triggers backoff and succeeds on retry."""
    client = GeminiClient(api_key="mock-key", model_name="llama-3.3-70b-versatile")

    good_json = json.dumps({"name": "Success After RateLimit", "count": 5, "is_active": True})
    mock_resp = _mock_completion_choice(good_json)

    # First call raises RateLimitError, second call succeeds
    mock_request = MagicMock()
    rate_limit_err = RateLimitError(
        message="Rate limit exceeded",
        response=MagicMock(status_code=429, headers={}),
        body=None,
    )

    with patch.object(
        client.client.chat.completions, "create", side_effect=[rate_limit_err, mock_resp]
    ) as mock_create:
        with patch("time.sleep") as mock_sleep:
            result = client.generate_structured("Generate sample", SampleSchema)

            assert result.name == "Success After RateLimit"
            assert mock_create.call_count == 2
            mock_sleep.assert_called_once_with(2.0)
