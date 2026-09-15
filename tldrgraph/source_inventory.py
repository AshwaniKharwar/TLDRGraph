"""Deterministic, graph-free repository source inventory."""

from __future__ import annotations

import hashlib
import os
import subprocess
from typing import Dict, Iterable, List, Optional

EXCLUDED_DIRS = {
    ".git", ".tldrgraph", ".hg", ".svn", ".venv", "venv", "env",
    "node_modules", "vendor", "dist", "build", "target", "coverage",
    ".cache", ".pytest_cache", ".mypy_cache", ".ruff_cache", "__pycache__",
    ".tox", ".nox", ".next", ".nuxt", "out",
}
EXCLUDED_SUFFIXES = {
    ".pyc", ".pyo", ".class", ".o", ".a", ".so", ".dylib", ".dll",
    ".exe", ".zip", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".pdf",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".woff", ".woff2",
}
LANGUAGES = {
    ".py": "python", ".js": "javascript", ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "typescript", ".go": "go", ".rs": "rust",
    ".java": "java", ".kt": "kotlin", ".rb": "ruby", ".php": "php",
    ".cs": "csharp", ".c": "c", ".h": "c", ".cpp": "cpp", ".hpp": "cpp",
    ".html": "html", ".css": "css", ".scss": "scss", ".sql": "sql",
    ".sh": "shell", ".yaml": "yaml", ".yml": "yaml", ".json": "json",
    ".toml": "toml", ".md": "markdown",
}


def _git_files(root: str) -> Optional[List[str]]:
    try:
        check = subprocess.run(
            ["git", "-C", root, "rev-parse", "--is-inside-work-tree"],
            check=True, capture_output=True, text=True, timeout=10,
        )
        if check.stdout.strip() != "true":
            return None
        result = subprocess.run(
            ["git", "-C", root, "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            check=True, capture_output=True, timeout=30,
        )
        return [os.fsdecode(item) for item in result.stdout.split(b"\0") if item]
    except (OSError, subprocess.SubprocessError):
        return None


def _walk_files(root: str) -> List[str]:
    paths: List[str] = []
    for current, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if not _excluded_dir(d))
        paths.extend(os.path.relpath(os.path.join(current, name), root) for name in sorted(files))
    return paths


def _allowed_path(relative: str) -> bool:
    normalized = relative.replace("\\", "/").lstrip("./")
    parts = normalized.split("/")
    return bool(normalized and not any(_excluded_dir(part) for part in parts[:-1])
                and os.path.splitext(normalized)[1].lower() not in EXCLUDED_SUFFIXES)


def _excluded_dir(name: str) -> bool:
    return name in EXCLUDED_DIRS or name.endswith(".egg-info")


def _text_bytes(path: str) -> Optional[bytes]:
    try:
        with open(path, "rb") as handle:
            content = handle.read()
    except OSError:
        return None
    if b"\0" in content[:8192]:
        return None
    try:
        content.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return content


def inventory_sources(root: str) -> List[Dict[str, object]]:
    root = os.path.abspath(root)
    git_files = _git_files(root)
    candidates: Iterable[str] = _walk_files(root) if git_files is None else git_files
    records: List[Dict[str, object]] = []
    for relative in sorted(set(candidates)):
        relative = relative.replace("\\", "/")
        if not _allowed_path(relative):
            continue
        candidate = os.path.realpath(os.path.join(root, relative))
        try:
            inside_root = os.path.commonpath((root, candidate)) == root
        except ValueError:
            inside_root = False
        content = _text_bytes(candidate) if inside_root and os.path.isfile(candidate) else None
        if content is None:
            continue
        suffix = os.path.splitext(relative)[1].lower()
        records.append({"path": relative, "size": len(content),
                        "sha256": hashlib.sha256(content).hexdigest(),
                        "language": LANGUAGES.get(suffix, "plain")})
    return records


def source_hash(files: List[Dict[str, object]]) -> str:
    digest = hashlib.sha256()
    for item in files:
        digest.update(str(item["path"]).encode("utf-8") + b"\0")
        digest.update(str(item["sha256"]).encode("ascii") + b"\n")
    return digest.hexdigest()


def build_source_inventory(root: str) -> Dict[str, object]:
    files = inventory_sources(root)
    return {"source_hash": source_hash(files), "files": files}
