"""Descriptor-relative access to the approved rendered and staging directories."""

from __future__ import annotations

import os
import secrets
import stat
from pathlib import Path

from promotion_preflight import PromotionRejected, SUBJECT

MAX_RENDER = 16 * 1024 * 1024
DEFAULT_STAGE_ROOT = Path("/Users/Shared/nuum-work/stage")
DIR_FLAGS = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)


def subject_name(subject: str) -> str:
    if not SUBJECT.fullmatch(subject):
        raise PromotionRejected("invalid subject slug")
    return subject


def _open_directories(anchor: Path, components: tuple[str, ...], *, create_last: bool = False) -> int:
    """Open each directory without following a link in any selected component."""
    fd = os.open(anchor, DIR_FLAGS)
    try:
        for index, component in enumerate(components):
            if component in ("", ".", "..") or "/" in component:
                raise PromotionRejected("unsafe directory component")
            if create_last and index == len(components) - 1:
                try:
                    os.mkdir(component, 0o755, dir_fd=fd)
                except FileExistsError:
                    pass
            next_fd = os.open(component, DIR_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        if not stat.S_ISDIR(os.fstat(fd).st_mode):
            raise PromotionRejected("selected path is not a directory")
        return fd
    except BaseException:
        os.close(fd)
        raise


def rendered_directory(repo: Path, *, create: bool = False) -> int:
    return _open_directories(repo.resolve(), ("views", "rendered"), create_last=create)


def stage_directory(stage_root: Path) -> int:
    if not stage_root.is_absolute() or ".." in stage_root.parts:
        raise PromotionRejected("stage root must be an absolute non-escaping path")
    return _open_directories(Path("/"), tuple(stage_root.parts[1:]))


def read_rendered(repo: Path, subject: str) -> bytes:
    name = f"{subject_name(subject)}.md"
    directory_fd = rendered_directory(repo)
    try:
        fd = os.open(name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=directory_fd)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_RENDER:
                raise PromotionRejected("rendered source is not a bounded regular file")
            raw = stream.read(MAX_RENDER + 1)
        if len(raw) > MAX_RENDER:
            raise PromotionRejected("rendered source exceeds size limit")
        return raw
    finally:
        os.close(directory_fd)


def replace_regular(directory_fd: int, name: str, raw: bytes, *, mode: int = 0o644) -> None:
    """Replace a regular leaf from a private, already-open snapshot in the same directory."""
    if "/" in name or name in ("", ".", ".."):
        raise PromotionRejected("unsafe output name")
    try:
        prior = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        prior = None
    if prior is not None and not stat.S_ISREG(prior.st_mode):
        raise PromotionRejected("output target is not a regular file")
    temp_name = f".{name}.{secrets.token_hex(12)}.tmp"
    fd = os.open(temp_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                 mode, dir_fd=directory_fd)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
    finally:
        try:
            os.unlink(temp_name, dir_fd=directory_fd)
        except FileNotFoundError:
            pass


def write_rendered(repo: Path, subject: str, raw: bytes) -> None:
    if len(raw) > MAX_RENDER:
        raise PromotionRejected("rendered output exceeds size limit")
    directory_fd = rendered_directory(repo, create=True)
    try:
        replace_regular(directory_fd, f"{subject_name(subject)}.md", raw)
    finally:
        os.close(directory_fd)
