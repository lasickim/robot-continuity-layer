from __future__ import annotations

import sys

from .cli_router import main as existing_main
from .experience_retention_cli import run_archive as run_experience_archive
from .experience_retention_cli import run_evaluate as run_experience_retention
from .goal_governance_cli import run_decision as run_goal_decision
from .goal_governance_cli import run_review as run_goal_review
from .habit_evidence_cli import run_raw as run_habit_evidence
from .habit_evidence_cli import run_summary as run_habit_evidence_summary
from .intent_proposer_cli import run as run_intent_proposal_inspect
from .profile import RCLValidationError
from .provenance_privacy_cli import run_evaluate as run_artifact_governance
from .provenance_privacy_cli import run_record as run_artifact_provenance_record


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "review-goal-proposal":
        try:
            return run_goal_review(sys.argv[2:])
        except (RCLValidationError, ValueError, OSError) as exc:
            print(f"ERROR: {exc}")
            return 2
    if len(sys.argv) >= 2 and sys.argv[1] == "decide-goal-proposal":
        try:
            return run_goal_decision(sys.argv[2:])
        except (RCLValidationError, ValueError, OSError) as exc:
            print(f"ERROR: {exc}")
            return 2
    if len(sys.argv) >= 2 and sys.argv[1] == "inspect-intent-proposal":
        try:
            return run_intent_proposal_inspect(sys.argv[2:])
        except (RCLValidationError, ValueError, OSError) as exc:
            print(f"ERROR: {exc}")
            return 2
    if len(sys.argv) >= 2 and sys.argv[1] == "evaluate-experience-retention":
        try:
            return run_experience_retention(sys.argv[2:])
        except (RCLValidationError, ValueError, OSError) as exc:
            print(f"ERROR: {exc}")
            return 2
    if len(sys.argv) >= 2 and sys.argv[1] == "record-experience-archive":
        try:
            return run_experience_archive(sys.argv[2:])
        except (RCLValidationError, ValueError, OSError) as exc:
            print(f"ERROR: {exc}")
            return 2
    if len(sys.argv) >= 2 and sys.argv[1] == "evaluate-habit-evidence":
        try:
            return run_habit_evidence(sys.argv[2:])
        except (RCLValidationError, ValueError, OSError) as exc:
            print(f"ERROR: {exc}")
            return 2
    if len(sys.argv) >= 2 and sys.argv[1] == "evaluate-habit-evidence-summary":
        try:
            return run_habit_evidence_summary(sys.argv[2:])
        except (RCLValidationError, ValueError, OSError) as exc:
            print(f"ERROR: {exc}")
            return 2
    if len(sys.argv) >= 2 and sys.argv[1] == "record-artifact-provenance":
        try:
            return run_artifact_provenance_record(sys.argv[2:])
        except (RCLValidationError, ValueError, OSError) as exc:
            print(f"ERROR: {exc}")
            return 2
    if len(sys.argv) >= 2 and sys.argv[1] == "evaluate-artifact-governance":
        try:
            return run_artifact_governance(sys.argv[2:])
        except (RCLValidationError, ValueError, OSError) as exc:
            print(f"ERROR: {exc}")
            return 2
    return existing_main()


if __name__ == "__main__":
    raise SystemExit(main())
