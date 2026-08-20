import json

import pytest

import qoblib
from qoblib import _core


@pytest.fixture()
def manifest(tmp_path):
    data = {
        "schema_version": 1,
        "repository": "ZIB-AOPT/QOBLIB",
        "problems": {
            "marketsplit": {
                "directory": "01-marketsplit",
                "files": [
                    {
                        "path": "01-marketsplit/instances/ms_a.dat",
                        "kind": "instance",
                        "name": "ms_a",
                        "filename": "ms_a.dat",
                        "size": 3,
                        "sha256": "0" * 64,
                    },
                    {
                        "path": "01-marketsplit/instances/ms_a.opt.sol",
                        "kind": "solution",
                        "name": "ms_a",
                        "filename": "ms_a.opt.sol",
                        "size": 3,
                        "sha256": "1" * 64,
                    },
                    {
                        "path": "01-marketsplit/solutions/ms_a.opt.sol",
                        "kind": "solution",
                        "name": "ms_a",
                        "filename": "ms_a.opt.sol",
                        "size": 3,
                        "sha256": "2" * 64,
                    },
                    {
                        "path": "01-marketsplit/models/ms_a.lp.xz",
                        "kind": "model",
                        "name": "ms_a",
                        "filename": "ms_a.lp.xz",
                        "size": 3,
                        "sha256": "3" * 64,
                    },
                ],
            },
            "labs": {"directory": "02-labs", "files": []},
        },
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    qoblib.set_manifest_source(path)
    yield data
    qoblib.set_manifest_source(None)


def test_problem_classes(manifest):
    assert qoblib.problem_classes() == ["labs", "marketsplit"]


def test_directory_alias(manifest):
    assert qoblib.instances("01-marketsplit") == ["ms_a"]
    assert qoblib.instances("MarketSplit") == ["ms_a"]


def test_listing(manifest):
    assert qoblib.instances("marketsplit") == ["ms_a"]
    assert qoblib.solutions("marketsplit") == ["ms_a"]
    assert qoblib.models("marketsplit") == ["ms_a"]
    assert qoblib.instances("labs") == []


def test_files_filter(manifest):
    entries = qoblib.files("marketsplit", kind="solution")
    assert len(entries) == 2
    assert all(entry["kind"] == "solution" for entry in entries)


def test_solution_prefers_canonical_directory(manifest):
    entry = qoblib.info("marketsplit", "ms_a", kind="solution")
    assert entry["path"] == "01-marketsplit/solutions/ms_a.opt.sol"


def test_full_path_overrides_canonical_preference(manifest):
    entry = qoblib.info(
        "marketsplit", "01-marketsplit/instances/ms_a.opt.sol", kind="solution"
    )
    assert entry["sha256"] == "1" * 64


def test_info_url_uses_ref(manifest, monkeypatch):
    monkeypatch.setitem(_core._state, "ref", "deadbeef")
    entry = qoblib.info("marketsplit", "ms_a")
    assert entry["ref"] == "deadbeef"
    assert entry["url"] == (
        "https://raw.githubusercontent.com/ZIB-AOPT/QOBLIB/deadbeef/"
        "01-marketsplit/instances/ms_a.dat"
    )


def test_unknown_problem(manifest):
    with pytest.raises(KeyError, match="unknown problem class"):
        qoblib.instances("does-not-exist")


def test_unknown_name(manifest):
    with pytest.raises(KeyError, match="no instance named"):
        qoblib.info("marketsplit", "nope")


def test_bad_kind(manifest):
    with pytest.raises(ValueError, match="kind must be one of"):
        qoblib.files("marketsplit", kind="banana")


def test_set_ref_validation():
    with pytest.raises(ValueError):
        qoblib.set_ref("")


def test_set_version_validation():
    """set_version is a deprecated alias; still validates the argument."""
    import warnings
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        with pytest.raises(ValueError):
            qoblib.set_version("")


def test_match_suffix_path():
    """Path suffix matching resolves directory-based instances (steiner, portfolio)."""
    from qoblib._core import _match
    entries = [
        {"path": "04-steiner/instances/stp_abc/arcs.dat",  "kind": "instance", "name": "stp_abc", "filename": "arcs.dat"},
        {"path": "04-steiner/instances/stp_abc/terms.dat", "kind": "instance", "name": "stp_abc", "filename": "terms.dat"},
        {"path": "04-steiner/instances/stp_xyz/arcs.dat",  "kind": "instance", "name": "stp_xyz", "filename": "arcs.dat"},
    ]
    # Suffix match resolves to exactly one file
    r = _match(entries, "stp_abc/arcs.dat")
    assert len(r) == 1 and r[0]["path"].endswith("stp_abc/arcs.dat")

    r = _match(entries, "stp_abc/terms.dat")
    assert len(r) == 1 and r[0]["filename"] == "terms.dat"

    # Full path match still works
    r = _match(entries, "04-steiner/instances/stp_abc/arcs.dat")
    assert len(r) == 1

    # Logical name returns all files for that instance
    r = _match(entries, "stp_abc")
    assert len(r) == 2

    # Ambiguous filename returns empty (caller raises)
    r = _match(entries, "arcs.dat")
    assert r == []

    # Unambiguous filename returns single match
    r = _match(entries, "terms.dat")
    assert len(r) == 1




@pytest.mark.network
def test_live_roundtrip(tmp_path, monkeypatch):
    """End-to-end against the live repository. Run with: pytest -m network"""
    monkeypatch.setenv("QOBLIB_CACHE_DIR", str(tmp_path))
    qoblib.set_manifest_source(None)
    try:
        names = qoblib.instances("marketsplit")
        path = qoblib.fetch("marketsplit", names[0])
    except qoblib.QoblibError as err:
        pytest.skip(f"manifest not deployed yet: {err}")
    assert path.is_file()
    assert path.stat().st_size > 0
