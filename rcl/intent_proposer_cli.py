from __future__ import annotations

import argparse
import json
from pathlib import Path

from .intent_proposer import (
    intent_hypothesis_proposal_sha256,
    validate_intent_hypothesis_proposal,
)


def _read_json(path: str | Path):
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rcl inspect-intent-proposal")
    parser.add_argument("proposal")
    parser.add_argument("--json", action="store_true")
    return parser


def run(argv: list[str]) -> int:
    args = _parser().parse_args(argv)
    proposal = _read_json(args.proposal)
    validate_intent_hypothesis_proposal(proposal)
    digest = intent_hypothesis_proposal_sha256(proposal)
    proposer = proposal["proposer"]

    if args.json:
        print(
            json.dumps(
                {
                    "proposal": proposal,
                    "proposal_sha256": digest,
                    "rcl_confidence_evaluated": False,
                    "profile_mutated": False,
                    "approval_granted": False,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    print("RCL Intent Hypothesis Proposal")
    print(f"Proposal: {proposal['proposal_id']}")
    print(f"SHA-256: {digest}")
    print(f"Proposer: {proposer['kind']} / {proposer['proposer_id']}")
    if proposer.get("provider"):
        print(f"Provider: {proposer['provider']}")
    if proposer.get("model"):
        print(f"Model: {proposer['model']}")
    if proposer.get("tool"):
        print(f"Tool: {proposer['tool']}")
    print(f"Goal: {proposal['proposed_intent']['goal_id']}")
    print(f"Action: {proposal['candidate_action_id']}")
    print(f"Context: {proposal['context_match']}")
    confidence = proposal["self_confidence"]
    confidence_text = "N/A" if confidence is None else f"{confidence:.3f}"
    print(f"Proposer Self-Confidence: {confidence_text} (NON-NORMATIVE)")
    print("RCL Confidence Evaluated: NO")
    print("Approved: NO")
    print("Profile Mutation: NO")
    print("Next: combine this hypothesis with observed evidence and run Intent Discovery.")
    return 0
