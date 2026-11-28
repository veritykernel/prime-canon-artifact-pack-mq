"""Bind a current-state view to exact node, view, and render-policy bytes."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat


POLICY_PATHS = (
    "control/render/render-profile.default.yaml",
    "control/render/render-order.default.yaml",
    "control/render/render-targets.default.yaml",
    "control/render/render-redaction.default.yaml",
)
MAX_INPUT_BYTES = 2 * 1024 * 1024


def _file_digest(repo: Path, relative: str) -> str:
    path = repo / relative
    if not path.parent.resolve(strict=True).is_relative_to(repo):
        raise ValueError(f"render input escapes repository: {relative}")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ValueError(f"cannot open render input: {relative}") from exc
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_INPUT_BYTES:
            raise ValueError(f"render input is not a bounded regular file: {relative}")
        digest = hashlib.sha256()
        total = 0
        while chunk := os.read(descriptor, 1024 * 1024):
            total += len(chunk)
            if total > MAX_INPUT_BYTES:
                raise ValueError(f"render input exceeds size limit: {relative}")
            digest.update(chunk)
        return digest.hexdigest()
    finally:
        os.close(descriptor)


def compute_view_hash(repo: Path, subject_slug: str, view: dict) -> str:
    """Hash the complete source state consumed by the render contract."""
    repo = repo.resolve(strict=True)
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", subject_slug):
        raise ValueError("invalid render subject slug")
    spec = dict(view["spec"])
    spec.pop("view_hash", None)
    node_refs = list(spec.get("active_node_refs", []))
    if len(node_refs) != len(set(node_refs)):
        raise ValueError("duplicate active node reference")

    inputs = []
    for node_ref in node_refs:
        match = re.fullmatch(
            rf"pc\.canon_node\.{re.escape(subject_slug)}\.(\d{{4}})", node_ref
        )
        if not match:
            raise ValueError(f"invalid active node reference: {node_ref}")
        relative = f"canon/nodes/{subject_slug}/node-{match.group(1)}.yaml"
        inputs.append({
            "ref": node_ref,
            "path": relative,
            "sha256": _file_digest(repo, relative),
        })
    for relative in POLICY_PATHS:
        inputs.append({"path": relative, "sha256": _file_digest(repo, relative)})

    payload = {"binding_version": 2, "view_spec": spec, "inputs": inputs}
    encoded = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
