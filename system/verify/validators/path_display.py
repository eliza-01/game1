"""Stable cross-platform path rendering for validator diagnostics."""

from pathlib import PurePath


def project_relative_path(path: PurePath, root: PurePath) -> str:
    """Return a project-relative path with POSIX separators on any host OS."""
    return path.relative_to(root).as_posix()
