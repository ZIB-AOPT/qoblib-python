# qoblib

Python interface to [QOBLIB](https://github.com/ZIB-AOPT/QOBLIB), the Quantum Optimization Benchmarking Library. Download the problem instances and reference solutions, load them as Python objects, and check your own solutions with the official checkers, without cloning the repository.

## Installation

```
pip install qoblib
```

Requires Python 3.10 or newer; the only dependency is NumPy.

## Quickstart

Every QOBLIB problem is one class, and every object of that class is one instance.

```python
from qoblib import MarketSplit

MarketSplit.instances()                  # ['ms_03_050_002', ...]; works offline

problem = MarketSplit.load("ms_03_050_002")   # downloaded on first use, then cached
problem.A, problem.b                     # the data, as NumPy arrays

best = problem.best_known                # reference solution shipped with QOBLIB
best.solution                            # array([1, 0, 0, ...])
best.optimal                             # True if proven optimal

result = problem.check(best.solution)    # runs the official checker
result.feasible, result.status, result.objective
```

The ten classes are:

| Class | QOBLIB directory | An instance is | A solution is |
|---|---|---|---|
| `MarketSplit` | `01-marketsplit` | matrix `A`, vector `b` | 0/1 vector |
| `Labs` | `02-labs` | sequence length `n` | ±1 sequence |
| `Birkhoff` | `03-birkhoff` | doubly stochastic `matrix`, `scale` | `(weights, permutations)` |
| `Steiner` | `04-steiner` | graph `edges`, `terminals` per net | list of `(u, v, net)` |
| `Sports` | `05-sports` | ITC2021 tournament (`teams`, `slots`, `root`) | list of `(home, away, slot)` |
| `Portfolio` | `06-portfolio` | `prices`, `covariances`, `budget`, `risk_aversion` | list of `(period, symbol, long, short)` |
| `IndependentSet` | `07-independentset` | graph with `n` nodes and `edges` | list of nodes |
| `Network` | `08-network` | node count `n`, `demand` matrix | `(edges, flows)` |
| `Routing` | `09-routing` | `coords`, `demands`, `capacity`, `depot` | list of routes |
| `Topology` | `10-topology` | node count `n`, maximum `degree` | edge list of a graph |

Solutions are plain Python and NumPy data. Nodes, teams and so on keep the numbering of the QOBLIB files (mostly starting at 1), so everything can be compared with the repository directly. [FORMATS.md](FORMATS.md) describes each problem's data and file formats.

Every class offers the same methods:

| | |
|---|---|
| `Problem.instances()` | names of all instances |
| `Problem.download(*names, dest=None, solutions=True)` | download instances and reference solutions |
| `Problem.load(name)` | one instance as an object |
| `Problem.from_file(path)` | an instance from your own file |
| `problem.best_known` | reference solution (`solution`, `optimal`, `path`), or `None` |
| `problem.check(solution)` | verdict of the official checker |
| `problem.read_solution(path)`, `problem.write_solution(solution, path)` | solution files in QOBLIB format |

Three problems have no instance files, so their objects can also be created directly: `Labs(n)`, `Network(n)` and `Topology(n, degree)`.

## Downloading

`load` fetches what it needs, so downloading up front is optional. To get the files themselves:

```python
import qoblib
from qoblib import Steiner

Steiner.download()                          # all Steiner instances and solutions, into the cache
Steiner.download(dest="data")               # ... into ./data/04-steiner/ instead
Steiner.download("stp_s003_l1_t2_h0_rs97531", dest="data")   # a single instance
qoblib.download(dest="data")                # every problem, about 0.8 GB
```

With `dest`, files are laid out as in the QOBLIB repository (`data/04-steiner/instances/...`, `data/04-steiner/solutions/...`). The same is available from the shell:

```
qoblib list                       # problems with instance counts and download sizes
qoblib list steiner               # instance names
qoblib download steiner --dest data
qoblib download all --dest data
```

Downloads are verified against the hash recorded for each file and cached, by default in `~/.cache/qoblib` on Linux. `qoblib.cache_dir()` returns the location and the environment variable `QOBLIB_CACHE_DIR` changes it. Deleting the cache is always safe.

Only instances and reference solutions are downloaded. The model files (LP and QUBO formulations) and the submissions in the QOBLIB repository are not covered by this package.

## Checking solutions

`check` runs the official checkers from the QOBLIB repository, so the verdict is the same one the benchmark uses. The checkers are written in Rust and are compiled the first time a problem is checked. **This needs the Rust toolchain**; install it once from [rustup.rs](https://rustup.rs):

```
curl https://sh.rustup.rs | sh
```

Without `cargo` on the `PATH`, `check` raises a `QoblibError` that says so. Everything else in this package works without Rust.

```python
from qoblib import Routing

problem = Routing.load("XSH-n20-k4-01")
result = problem.check([[15, 2, 18, 1, 8], [10, 11, 7, 9, 6], [17, 4, 5, 19, 3], [20, 12, 13, 14, 16]])

result.status      # 'VALID', 'SUBOPTIMAL', 'INFEASIBLE' or 'INVALID_FILE'
result.feasible    # True for VALID and SUBOPTIMAL; bool(result) is the same
result.objective   # 646, as computed by the checker
result.output      # everything the checker printed

problem.check("my_solution.sol")        # a solution file works as well
```

`SUBOPTIMAL` is only reported where the checker knows the optimum (currently LABS up to length 66). `MarketSplit` has no objective. QOBLIB ships no checker for `Sports`; its `check` raises a `QoblibError`.

From the shell: `qoblib check routing XSH-n20-k4-01 my_solution.sol` prints the checker output and exits with 0 if the solution is feasible.

## Problem-specific notes

- **Labs**: `Labs(n)` works for any `n`; `Labs.instances()` lists the lengths that have a reference solution.
- **Birkhoff**: QOBLIB stores ten matrices per file. Each matrix is one instance here, named by its id, for example `Birkhoff.load("B3_9_1")`.
- **Portfolio**: `Portfolio.instances()` lists the market data sets. A benchmark instance adds a budget and a risk aversion: `Portfolio.load("po_a010_t10_orig", budget=4, risk_aversion="1e-4")`, or equivalently `Portfolio.load("po_a010_t10_orig_b004_l1e-4")`. Without a budget, QOBLIB's default for the number of assets is used. `check` and `best_known` need both values.
- **Network**: `Network(n)` uses the first `n` nodes of the single demand matrix QOBLIB ships (up to 24).
- **Topology**: the objective is the diameter. `problem.check(edges, max_diameter=3)` additionally rejects graphs with a larger diameter. `problem.bounds` gives the diameter bounds QOBLIB lists for small instances.
- **Sports**: `root` is the parsed ITC2021 XML document, which holds the constraints.

## Which version of QOBLIB

The package ships an index of the QOBLIB repository at one commit, so results are reproducible and listing works offline. `qoblib.get_ref()` returns that commit. To use a different state of the repository:

```python
qoblib.set_ref("main")        # branch, tag or commit; queries GitHub once
qoblib.set_ref(None)          # back to the bundled commit
```

## Maintainer notes

- **Updating the index**: `python tools/build_index.py` rewrites `src/qoblib/index.json` for the current `main` of QOBLIB. The `Update index` workflow does this weekly and opens a pull request when something changed.
- **Tests**: `pytest` runs offline against the small sample of QOBLIB files in `tests/data`. `pytest -m network` additionally builds every Rust checker and runs it on reference solutions from the live repository; it needs network access and `cargo`.
- **Releasing**: bump `__version__` in `src/qoblib/__init__.py`, commit, tag `vX.Y.Z` and push the tag. The release workflow publishes to PyPI through trusted publishing (project `qoblib`, owner `ZIB-AOPT`, repository `qoblib-python`, workflow `release.yml`, environment `pypi`).

## License and citation

This package is licensed under Apache-2.0. The QOBLIB data, including the sample in `tests/data`, is licensed separately under CC BY 4.0 (see `LICENSE.data` in the main repository). If you use QOBLIB in academic work, please cite it as described in the [main repository](https://github.com/ZIB-AOPT/QOBLIB).
