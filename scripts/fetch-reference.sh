#!/usr/bin/env bash
# Pull the reference docs of the two code repos into docs/reference/{trunkd,keyup}/
# at the refs pinned in mkdocs.yml (extra.trunkd_ref / extra.keyup_ref).
# A ref is a tag, a branch, or a full 40-character commit sha.
# Override with TRUNKD_REF / KEYUP_REF, or the repo URLs with TRUNKD_REPO / KEYUP_REPO.
# TRUNKD_WEB / KEYUP_WEB are the https://github.com/<owner>/<repo> bases the rewritten links
# point at. They follow a github.com TRUNKD_REPO / KEYUP_REPO; with any other repo (a local
# path, a mirror) they stay at github.com/pwsh, so the built site has the same links as CI.
#
# Relative links in the pulled pages that point outside the repo's docs/ directory
# (source files, scripts, the example config) are rewritten to GitHub URLs at the
# same ref by scripts/rewrite-reference-links.py, and GitHub links from one repo's
# docs to the other's become links to the in-site copy; links between pulled pages
# are left for MkDocs to resolve.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$here"

pinned() {
  # Read "  <key>: <value>" from mkdocs.yml.
  sed -n "s/^[[:space:]]*$1:[[:space:]]*\([^[:space:]#]*\).*/\1/p" mkdocs.yml | head -n1
}

TRUNKD_REF="${TRUNKD_REF:-$(pinned trunkd_ref)}"
KEYUP_REF="${KEYUP_REF:-$(pinned keyup_ref)}"
TRUNKD_REPO="${TRUNKD_REPO:-https://github.com/pwsh/trunkd.git}"
KEYUP_REPO="${KEYUP_REPO:-https://github.com/pwsh/keyup.git}"

web_base() {
  # github.com repo URL -> its web base; anything else -> the default pwsh repo.
  case "$1" in
    https://github.com/*) echo "${1%.git}" ;;
    *) echo "https://github.com/pwsh/$2" ;;
  esac
}
TRUNKD_WEB="${TRUNKD_WEB:-$(web_base "$TRUNKD_REPO" trunkd)}"
KEYUP_WEB="${KEYUP_WEB:-$(web_base "$KEYUP_REPO" keyup)}"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

fetch() {
  local name="$1" repo="$2" ref="$3" web="$4"
  if [[ -z "$ref" ]]; then
    echo "fetch-reference: no ref pinned for $name (extra.${name}_ref in mkdocs.yml)" >&2
    exit 1
  fi
  echo "fetch-reference: $name @ $ref from $repo"
  # init + fetch (rather than clone --branch) so a commit sha works as well as a tag.
  git init --quiet "$tmp/$name"
  git -C "$tmp/$name" fetch --quiet --depth 1 "$repo" "$ref"
  git -C "$tmp/$name" -c advice.detachedHead=false checkout --quiet FETCH_HEAD
  local dest="docs/reference/$name"
  rm -rf "$dest"
  mkdir -p "$dest"
  cp -R "$tmp/$name/docs/." "$dest/"
  printf '%s\n' "$ref" > "$dest/.ref"
  python3 scripts/rewrite-reference-links.py "$dest" "$tmp/$name" "$web" trunkd,keyup
}

fetch trunkd "$TRUNKD_REPO" "$TRUNKD_REF" "$TRUNKD_WEB"
fetch keyup "$KEYUP_REPO" "$KEYUP_REF" "$KEYUP_WEB"
