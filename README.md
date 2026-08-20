# qoblib

Python interface to [QOBLIB](https://github.com/ZIB-AOPT/QOBLIB), the Quantum Optimization Benchmarking Library. List, download, verify, and cache problem instances, models, solutions, and submissions without cloning the repository.

## Installation

```
pip install qoblib
```

## Quickstart

```python
import qoblib

qoblib.problem_classes()
# ['birkhoff', 'independentset', 'labs', 'marketsplit', 'network',
#  'portfolio', 'routing', 'sports', 'steiner', 'topology']

qoblib.instances("marketsplit")[:3]
# ['ms_03_050_002', 'ms_03_100_001', ...]

path = qoblib.fetch("marketsplit", "ms_03_050_002")
# PosixPath('~/.cache/qoblib/main/01-marketsplit/instances/ms_03_050_002.dat')
```

Files are downloaded once, verified against their SHA-256 hash from the repository manifest, and cached locally. Repeated calls return the cached copy without touching the network.

## Problem objects and solution checkers

Each problem class can also be accessed through a `Problem` object, which adds parsing and solution verification on top of the generic download layer.

```python
ms = qoblib.get_problem("marketsplit")

# Same listing / download API, but bound to the problem
ms.instances()                     # ['ms_03_050_002', ...]
path = ms.fetch("ms_03_050_002")   # download & cache

# Parse files into structured objects
inst = ms.load_instance("ms_03_050_002")   # MarketSplitInstance
sol  = ms.load_solution("ms_03_050_002")   # MarketSplitSolution

# Verify the solution
result = ms.check_solution(inst, sol)
result.feasible     # True / False
result.objective    # objective value (0.0 when feasible for market split)
result.violations   # list of human-readable constraint violations
result.details      # problem-specific supplementary info
                    # includes 'checker': 'rust', 'exit_code', 'stdout', 'stderr'
```

### Solution checker prerequisite

`check_solution` uses the **official Rust checkers** from the main QOBLIB repository as the single source of truth for feasibility. The first call for a given problem class downloads the checker source and compiles it with Cargo; subsequent calls use the cached binary.

**Cargo must be installed on your system.** If it is not, `check_solution` raises `QoblibError` with a clear message. Install the Rust toolchain once with:

```
curl https://sh.rustup.rs | sh   # Linux / macOS
```

or visit [rustup.rs](https://rustup.rs) for Windows and other options. After installation, restart your shell so `cargo` is on `PATH`.

The compiled binaries are cached in `~/.cache/qoblib/checkers/` and are reused across sessions. The cache is keyed by problem slug and git ref, so pinning a ref with `qoblib.set_ref("v1.0")` always uses the checker from that exact version of the repository.

### LABS — instances defined implicitly

LABS has no instance files; a problem instance is just the sequence length *n*.

```python
from qoblib.problems.labs import LABSSolution

labs = qoblib.get_problem("labs")

sol    = LABSSolution(s=[1, -1, -1, 1, -1, 1, 1, -1])
result = labs.check_solution(8, sol)
result.feasible             # True
result.objective            # energy E(s)  (lower is better)
result.details["merit_factor"]   # F = n² / 2E(s)

# Download QUBO / ILP model files
labs.models()               # list of formulations
labs.fetch_all(kind="model", decompress=True)
```

### Model files

All problem classes that ship LP / ILP model files support `load_model()`:

```python
# Return a local Path (no solver required)
path = ms.load_model("ms_03_050_002", formulation="binary_linear")

# Open directly in SCIP / PySCIPOpt (requires pyscipopt)
m = ms.load_model("ms_03_050_002", backend="pyscipopt")

# Open directly in CPLEX / DOcplex (requires docplex)
m = ms.load_model("ms_03_050_002", backend="docplex")
```

### Third-party plugins

Anyone can register a new problem class with `@qoblib.register_problem`:

```python
import qoblib

@qoblib.register_problem
class MyProblem(qoblib.Problem):
    slug = "myproblem"           # must match the manifest slug
    description = "My Problem"

    def load_instance(self, name):
        path = self.fetch(name, kind="instance")
        return parse_my_format(path)

    def load_solution(self, name):
        path = self.fetch(name, kind="solution")
        return parse_my_solution(path)

    def check_solution(self, instance, solution):
        violations = []
        # ... check constraints ...
        return qoblib.CheckResult(
            feasible=len(violations) == 0,
            objective=compute_obj(instance, solution),
            violations=violations,
        )
```

`qoblib.registered_problems()` returns the slugs of all currently registered plugins.

## File kinds

Every file has a kind: `instance`, `solution`, `model`, or `submission`.

```python
sol = qoblib.fetch("marketsplit", "ms_03_050_002", kind="solution")

lp = qoblib.fetch(
    "marketsplit",
    "01-marketsplit/models/binary_linear/lp_files/ms_03_050_002.lp.xz",
    kind="model",
    decompress=True,
)

qoblib.files("independentset", kind="instance")
# full manifest records: path, kind, name, filename, size, sha256
```

`fetch` accepts a logical name (`"ms_03_050_002"`), an exact file name (`"ms_03_050_002.dat"`), or a full repository path. When a name matches several files, the file in the canonical directory (`solutions/` for solutions, and so on) is preferred; remaining ambiguity raises an error listing the candidate paths. Models in particular usually exist in several formulations (for example `binary_linear` and `binary_unconstrained` subdirectories), so they are best addressed by full path; `qoblib.files(problem, kind="model")` shows what is available.

`decompress=True` transparently decompresses `.gz`, `.xz`, `.bz2`, and `.lzma` files and returns the path of the decompressed copy. Note that some problem classes, for example LABS, have no instance files at all because instances are defined implicitly; their `models/` directory is the downloadable artifact.

`fetch_all(problem, kind=...)` downloads a whole category — `kind` is required. Check the total size first if bandwidth matters:

```python
sum(f["size"] for f in qoblib.files("steiner", kind=qoblib.Kind.INSTANCE))
```

For a progress bar, install `pip install qoblib[progress]` and pass `progressbar=True`.

## Pinning a version

By default files come from the `main` branch. For reproducible experiments, pin a tag or commit:

```python
qoblib.set_ref("v1.0")          # tag, branch, or commit SHA
qoblib.get_ref()
```

The pin applies to the manifest and to every file downloaded afterwards, and the cache keeps versions separate. Individual calls also accept `ref="..."`. The environment variable `QOBLIB_REF` sets the initial value.

## Cache

The cache lives in an OS-appropriate location (for example `~/.cache/qoblib` on Linux). `qoblib.cache_dir()` returns it, and `QOBLIB_CACHE_DIR` overrides it. Deleting the directory is always safe; files are re-downloaded on demand.

## Custom manifest (development)

To work against a locally generated manifest, for example while preparing changes to the main repository:

```python
qoblib.set_manifest_source("path/to/manifest.json")   # or a URL, or None to reset
```

The environment variable `QOBLIB_MANIFEST` does the same. Generate a manifest with `misc/ci/generate_manifest.py` from the main repository.

## File kinds

Use `qoblib.Kind` constants instead of bare strings to get IDE completion:

```python
qoblib.fetch("marketsplit", "ms_03_050_002", kind=qoblib.Kind.INSTANCE)
qoblib.files("marketsplit", kind=qoblib.Kind.SOLUTION)
ms.fetch_all(kind=qoblib.Kind.MODEL)
```

The plain string forms (`"instance"`, `"solution"`, `"model"`, `"submission"`) continue to work.

## File formats

Instance, solution, and model file formats for all 10 problem classes are
documented in [FORMATS.md](FORMATS.md).

## How it works

The main repository publishes a `manifest.json` at its root, regenerated by CI whenever data changes. It lists every data file with its size and SHA-256 hash. This package reads that manifest at the pinned ref and downloads files from `raw.githubusercontent.com`, so the manifest and the files always describe the same snapshot. The manifest format is language-agnostic; clients in other languages can consume the same file.

## Maintainer notes

Releasing: bump `__version__` in `src/qoblib/__init__.py`, commit, tag `vX.Y.Z`, and push the tag. The release workflow builds the distribution and publishes to PyPI via trusted publishing (OIDC); no API tokens are involved. The PyPI trusted publisher must be configured as: project `qoblib`, owner `ZIB-AOPT`, repository `qoblib-python`, workflow `release.yml`, environment `pypi`.

This package requires `manifest.json` to exist in the main repository, generated by `misc/ci/generate_manifest.py` via the `Update manifest` workflow there.

## License and citation

This package is licensed under Apache-2.0. The QOBLIB instance data is licensed separately (CC BY 4.0, see `LICENSE.data` in the main repository). If you use QOBLIB in academic work, please cite it as described in the [main repository](https://github.com/ZIB-AOPT/QOBLIB).
