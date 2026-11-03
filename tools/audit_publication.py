#!/usr/bin/env python3
"""Read-only publication inventory and secret-pattern audit for MediaForge."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
OMITTED_DIRS = {
    ".git": "Git internals",
    ".venv": "virtual environment",
    "__pycache__": "Python bytecode cache",
    ".pytest_cache": "pytest cache",
    "build": "PyInstaller build output",
    "dist": "compiled distribution",
    ".idea": "user/IDE workspace settings",
    ".vscode": "user/IDE workspace settings; review selectively if project config is needed",
    "logs": "local logs",
    "tmp": "temporary files",
    "temp": "temporary files",
    "downloads": "downloaded assets",
}
OMITTED_SUFFIXES = {
    ".bak": "preserved backup",
    ".tmp": "temporary file",
    ".part": "partial download",
    ".log": "local log",
    ".pyc": "compiled Python bytecode",
    ".pyo": "compiled Python bytecode",
    ".exe": "compiled executable",
    ".dll": "compiled/shared library",
    ".pyd": "compiled Python extension",
    ".zip": "archive/build/source bundle",
    ".7z": "archive",
    ".rar": "archive",
    ".whl": "built Python package",
    ".sqlite": "local database/history",
    ".sqlite3": "local database/history",
    ".db": "local database/history",
    ".dmp": "diagnostic dump",
    ".dump": "diagnostic dump",
    ".core": "diagnostic dump",
}
OMITTED_NAMES = {
    ".env": "local environment/credentials file",
    "credentials": "credentials file",
    "credentials.json": "credentials file",
    "secrets.json": "secrets file",
}
INCLUDE_ROOT_FILES = {
    ".gitignore",
    "LICENSE",
    "README.md",
    "THIRD_PARTY_NOTICES.md",
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "run.bat",
    "build_exe.bat",
    "MediaForgeLocal.spec",
}
INCLUDE_DIRS = {"mediaforge", "tests", "docs", "LICENSES", "tools"}
TEXT_SUFFIXES = {
    ".bat",
    ".cfg",
    ".ini",
    ".json",
    ".md",
    ".py",
    ".rst",
    ".spec",
    ".svg",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
PLACEHOLDER_VALUES = {
    "",
    "changeme",
    "change-me",
    "example",
    "example.com",
    "fake",
    "none",
    "null",
    "not-a-real-secret",
    "placeholder",
    "test",
    "testing",
    "your-token",
    "your_api_key",
    "your-api-key",
    "user",
    "username",
    "pass",
    "your_password",
}

_PRIVATE_KEY = re.compile(
    r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----", re.IGNORECASE
)
_CLOUD_KEY = re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")
_GITHUB_TOKEN = re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")
_SLACK_TOKEN = re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")
_BEARER = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{20,}", re.IGNORECASE)
_URL_CREDENTIALS = re.compile(r"https?://[^/\s:@]+:[^/\s@]+@", re.IGNORECASE)
_ASSIGNMENT = re.compile(
    r"""(?imx)
    ^[ \t]*
    (?:[A-Za-z_]\w*\.)?
    (?P<key>
        (?:api[_-]?key|client[_-]?secret|password|passwd|secret|token|
           access[_-]?token|refresh[_-]?token|private[_-]?key)
    )\b[ \t]*[:=][ \t]*
    (?P<value>
        "(?:\\.|[^"\\\r\n])*" |
        '(?:\\.|[^'\\\r\n])*' |
        [^\s,;#]+
    )
    """
)
_URL = re.compile(r"\bhttps?://[^\s'\"<>]+", re.IGNORECASE)
_URL_SECRET_PARAMETER = re.compile(
    r"(?i)(?:[?&])(?:api[_-]?key|client[_-]?secret|password|passwd|secret|"
    r"token|access[_-]?token|refresh[_-]?token)=([^&#\s]+)"
)
_PRIVATE_ADDRESS = re.compile(
    r"(?i)\b(?:"
    r"10(?:\.\d{1,3}){3}|"
    r"192\.168(?:\.\d{1,3}){2}|"
    r"172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2}|"
    r"127(?:\.\d{1,3}){3}|"
    r"localhost"
    r")\b"
)


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _ignored_reason(relative: str) -> str | None:
    path = Path(relative)
    parts = path.parts
    for part in parts[:-1]:
        if part in OMITTED_DIRS:
            return OMITTED_DIRS[part]
    name = path.name
    lower_name = name.lower()
    if lower_name in OMITTED_NAMES:
        return OMITTED_NAMES[lower_name]
    if lower_name.startswith(".env.") and lower_name not in {
        ".env.example",
        ".env.template",
    }:
        return "local environment/credentials file"
    if name.endswith(".code-workspace") or name.endswith(".sublime-workspace"):
        return "user workspace configuration"
    suffix = path.suffix.lower()
    if suffix in OMITTED_SUFFIXES:
        return OMITTED_SUFFIXES[suffix]
    if lower_name.startswith("warn-") or lower_name.endswith(
        (".toc", ".manifest", ".xref")
    ):
        return "generated build/diagnostic report"
    return None


def _include_reason(relative: str) -> str | None:
    path = Path(relative)
    if len(path.parts) == 1 and path.name in INCLUDE_ROOT_FILES:
        return "project source, license, documentation, or build/development configuration"
    if path.parts and path.parts[0] == "LICENSES":
        return "third-party license texts/notices"
    if path.parts and path.parts[0] in INCLUDE_DIRS:
        if path.suffix.lower() in TEXT_SUFFIXES:
            return {
                "mediaforge": "application source/assets",
                "tests": "automated tests",
                "docs": "project documentation and publication inventory",
                "tools": "read-only project audit tooling",
            }[path.parts[0]]
    return None


def _assignment_is_placeholder(value: str) -> bool:
    value = value.strip().strip("\"'`").strip()
    if value.startswith(("$", "%", "{", "<")):
        return True
    return value.lower() in PLACEHOLDER_VALUES


def _is_reserved_test_url(value: str, relative: str) -> bool:
    if not relative.startswith("tests/"):
        return False
    try:
        host = urlsplit(value.rstrip(").,;]")).hostname or ""
    except ValueError:
        return False
    return (
        host in {"example.com", "example.net", "example.org", "localhost"}
        or host.endswith(
            (
                ".example.com",
                ".example.net",
                ".example.org",
                ".test",
                ".invalid",
                ".localhost",
            )
        )
    )


def _find_findings(text: str, relative: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    def add_matches(pattern: re.Pattern[str], category: str) -> None:
        for match in pattern.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            findings.append({"line": line, "category": category})

    for pattern, category in (
        (_PRIVATE_KEY, "private-key material"),
        (_CLOUD_KEY, "cloud access-key pattern"),
        (_GITHUB_TOKEN, "GitHub token pattern"),
        (_SLACK_TOKEN, "Slack token pattern"),
        (_BEARER, "bearer credential"),
    ):
        add_matches(pattern, category)

    for match in _URL_CREDENTIALS.finditer(text):
        complete_url = _URL.search(text, match.start())
        url_text = complete_url.group(0) if complete_url else match.group(0)
        if not _is_reserved_test_url(url_text, relative):
            line = text.count("\n", 0, match.start()) + 1
            findings.append({"line": line, "category": "credentials embedded in URL"})

    for match in _ASSIGNMENT.finditer(text):
        if not _assignment_is_placeholder(match.group("value")):
            line = text.count("\n", 0, match.start()) + 1
            findings.append(
                {"line": line, "category": "non-placeholder credential assignment"}
            )

    for match in _URL.finditer(text):
        if _is_reserved_test_url(match.group(0), relative):
            continue
        for parameter in _URL_SECRET_PARAMETER.finditer(match.group(0)):
            if not _assignment_is_placeholder(parameter.group(1)):
                line = text.count("\n", 0, match.start()) + 1
                findings.append(
                    {"line": line, "category": "credential-like URL parameter"}
                )

    # Flag personal home-directory paths only when they identify the current
    # Windows account; generic documentation paths are not user data.
    username = os.environ.get("USERNAME")
    if username:
        escaped = re.escape(username)
        personal_path = re.compile(
            rf"(?i)(?:[A-Z]:\\Users\\{escaped}(?:\\|\\b)|/Users/{escaped}(?:/|\b))"
        )
        add_matches(personal_path, "current-user absolute path")

    # Private addresses in tests are expected SSRF fixtures, not machine
    # endpoints. Elsewhere, a private-network URL requires manual review.
    if not relative.startswith("tests/"):
        for match in _URL.finditer(text):
            if _PRIVATE_ADDRESS.search(match.group(0)):
                line = text.count("\n", 0, match.start()) + 1
                findings.append({"line": line, "category": "private-network URL"})

    return sorted(findings, key=lambda item: (item["line"], item["category"]))


def audit() -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    total = 0
    unreadable: list[str] = []

    for current, dirnames, filenames in os.walk(ROOT, topdown=True, followlinks=False):
        current_path = Path(current)
        kept_dirs = []
        for dirname in dirnames:
            child = current_path / dirname
            rel = _relative(child)
            reason = _ignored_reason(rel + "/placeholder")
            if reason:
                # Count files below an excluded directory without traversing it
                # in the classification loop; os.walk still prunes the subtree.
                count = sum(
                    1
                    for _, _, files in os.walk(
                        child, topdown=True, followlinks=False
                    )
                    for _ in files
                )
                total += count
                records.append(
                    {
                        "path": rel + "/",
                        "status": "excluded",
                        "reason": reason,
                        "file_count": count,
                    }
                )
            else:
                kept_dirs.append(dirname)
        dirnames[:] = kept_dirs

        for filename in filenames:
            path = current_path / filename
            relative = _relative(path)
            total += 1
            ignored = _ignored_reason(relative)
            if ignored:
                records.append(
                    {"path": relative, "status": "excluded", "reason": ignored}
                )
                continue
            include = _include_reason(relative)
            if include is None:
                records.append(
                    {
                        "path": relative,
                        "status": "excluded",
                        "reason": "not part of the reviewed source/documentation allowlist",
                    }
                )
                continue

            record: dict[str, Any] = {
                "path": relative,
                "status": "included",
                "reason": include,
            }
            if (
                path.suffix.lower() in TEXT_SUFFIXES
                or path.parts[0] == "LICENSES"
                or path.name in {"LICENSE", "NOTICE"}
            ):
                try:
                    content = path.read_text(encoding="utf-8")
                except (UnicodeDecodeError, OSError):
                    unreadable.append(relative)
                    record["status"] = "pending"
                    record["reason"] = "text candidate could not be decoded/read as UTF-8"
                else:
                    file_findings = _find_findings(content, relative)
                    if file_findings:
                        record["status"] = "pending"
                        record["reason"] = "potentially sensitive content; manual review required"
                        findings.extend(
                            {"path": relative, **finding} for finding in file_findings
                        )
            records.append(record)

    records.sort(key=lambda item: item["path"].casefold())
    included_paths = {
        record["path"] for record in records if record["status"] == "included"
    }
    manifest_errors: list[str] = []
    manifest_path = ROOT / "docs" / "GITHUB_PUBLICATION_MANIFEST.md"
    if manifest_path.is_file():
        try:
            manifest_text = manifest_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            manifest_errors.append("publication manifest cannot be read as UTF-8")
        else:
            section = re.search(
                r"(?ms)^## A\. ARQUIVOS INCLUÍDOS\s*\n(.*?)(?=^## B\.)",
                manifest_text,
            )
            block = (
                re.search(r"(?ms)^```text\s*\n(.*?)^```", section.group(1))
                if section
                else None
            )
            if not block:
                manifest_errors.append("included-file list is missing its text block")
            else:
                listed_paths = [
                    line.strip()
                    for line in block.group(1).splitlines()
                    if line.strip()
                ]
                if len(listed_paths) != len(set(listed_paths)):
                    manifest_errors.append("included-file list contains duplicates")
                if set(listed_paths) != included_paths:
                    manifest_errors.append("included-file list does not match the audit")
                declared = re.search(
                    r"\*\*(\d+) arquivos aprovados no inventário atual\*\*",
                    section.group(1),
                )
                if not declared or int(declared.group(1)) != len(included_paths):
                    manifest_errors.append("declared included-file count does not match")

    included_count = sum(1 for record in records if record["status"] == "included")
    pending_count = sum(1 for record in records if record["status"] == "pending")
    excluded_count = sum(
        record.get("file_count", 1)
        for record in records
        if record["status"] == "excluded"
    )
    return {
        "root": str(ROOT),
        "files_examined": total,
        "included_count": included_count,
        "excluded_count": excluded_count,
        "pending_count": pending_count,
        "manifest_errors": manifest_errors,
        "excluded_directory_records": sum(
            1 for record in records if record.get("file_count") is not None
        ),
        "secret_findings": findings,
        "unreadable_text_candidates": unreadable,
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--format",
        choices=("summary", "json"),
        default="summary",
        help="summary prints included paths and exclusion groups; json emits every file record",
    )
    args = parser.parse_args()
    result = audit()
    if args.format == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(
            "Files examined: {files_examined}; included: {included_count}; "
            "excluded: {excluded_count}; pending: {pending_count}".format(**result)
        )
        for error in result["manifest_errors"]:
            print(f"Manifest error: {error}")
        if result["secret_findings"]:
            print("Potential sensitive findings (values are never displayed):")
            for finding in result["secret_findings"]:
                print(
                    f"  {finding['path']}:{finding['line']} [{finding['category']}]"
                )
        if result["unreadable_text_candidates"]:
            print("Unreadable candidates:")
            for path in result["unreadable_text_candidates"]:
                print(f"  {path}")
        print("Included files:")
        for record in result["records"]:
            if record["status"] == "included":
                print(f"  {record['path']}")
        excluded = Counter(
            record["reason"]
            for record in result["records"]
            if record["status"] == "excluded"
        )
        print("Excluded paths grouped by reason:")
        for reason, count in sorted(excluded.items()):
            print(f"  {reason}: {count}")
        print("Excluded files and directories:")
        for record in result["records"]:
            if record["status"] == "excluded":
                count = record.get("file_count")
                suffix = f" ({count} files)" if count is not None else ""
                print(f"  {record['path']}{suffix} — {record['reason']}")
        if result["pending_count"]:
            print("Pending paths:")
            for record in result["records"]:
                if record["status"] == "pending":
                    print(f"  {record['path']} — {record['reason']}")
    return (
        1
        if result["secret_findings"]
        or result["pending_count"]
        or result["manifest_errors"]
        else 0
    )


if __name__ == "__main__":
    sys.exit(main())
