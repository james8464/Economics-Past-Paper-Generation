from __future__ import annotations

import json
import sys
from types import ModuleType

import pytest

from Backend.Core.providers import (
    HostedLLMClient,
    _ollama_json_schema,
    _ollama_output_budget,
    _ollama_temperature,
)


def test_apple_provider_loads_model_once(monkeypatch) -> None:
    calls = {"load": 0, "generate": 0}
    module = ModuleType("mlx_lm")

    def load(model_name: str) -> tuple[object, object]:
        calls["load"] += 1
        assert model_name == "test-model"
        return object(), object()

    def generate(
        _model: object,
        _tokenizer: object,
        *,
        prompt: str,
        max_tokens: int,
        verbose: bool,
    ) -> str:
        calls["generate"] += 1
        assert max_tokens == 4096
        assert verbose is False
        return f'{{"prompt": "{prompt}"}}'

    module.load = load
    module.generate = generate
    monkeypatch.setitem(sys.modules, "mlx_lm", module)
    client = HostedLLMClient(
        provider="apple",
        model="test-model",
        api_key="",
    )

    assert client.generate_json("first") == {"prompt": "first"}
    assert client.generate_json("second") == {"prompt": "second"}
    assert calls == {"load": 1, "generate": 2}
    assert client.supports_parallel_generation is False


def test_remote_hosted_providers_allow_parallel_generation() -> None:
    assert HostedLLMClient(
        provider="openai",
        model="test-model",
        api_key="test-key",
    ).supports_parallel_generation
    assert HostedLLMClient(
        provider="anthropic",
        model="test-model",
        api_key="test-key",
    ).supports_parallel_generation


def test_client_repairs_one_invalid_structured_response(monkeypatch) -> None:
    client = HostedLLMClient(
        provider="ollama",
        model="test-model",
        api_key="",
    )
    prompts: list[str] = []

    def generate(prompt: str) -> dict[str, object]:
        prompts.append(prompt)
        if len(prompts) == 1:
            raise ValueError("truncated JSON")
        return {"ok": True}

    monkeypatch.setattr(client, "_ollama", generate)

    assert client.generate_json("Return JSON.") == {"ok": True}
    assert len(prompts) == 2
    assert "REPAIR INSTRUCTION" in prompts[1]


def test_client_stops_after_one_structured_response_repair(monkeypatch) -> None:
    client = HostedLLMClient(
        provider="ollama",
        model="test-model",
        api_key="",
    )
    monkeypatch.setattr(
        client,
        "_ollama",
        lambda _prompt: (_ for _ in ()).throw(ValueError("invalid")),
    )

    with pytest.raises(ValueError, match="invalid"):
        client.generate_json("Return JSON.")


def test_ollama_schema_constrains_shared_generation_and_review() -> None:
    generation = _ollama_json_schema(
        'Return one JSON object with a `questions` array. '
        'BLUEPRINT_DATA=[{"id":"0/0/0"},{"id":"0/0/1"}]'
    )
    review = _ollama_json_schema(
        'Return JSON only: `reviews` must contain one object per id. '
        'REVIEW_DATA=[{"id":"0/0/0"},{"id":"0/0/1"}]'
    )

    assert generation["required"] == ["questions"]
    assert generation["properties"]["questions"]["type"] == "array"
    assert generation["properties"]["questions"]["minItems"] == 2
    assert generation["properties"]["questions"]["maxItems"] == 2
    assert review["required"] == ["reviews"]
    assert review["properties"]["reviews"]["minItems"] == 2
    assert review["properties"]["reviews"]["maxItems"] == 2
    review_fields = review["properties"]["reviews"]["items"]["required"]
    assert "difficulty_issues" in review_fields
    assert "ambiguity_issues" in review_fields
    assert _ollama_output_budget(generation) == 3072
    assert _ollama_output_budget(review) == 1024


def test_ollama_uses_structured_chat_with_bounded_output(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, _limit: int) -> bytes:
            return json.dumps(
                {
                    "message": {
                        "content": '{"questions":[]}',
                    },
                    "done_reason": "stop",
                }
            ).encode()

    def request(
        url: str,
        data: bytes,
        _headers: dict[str, str],
        *,
        attempts: int,
    ) -> _Response:
        captured.update(
            {
                "url": url,
                "payload": json.loads(data),
                "attempts": attempts,
            }
        )
        return _Response()

    monkeypatch.setattr("Backend.Core.providers.urllib_request", request)
    client = HostedLLMClient(
        provider="ollama",
        model="gemma4:12b",
        api_key="",
    )

    assert client.generate_json(
        "Return one JSON object with a `questions` array."
    ) == {"questions": []}
    payload = captured["payload"]
    assert captured["url"] == "http://localhost:11434/api/chat"
    assert captured["attempts"] == 2
    assert payload["messages"][0]["role"] == "user"
    assert payload["think"] is False
    assert payload["options"]["temperature"] == 0.2
    assert payload["options"]["seed"] == 0
    assert payload["options"]["num_predict"] == 2304
    question_schema = payload["format"]["properties"]["questions"]["items"]
    assert question_schema["additionalProperties"] is False
    assert question_schema["properties"]["mark_scheme"]["maxItems"] == 10


def test_second_pass_review_is_deterministic() -> None:
    assert _ollama_temperature(
        "Act as a second-pass UK A-level assessment editor."
    ) == 0
