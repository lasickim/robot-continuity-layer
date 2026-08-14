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
from .experiment_context import (
    CONTEXT_VERSION,
    DEFAULT_COMPARISON_FIELDS,
    compare_experiment_context,
)
from .habit_policy import (
    HABIT_PROMOTION_METHOD,
    HABIT_PROMOTION_VERSION,
    evaluate_habit_promotion_candidates,
    load_default_habit_promotion_policy,
)
from .history import HABIT_LIFECYCLES, validate_behavior_habit_metadata
from .migration import migrate_profile
from .profile import RCLProfile, RCLValidationError, RCL_VERSION
from .profile_diff import (
    PROFILE_DIFF_METHOD,
    PROFILE_DIFF_VERSION,
    diff_profiles,
)
from .score import calculate_continuity_score
from .session_evaluation import (
    CONFIDENCE_LEVEL,
    DEFAULT_MIN_SESSIONS,
    SESSION_EVALUATION_METHOD,
    SESSION_EVALUATION_VERSION,
    confidence_interval_95,
    evaluate_repeated_sessions,
    t95_critical,
)
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
    "CONFIDENCE_LEVEL",
    "CONTEXT_VERSION",
    "DEFAULT_COMPARISON_FIELDS",
    "DEFAULT_MIN_SESSIONS",
    "DEFAULT_MIN_TRIALS",
    "EVALUATION_METHOD",
    "EVALUATION_VERSION",
    "HABIT_LIFECYCLES",
    "HABIT_PROMOTION_METHOD",
    "HABIT_PROMOTION_VERSION",
    "PROFILE_DIFF_METHOD",
    "PROFILE_DIFF_VERSION",
    "RCLAdapter",
    "RCLProfile",
    "RCLValidationError",
    "RCL_VERSION",
    "SESSION_EVALUATION_METHOD",
    "SESSION_EVALUATION_VERSION",
    "STATISTICAL_EVALUATION_METHOD",
    "STATISTICAL_EVALUATION_VERSION",
    "calculate_continuity_score",
    "classify_capability_id",
    "compare_experiment_context",
    "compare_trial_distributions",
    "confidence_interval_95",
    "diff_profiles",
    "evaluate_habit_promotion_candidates",
    "evaluate_observed_continuity",
    "evaluate_repeated_sessions",
    "get_capability",
    "load_capability_registry",
    "load_default_habit_promotion_policy",
    "migrate_profile",
    "registered_capabilities",
    "reserved_namespaces",
    "run_adapter_conformance",
    "sample_mean",
    "sample_std",
    "t95_critical",
    "validate_behavior_evaluation_metadata",
    "validate_behavior_habit_metadata",
    "validate_capability_id",
    "validate_capability_set",
    "wasserstein_1d",
]
