from __future__ import annotations

import json

from tools.live_generation_matrix import REGISTRY_PATH, matrix_jobs, matrix_markdown


def jobs():
    return matrix_jobs(json.loads(REGISTRY_PATH.read_text(encoding="utf-8")))


def test_live_matrix_is_derived_from_every_advertised_registry_paper() -> None:
    value = jobs()

    assert len(value) == 18
    assert [job.seed_offset for job in value] == list(range(18))
    assert len({job.id for job in value}) == 18
    assert {job.backend_subject for job in value} == {
        "accounting_aqa",
        "business_aqa",
        "computer_science",
        "computer_science_ocr",
        "economics",
        "economics_aqa",
        "economics_ocr",
    }
    assert all("assessment_package" in job.expected_roles for job in value)


def test_live_matrix_markdown_reports_failures_without_false_success() -> None:
    report = {
        "model": "test:model",
        "summary": {"papers": 1, "passed": 0, "failed": 1},
        "results": [
            {
                "family_id": "test/family",
                "paper": "1",
                "passed": False,
                "duration_seconds": 12.2,
                "errors": ["model rejected the schema"],
            }
        ],
    }

    rendered = matrix_markdown(report)
    assert "0/1 papers passed" in rendered
    assert "model rejected the schema" in rendered
