# radio-docs

Source for the user guide to [trunkd](https://github.com/pwsh/trunkd) and
[keyup](https://github.com/pwsh/keyup), published at
<https://pwsh.github.io/radio-docs/>.

The site is built with [MkDocs](https://www.mkdocs.org/) and
[Material for MkDocs](https://squidfunk.github.io/mkdocs-material/). The guide
pages live in `docs/`; the reference pages under `docs/reference/` are pulled
from the two code repositories at the refs pinned in `mkdocs.yml`
(`extra.trunkd_ref`, `extra.keyup_ref`) and are not committed. The guide links
into them, so run `scripts/fetch-reference.sh` before `mkdocs build --strict`.
Links in the pulled pages to files outside the repos' `docs/` folders are
rewritten to GitHub URLs at the pinned ref by `scripts/rewrite-reference-links.py`.

## Build locally

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
scripts/fetch-reference.sh        # pull the reference docs (needs git and python3)
.venv/bin/mkdocs serve            # preview at http://127.0.0.1:8000/
.venv/bin/mkdocs build --strict   # what CI runs
```

To build from local clones instead of GitHub (before a release is pushed, say), point
`TRUNKD_REPO` / `KEYUP_REPO` at them; `TRUNKD_REF` / `KEYUP_REF` override the pinned refs:

```sh
TRUNKD_REPO=../trunkd KEYUP_REPO=../keyup scripts/fetch-reference.sh
```

The rewritten source links still point at `https://github.com/pwsh/<repo>`, as in CI, because
`TRUNKD_WEB` / `KEYUP_WEB` (the GitHub base the links use) only follow a repo URL that is
itself on github.com. Set them only if the docs should link to a fork.

The reference pages are not edited here: change them in their code repository. The fetch step
marks each pulled page `edit_url: false`, and `hooks/reference_pages.py` then hides its edit
and view buttons.

Pushes to `main` are built and deployed to GitHub Pages by
`.github/workflows/pages.yml`.

## License

The documentation text is licensed under the Creative Commons Attribution 4.0
International license ([CC-BY-4.0](LICENSE)). Code samples are under the license
of the repository they come from: trunkd is GPL-3.0-or-later, keyup is
AGPL-3.0-or-later.
