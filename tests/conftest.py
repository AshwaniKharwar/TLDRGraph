from pathlib import Path

import pytest

from tldrgraph.source_inventory import build_source_inventory


@pytest.fixture
def source_repo(tmp_path: Path) -> Path:
    (tmp_path / "app.py").write_text(
        "def start():\n    return run()\n\ndef run():\n    return {'ok': True}\n",
        encoding="utf-8",
    )
    return tmp_path


def complete_catalog(root: Path, source_hash: str):
    evidence = {"file": "app.py", "symbol": "run", "line": 4,
                "code_start": 4, "code_end": 5}
    feature = {
        "id": "run_application", "area_id": "runtime", "title": "Run application",
        "audience": "developer", "summary": "Run the application and return its result.",
        "workflow_path": ".tldrgraph/workflows/run_application.yaml",
    }
    workflow = {
        "schema": "tldrgraph/feature-workflow@4", "source_hash": source_hash,
        "generator": "feature-workflow-subagent@4", "feature_id": "run_application",
        "title": feature["title"], "summary": "Application execution.", "status": "generated",
        "missing_coverage": "", "evidence": [evidence],
        "steps": [
            {"number": 1, "phase": "backend", "title": "Start",
             "text": "The runtime starts execution.", "evidence": [evidence]},
            {"number": 2, "phase": "backend", "title": "Run",
             "text": "The function performs its work.", "evidence": [evidence]},
            {"number": 3, "phase": "response", "title": "Return",
             "text": "The result is returned.", "evidence": [evidence]},
        ],
    }
    return {
        "schema": "tldrgraph/features@4", "generator": "feature-catalog-agent@4",
        "source_hash": source_hash,
        "areas": [{"id": "runtime", "title": "Runtime", "summary": "Runtime behavior.",
                   "perspective": "technical", "order": 0}],
        "features": [feature],
    }, {"run_application": workflow}


@pytest.fixture
def inventory(source_repo: Path):
    return build_source_inventory(str(source_repo))
