from __future__ import annotations

import hashlib
import json
import tempfile
import zipfile
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


RCL_VERSION = "0.2"
PAYLOADS = (
    "identity.json",
    "preferences.json",
    "behavior.json",
    "skills.json",
    "embodiment.json",
)


class RCLValidationError(ValueError):
    pass


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _schema_text(name: str) -> str:
    resource = files("rcl").joinpath("schemas", f"{name}.schema.json")
    return resource.read_text(encoding="utf-8")


def validate_schema(instance: Any, schema_name: str) -> None:
    schema = json.loads(_schema_text(schema_name))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
    if errors:
        msg = "; ".join(
            f"{'.'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in errors
        )
        raise RCLValidationError(f"{schema_name} validation failed: {msg}")


@dataclass
class RCLProfile:
    root: Path

    @classmethod
    def open(cls, path: str | Path) -> "RCLProfile":
        path = Path(path)
        if path.is_dir():
            profile = cls(path)
            profile.validate(require_manifest=(path / "manifest.json").exists())
            return profile

        if path.suffix.lower() != ".rcl":
            raise RCLValidationError("Expected a directory or .rcl package")

        tmp = Path(tempfile.mkdtemp(prefix="rcl-"))
        with zipfile.ZipFile(path, "r") as zf:
            names = set(zf.namelist())
            expected = set(PAYLOADS) | {"manifest.json"}
            if names != expected:
                raise RCLValidationError(
                    f"Package entries must exactly match {sorted(expected)}; got {sorted(names)}"
                )
            zf.extractall(tmp)
        profile = cls(tmp)
        profile.validate(require_manifest=True)
        return profile

    def load(self, filename: str) -> Any:
        if filename not in PAYLOADS and filename != "manifest.json":
            raise KeyError(filename)
        return _load_json(self.root / filename)

    def validate(self, require_manifest: bool = True) -> None:
        for payload in PAYLOADS:
            path = self.root / payload
            if not path.exists():
                raise RCLValidationError(f"Missing required payload: {payload}")
            instance = _load_json(path)
            validate_schema(instance, payload.removesuffix(".json"))
            if payload == "behavior.json":
                # Local imports avoid cycles: the evaluation/history/intent/timing
                # validators depend on profile helpers, while profile validation
                # only needs their cross-field checks at runtime.
                from .evaluation import validate_behavior_evaluation_metadata
                from .expression_history import validate_behavior_expression_history_metadata
                from .expression_timing import validate_behavior_expression_timing_metadata
                from .history import validate_behavior_habit_metadata
                from .intent import validate_behavior_intent_metadata

                validate_behavior_evaluation_metadata(instance)
                validate_behavior_habit_metadata(instance)
                validate_behavior_intent_metadata(instance)
                validate_behavior_expression_timing_metadata(instance)
                validate_behavior_expression_history_metadata(instance)

        manifest_path = self.root / "manifest.json"
        if require_manifest:
            if not manifest_path.exists():
                raise RCLValidationError("Missing manifest.json")
            manifest = _load_json(manifest_path)
            validate_schema(manifest, "manifest")
            expected = {entry["path"]: entry["sha256"] for entry in manifest["files"]}
            if set(expected) != set(PAYLOADS):
                raise RCLValidationError("Manifest must list every required payload exactly once")
            for payload in PAYLOADS:
                actual = _sha256(self.root / payload)
                if actual != expected[payload]:
                    raise RCLValidationError(f"SHA-256 mismatch: {payload}")

    @staticmethod
    def create_manifest(source_dir: str | Path, profile_id: str, created_at: str) -> dict[str, Any]:
        source = Path(source_dir)
        files_payload = [{"path": name, "sha256": _sha256(source / name)} for name in PAYLOADS]
        return {
            "rcl_version": RCL_VERSION,
            "profile_id": profile_id,
            "created_at": created_at,
            "files": files_payload,
        }

    @staticmethod
    def pack(source_dir: str | Path, output_file: str | Path, profile_id: str, created_at: str) -> Path:
        source = Path(source_dir)
        profile = RCLProfile(source)
        profile.validate(require_manifest=False)
        manifest = RCLProfile.create_manifest(source, profile_id, created_at)
        validate_schema(manifest, "manifest")

        output = Path(output_file)
        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
            for payload in PAYLOADS:
                zf.write(source / payload, arcname=payload)
        return output

    def summary(self) -> dict[str, Any]:
        identity = self.load("identity.json")
        behavior = self.load("behavior.json")
        skills = self.load("skills.json")
        embodiment = self.load("embodiment.json")
        return {
            "rcl_version": RCL_VERSION,
            "robot_id": identity["robot_id"],
            "display_name": identity.get("display_name"),
            "generation": identity["continuity_generation"],
            "embodiment": embodiment["embodiment_id"],
            "behavior_count": len(behavior["behaviors"]),
            "skill_count": len(skills["skills"]),
        }
