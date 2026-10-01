"""Download, verify and cache files of the QOBLIB repository."""
from __future__ import annotations

import bz2
import gzip
import hashlib
import lzma
import os
import sys
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Iterable, TextIO

from qoblib._index import REPOSITORY, QoblibError, index

# Tests point this at a local directory through a file:// URL.
RAW_URL = "https://raw.githubusercontent.com/{repository}/{commit}/{path}"

_OPENERS = {".gz": gzip.open, ".xz": lzma.open, ".bz2": bz2.open}
_ATTEMPTS = 3
_WORKERS = 8


def cache_dir() -> Path:
    """Return the local cache directory.

    ``QOBLIB_CACHE_DIR`` overrides the OS default (``~/.cache/qoblib`` on
    Linux). Deleting the directory is always safe.
    """
    env = os.environ.get("QOBLIB_CACHE_DIR")
    if env:
        return Path(env).expanduser()
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return base / "qoblib"


def data_dir() -> Path:
    """Return the cache directory of the QOBLIB commit in use."""
    return cache_dir() / index().commit[:12]


def _git_blob_sha1(path: Path) -> str:
    digest = hashlib.sha1(b"blob %d\0" % path.stat().st_size)
    with open(path, "rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def _download(path: str, target: Path) -> None:
    size, sha = index().files[path]
    url = RAW_URL.format(
        repository=REPOSITORY, commit=index().commit, path=urllib.request.quote(path)
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(f"{target.name}.{threading.get_ident()}.part")
    for attempt in range(1, _ATTEMPTS + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "qoblib-python"})
            with urllib.request.urlopen(request, timeout=60) as response, open(partial, "wb") as out:
                while chunk := response.read(1 << 20):
                    out.write(chunk)
            if _git_blob_sha1(partial) != sha:
                raise QoblibError(f"downloaded file {path} does not match its expected hash")
            os.replace(partial, target)
            return
        except (urllib.error.URLError, OSError, QoblibError) as err:
            partial.unlink(missing_ok=True)
            if attempt == _ATTEMPTS:
                raise QoblibError(f"could not download {path} from {url}: {err}") from err


def fetch(path: str, root: Path | None = None) -> Path:
    """Return the local copy of a repository file, downloading it if needed.

    Files are stored under *root* (default: the cache) with the same relative
    path as in the repository and verified against their git blob hash.
    """
    if path not in index().files:
        raise QoblibError(f"{path} is not a known QOBLIB file at commit {index().commit[:12]}")
    target = (root or data_dir()) / path
    if not (target.is_file() and target.stat().st_size == index().files[path][0]):
        _download(path, target)
    return target


def fetch_many(
    paths: Iterable[str], root: Path | None = None, progress: bool = False
) -> list[Path]:
    """Fetch several repository files in parallel; see :func:`fetch`."""
    paths = list(paths)
    total = sum(index().files[path][0] for path in paths if path in index().files)
    done = [0, 0]
    lock = threading.Lock()

    def one(path: str) -> Path:
        local = fetch(path, root)
        if progress:
            with lock:
                done[0] += 1
                done[1] += index().files[path][0]
                print(
                    f"\r{done[0]}/{len(paths)} files, "
                    f"{done[1] / 1e6:.1f}/{total / 1e6:.1f} MB",
                    end="",
                    file=sys.stderr,
                    flush=True,
                )
        return local

    try:
        with ThreadPoolExecutor(_WORKERS) as pool:
            return list(pool.map(one, paths))
    finally:
        if progress and done[0]:
            print(file=sys.stderr)


def strip_compression(filename: str) -> str:
    """Return *filename* without a trailing ``.gz``, ``.xz`` or ``.bz2``."""
    for suffix in _OPENERS:
        if filename.endswith(suffix):
            return filename[: -len(suffix)]
    return filename


def open_text(path: str | os.PathLike) -> TextIO:
    """Open a text file, decompressing ``.gz``, ``.xz`` and ``.bz2`` on the fly."""
    opener = _OPENERS.get(Path(path).suffix, open)
    return opener(path, "rt", encoding="utf-8")
