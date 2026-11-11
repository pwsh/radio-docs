#!/usr/bin/env python3
"""Rewrite links in pulled reference docs so they work on the docs site.

Usage: rewrite-reference-links.py <dest> <checkout> <web-base> [<pulled-repo>,...]

  <dest>      docs/reference/<name>/ (the copy of the repo's docs/ directory)
  <checkout>  the clone the copy came from (to tell files from directories)
  <web-base>  https://github.com/<owner>/<repo>  (links become <web-base>/blob|tree/<ref>/<path>)
  <pulled-repo>  names of the repos of the same owner that are pulled into
              docs/reference/<name>/ (default: none)

- A relative link that leaves the repo's docs/ tree (a source file, a script) becomes
  a GitHub URL at the pinned ref, read from <dest>/.ref.
- A GitHub URL to a Markdown page under docs/ of one of the pulled repos (at any ref)
  becomes a relative link to the in-site copy, e.g. ../trunkd/NON-VOICE-DATA.md.
- Links that stay inside docs/ are left alone so MkDocs resolves them.
Fenced code blocks and inline code are not touched. Prints one line per rewritten link.

Every page also gets `edit_url: false` in its front matter: the page is edited in its code
repository, not here, so hooks/reference_pages.py drops the site's edit and view buttons
(which would point at a radio-docs path that does not exist).
"""
import posixpath
import re
import sys
from pathlib import Path

LINK = re.compile(r"(\]\()([^)\s]+)(\))")
FENCE = re.compile(r"^\s*(```|~~~)")
CODE_SPAN = re.compile(r"`[^`]*`")


def sibling_target(target, this, rel_dir, owner_base, pulled):
    """A GitHub URL to a pulled repo's docs page -> relative link to the in-site copy."""
    m = re.match(re.escape(owner_base) + r"/([^/]+)/blob/[^/]+/docs/([^#?]+\.md)(#.*)?$", target)
    if not m or m.group(1) not in pulled:
        return None
    # This page sits in reference/<this>/<rel_dir>/; the copy at reference/<repo>/<path>.
    there = posixpath.join(m.group(1), m.group(2))
    return posixpath.relpath(there, posixpath.join(this, rel_dir) or ".") + (m.group(3) or "")


def rewrite_target(target, rel_dir, checkout, web_base, ref):
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith(("#", "/")):
        return None
    path, sep, frag = target.partition("#")
    if not path:
        return None
    # Path inside the repo, relative to its root (the copy is of <repo>/docs/).
    repo_path = posixpath.normpath(posixpath.join("docs", rel_dir, path))
    if repo_path == "docs" or repo_path.startswith("docs/"):
        return None  # stays in the pulled tree; MkDocs resolves it
    if repo_path.startswith(".."):
        return None  # leaves the repo entirely; leave it for the build to flag
    kind = "tree" if (checkout / repo_path).is_dir() else "blob"
    return f"{web_base}/{kind}/{ref}/{repo_path}" + (sep + frag if sep else "")


def mark_not_editable(text):
    """Add `edit_url: false` to the page's front matter, creating it if there is none."""
    if text.startswith("---\n"):
        end = text.find("\n---\n", 3)
        if end != -1 and "\nedit_url:" not in text[3:end + 1]:
            return text[:end + 1] + "edit_url: false\n" + text[end + 1:]
        if end != -1:
            return text
    return "---\nedit_url: false\n---\n\n" + text


def main():
    dest, checkout, web_base = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3].rstrip("/")
    pulled = set(filter(None, sys.argv[4].split(","))) if len(sys.argv) > 4 else set()
    owner_base = web_base.rsplit("/", 1)[0]
    ref = (dest / ".ref").read_text().strip()
    for md in sorted(dest.rglob("*.md")):
        rel_dir = posixpath.dirname(md.relative_to(dest).as_posix())
        out, changed, in_fence = [], False, False
        for line in md.read_text(encoding="utf-8").splitlines(keepends=True):
            if FENCE.match(line):
                in_fence = not in_fence
                out.append(line)
                continue
            if in_fence:
                out.append(line)
                continue
            # Split off inline code spans so links shown as code are not touched.
            pieces, last = [], 0
            for m in CODE_SPAN.finditer(line):
                pieces.append((line[last:m.start()], True))
                pieces.append((m.group(0), False))
                last = m.end()
            pieces.append((line[last:], True))
            new_line = ""
            for text, is_prose in pieces:
                if is_prose:
                    def sub(m):
                        nonlocal changed
                        new = sibling_target(m.group(2), dest.name, rel_dir, owner_base, pulled)
                        if new is None:
                            new = rewrite_target(m.group(2), rel_dir, checkout, web_base, ref)
                        if new is None:
                            return m.group(0)
                        changed = True
                        print(f"  {md.relative_to(dest)}: {m.group(2)} -> {new}")
                        return m.group(1) + new + m.group(3)
                    text = LINK.sub(sub, text)
                new_line += text
            out.append(new_line)
        md.write_text(mark_not_editable("".join(out)), encoding="utf-8")


if __name__ == "__main__":
    main()
