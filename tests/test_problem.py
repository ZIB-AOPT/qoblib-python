"""Tests for the Problem plugin layer (no network access required)."""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import pytest

import qoblib
from qoblib._problem import CheckResult, CheckStatus, Problem, get_problem, register_problem
from qoblib.problems.labs import LABSSolution, LABSProblem, _OPTIMAL_ENERGY
from qoblib.problems.marketsplit import (
    MarketSplitInstance,
    MarketSplitProblem,
    MarketSplitSolution,
    _parse_instance,
    _parse_solution,
)


# ------------------------------------------------------------------ fixtures


@pytest.fixture()
def manifest(tmp_path):
    """Minimal manifest with one marketsplit instance + solution."""
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
                        "size": 10,
                        "sha256": "0" * 64,
                    },
                    {
                        "path": "01-marketsplit/solutions/ms_a.opt.sol",
                        "kind": "solution",
                        "name": "ms_a",
                        "filename": "ms_a.opt.sol",
                        "size": 4,
                        "sha256": "1" * 64,
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


# ------------------------------------------------------------------ CheckResult / CheckStatus


def test_checkresult_bool():
    assert CheckResult(feasible=True)
    assert not CheckResult(feasible=False)


def test_checkresult_repr_feasible():
    r = CheckResult(feasible=True, status=CheckStatus.VALID, objective=0.0)
    assert "VALID" in repr(r)
    assert "obj=0.0" in repr(r)


def test_checkresult_repr_infeasible():
    r = CheckResult(feasible=False, status=CheckStatus.INFEASIBLE, violations=["row 0 violated"])
    assert "INFEASIBLE" in repr(r)
    assert "1 violation" in repr(r)


def test_checkresult_repr_suboptimal():
    r = CheckResult(feasible=True, status=CheckStatus.SUBOPTIMAL, objective=6.0)
    assert "SUBOPTIMAL" in repr(r)


def test_checkresult_defaults():
    r = CheckResult(feasible=True)
    assert r.status is None
    assert r.objective is None
    assert r.violations == []
    assert r.details == {}


def test_checkstatus_constants():
    assert CheckStatus.VALID == "VALID"
    assert CheckStatus.SUBOPTIMAL == "SUBOPTIMAL"
    assert CheckStatus.INFEASIBLE == "INFEASIBLE"
    assert CheckStatus.INVALID_FILE == "INVALID_FILE"
    assert CheckStatus.USAGE == "USAGE"


# ------------------------------------------------------------------ Problem base class


def test_problem_base_requires_slug():
    with pytest.raises(TypeError, match="must define a non-empty 'slug'"):

        class BadProblem(Problem):
            slug = ""

        BadProblem()


def test_problem_base_raises_not_implemented(manifest):
    p = get_problem("marketsplit")
    assert isinstance(p, Problem)
    assert "ms_a" in p.instances()
    assert "ms_a" in p.solutions()


def test_generic_fallback_problem(manifest):
    """A slug with no registered plugin still returns a usable Problem."""
    p = get_problem("labs")
    assert isinstance(p, Problem)
    assert p.slug == "labs"
    assert p.instances() == []


def test_generic_unknown_slug_raises_on_load(manifest):
    """An unregistered, unknown slug raises on listing (manifest key missing)."""
    p = get_problem("does-not-exist")
    with pytest.raises(KeyError, match="unknown problem class"):
        p.instances()


def test_get_problem_repr(manifest):
    p = get_problem("marketsplit")
    assert "marketsplit" in repr(p)


def test_compute_objective_base_returns_none():
    """Base compute_objective() returns None by default."""
    ms = MarketSplitProblem()
    inst = MarketSplitInstance(n_rows=1, n_cols=2, A=[[1, 1]], b=[2])
    sol = MarketSplitSolution(x=[1, 1])
    # MarketSplitProblem overrides compute_objective to return 0.0
    assert ms.compute_objective(inst, sol) == 0.0


def test_compute_objective_base_default():
    """A plain Problem subclass returns None from compute_objective."""
    @register_problem
    class _TrivialProblem(Problem):
        slug = "_trivial_obj_test"
    p = _TrivialProblem()
    assert p.compute_objective(None, None) is None


# ------------------------------------------------------------------ registry


def test_register_problem_decorator():
    @register_problem
    class DummyProblem(Problem):
        slug = "dummy_test_abc"
        description = "Test"

    p = get_problem("dummy_test_abc")
    assert isinstance(p, DummyProblem)
    assert "dummy_test_abc" in qoblib.registered_problems()


def test_register_problem_bad_type():
    with pytest.raises(TypeError):
        register_problem(object())  # type: ignore


def test_register_problem_no_slug():
    with pytest.raises(ValueError, match="must define a non-empty 'slug'"):

        @register_problem
        class NoSlug(Problem):
            slug = ""


def test_registered_problems_contains_builtins():
    names = qoblib.registered_problems()
    assert "marketsplit" in names
    assert "labs" in names


# ------------------------------------------------------------------ Kind constants


def test_kind_constants():
    assert qoblib.Kind.INSTANCE == "instance"
    assert qoblib.Kind.SOLUTION == "solution"
    assert qoblib.Kind.MODEL == "model"
    assert qoblib.Kind.SUBMISSION == "submission"


def test_kinds_backward_compat():
    """KINDS tuple is still present for backward compatibility."""
    assert "instance" in qoblib.KINDS
    assert len(qoblib.KINDS) == 4


# ------------------------------------------------------------------ set_ref / get_ref


def test_set_ref_get_ref(monkeypatch):
    from qoblib import _core
    monkeypatch.setitem(_core._state, "ref", "main")
    qoblib.set_ref("v2.0")
    assert qoblib.get_ref() == "v2.0"
    monkeypatch.setitem(_core._state, "ref", "main")  # restore


def test_set_ref_validation():
    with pytest.raises(ValueError):
        qoblib.set_ref("")


def test_set_version_deprecated():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        qoblib.set_version("main")
    assert any("deprecated" in str(warning.message).lower() for warning in w)
    assert any(issubclass(warning.category, DeprecationWarning) for warning in w)


def test_get_version_deprecated():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        qoblib.get_version()
    assert any(issubclass(warning.category, DeprecationWarning) for warning in w)


# ------------------------------------------------------------------ fetch_all requires kind


def test_fetch_all_requires_kind_argument(manifest):
    """fetch_all() no longer accepts kind=None — kind is a required kwarg."""
    ms = get_problem("marketsplit")
    with pytest.raises(TypeError):
        ms.fetch_all()  # type: ignore[call-arg]


# ------------------------------------------------------------------ MarketSplit parser
# Instance format: n_rows n_cols / row: w1..wn rhs


def test_parse_instance(tmp_path):
    dat = tmp_path / "test.dat"
    dat.write_text("2 3\n1 0 1 1\n0 1 1 1\n", encoding="utf-8")
    inst = _parse_instance(dat, "test")
    assert inst.n_rows == 2
    assert inst.n_cols == 3
    assert inst.A == [[1, 0, 1], [0, 1, 1]]
    assert inst.b == [1, 1]
    assert inst.name == "test"


def test_parse_instance_with_comments(tmp_path):
    dat = tmp_path / "test.dat"
    dat.write_text("# comment\n2 3\n1 0 1 1\n0 1 1 1\n", encoding="utf-8")
    inst = _parse_instance(dat, "test")
    assert inst.n_rows == 2


def test_parse_instance_with_commas(tmp_path):
    dat = tmp_path / "test.dat"
    dat.write_text("2,3\n1,0,1,1\n0,1,1,1\n", encoding="utf-8")
    inst = _parse_instance(dat, "test")
    assert inst.A == [[1, 0, 1], [0, 1, 1]]


def test_parse_solution(tmp_path):
    sol_file = tmp_path / "test.sol"
    sol_file.write_text("1 0 1\n", encoding="utf-8")
    sol = _parse_solution(sol_file, "test")
    assert sol.x == [1, 0, 1]
    assert sol.name == "test"


def test_parse_instance_invalid(tmp_path):
    bad = tmp_path / "bad.dat"
    bad.write_text("not a number", encoding="utf-8")
    with pytest.raises(ValueError, match="Failed to parse"):
        _parse_instance(bad)


def test_solution_to_checker_string():
    sol = MarketSplitSolution(x=[1, 0, 1, 0])
    assert sol.to_checker_string() == "1010"


# ------------------------------------------------------------------ MarketSplit compute_objective


def _make_instance(A, b):
    return MarketSplitInstance(n_rows=len(b), n_cols=len(A[0]), A=A, b=b)


def test_marketsplit_compute_objective_returns_zero():
    """Market split is a pure feasibility problem — objective is always 0.0."""
    inst = _make_instance([[1, 0, 1], [0, 1, 1]], [2, 2])
    sol = MarketSplitSolution(x=[1, 1, 1])
    assert MarketSplitProblem().compute_objective(inst, sol) == 0.0


# ------------------------------------------------------------------ LABS compute_objective


def _labs():
    return LABSProblem()


def test_labs_compute_objective_known_sequence():
    # n=4 sequence [1,-1,-1,1]: E = C1^2 + C2^2 + C3^2 = 1 + 4 + 1 = 6
    sol = LABSSolution(s=[1, -1, -1, 1])
    energy = _labs().compute_objective(4, sol)
    assert energy == 6.0


def test_labs_compute_objective_optimal():
    # For n=4, optimal E = 2 (from _OPTIMAL_ENERGY[4])
    # sequence [1,1,-1,1]: E=2
    sol = LABSSolution(s=[1, 1, -1, 1])
    energy = _labs().compute_objective(4, sol)
    assert energy == float(_OPTIMAL_ENERGY[4])


def test_labs_compute_objective_zero_one_encoding():
    """{0,1} and {-1,+1} encodings produce the same energy."""
    sol_pm = LABSSolution(s=[1, -1, -1, 1])
    sol_01 = LABSSolution(s=[1, 0, 0, 1])
    labs = _labs()
    assert labs.compute_objective(4, sol_pm) == labs.compute_objective(4, sol_01)


def test_labs_load_instance_from_string():
    labs = _labs()
    assert labs.load_instance("32") == 32
    assert labs.load_instance("labs_032.lp.xz") == 32


def test_labs_make_instance():
    labs = _labs()
    assert labs.make_instance(16) == 16
    with pytest.raises(ValueError):
        labs.make_instance(0)


def test_labs_to_checker_string_pm():
    """±1 encoding is mapped to 0/1 for the Rust checker."""
    sol = LABSSolution(s=[1, -1, -1, 1])
    assert sol.to_checker_string() == "1001"


def test_labs_to_checker_string_01():
    sol = LABSSolution(s=[1, 0, 0, 1])
    assert sol.to_checker_string() == "1001"


# ------------------------------------------------------------------ check_solution raises QoblibError without Cargo


def _cargo_available() -> bool:
    import shutil
    return shutil.which("cargo") is not None


def test_check_solution_raises_without_cargo(monkeypatch):
    """check_solution() raises QoblibError when Cargo is not available."""
    import shutil
    monkeypatch.setattr(shutil, "which", lambda _: None)  # pretend no cargo

    # Also clear build cache so we don't use a previously built binary
    from qoblib._checker import _build_cache
    _build_cache.clear()

    inst = _make_instance([[1, 1]], [1])
    inst.path = Path("/tmp/fake.dat")
    sol = MarketSplitSolution(x=[1, 0])

    with pytest.raises(qoblib.QoblibError, match="cargo"):
        MarketSplitProblem().check_solution(inst, sol)


# ------------------------------------------------------------------ Rust checker integration


@pytest.mark.skipif(not _cargo_available(), reason="Cargo not installed")
def test_rust_checker_marketsplit(tmp_path):
    """Build and invoke the real Rust checker for market-split (network required)."""
    from qoblib._checker import get_checker_binary, _build_cache
    _build_cache.clear()

    binary = get_checker_binary("marketsplit", "main")
    assert binary is not None and binary.is_file()

    inst_file = tmp_path / "inst.dat"
    inst_file.write_text("1 2\n1 1 1\n", encoding="utf-8")
    sol_file = tmp_path / "sol.txt"
    sol_file.write_text("10\n", encoding="utf-8")  # x1=1, x2=0 → sum=1 ✓

    import subprocess
    result = subprocess.run(
        [str(binary), str(inst_file), str(sol_file)],
        capture_output=True, text=True
    )
    assert result.returncode == 0, f"Checker failed:\n{result.stdout}\n{result.stderr}"


@pytest.mark.skipif(not _cargo_available(), reason="Cargo not installed")
def test_rust_checker_labs(tmp_path):
    """Build and invoke the real Rust checker for LABS."""
    from qoblib._checker import get_checker_binary, _build_cache
    _build_cache.clear()

    binary = get_checker_binary("labs", "main")
    assert binary is not None and binary.is_file()

    sol_file = tmp_path / "sol.txt"
    sol_file.write_text("1101\n", encoding="utf-8")  # n=4 optimal [1,1,-1,1]

    import subprocess
    result = subprocess.run(
        [str(binary), "4", str(sol_file)],
        capture_output=True, text=True
    )
    assert result.returncode in (0, 20), \
        f"Unexpected exit {result.returncode}:\n{result.stdout}\n{result.stderr}"


@pytest.mark.skipif(not _cargo_available(), reason="Cargo not installed")
def test_check_solution_uses_rust_when_available(tmp_path):
    """check_solution() returns a Rust-backed result for file-backed instances."""
    from qoblib._checker import get_checker_binary, _build_cache
    _build_cache.clear()

    binary = get_checker_binary("marketsplit", "main")
    assert binary is not None

    inst_file = tmp_path / "inst.dat"
    inst_file.write_text("1 2\n1 1 1\n", encoding="utf-8")
    from qoblib.problems.marketsplit import _parse_instance, MarketSplitSolution
    inst = _parse_instance(inst_file, "test")
    inst.path = inst_file

    sol = MarketSplitSolution(x=[1, 0])

    ms = MarketSplitProblem()
    result = ms.check_solution(inst, sol)
    assert result.feasible
    assert result.details.get("checker") == "rust"
    assert result.status == CheckStatus.VALID
    assert result.objective == 0.0  # compute_objective called after VALID


# ------------------------------------------------------------------ get_problem OO listing


def test_get_problem_instances(manifest):
    ms = get_problem("marketsplit")
    assert isinstance(ms, MarketSplitProblem)
    assert ms.instances() == ["ms_a"]
    assert ms.solutions() == ["ms_a"]


def test_get_problem_files(manifest):
    ms = get_problem("marketsplit")
    entries = ms.files(kind="instance")
    assert len(entries) == 1
    assert entries[0]["name"] == "ms_a"


def test_get_problem_files_with_kind_constant(manifest):
    ms = get_problem("marketsplit")
    entries = ms.files(kind=qoblib.Kind.INSTANCE)
    assert len(entries) == 1


# ================================================================ new problem plugins

# ------------------------------------------------------------------ registry completeness

def test_all_problem_classes_registered():
    """Every QOBLIB problem class has a registered plugin."""
    expected = {
        "birkhoff", "independentset", "labs", "marketsplit",
        "network", "portfolio", "routing", "sports", "steiner", "topology",
    }
    registered = set(qoblib.registered_problems())
    missing = expected - registered
    assert not missing, f"Missing registrations: {missing}"


# ------------------------------------------------------------------ Birkhoff


def test_birkhoff_compute_objective():
    from qoblib.problems.birkhoff import BirkhoffInstance, BirkhoffSolution, BirkhoffProblem

    inst = BirkhoffInstance(instances={
        "B2": {"n": 2, "scale": 1000, "scaled_doubly_stochastic_matrix": [500, 500, 500, 500]},
    })
    sol = BirkhoffSolution(solutions={
        "B2": {"permutations": [1, 2, 2, 1], "weights": [500.0, 500.0]},
    })
    obj = BirkhoffProblem().compute_objective(inst, sol)
    assert obj == 2.0  # two permutation matrices


def test_birkhoff_to_checker_string():
    from qoblib.problems.birkhoff import BirkhoffSolution
    sol = BirkhoffSolution(solutions={"B2": {"weights": [500.0, 500.0]}})
    s = sol.to_checker_string()
    assert "B2" in s
    assert "weights" in s


# ------------------------------------------------------------------ Steiner


def test_steiner_compute_objective(tmp_path):
    from qoblib.problems.steiner import (
        SteinerSolution, SteinerProblem,
        _parse_instance, _parse_sol,
    )

    arcs = tmp_path / "arcs.dat"
    arcs.write_text("1 2 5\n2 3 4\n1 3 10\n", encoding="utf-8")
    terms = tmp_path / "terms.dat"
    terms.write_text("1 0\n3 0\n", encoding="utf-8")
    sol_file = tmp_path / "sol.sol"
    sol_file.write_text("1 2 0\n2 3 0\n", encoding="utf-8")

    inst = _parse_instance(arcs, terms, "test")
    assert inst.n_nodes == 3
    assert inst.n_nets == 1
    assert frozenset({1, 3}) == inst.terminals[0]
    assert inst.nodes == frozenset({1, 2, 3})

    sol = SteinerSolution(edges=_parse_sol(sol_file), path=sol_file)
    obj = SteinerProblem().compute_objective(inst, sol)
    assert obj == 9.0  # edge weights 5 + 4


# ------------------------------------------------------------------ Independent Set


def test_independentset_compute_objective():
    from qoblib.problems.independentset import StableSetInstance, StableSetSolution, StableSetProblem

    inst = StableSetInstance(n=4, edges=frozenset([(1, 2), (2, 3), (3, 4)]))
    sol = StableSetSolution(selected={1, 3})
    obj = StableSetProblem().compute_objective(inst, sol)
    assert obj == 2.0  # two nodes selected


def test_independentset_parse_gph(tmp_path):
    from qoblib.problems.independentset import _parse_gph

    gph = tmp_path / "test.gph"
    gph.write_text("c example\np edge 4 3\ne 1 2\ne 2 3\ne 3 4\n", encoding="utf-8")
    inst = _parse_gph(gph)
    assert inst.n == 4
    assert (1, 2) in inst.edges
    assert len(inst.edges) == 3


def test_independentset_solution_to_checker_string():
    from qoblib.problems.independentset import StableSetSolution

    sol = StableSetSolution(selected={1, 3})
    s = sol.to_checker_string()
    assert s == "101"


# ------------------------------------------------------------------ Routing (CVRP)


def test_routing_compute_objective():
    from qoblib.problems.routing import CVRPInstance, CVRPSolution, RoutingProblem

    inst = CVRPInstance(
        name="test",
        n=4,
        capacity=15,
        coords={1: (0.0, 0.0), 2: (3.0, 0.0), 3: (3.0, 4.0), 4: (0.0, 4.0)},
        demands={1: 0, 2: 5, 3: 5, 4: 5},
        depot=1,
    )
    sol = CVRPSolution(routes=[[2, 3], [4]])
    obj = RoutingProblem().compute_objective(inst, sol)
    # Route 1: depot(1)→2→3→depot = 3 + 4 + 5 = 12
    # Route 2: depot(1)→4→depot = 4 + 4 = 8
    assert obj == 20.0


def test_routing_to_checker_string():
    from qoblib.problems.routing import CVRPSolution

    sol = CVRPSolution(routes=[[2, 3], [4]], claimed_cost=100)
    s = sol.to_checker_string()
    assert "Route #1: 2 3" in s
    assert "Route #2: 4" in s
    assert "Cost 100" in s


# ------------------------------------------------------------------ Topology


def test_topology_compute_objective_diameter():
    from qoblib.problems.topology import TopologyInstance, TopologySolution, TopologyProblem

    # 4-cycle: diameter = 2
    inst = TopologyInstance(n=4, degree=2, diameter=2)
    sol = TopologySolution(n=4, edges=frozenset([(1, 2), (2, 3), (3, 4), (1, 4)]))
    obj = TopologyProblem().compute_objective(inst, sol)
    assert obj == 2.0


def test_topology_compute_objective_disconnected():
    from qoblib.problems.topology import TopologyInstance, TopologySolution, TopologyProblem

    # Disconnected graph → compute_objective returns None (Rust checker handles infeasibility)
    inst = TopologyInstance(n=4, degree=2)
    sol = TopologySolution(n=4, edges=frozenset([(1, 2), (3, 4)]))
    obj = TopologyProblem().compute_objective(inst, sol)
    assert obj is None


def test_topology_load_instance_from_name():
    from qoblib.problems.topology import TopologyProblem

    top = TopologyProblem()
    inst = top.load_instance("topology_15_3")
    assert inst.n == 15
    assert inst.degree == 3


def test_topology_parse_gph(tmp_path):
    from qoblib.problems.topology import _parse_gph

    gph = tmp_path / "test.gph"
    gph.write_text(
        "c Undirected Graph with Diameter 2\np edge 4 4\ne 1 2\ne 2 3\ne 3 4\ne 1 4\n",
        encoding="utf-8",
    )
    sol = _parse_gph(gph)
    assert sol.n == 4
    assert sol.diameter == 2
    assert len(sol.edges) == 4


# ------------------------------------------------------------------ Network


def test_network_compute_objective():
    from qoblib.problems.network import NetworkInstance, NetworkSolution, NetworkProblem

    inst = NetworkInstance(n=3, demand={(1, 2): 10})
    sol = NetworkSolution(objective=42.5)
    obj = NetworkProblem().compute_objective(inst, sol)
    assert obj == 42.5


def test_network_compute_objective_none():
    from qoblib.problems.network import NetworkInstance, NetworkSolution, NetworkProblem

    inst = NetworkInstance(n=3, demand={})
    sol = NetworkSolution(objective=None)
    assert NetworkProblem().compute_objective(inst, sol) is None


# ------------------------------------------------------------------ Portfolio


def test_portfolio_parse_solution(tmp_path):
    from qoblib.problems.portfolio import _parse_solution

    sol_file = tmp_path / "test.sol"
    sol_file.write_text(
        "instance po_test\nbudget 4\nlambda 0.0001\nobjective -100\n"
        "# period symbol long short\n0 AAPL 1 0\n1 META 0 2\n",
        encoding="utf-8",
    )
    sol = _parse_solution(sol_file)
    assert sol.instance_name == "po_test"
    assert sol.budget == 4
    assert abs(sol.lambda_ - 0.0001) < 1e-9
    assert sol.objective == -100.0
    assert len(sol.positions) == 2
    assert sol.positions[0].symbol == "AAPL"


def test_portfolio_compute_objective():
    from qoblib.problems.portfolio import (
        PortfolioInstance, PortfolioSolution, PortfolioProblem,
        PortfolioPrices, PortfolioCovariances,
    )

    prices = PortfolioPrices(symbols=["AAPL"], dates=["2020-01-01"], prices={("2020-01-01", "AAPL"): 100.0})
    covs = PortfolioCovariances(dates=["2020-01-01"], symbols=["AAPL"], covariances={("2020-01-01", "AAPL", "AAPL"): 0.01})
    inst = PortfolioInstance(
        instance_dir=Path("/tmp/fake"),
        name="po_test",
        n_periods=1,
        n_assets=1,
        symbols=["AAPL"],
        prices=prices,
        covariances=covs,
    )
    sol = PortfolioSolution(objective=-69482.0)
    obj = PortfolioProblem().compute_objective(inst, sol)
    assert obj == -69482.0


def test_portfolio_parse_prices(tmp_path):
    import gzip
    from qoblib.problems.portfolio import _parse_prices, _parse_covariances

    # Write a minimal prices CSV (gzip)
    prices_csv = "date,symbol,price\n2020-01-01,AAPL,300.0\n2020-01-01,META,200.0\n2020-01-02,AAPL,310.0\n2020-01-02,META,205.0\n"
    prices_file = tmp_path / "stock_prices.csv.gz"
    with gzip.open(prices_file, "wt", encoding="utf-8") as f:
        f.write(prices_csv)

    p = _parse_prices(prices_file)
    assert p.symbols == ["AAPL", "META"]
    assert p.dates == ["2020-01-01", "2020-01-02"]
    assert p.prices[("2020-01-01", "AAPL")] == 300.0
    assert p.prices[("2020-01-02", "META")] == 205.0

    # Write a minimal covariance CSV (plain)
    cov_csv = "date,symbol_i,symbol_j,covariance\n2020-01-01,AAPL,AAPL,0.01\n2020-01-01,AAPL,META,0.005\n2020-01-01,META,META,0.02\n"
    cov_file = tmp_path / "covariance_matrices.csv"
    cov_file.write_text(cov_csv, encoding="utf-8")

    c = _parse_covariances(cov_file)
    assert "AAPL" in c.symbols and "META" in c.symbols
    assert c.covariances[("2020-01-01", "AAPL", "META")] == 0.005


def test_portfolio_to_checker_string():
    from qoblib.problems.portfolio import PortfolioSolution, PortfolioPosition

    sol = PortfolioSolution(
        instance_name="po_test",
        budget=4,
        lambda_=0.0001,
        objective=-100,
        positions=[PortfolioPosition(period=0, symbol="AAPL", long_units=1, short_units=0)],
    )
    s = sol.to_checker_string()
    assert "budget 4" in s
    assert "0 AAPL 1 0" in s


# ------------------------------------------------------------------ Sports


def test_sports_no_checker():
    from qoblib.problems.sports import SportsProblem

    sp = SportsProblem()
    with pytest.raises(qoblib.QoblibError, match="No solution checker"):
        sp.check_solution(None, None)
