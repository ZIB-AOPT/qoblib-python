"""Run the official Rust checkers on reference solutions of the live repository.

Needs network access and cargo: ``pytest -m network``.
"""
import shutil

import pytest

import qoblib
from qoblib import (
    Birkhoff,
    IndependentSet,
    Labs,
    MarketSplit,
    Network,
    Portfolio,
    Routing,
    Steiner,
    Topology,
)

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


def best_is_valid(problem, objective):
    """Check the reference solution as data and as a file; return it."""
    best = problem.best_known
    for solution in (best.solution, best.path):
        result = problem.check(solution)
        assert (result.status, result.objective) == ("VALID", objective), result.output
    return best.solution


def test_labs():
    best_is_valid(Labs(3), 1)
    worse = Labs(3).check([1, 1, 1])
    assert (worse.status, worse.objective, worse.feasible) == ("SUBOPTIMAL", 5, True)
    assert Labs(3).check([1, 1]).status == "INVALID_FILE"
    assert Labs(150).check([1, -1] * 75).feasible


def test_birkhoff():
    weights, permutations = best_is_valid(Birkhoff.load("B3_9_3"), 5)
    assert Birkhoff.load("B3_9_3").check((weights, permutations[::-1])).status == "INFEASIBLE"
    assert Birkhoff.load("B4_4_1").best_known is not None


def test_steiner():
    problem = Steiner.load("stp_s003_l1_t2_h0_rs97531")
    solution = best_is_valid(problem, 4)
    assert problem.check(solution[:1]).status == "INFEASIBLE"


def test_portfolio():
    problem = Portfolio.load("po_a010_t10_orig_b004_l1e-4")
    solution = best_is_valid(problem, -69482)
    assert not problem.check(solution + [(0, "MSFT", 3, 0), (0, "NVDA", 3, 0)]).feasible
    with pytest.raises(qoblib.QoblibError, match="lambda not given"):
        Portfolio.load("po_a010_t10_orig").check(solution)


def test_independentset():
    problem = IndependentSet.load("karate")
    solution = best_is_valid(problem, 20)
    assert problem.check(solution + [1, 2]).status == "INFEASIBLE"


def test_network():
    edges, flows = best_is_valid(Network(5), 65500)
    assert Network(5).check((edges[1:], flows)).status == "INFEASIBLE"


def test_routing():
    problem = Routing.load("XSH-n20-k4-01")
    solution = best_is_valid(problem, 646)
    assert problem.check(solution[1:]).status == "INFEASIBLE"


def test_topology():
    problem = Topology(15, 3)
    solution = best_is_valid(problem, 3)
    assert problem.check(solution, max_diameter=2).status == "INFEASIBLE"
    assert problem.check(solution[:-1]).objective == 6
    assert problem.check(solution[:-5]).status == "INFEASIBLE"  # disconnected
