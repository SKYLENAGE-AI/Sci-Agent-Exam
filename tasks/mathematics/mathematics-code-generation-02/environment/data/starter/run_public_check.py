from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from cpcw_audit import run_audit


SUMMARY_FIELDS = [
    "instance_summaries",
    "feasibility_summaries",
    "parameter_review_summaries",
    "source_claim_summaries",
    "policy_summaries",
    "review_recommendation",
    "review_blockers",
]


def digest_summary(answer):
    summary = {key: answer[key] for key in SUMMARY_FIELDS}
    blob = json.dumps(summary, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


def main() -> int:
    data_dir = Path(os.environ.get("DATA_DIR", "/home/agent/data"))
    check_path = data_dir / "cpcw_public_check.json"
    expected = json.loads(check_path.read_text(encoding="utf-8"))["summary_sha256"]
    actual = digest_summary(
        run_audit(
            data_dir / "cpcw_instances.json",
            data_dir / "cpcw_feasibility_cases.json",
            data_dir / "cpcw_source_claims.json",
            data_dir / "cpcw_review_policy.json",
        )
    )
    print(f"summary_sha256={actual}")
    print(f"match={str(actual == expected).lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
