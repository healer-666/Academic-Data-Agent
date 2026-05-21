from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from data_analysis_agent.skills.datascibench_artifact import (  # noqa: E402,F401
    ARTIFACT_EXTENSIONS,
    ARTIFACT_LITERAL_RE,
    CONTRACT_GROUPS,
    DataSciBenchArtifactContract,
    DataSciBenchMetricSpec,
    load_artifact_contract,
    render_contract_summary,
    should_apply_contract,
    task_group_from_id,
    validate_artifact_contract,
)
