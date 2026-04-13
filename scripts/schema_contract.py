#!/usr/bin/env python3
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

@lru_cache(maxsize=None)
def _load_bundle(bundle_path_str: str) -> dict[str, Any]:
    return json.loads(Path(bundle_path_str).read_text(encoding="utf-8"))

def bundle_path(repo_root: Path) -> Path:
    return (repo_root / "schemas" / "prime-canon-bundle.schema.json").resolve()

def bundle(repo_root: Path) -> dict[str, Any]:
    return _load_bundle(str(bundle_path(repo_root)))

def object_schema(repo_root: Path, kind: str) -> dict[str, Any]:
    defs = bundle(repo_root).get("$defs", {})
    if kind not in defs:
        raise SystemExit(f"schema kind not found in bundle: {kind}")
    return defs[kind]

def section_schema(repo_root: Path, kind: str, section: str) -> dict[str, Any]:
    schema = object_schema(repo_root, kind)
    props = schema.get("properties", {})
    if section not in props:
        raise SystemExit(f"section {section} not found for schema kind {kind}")
    return props[section]

def property_schema(repo_root: Path, kind: str, section: str, field: str) -> dict[str, Any]:
    sec = section_schema(repo_root, kind, section)
    props = sec.get("properties", {})
    if field not in props:
        raise SystemExit(f"field {field} not found in {kind}.{section}")
    return props[field]

def required_fields(repo_root: Path, kind: str, section: str = "spec") -> list[str]:
    sec = section_schema(repo_root, kind, section)
    return list(sec.get("required", []))

def enum_values(repo_root: Path, kind: str, field: str, section: str = "spec") -> list[Any]:
    prop = property_schema(repo_root, kind, section, field)
    enum = prop.get("enum")
    if enum is None:
        raise SystemExit(f"field {kind}.{section}.{field} has no enum")
    return list(enum)

def choose_enum(repo_root: Path, kind: str, field: str, preferred: Any, fallback: Any | None = None, section: str = "spec") -> Any:
    allowed = enum_values(repo_root, kind, field, section)
    if preferred in allowed:
        return preferred
    if fallback is not None and fallback in allowed:
        return fallback
    raise SystemExit(f"value {preferred!r} not allowed for {kind}.{section}.{field}; allowed={allowed}")

def ensure_required_fields(repo_root: Path, kind: str, payload: dict[str, Any], section: str = "spec") -> None:
    missing = [field for field in required_fields(repo_root, kind, section) if field not in payload]
    if missing:
        raise SystemExit(f"missing required {section} fields for {kind}: {missing}")

def ensure_enum(repo_root: Path, kind: str, field: str, value: Any, section: str = "spec") -> None:
    allowed = enum_values(repo_root, kind, field, section)
    if value not in allowed:
        raise SystemExit(f"invalid enum value for {kind}.{section}.{field}: {value!r}; allowed={allowed}")

def validate_instance(repo_root: Path, instance: dict[str, Any]) -> None:
    kind = instance.get("kind")
    if not kind:
        raise SystemExit("instance missing kind")
    schema = object_schema(repo_root, kind)
    Draft202012Validator(schema).validate(instance)
