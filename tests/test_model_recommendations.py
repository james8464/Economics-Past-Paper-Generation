from __future__ import annotations

import copy
import json

import pytest

from Backend.Core.model_recommendations import (
    MODEL_RECOMMENDATIONS_PATH,
    default_ollama_model,
    parse_model_recommendations,
)


def payload() -> dict[str, object]:
    return json.loads(MODEL_RECOMMENDATIONS_PATH.read_text(encoding="utf-8"))


def test_recommendation_registry_is_contiguous_and_owns_cli_default() -> None:
    recommendations = parse_model_recommendations(payload())

    assert recommendations.default_model == default_ollama_model()
    assert recommendations.tiers[0].minimum_memory_gb == 0
    assert recommendations.tiers[0].maximum_memory_gb == 16
    assert recommendations.tiers[1].minimum_memory_gb == 16
    assert recommendations.tiers[-1].maximum_memory_gb is None
    assert "results" in recommendations.other_model_warning.casefold()


def test_recommendation_registry_rejects_memory_gaps() -> None:
    value = copy.deepcopy(payload())
    value["tiers"][1]["minimum_memory_gb"] = 17

    with pytest.raises(ValueError, match="contiguous"):
        parse_model_recommendations(value)


def test_default_model_must_be_a_declared_recommendation() -> None:
    value = copy.deepcopy(payload())
    value["default_model"] = "undeclared:model"

    with pytest.raises(ValueError, match="default_model"):
        parse_model_recommendations(value)
