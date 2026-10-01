"""Run the official Rust checkers on reference solutions of the live repository.

Needs network access and cargo: ``pytest -m network``.
"""
import shutil

import pytest

import qoblib
from qoblib import MarketSplit

pytestmark = [
    pytest.mark.network,
    pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo is not installed"),
]


@pytest.fixture(scope="session", autouse=True)
def cache(tmp_path_factory):
    patch = pytest.MonkeyPatch()
    patch.setenv("QOBLIB_CACHE_DIR", str(tmp_path_factory.mktemp("cache")))
    yield
    patch.undo()


def test_missing_cargo_is_explained(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    with pytest.raises(qoblib.QoblibError, match="rustup.rs"):
        MarketSplit.load("ms_03_050_002").check([0] * 20)


def test_marketsplit():
    problem = MarketSplit.load("ms_03_050_002")
    best = problem.best_known
    assert problem.check(best.solution).status == "VALID"
    assert problem.check(best.path).feasible
    wrong = problem.check(1 - best.solution)
    assert wrong.status == "INFEASIBLE" and not wrong and wrong.objective is None
