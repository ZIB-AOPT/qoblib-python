"""Offline tests of listing, loading and solution parsing; see conftest.py."""
import numpy as np
import pytest

import qoblib
from qoblib import MarketSplit

pytestmark = pytest.mark.usefixtures("repo")


def roundtrip(problem, solution, tmp_path):
    """Write *solution* and read it back."""
    return problem.read_solution(problem.write_solution(solution, tmp_path / "solution"))


def test_unknown_instance_suggests_names():
    with pytest.raises(qoblib.QoblibError, match="did you mean ms_03_050_002"):
        MarketSplit.load("ms_03_050_02")


def test_download_to_directory(tmp_path):
    out = MarketSplit.download(dest=tmp_path, progress=False)
    assert out == tmp_path / "01-marketsplit"
    assert (out / "instances" / "ms_03_050_002.dat").is_file()
    assert (out / "solutions" / "ms_03_050_002.opt.sol").is_file()


def test_download_selected_without_solutions(tmp_path):
    out = MarketSplit.download("ms_03_050_002", dest=tmp_path, solutions=False, progress=False)
    assert not (out / "solutions").exists()


def test_check_without_instance_file():
    with pytest.raises(qoblib.QoblibError, match="load\\(\\) or from_file\\(\\)"):
        MarketSplit(A=np.ones((1, 2)), b=np.ones(1))._instance_path()


def test_marketsplit(tmp_path):
    assert MarketSplit.instances() == ["ms_03_050_002"]
    problem = MarketSplit.load("ms_03_050_002")
    assert problem.A.shape == (3, 20) and problem.b.shape == (3,)
    best = problem.best_known
    assert best.optimal and (problem.A @ best.solution == problem.b).all()
    assert (roundtrip(problem, best.solution, tmp_path) == best.solution).all()
    compact = "".join(map(str, best.solution))
    assert (problem._parse_solution(compact) == best.solution).all()
