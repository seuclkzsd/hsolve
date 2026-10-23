# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 seuclkzsd and the hsolve contributors
"""MkDocs hooks of the hsolve documentation site (registered in mkdocs.yml under `hooks:`).

The repository keeps one copy of every document, written for reading on GitHub, where relative
links point at repository files. The site (docs_dir = docs/) needs two things on top of that:

1. Root project documents (CONTRIBUTING.md, ROADMAP.md, CHANGELOG.md, ...) are published as
   site pages under project/ (ROOT_PAGES), so they are not copied into docs/.
2. Every relative link of every page is resolved against the page's location in the repository:
   a link to a documentation page becomes a link to that site page; a link to any other existing
   repository file or directory (results/, tools/, bench/, LICENSE, ...) becomes a GitHub link.
   Links that resolve to nothing are left unchanged, so `mkdocs build --strict` still reports
   them as broken.

Fenced code blocks and inline code spans are never rewritten.
"""
from __future__ import annotations

import posixpath
import re
from pathlib import Path
from urllib.parse import quote, unquote

from mkdocs.structure.files import File, Files

BRANCH = "main"

# Root documents published on the site: repository path -> site source path (under docs_dir).
ROOT_PAGES = {
    "CONTRIBUTING.md": "project/contributing.md",
    "GOVERNANCE.md": "project/governance.md",
    "MAINTAINERS.md": "project/maintainers.md",
    "SECURITY.md": "project/security.md",
    "CODE_OF_CONDUCT.md": "project/code-of-conduct.md",
    "ROADMAP.md": "project/roadmap.md",
    "CHANGELOG.md": "project/changelog.md",
}
_SITE_TO_ROOT = {site: repo for repo, site in ROOT_PAGES.items()}

_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_CODE_SPAN = re.compile(r"(`+).+?\1")
# Inline links and images: [text](target "title") / ![alt](<target>).
_INLINE_LINK = re.compile(r"(!?\[[^\]]*\]\()(<[^>\n]*>|[^)\s]+)((?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\))")
# Reference definitions: [id]: target "title".
_REF_DEF = re.compile(r"^( {0,3}\[[^\]]+\]:[ \t]*)(<[^>\n]*>|\S+)(.*)$")
# Raw HTML attributes.
_HTML_ATTR = re.compile(r"(\b(?:href|src)=\")([^\"]+)(\")")
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


class _Context:
    def __init__(self, config) -> None:
        self.repo_root = Path(config["config_file_path"]).resolve().parent
        docs_dir = Path(config["docs_dir"]).resolve()
        self.docs_rel = docs_dir.relative_to(self.repo_root).as_posix()
        repo_url = (config.get("repo_url") or "").rstrip("/")
        if not repo_url:
            raise ValueError("mkdocs.yml must set repo_url (links to repository files point there)")
        self.repo_url = repo_url
        self.blob = f"{repo_url}/blob/{BRANCH}/"
        self.tree = f"{repo_url}/tree/{BRANCH}/"


_ctx: _Context | None = None


def on_config(config):
    global _ctx
    _ctx = _Context(config)
    return config


def on_files(files: Files, config) -> Files:
    assert _ctx is not None
    for repo_path, site_path in ROOT_PAGES.items():
        source = _ctx.repo_root / repo_path
        if not source.is_file():
            raise FileNotFoundError(f"{repo_path} is listed in ROOT_PAGES but does not exist")
        files.append(File.generated(config, site_path, abs_src_path=str(source)))
    return files


def on_page_markdown(markdown: str, page, config, files: Files) -> str:
    assert _ctx is not None
    src_uri = page.file.src_uri
    repo_path = _SITE_TO_ROOT.get(src_uri, f"{_ctx.docs_rel}/{src_uri}")
    if src_uri in _SITE_TO_ROOT and config.get("edit_uri"):
        page.edit_url = f"{_ctx.repo_url}/edit/{BRANCH}/{repo_path}"

    def rewrite(target: str) -> str:
        bracketed = target.startswith("<") and target.endswith(">")
        raw = target[1:-1] if bracketed else target
        new = _resolve(raw, repo_path, src_uri, files)
        if new is None:
            return target
        return f"<{new}>" if bracketed else new

    def fix_text(text: str) -> str:
        text = _INLINE_LINK.sub(lambda m: m.group(1) + rewrite(m.group(2)) + m.group(3), text)
        return _HTML_ATTR.sub(lambda m: m.group(1) + rewrite(m.group(2)) + m.group(3), text)

    out = []
    fence = None
    for line in markdown.splitlines(keepends=True):
        m = _FENCE.match(line)
        if fence is not None:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
                fence = None
            out.append(line)
            continue
        if m:
            fence = m.group(1)
            out.append(line)
            continue
        ref = _REF_DEF.match(line.rstrip("\n"))
        if ref:
            end = line[len(line.rstrip("\n")):]
            out.append(ref.group(1) + rewrite(ref.group(2)) + ref.group(3) + end)
            continue
        out.append(_outside_code_spans(line, fix_text))
    return "".join(out)


def _outside_code_spans(line: str, fn) -> str:
    """fn applied to the line with its code spans masked, so that a link whose text contains code
    (`[`.clang-format`](.clang-format)`) is still seen whole while code itself is never rewritten."""
    spans = []

    def mask(m: re.Match) -> str:
        spans.append(m.group(0))
        return f"\x00{len(spans) - 1}\x00"

    masked = fn(_CODE_SPAN.sub(mask, line))
    return re.sub(r"\x00(\d+)\x00", lambda m: spans[int(m.group(1))], masked)


def _resolve(target: str, page_repo_path: str, page_src_uri: str, files: Files) -> str | None:
    """New link for a relative target, or None to leave it unchanged."""
    assert _ctx is not None
    if not target or target.startswith(("#", "/")) or _SCHEME.match(target):
        return None
    path, sep, fragment = target.partition("#")
    if not path or "?" in path:
        return None
    repo_target = posixpath.normpath(posixpath.join(posixpath.dirname(page_repo_path), unquote(path)))
    if repo_target == ".." or repo_target.startswith("../"):
        return None
    site_target = ROOT_PAGES.get(repo_target)
    prefix = _ctx.docs_rel + "/"
    if site_target is None and repo_target.startswith(prefix):
        candidate = repo_target[len(prefix):]
        file = files.get_file_from_path(candidate)
        if file is not None and file.inclusion.is_included():
            site_target = candidate
    if site_target is not None:
        base = posixpath.dirname(page_src_uri) or "."
        return posixpath.relpath(site_target, base) + sep + fragment
    full = _ctx.repo_root / repo_target
    if full.is_file():
        return _ctx.blob + quote(repo_target) + sep + fragment
    if full.is_dir():
        return _ctx.tree + quote(repo_target)
    return None
