from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from .intent import validate_behavior_intent_metadata
from .profile import RCLValidationError, validate_schema


INTENT_PROPOSER_VERSION = "0.1"
INTENT_PROPOSER_METHOD = "rcl.intent.hypothesis_proposer.v0.1"
PROPOSER_KINDS = (
    "human",
    "rule_based",
    "llm",
    "vlm",
    "external_model",
    "other",
)
SELF_CONFIDENCE_SEMANTICS = "proposer_self_reported_non_normative"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _parse_datetime(value: str, *, label: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RCLValidationError(f"{label}: invalid date-time {value!r}") from exc
    if result.tzinfo is None:
        raise RCLValidationError(f"{label}: date-time must include a timezone")
    return result


def _proposal_material(proposal: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in proposal.items() if key != "proposal_id"}


def expected_intent_hypothesis_proposal_id(proposal: dict[str, Any]) -> str:
    digest = _sha256_json(_proposal_material(proposal))[:16]
    return f"intent-proposal-{digest}"


def intent_hypothesis_proposal_sha256(proposal: dict[str, Any]) -> str:
    return _sha256_json(proposal)


def _validate_proposed_intent(intent: dict[str, Any]) -> None:
    synthetic = {
        "behaviors": [
            {
                "behavior_id": "x.rcl.intent_proposer_candidate",
                "parameters": {},
                "preservation": {"priority": "optional", "mode": "semantic"},
                "intent": intent,
            }
        ]
    }
    validate_schema(synthetic, "behavior")
    validate_behavior_intent_metadata(synthetic)


def validate_intent_hypothesis_proposal(proposal: dict[str, Any]) -> None:
    """Validate an untrusted proposer envelope without granting it authority."""

    validate_schema(proposal, "intent-hypothesis-proposal")
    _parse_datetime(proposal["created_at"], label="proposal.created_at")

    expected = expected_intent_hypothesis_proposal_id(proposal)
    if proposal["proposal_id"] != expected:
        raise RCLValidationError(
            f"Intent hypothesis proposal_id does not match proposal material: expected {expected}"
        )

    if proposal["proposer"]["kind"] not in PROPOSER_KINDS:
        raise RCLValidationError(f"Unsupported proposer kind: {proposal['proposer']['kind']}")

    if proposal["status"] != "proposed" or proposal["approved"] is not False:
        raise RCLValidationError("Proposer envelopes must remain proposed and not approved")
    if proposal["non_mutating"] is not True:
        raise RCLValidationError("Proposer envelopes must declare non_mutating=true")
    if proposal["self_confidence_semantics"] != SELF_CONFIDENCE_SEMANTICS:
        raise RCLValidationError("Unsupported proposer self-confidence semantics")

    _validate_proposed_intent(proposal["proposed_intent"])


def build_intent_hypothesis_proposal(
    *,
    created_at: str,
    proposer: dict[str, Any],
    candidate_action_id: str,
    context_match: dict[str, Any],
    outcome: dict[str, Any],
    proposed_intent: dict[str, Any],
    rationale_summary: str,
    evidence_refs: list[str] | tuple[str, ...] = (),
    self_confidence: float | None = None,
) -> dict[str, Any]:
    """Build a deterministic proposal envelope from external proposer output."""

    proposal: dict[str, Any] = {
        "intent_hypothesis_proposal_version": INTENT_PROPOSER_VERSION,
        "method": INTENT_PROPOSER_METHOD,
        "proposal_id": "intent-proposal-0000000000000000",
        "created_at": created_at,
        "status": "proposed",
        "non_mutating": True,
        "approved": False,
        "proposer": copy.deepcopy(proposer),
        "candidate_action_id": candidate_action_id,
        "context_match": copy.deepcopy(context_match),
        "outcome": copy.deepcopy(outcome),
        "proposed_intent": copy.deepcopy(proposed_intent),
        "rationale_summary": rationale_summary,
        "evidence_refs": list(evidence_refs),
        "self_confidence": self_confidence,
        "self_confidence_semantics": SELF_CONFIDENCE_SEMANTICS,
    }
    proposal["proposal_id"] = expected_intent_hypothesis_proposal_id(proposal)
    validate_intent_hypothesis_proposal(proposal)
    return proposal


@dataclass(frozen=True)
class ProposerMetadata:
    proposer_id: str
    kind: str
    provider: str | None = None
    model: str | None = None
    tool: str | None = None
    version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "kind": self.kind,
            "proposer_id": self.proposer_id,
        }
        for key in ("provider", "model", "tool", "version"):
            value = getattr(self, key)
            if value is not None:
                result[key] = value
        return result


@runtime_checkable
class IntentHypothesisProposer(Protocol):
    """Minimal vendor-neutral contract for third-party WHY hypothesis proposers."""

    @property
    def metadata(self) -> ProposerMetadata:
        ...

    def propose(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        ...


def run_intent_hypothesis_proposer(
    proposer: IntentHypothesisProposer,
    request: dict[str, Any],
) -> list[dict[str, Any]]:
    """Run a proposer and validate its envelopes as untrusted interchange data."""

    metadata = proposer.metadata
    if metadata.kind not in PROPOSER_KINDS:
        raise RCLValidationError(f"Unsupported proposer kind: {metadata.kind}")
    if not metadata.proposer_id:
        raise RCLValidationError("Proposer metadata requires proposer_id")

    proposals = proposer.propose(copy.deepcopy(request))
    if not isinstance(proposals, list):
        raise RCLValidationError("Intent proposer must return a list of proposal envelopes")

    expected_metadata = metadata.to_dict()
    validated: list[dict[str, Any]] = []
    for index, proposal in enumerate(proposals):
        if not isinstance(proposal, dict):
            raise RCLValidationError(f"Intent proposer result {index} must be an object")
        validate_intent_hypothesis_proposal(proposal)
        if proposal["proposer"] != expected_metadata:
            raise RCLValidationError(
                f"Intent proposer result {index} metadata does not match proposer metadata"
            )
        validated.append(copy.deepcopy(proposal))
    return validated


class DeterministicReferenceProposer:
    """Reference-only proposer used to exercise the plugin boundary without AI inference."""

    def __init__(self) -> None:
        self._metadata = ProposerMetadata(
            proposer_id="rcl.reference.intent-proposer",
            kind="rule_based",
            provider="rcl",
            tool="deterministic_reference",
            version=INTENT_PROPOSER_VERSION,
        )

    @property
    def metadata(self) -> ProposerMetadata:
        return self._metadata

    def propose(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        required = (
            "created_at",
            "candidate_action_id",
            "context_match",
            "outcome",
            "proposed_intent",
            "rationale_summary",
        )
        missing = [key for key in required if key not in request]
        if missing:
            raise RCLValidationError(
                "Reference proposer request missing fields: " + ", ".join(missing)
            )
        return [
            build_intent_hypothesis_proposal(
                created_at=request["created_at"],
                proposer=self.metadata.to_dict(),
                candidate_action_id=request["candidate_action_id"],
                context_match=request["context_match"],
                outcome=request["outcome"],
                proposed_intent=request["proposed_intent"],
                rationale_summary=request["rationale_summary"],
                evidence_refs=request.get("evidence_refs", []),
                self_confidence=request.get("self_confidence"),
            )
        ]


def proposal_to_raw_discovery_dataset(
    proposal: dict[str, Any],
    *,
    dataset_id: str,
    episodes: list[dict[str, Any]],
) -> dict[str, Any]:
    """Combine a hypothesis proposal with caller-supplied raw evidence episodes.

    The episodes are copied exactly. This helper never invents or reconstructs
    observations.
    """

    validate_intent_hypothesis_proposal(proposal)
    dataset = {
        "discovery_dataset_version": "0.1",
        "dataset_id": dataset_id,
        "candidate_action_id": proposal["candidate_action_id"],
        "context_match": copy.deepcopy(proposal["context_match"]),
        "outcome": copy.deepcopy(proposal["outcome"]),
        "proposed_intent": copy.deepcopy(proposal["proposed_intent"]),
        "episodes": copy.deepcopy(episodes),
    }
    validate_schema(dataset, "intent-discovery-dataset")
    return dataset


def proposal_to_summary_hypothesis(
    proposal: dict[str, Any],
    *,
    dataset_id: str,
) -> dict[str, Any]:
    """Convert only hypothesis metadata; no aggregate statistics are fabricated."""

    validate_intent_hypothesis_proposal(proposal)
    hypothesis = {
        "summary_hypothesis_version": "0.1",
        "dataset_id": dataset_id,
        "candidate_action_id": proposal["candidate_action_id"],
        "context_match": copy.deepcopy(proposal["context_match"]),
        "outcome": copy.deepcopy(proposal["outcome"]),
        "proposed_intent": copy.deepcopy(proposal["proposed_intent"]),
    }
    validate_schema(hypothesis, "intent-summary-hypothesis")
    return hypothesis
