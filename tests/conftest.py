"""Offline test setup.

``tests/data`` mirrors a small part of the QOBLIB repository (the files are
CC BY 4.0, see ``LICENSE.data`` upstream). The ``repo`` fixture makes the
package treat that directory as the remote repository.
"""
from pathlib import Path

import pytest

import qoblib._download as download
import qoblib._index as index_module
from qoblib._download import _git_blob_sha1
from qoblib._index import Index

DATA = Path(__file__).parent / "data"


@pytest.fixture
def repo(tmp_path, monkeypatch):
    files = {
        path.relative_to(DATA).as_posix(): (path.stat().st_size, _git_blob_sha1(path))
        for path in DATA.rglob("*")
        if path.is_file()
    }
    monkeypatch.setattr(index_module, "_current", Index(commit="f" * 40, files=files))
    monkeypatch.setattr(download, "RAW_URL", DATA.as_uri() + "/{path}")
    monkeypatch.setenv("QOBLIB_CACHE_DIR", str(tmp_path / "cache"))
    return DATA
