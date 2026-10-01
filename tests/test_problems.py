"""Offline tests of listing, loading and solution parsing; see conftest.py."""
import numpy as np
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
    Sports,
    Steiner,
    Topology,
)

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


def test_labs(tmp_path):
    assert Labs.instances() == ["labs003", "labs067"]
    problem = Labs.load("labs003")
    assert (problem.n, problem.name) == (3, "labs003")
    best = problem.best_known
    assert best.optimal and best.solution == [-1, 1, 1]
    assert roundtrip(problem, best.solution, tmp_path) == best.solution
    assert problem._format_solution([1, 0, 0]) == "1\n0\n0\n"
    assert not Labs(67).best_known.optimal
    assert Labs(150).best_known is None


def test_birkhoff(tmp_path):
    names = Birkhoff.instances()
    assert len(names) == 20 and "B3_9_1" in names and "B3_3_10" in names
    problem = Birkhoff.load("B3_9_3")
    assert problem.matrix.shape == (3, 3) and (problem.matrix.sum(axis=0) == problem.scale).all()
    weights, permutations = problem.best_known.solution
    assert problem.best_known.optimal and permutations.shape == (len(weights), 3)
    rebuilt = np.zeros((3, 3))
    for weight, permutation in zip(weights, permutations):
        rebuilt[np.arange(3), permutation - 1] += weight
    assert (rebuilt == problem.matrix).all()
    again = roundtrip(problem, (weights, permutations), tmp_path)
    assert again[0] == weights and (again[1] == permutations).all()
    # Only a per-instance .bst.json exists for the sparse matrices.
    sparse = Birkhoff.load("B3_3_2").best_known
    assert not sparse.optimal and sparse.path.name == "B3_3_2.bst.json"
    with pytest.raises(qoblib.QoblibError, match="pass name="):
        Birkhoff.from_file(sparse.path.parents[1] / "instances" / "qbench_03_sparse.json")


def test_steiner(tmp_path):
    (name,) = Steiner.instances()
    problem = Steiner.load(name)
    assert problem.n_nodes == 9 and problem.path.is_dir()
    assert problem.edges[1, 2] == 1 and problem.terminals == {1: [9, 1]} and problem.roots == {1: 1}
    best = problem.best_known
    assert best.optimal and best.solution[0] == (1, 2, 1)
    assert roundtrip(problem, best.solution, tmp_path) == best.solution


def test_sports(tmp_path):
    assert Sports.instances() == ["Early_005_Tiny", "ITC2021_Early_01"]
    problem = Sports.load("Early_005_Tiny")
    assert problem.teams[5] == "Team 5" and len(problem.slots) == 10
    assert problem.root.tag == "Instance"
    best = problem.best_known
    assert best.optimal and len(best.solution) == 30 and best.solution[0] == (5, 4, 4)
    assert roundtrip(problem, best.solution, tmp_path) == best.solution
    assert not Sports.load("ITC2021_Early_01").best_known.optimal
    with pytest.raises(qoblib.QoblibError, match="no solution checker"):
        problem.check(best.solution)


def test_portfolio(tmp_path):
    assert Portfolio.instances() == ["po_a003_t02_orig"]
    problem = Portfolio.load("po_a003_t02_orig", risk_aversion=1e-5)
    assert problem.budget == 3 and problem.risk_aversion == "1e-05"
    assert problem.symbols == ["AAPL", "NVDA", "MSFT"]
    assert problem.prices.shape == (2, 3) and problem.covariances.shape == (2, 3, 3)
    assert np.allclose(problem.covariances[0], problem.covariances[0].T)
    best = problem.best_known
    assert not best.optimal and best.solution == [(0, "AAPL", 0, 1), (0, "MSFT", 1, 0)]
    assert roundtrip(problem, best.solution, tmp_path) == best.solution
    named = Portfolio.load("po_a003_t02_orig_b003_l0.00001")
    assert (named.name, named.budget) == ("po_a003_t02_orig", 3)
    assert named.best_known.solution == best.solution
    assert Portfolio.load("po_a003_t02_orig").best_known is None
    assert Portfolio.load("po_a003_t02_orig", budget=4, risk_aversion=0).best_known is None


def test_independentset(tmp_path):
    problem = IndependentSet.load("karate")
    assert problem.n == 34 and problem.edges.shape == (78, 2)
    best = problem.best_known
    assert best.optimal and len(best.solution) == 20
    chosen = set(best.solution)
    assert not any(u in chosen and v in chosen for u, v in problem.edges)
    assert roundtrip(problem, best.solution, tmp_path) == best.solution


def test_network(tmp_path):
    assert Network.instances() == ["network05"]
    problem = Network.load("network05")
    assert problem.n == 5 and problem.demand.shape == (5, 5) and problem.demand[0, 1] == 24
    edges, flows = problem.best_known.solution
    assert len(edges) == 10 and (1, 3) in edges and all(flows.values())
    assert roundtrip(problem, (edges, flows), tmp_path) == (edges, flows)
    assert Network(24).demand.shape == (24, 24)


def test_routing(tmp_path):
    problem = Routing.load("XSH-n20-k4-01")
    assert problem.capacity == 231 and problem.depot == 1
    assert problem.coords.shape == (21, 2) and tuple(problem.coords[0]) == (84, 96)
    assert problem.demands[0] == 0 and problem.demands[1] == 75
    best = problem.best_known
    assert best.optimal and best.solution[0] == [15, 2, 18, 1, 8]
    assert roundtrip(problem, best.solution, tmp_path) == best.solution


def test_topology(tmp_path):
    assert Topology.instances() == ["topology_15_3"]
    problem = Topology.load("topology_15_3")
    assert (problem.n, problem.degree, problem.bounds) == (15, 3, (3, 3))
    assert Topology(7, 2).bounds is None
    best = problem.best_known
    assert best.optimal and best.solution.shape == (22, 2)
    assert (roundtrip(problem, best.solution, tmp_path) == best.solution).all()
    assert np.bincount(best.solution.ravel()).max() <= 3


def test_every_problem_is_exported():
    assert len(qoblib.PROBLEMS) == 10
    assert sorted(p.directory[:2] for p in qoblib.PROBLEMS) == [f"{i:02d}" for i in range(1, 11)]
