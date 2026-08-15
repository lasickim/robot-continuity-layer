from __future__ import annotations

import sys

from .cli_router import main as existing_main
from .goal_governance_cli import run_decision as run_goal_decision
from .goal_governance_cli import run_review as run_goal_review
from .profile import RCLValidationError


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
    return existing_main()


if __name__ == "__main__":
    raise SystemExit(main())
