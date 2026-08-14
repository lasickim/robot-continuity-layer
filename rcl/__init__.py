from .adapter import BehaviorMigrationResult, RCLAdapter
from .capabilities import (
    CapabilityClassification,
    CapabilityValidationError,
    classify_capability_id,
    get_capability,
    load_capability_registry,
    registered_capabilities,
    reserved_namespaces,
    validate_capability_id,
    validate_capability_set,
)
from .conformance import run_adapter_conformance
from .evaluation import (
    EVALUATION_METHOD,
    EVALUATION_VERSION,
    evaluate_observed_continuity,
    validate_behavior_evaluation_metadata,
)
from .migration import migrate_profile
from .profile import RCLProfile, RCLValidationError, RCL_VERSION
from .score import calculate_continuity_score
from .statistical_evaluation import (
    DEFAULT_MIN_TRIALS,
    STATISTICAL_EVALUATION_METHOD,
    STATISTICAL_EVALUATION_VERSION,
    compare_trial_distributions,
    sample_mean,
    sample_std,
    wasserstein_1d,
)

__all__ = [
    "BehaviorMigrationResult",
    "CapabilityClassification",
    "CapabilityValidationError",
    "DEFAULT_MIN_TRIALS",
    "EVALUATION_METHOD",
    "EVALUATION_VERSION",
    "RCLAdapter",
    "RCLProfile",
    "RCLValidationError",
    "RCL_VERSION",
    "STATISTICAL_EVALUATION_METHOD",
    "STATISTICAL_EVALUATION_VERSION",
    "calculate_continuity_score",
    "classify_capability_id",
    "compare_trial_distributions",
    "evaluate_observed_continuity",
    "get_capability",
    "load_capability_registry",
    "migrate_profile",
    "registered_capabilities",
    "reserved_namespaces",
    "run_adapter_conformance",
    "sample_mean",
    "sample_std",
    "validate_behavior_evaluation_metadata",
    "validate_capability_id",
    "validate_capability_set",
    "wasserstein_1d",
]
