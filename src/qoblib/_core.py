"""Manifest handling and file retrieval for QOBLIB.

The QOBLIB repository publishes a ``manifest.json`` at its root, generated
by ``misc/ci/generate_manifest.py``, which lists every data file with its
size and SHA-256 hash. This module downloads files listed there from
``raw.githubusercontent.com`` at a configurable git ref, verifies them
against the manifest hash, and caches them locally via :mod:`pooch`.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from typing import TypedDict
except ImportError:  # Python 3.7
    from typing_extensions import TypedDict  # type: ignore[assignment]

import pooch

REPOSITORY = "ZIB-AOPT/QOBLIB"
RAW_BASE = f"https://raw.githubusercontent.com/{REPOSITORY}"
DEFAULT_REF = "main"


class Kind:
    """String constants for the file-kind field in the manifest.

    Use these instead of bare strings to get IDE completion and to future-proof
    against any renaming::

        qoblib.fetch("marketsplit", "ms_03_050_002", kind=qoblib.Kind.INSTANCE)
    """

    INSTANCE = "instance"
    SOLUTION = "solution"
    MODEL = "model"
    SUBMISSION = "submission"

    # Convenience tuple for validation — same content as the old KINDS constant.
    _ALL: tuple = ("instance", "solution", "model", "submission")

    def __iter__(self):  # makes Kind() iterable like the old tuple
        return iter(self._ALL)


#: Tuple of valid kind strings.  Prefer :class:`Kind` constants in new code.
KINDS = Kind._ALL


class FileEntry(TypedDict):
    """A single entry from the QOBLIB manifest.

    Returned by :func:`files` and :func:`info`.  All fields are always
    present; ``info`` additionally injects ``url`` and ``ref``.
    """

    path: str
    kind: str
    name: str
    filename: str
    size: int
    sha256: str


_MUTABLE_REFS = {"main", "master"}
_DECOMPRESSIBLE = (".gz", ".xz", ".bz2", ".lzma")
_CANONICAL_DIR = {
    "instance": "instances",
    "solution": "solutions",
    "model": "models",
    "submission": "submissions",
}


class QoblibError(RuntimeError):
    """Raised for QOBLIB-specific failures (missing manifest, bad download)."""


_state: Dict[str, Any] = {
    "ref": os.environ.get("QOBLIB_REF", DEFAULT_REF),
    "manifest_source": os.environ.get("QOBLIB_MANIFEST") or None,
    "manifests": {},
}


# ---------------------------------------------------------------- settings


def set_ref(ref: str) -> None:
    """Pin all lookups and downloads to a git ref of ZIB-AOPT/QOBLIB.

    ``ref`` may be a branch name, a tag, or a commit SHA. For reproducible
    experiments, pin a tag or commit rather than the default ``main``::

        qoblib.set_ref("v1.0")
        qoblib.set_ref("deadbeef")   # commit SHA
    """
    if not ref or not isinstance(ref, str):
        raise ValueError("ref must be a non-empty string")
    _state["ref"] = ref


def get_ref() -> str:
    """Return the currently pinned git ref."""
    return _state["ref"]


def set_version(ref: str) -> None:
    """Deprecated alias for :func:`set_ref`."""
    warnings.warn(
        "set_version() is deprecated; use set_ref() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    set_ref(ref)


def get_version() -> str:
    """Deprecated alias for :func:`get_ref`."""
    warnings.warn(
        "get_version() is deprecated; use get_ref() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return get_ref()


def set_manifest_source(source: Union[str, Path, None]) -> None:
    """Override where the manifest is loaded from.

    ``source`` may be a local file path or an HTTP(S) URL; ``None`` restores
    the default (``manifest.json`` at the pinned ref of the repository).
    Mainly useful for development and testing against a locally generated
    manifest. Can also be set via the ``QOBLIB_MANIFEST`` environment
    variable.
    """
    _state["manifest_source"] = str(source) if source is not None else None
    _state["manifests"].clear()


def cache_dir() -> Path:
    """Return the local cache directory.

    Defaults to an OS-appropriate location (via :func:`pooch.os_cache`) and
    can be overridden with the ``QOBLIB_CACHE_DIR`` environment variable.
    """
    env = os.environ.get("QOBLIB_CACHE_DIR")
    return Path(env).expanduser() if env else Path(pooch.os_cache("qoblib"))


# ---------------------------------------------------------------- manifest


def _safe_ref(ref: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", ref)


def _http_get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "qoblib-python"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read()
    except urllib.error.HTTPError as err:
        if err.code == 404:
            raise QoblibError(
                f"nothing found at {url} (HTTP 404). If this is the manifest, "
                f"either the ref predates manifest generation or the "
                f"'Update manifest' workflow has not run yet."
            ) from err
        raise


def _load_manifest(ref: str) -> Dict[str, Any]:
    cached = _state["manifests"].get(ref)
    if cached is not None:
        return cached

    source = _state["manifest_source"]
    if source is not None:
        parsed = urllib.parse.urlparse(source)
        if parsed.scheme in ("http", "https"):
            data = json.loads(_http_get(source))
        else:
            data = json.loads(Path(source).expanduser().read_text(encoding="utf-8"))
    else:
        url = f"{RAW_BASE}/{urllib.parse.quote(ref, safe='/')}/manifest.json"
        disk = cache_dir() / "manifests" / f"{_safe_ref(ref)}.json"
        if ref not in _MUTABLE_REFS and disk.is_file():
            data = json.loads(disk.read_text(encoding="utf-8"))
        else:
            raw = _http_get(url)
            data = json.loads(raw)
            if ref not in _MUTABLE_REFS:
                disk.parent.mkdir(parents=True, exist_ok=True)
                disk.write_bytes(raw)

    if not isinstance(data, dict) or "problems" not in data:
        raise QoblibError("invalid manifest: missing 'problems' key")
    _state["manifests"][ref] = data
    return data


def _resolve_problem(manifest: Dict[str, Any], problem: str) -> Tuple[str, Dict[str, Any]]:
    problems = manifest["problems"]
    key = problem.strip().lower()
    if key in problems:
        return key, problems[key]
    for slug, data in problems.items():
        if data.get("directory", "").lower() == key:
            return slug, data
    available = ", ".join(sorted(problems))
    raise KeyError(f"unknown problem class {problem!r}; available: {available}")


def _check_kind(kind: Optional[str]) -> None:
    if kind is not None and kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS} or None, got {kind!r}")


# ---------------------------------------------------------------- listing


def problem_classes(*, ref: Optional[str] = None) -> List[str]:
    """Return the sorted list of problem class slugs, e.g. ``'marketsplit'``."""
    manifest = _load_manifest(ref or _state["ref"])
    return sorted(manifest["problems"])


def files(
    problem: str, *, kind: Optional[str] = None, ref: Optional[str] = None
) -> List[FileEntry]:
    """Return manifest entries for a problem class.

    Each entry is a :class:`FileEntry` dict with ``path``, ``kind``, ``name``,
    ``filename``, ``size``, and ``sha256``. Pass *kind* to filter to one
    category (use :class:`Kind` constants or plain strings).
    """
    _check_kind(kind)
    manifest = _load_manifest(ref or _state["ref"])
    _, data = _resolve_problem(manifest, problem)
    entries = data["files"]
    if kind is not None:
        entries = [entry for entry in entries if entry["kind"] == kind]
    return [dict(entry) for entry in entries]  # type: ignore[return-value]


def _names(problem: str, kind: str, ref: Optional[str]) -> List[str]:
    return sorted({entry["name"] for entry in files(problem, kind=kind, ref=ref)})


def instances(problem: str, *, ref: Optional[str] = None) -> List[str]:
    """Return the sorted logical names of all instances of a problem class."""
    return _names(problem, Kind.INSTANCE, ref)


def solutions(problem: str, *, ref: Optional[str] = None) -> List[str]:
    """Return the sorted logical names of all solutions of a problem class."""
    return _names(problem, Kind.SOLUTION, ref)


def models(problem: str, *, ref: Optional[str] = None) -> List[str]:
    """Return the sorted logical names of all model files of a problem class."""
    return _names(problem, Kind.MODEL, ref)


# ---------------------------------------------------------------- fetching


def _match(entries: List[Dict[str, Any]], name: str) -> List[Dict[str, Any]]:
    # 1. Exact full repo path match: "04-steiner/instances/stp_abc/arcs.dat"
    exact_path = [entry for entry in entries if entry["path"] == name]
    if exact_path:
        return exact_path
    # 2. Path suffix match: "stp_abc/arcs.dat" matches "04-steiner/instances/stp_abc/arcs.dat"
    #    Only attempted when name contains a "/" (i.e. is a partial path, not a bare filename).
    #    Used by directory-based plugins (steiner, portfolio) that pass "<instname>/<filename>".
    if "/" in name:
        suffix = name if name.startswith("/") else f"/{name}"
        suffix_match = [entry for entry in entries if entry["path"].endswith(suffix)]
        if suffix_match:
            return suffix_match
    # 3. Exact filename match — only if unambiguous across all entries
    exact_file = [entry for entry in entries if entry["filename"] == name]
    if len(exact_file) == 1:
        return exact_file
    if len(exact_file) > 1:
        return []  # ambiguous filename — caller will raise
    # 4. Logical name match: "stp_abc" matches all files for that instance
    return [entry for entry in entries if entry["name"] == name]


def _select_entry(
    problem: str, name: str, kind: Optional[str], ref: Optional[str]
) -> Tuple[Dict[str, Any], str]:
    ref = ref or _state["ref"]
    _check_kind(kind)
    manifest = _load_manifest(ref)
    slug, data = _resolve_problem(manifest, problem)
    entries = data["files"]
    if kind is not None:
        entries = [entry for entry in entries if entry["kind"] == kind]

    matches = _match(entries, name)
    if not matches:
        raise KeyError(
            f"no {kind or 'file'} named {name!r} in problem class {slug!r}"
        )
    if len(matches) > 1 and kind is not None:
        # Prefer the canonical directory, e.g. solutions/ over a .sol file
        # that sits next to its instance.
        canonical = f"/{_CANONICAL_DIR[kind]}/"
        preferred = [entry for entry in matches if canonical in f"/{entry['path']}"]
        if len(preferred) == 1:
            matches = preferred
    if len(matches) > 1:
        candidates = "\n  ".join(entry["path"] for entry in matches[:10])
        raise ValueError(
            f"{name!r} is ambiguous in problem class {slug!r}; pass the file "
            f"name or the full path instead. Candidates:\n  {candidates}"
        )
    return matches[0], ref


def _raw_url(ref: str, path: str) -> str:
    return (
        f"{RAW_BASE}/{urllib.parse.quote(ref, safe='/')}/"
        f"{urllib.parse.quote(path)}"
    )


def _strip_compression(filename: str) -> str:
    for suffix in _DECOMPRESSIBLE:
        if filename.endswith(suffix):
            return filename[: -len(suffix)]
    return filename


def info(
    problem: str,
    name: str,
    *,
    kind: Optional[str] = Kind.INSTANCE,
    ref: Optional[str] = None,
) -> FileEntry:
    """Return the manifest entry for one file, plus its ``url`` and ``ref``."""
    entry, ref = _select_entry(problem, name, kind, ref)
    result = dict(entry)
    result["ref"] = ref
    result["url"] = _raw_url(ref, entry["path"])
    return result  # type: ignore[return-value]


def _retrieve(
    entry: Dict[str, Any], ref: str, decompress: bool, progressbar: bool
) -> Path:
    url = _raw_url(ref, entry["path"])
    relative = Path(entry["path"])
    local_dir = cache_dir() / _safe_ref(ref) / relative.parent
    processor = None
    if decompress and entry["filename"].endswith(_DECOMPRESSIBLE):
        processor = pooch.Decompress(
            method="auto", name=_strip_compression(entry["filename"])
        )
    known_hash = f"sha256:{entry['sha256']}" if entry.get("sha256") else None
    try:
        result = pooch.retrieve(
            url=url,
            known_hash=known_hash,
            fname=entry["filename"],
            path=local_dir,
            processor=processor,
            progressbar=progressbar,
        )
    except ValueError as err:
        raise QoblibError(
            f"download of {entry['path']} at ref {ref!r} failed verification "
            f"({err}). If the ref is a branch, the manifest may be out of "
            f"sync with the data; retry later or pin a commit via "
            f"qoblib.set_ref()."
        ) from err
    return Path(result)


def fetch(
    problem: str,
    name: str,
    *,
    kind: Optional[str] = Kind.INSTANCE,
    decompress: bool = False,
    progressbar: bool = False,
    ref: Optional[str] = None,
) -> Path:
    """Download one file and return the path to the cached local copy.

    ``name`` may be a logical instance name (``'ms_03_050_002'``), an exact
    file name (``'ms_03_050_002.dat'``), or a full repository path. The file
    is verified against its SHA-256 from the manifest and cached, so
    repeated calls do not download again.

    Set ``decompress=True`` to transparently decompress ``.gz``, ``.xz``,
    ``.bz2``, or ``.lzma`` files; the returned path then points to the
    decompressed copy. Set ``progressbar=True`` for a download progress bar
    (requires ``tqdm``, installable via ``pip install qoblib[progress]``).
    """
    entry, ref = _select_entry(problem, name, kind, ref)
    return _retrieve(entry, ref, decompress, progressbar)


def fetch_all(
    problem: str,
    *,
    kind: str,
    decompress: bool = False,
    progressbar: bool = False,
    ref: Optional[str] = None,
) -> List[Path]:
    """Download all files of a kind for a problem class; returns their paths.

    ``kind`` is required (use a :class:`Kind` constant or a plain string such
    as ``"instance"``). Check the total size first if bandwidth matters::

        sum(f["size"] for f in qoblib.files(problem, kind=qoblib.Kind.INSTANCE))
    """
    _check_kind(kind)
    ref = ref or _state["ref"]
    return [
        _retrieve(entry, ref, decompress, progressbar)
        for entry in files(problem, kind=kind, ref=ref)
    ]
