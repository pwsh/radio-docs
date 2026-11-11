"""MkDocs hook: honour `edit_url` in a page's front matter.

The reference pages under docs/reference/{trunkd,keyup}/ are copies of the code
repositories' docs/ folders (scripts/fetch-reference.sh). They are not in this repository,
so the edit and view buttons MkDocs derives from `edit_uri` would point at paths that do
not exist. scripts/rewrite-reference-links.py gives each pulled page `edit_url: false`;
this hook turns that into "no edit URL", which hides both buttons. A string value replaces
the URL instead.
"""


def on_page_markdown(markdown, page, config, files):
    if "edit_url" in page.meta:
        value = page.meta["edit_url"]
        page.edit_url = value if isinstance(value, str) and value else None
    return markdown
