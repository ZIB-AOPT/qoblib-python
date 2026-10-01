"""Index of the QOBLIB files this package can download.

The package ships ``index.json``, a snapshot of the instance, solution and
checker files of https://github.com/ZIB-AOPT/QOBLIB at one pinned commit.
Each entry records the file size and its git blob hash, so listing works
offline and every download can be verified.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

REPOSITORY = "ZIB-AOPT/QOBLIB"
_API = f"https://api.github.com/repos/{REPOSITORY}"

# Instances, solutions, and the sources needed to build the Rust checkers.
_WANTED = re.compile(
    r"^\d\d-[a-z]+/(?:(?:instances|solutions)/.+|check/(?:Cargo\.(?:toml|lock)|src/.+))$"
)


class QoblibError(RuntimeError):
    """Raised for QOBLIB-specific failures (download, checker, bad input)."""


@dataclass(frozen=True)
class Index:
    """Files of the QOBLIB repository at one commit."""

    commit: str
    files: dict[str, tuple[int, str]]  # repository path -> (size, git blob sha1)

    def under(self, prefix: str) -> list[str]:
        """Return the sorted paths that start with *prefix*."""
        return sorted(path for path in self.files if path.startswith(prefix))

    def dumps(self) -> str:
        """Serialise to JSON with one file per line, for readable diffs."""
        lines = [
            f"  {json.dumps(path)}: [{size}, {json.dumps(sha)}]"
            for path, (size, sha) in sorted(self.files.items())
        ]
        return (
            f'{{"repository": {json.dumps(REPOSITORY)}, '
            f'"commit": {json.dumps(self.commit)}, "files": {{\n'
            + ",\n".join(lines)
            + "\n}}\n"
        )

    @classmethod
    def loads(cls, text: str) -> Index:
        data = json.loads(text)
        files = {path: (size, sha) for path, (size, sha) in data["files"].items()}
        return cls(commit=data["commit"], files=files)


def _api_get(url: str, accept: str) -> bytes:
    request = urllib.request.Request(
        url, headers={"User-Agent": "qoblib-python", "Accept": accept}
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read()
    except urllib.error.URLError as err:
        raise QoblibError(f"could not query GitHub at {url}: {err}") from err


def build_index(ref: str = "main") -> Index:
    """Build an index of the QOBLIB repository at *ref* from the GitHub API."""
    commit = _api_get(f"{_API}/commits/{ref}", "application/vnd.github.sha").decode().strip()
    tree = json.loads(
        _api_get(f"{_API}/git/trees/{commit}?recursive=1", "application/vnd.github+json")
    )
    if tree.get("truncated"):
        raise QoblibError("GitHub returned a truncated file listing for QOBLIB")
    files = {
        entry["path"]: (entry["size"], entry["sha"])
        for entry in tree["tree"]
        if entry["type"] == "blob"
        and _WANTED.match(entry["path"])
        and not entry["path"].endswith(".md")
    }
    return Index(commit=commit, files=files)


_bundled: Index | None = None
_current: Index | None = None


def index() -> Index:
    """Return the index in use: the bundled one unless :func:`set_ref` was called."""
    global _bundled
    if _current is not None:
        return _current
    if _bundled is None:
        text = resources.files("qoblib").joinpath("index.json").read_text(encoding="utf-8")
        _bundled = Index.loads(text)
    return _bundled


def get_ref() -> str:
    """Return the commit of ZIB-AOPT/QOBLIB that files are taken from."""
    return index().commit


def set_ref(ref: str | None) -> None:
    """Use the QOBLIB repository at *ref* (branch, tag or commit) instead of
    the commit bundled with this package. ``None`` restores the bundled one.

    This queries the GitHub API once; the listing of a full commit hash is
    kept in the cache directory afterwards.
    """
    global _current
    if ref is None:
        _current = None
        return
    from qoblib._download import cache_dir

    cached = cache_dir() / "index" / f"{ref}.json"
    if re.fullmatch(r"[0-9a-f]{40}", ref) and cached.is_file():
        _current = Index.loads(cached.read_text(encoding="utf-8"))
        return
    built = build_index(ref)
    target = cache_dir() / "index" / f"{built.commit}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(built.dumps(), encoding="utf-8")
    _current = built


def write_bundled_index(ref: str = "main") -> Path:
    """Regenerate the ``index.json`` shipped with the package (maintainers)."""
    target = Path(__file__).with_name("index.json")
    target.write_text(build_index(ref).dumps(), encoding="utf-8")
    return target
