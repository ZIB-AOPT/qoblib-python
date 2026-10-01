import dataclasses

import pytest

import qoblib
import qoblib._index as index_module
from qoblib._download import data_dir, fetch, fetch_many, open_text
from qoblib._index import Index, index

MS = "01-marketsplit/instances/ms_03_050_002.dat"


def test_bundled_index_lists_all_problems():
    directories = {path.split("/")[0] for path in index().files}
    assert len(directories) == 10
    assert MS in index().files
    assert qoblib.get_ref() == index().commit
    assert not any("/models/" in path or path.endswith(".md") for path in index().files)


def test_index_roundtrip():
    assert Index.loads(index().dumps()) == index()


def test_fetch_caches_and_verifies(repo):
    local = fetch(MS)
    assert local == data_dir() / MS
    assert local.read_bytes() == (repo / MS).read_bytes()
    # A cached file is returned without touching the "remote".
    local.write_bytes(b"x" * local.stat().st_size)
    assert fetch(MS).read_bytes().startswith(b"x")


def test_fetch_into_other_root(repo, tmp_path):
    assert fetch(MS, tmp_path / "out") == tmp_path / "out" / MS


def test_fetch_rejects_wrong_hash(repo, monkeypatch):
    files = dict(index().files)
    files[MS] = (files[MS][0], "0" * 40)
    monkeypatch.setattr(index_module, "_current", dataclasses.replace(index(), files=files))
    with pytest.raises(qoblib.QoblibError, match="hash"):
        fetch(MS)
    assert not list(data_dir().rglob("*.part"))


def test_fetch_unknown_file(repo):
    with pytest.raises(qoblib.QoblibError, match="not a known"):
        fetch("01-marketsplit/instances/nope.dat")


def test_fetch_many_and_open_compressed(repo):
    paths = index().under("06-portfolio/instances/po_a003_t02_orig/")
    local = fetch_many(paths)
    assert [p.name for p in local] == ["covariance_matrices.txt.gz", "stock_prices.txt.gz"]
    with open_text(local[1]) as handle:
        assert handle.readline().startswith("#")
