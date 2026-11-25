#!/usr/bin/env python3
"""Publish exactly the rendered bytes verified against the frozen receipts."""

from __future__ import annotations

import hashlib
import os
import secrets
import stat
import sys
from pathlib import Path

from promotion_preflight import PromotionRejected, SUBJECT, _yaml

MAX_RENDER = 16 * 1024 * 1024


def read_render(repo: Path, source: Path) -> bytes:
    if source.is_symlink() or not source.resolve().is_relative_to(repo):
        raise PromotionRejected("rendered source is a symlink or escapes repository")
    fd = os.open(source, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_RENDER:
            raise PromotionRejected("rendered source is not a bounded regular file")
        raw = stream.read(MAX_RENDER + 1)
    if len(raw) > MAX_RENDER:
        raise PromotionRejected("rendered source exceeds size limit")
    return raw


def publish(repo: Path, subject: str) -> Path:
    repo = repo.resolve()
    if not SUBJECT.fullmatch(subject):
        raise PromotionRejected("invalid subject slug")
    cfg, _ = _yaml(repo, repo / "control" / "publish" / "publish-targets.default.yaml")
    view, _ = _yaml(repo, repo / "views" / "current" / f"{subject}.yaml")
    receipt_dir = repo / "receipts" / "immutable" / subject
    execution, _ = _yaml(repo, receipt_dir / "render-execution.yaml")
    drift, _ = _yaml(repo, receipt_dir / "render-drift.yaml")
    expected_ref = f"views/rendered/{subject}.md"
    spec = execution["spec"]
    drift_spec = drift["spec"]
    view_spec = view["spec"]
    if (spec.get("output_ref") != expected_ref or drift_spec.get("output_ref") != expected_ref
            or spec.get("target_view_ref") != view_spec.get("view_id")
            or drift_spec.get("target_view_ref") != view_spec.get("view_id")
            or drift_spec.get("current_view_hash") != view_spec.get("view_hash")
            or drift_spec.get("output_sha256") != spec.get("output_sha256")
            or drift_spec.get("drift_status") != "in_sync"
            or drift_spec.get("blocker") is not False
            or drift_spec.get("recommended_route") != "export_prep"):
        raise PromotionRejected("render receipts and current view do not authorize these exact bytes")
    source = repo / expected_ref
    raw = read_render(repo, source)
    if hashlib.sha256(raw).hexdigest() != spec.get("output_sha256"):
        raise PromotionRejected("rendered source bytes differ from execution receipt")
    target_value = cfg.get("subjects", {}).get(subject, {}).get("rendered_markdown_path")
    if not isinstance(target_value, str) or not target_value:
        raise PromotionRejected("missing publish target")
    target = Path(target_value)
    if not target.is_absolute() or target.name != f"{subject}.rendered.md":
        raise PromotionRejected("publish target must be the configured absolute subject file")
    if target.is_symlink():
        raise PromotionRejected("publish target is a symlink")
    if not target.parent.is_dir() or target.parent.is_symlink():
        raise PromotionRejected("publish target directory is absent or a symlink")
    directory_fd = os.open(target.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0))
    try:
        if not stat.S_ISDIR(os.fstat(directory_fd).st_mode):
            raise PromotionRejected("publish target parent is not a directory")
        temp_name = f".{subject}.rendered.{secrets.token_hex(12)}.tmp"
        temp_fd = os.open(temp_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                          0o644, dir_fd=directory_fd)
        try:
            with os.fdopen(temp_fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            # Both pathnames are relative to the same already-open directory.
            # Replace never follows a destination symlink introduced by a race.
            os.replace(temp_name, target.name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
        finally:
            try:
                os.unlink(temp_name, dir_fd=directory_fd)
            except FileNotFoundError:
                pass
    finally:
        os.close(directory_fd)
    return target


if __name__ == "__main__":
    try:
        destination = publish(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("."),
                              sys.argv[2] if len(sys.argv) > 2 else "subject-0001")
    except (PromotionRejected, OSError) as exc:
        raise SystemExit(f"publication rejected: {exc}") from exc
    print(f"published_to={destination}")
