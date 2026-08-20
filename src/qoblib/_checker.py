"""Rust-checker integration for QOBLIB.

Each problem class in the main QOBLIB repository ships a small Rust program
under ``NN-problem/check/`` that is the *official* solution checker.  This
module downloads, builds (via ``cargo build --release``), and invokes those
binaries.  The result is parsed back into a :class:`~qoblib._problem.CheckResult`.

:func:`rust_check` is called by :meth:`~qoblib._problem.Problem.check_solution`.
It raises :exc:`~qoblib.QoblibError` if the toolchain is unavailable rather
than silently returning ``None`` — the caller is expected to propagate the
error to the user.

After a VALID or SUBOPTIMAL result the checker calls
:meth:`~qoblib._problem.Problem.compute_objective` on the plugin to obtain the
objective value.  This keeps all objective logic in the plugin and keeps the
checker layer free of per-problem stdout scraping.

Checker binaries are cached in ``<cache_dir>/checkers/<slug>/<ref>/``.  They
are rebuilt only when the source changes (identified by the git ref).

CLI patterns per problem
------------------------

    marketsplit    : binary  <instance-file>  <solution-file>
    labs           : binary  <n>              <solution-file>
    birkhoff       : binary  <instance-json>  <solution-json>
    steiner        : binary  --arcs <arcs>    --terms <terms>  --sol <sol>
    portfolio      : binary  <instance-dir>   <solution-file>
    independentset : binary  <graph-file>     <solution-file>
    network        : binary  <n>  <demand-file>  <solution-file>
    routing        : binary  <instance-vrp>   <solution-file>
    topology       : binary  <n>  <degree>  <diameter>  <solution-file>
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Optional

if TYPE_CHECKING:
    from qoblib._problem import CheckResult, Problem

# Exit codes defined in misc/ci/CHECKER_CONTRACT.md
_EXIT_VALID = 0
_EXIT_SUBOPTIMAL = 20
_EXIT_INFEASIBLE = 21
_EXIT_INVALID_FILE = 10
_EXIT_USAGE = 2

# Map exit code → (feasible, status string)
_EXIT_MAP = {
    _EXIT_VALID:        (True,  "VALID"),
    _EXIT_SUBOPTIMAL:   (True,  "SUBOPTIMAL"),
    _EXIT_INFEASIBLE:   (False, "INFEASIBLE"),
    _EXIT_INVALID_FILE: (False, "INVALID_FILE"),
    _EXIT_USAGE:        (False, "USAGE"),
}

REPOSITORY = "ZIB-AOPT/QOBLIB"
RAW_BASE = f"https://raw.githubusercontent.com/{REPOSITORY}"

# ------------------------------------------------------------------ per-problem metadata


class _CheckerSpec:
    """Metadata for one problem's Rust checker."""

    def __init__(self, prob_dir: str, bin_name: str, rs_path: str) -> None:
        self.prob_dir = prob_dir
        self.bin_name = bin_name
        self.rs_path = rs_path  # "src/bin/<bin>.rs"  or  "src/main.rs"

    def source_files(self) -> list[tuple[str, str]]:
        """Return [(remote_relative_path, local_relative_path), ...] inside check/."""
        return [
            ("Cargo.toml", "Cargo.toml"),
            ("Cargo.lock", "Cargo.lock"),
            (self.rs_path, self.rs_path),
        ]


_SPECS: dict[str, _CheckerSpec] = {
    "marketsplit":    _CheckerSpec("01-marketsplit",   "check_marketsplit", "src/bin/check_marketsplit.rs"),
    "labs":           _CheckerSpec("02-labs",           "check_labs",        "src/bin/check_labs.rs"),
    "birkhoff":       _CheckerSpec("03-birkhoff",       "check_birkhoff",    "src/bin/check_birkhoff.rs"),
    "steiner":        _CheckerSpec("04-steiner",        "check_steiner",     "src/main.rs"),
    "portfolio":      _CheckerSpec("06-portfolio",      "check_portfolio",   "src/main.rs"),
    "independentset": _CheckerSpec("07-independentset", "check_stableset",   "src/bin/check_stableset.rs"),
    "network":        _CheckerSpec("08-network",        "check_network",     "src/main.rs"),
    "routing":        _CheckerSpec("09-routing",        "check_cvrp",        "src/bin/check_cvrp.rs"),
    "topology":       _CheckerSpec("10-topology",       "check_topology",    "src/bin/check_topology.rs"),
}

# ------------------------------------------------------------------ build cache

_build_cache: dict[str, Optional[Path]] = {}  # "slug:ref" -> binary path or None (build failed)


def _checker_cache_dir(slug: str, ref: str) -> Path:
    from qoblib._core import cache_dir, _safe_ref
    return cache_dir() / "checkers" / slug / _safe_ref(ref)


def _fetch_file(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "qoblib-python"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read()
    except urllib.error.HTTPError as err:
        if err.code == 404:
            raise FileNotFoundError(f"Not found: {url}") from err
        raise


def _build_checker(slug: str, ref: str) -> Path:
    """Download source and build the Rust checker for *slug* at *ref*.

    Returns the path to the compiled binary.

    Raises:
        :exc:`~qoblib.QoblibError`: if Cargo is missing, the source cannot be
            fetched, or compilation fails.
    """
    from qoblib._core import QoblibError

    if shutil.which("cargo") is None:
        raise QoblibError(
            "Rust/Cargo is required to run the official QOBLIB solution checkers "
            "but 'cargo' was not found on PATH. Install it from https://rustup.rs/"
        )

    spec = _SPECS.get(slug)
    if spec is None:
        raise QoblibError(
            f"No Rust checker is registered for problem class {slug!r}. "
            "This problem may not yet have an official checker in the repository."
        )

    out_dir = _checker_cache_dir(slug, ref)
    dest = out_dir / spec.bin_name
    if dest.is_file():
        return dest  # already built

    check_base = f"{RAW_BASE}/{urllib.parse.quote(ref, safe='/')}/{spec.prob_dir}/check"

    with tempfile.TemporaryDirectory() as tmp:
        src_dir = Path(tmp) / "check"
        (src_dir / "src" / "bin").mkdir(parents=True)

        try:
            for remote_rel, local_rel in spec.source_files():
                local_path = src_dir / local_rel
                local_path.parent.mkdir(parents=True, exist_ok=True)
                local_path.write_bytes(_fetch_file(f"{check_base}/{remote_rel}"))
        except (FileNotFoundError, OSError) as exc:
            raise QoblibError(
                f"Could not download checker source for {slug!r} at ref {ref!r}: {exc}"
            ) from exc

        result = subprocess.run(
            ["cargo", "build", "--release",
             "--manifest-path", str(src_dir / "Cargo.toml"),
             "--target-dir", str(src_dir / "target")],
            capture_output=True,
            timeout=180,
        )
        if result.returncode != 0:
            raise QoblibError(
                f"Cargo build failed for {slug!r} checker "
                f"(exit {result.returncode}):\n{result.stderr.decode(errors='replace')}"
            )

        built = src_dir / "target" / "release" / spec.bin_name
        if not built.is_file():
            raise QoblibError(
                f"Cargo build succeeded but binary {spec.bin_name!r} was not found "
                f"in the release directory."
            )

        out_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(built, dest)
        dest.chmod(0o755)
        return dest


def get_checker_binary(slug: str, ref: Optional[str] = None) -> Path:
    """Return the path to the compiled Rust checker for *slug*.

    Builds and caches the binary on first call.  Raises
    :exc:`~qoblib.QoblibError` on any failure.
    """
    from qoblib._core import _state
    ref = ref or _state["ref"]
    cache_key = f"{slug}:{ref}"
    if cache_key in _build_cache:
        cached = _build_cache[cache_key]
        if cached is None:
            # A previous build attempt failed; surface the error again.
            from qoblib._core import QoblibError
            raise QoblibError(
                f"Checker for {slug!r} failed to build previously. "
                "Clear the checker cache or fix the build environment."
            )
        return cached
    path = _build_checker(slug, ref)
    _build_cache[cache_key] = path
    return path


# ------------------------------------------------------------------ invocation


def _write_solution_file(solution: Any, tmp_dir: Path) -> Path:
    """Serialise *solution* to a temporary file the Rust checker can read.

    Accepts:
    - A :class:`~pathlib.Path` — used as-is.
    - A ``str`` or ``bytes`` — written verbatim.
    - An object with a ``to_checker_string()`` method.
    - A ``list``/``tuple`` of ints — space-joined.
    """
    if isinstance(solution, Path):
        return solution
    sol_path = tmp_dir / "solution.txt"
    if isinstance(solution, bytes):
        sol_path.write_bytes(solution)
    elif isinstance(solution, str):
        sol_path.write_text(solution, encoding="utf-8")
    elif hasattr(solution, "to_checker_string"):
        sol_path.write_text(solution.to_checker_string(), encoding="utf-8")
    elif isinstance(solution, (list, tuple)):
        sol_path.write_text(" ".join(str(v) for v in solution), encoding="utf-8")
    else:
        raise TypeError(
            f"Cannot serialise solution of type {type(solution).__name__} for the "
            "Rust checker. Provide a Path, str, bytes, list of ints, or an object "
            "with a to_checker_string() method."
        )
    return sol_path


def _build_cmd(
    slug: str, binary: Path, instance: Any, solution: Any, tmp_dir: Path
) -> List[str]:
    """Build the full argv for the checker invocation.

    Raises:
        :exc:`~qoblib.QoblibError`: if required instance attributes are missing
            (e.g. an in-memory instance without a backing file path).
    """
    from qoblib._core import QoblibError

    sol_path = _write_solution_file(solution, tmp_dir)

    if slug == "labs":
        return [str(binary), str(int(instance)), str(sol_path)]

    if slug == "steiner":
        arcs = getattr(instance, "arcs_path", None)
        terms = getattr(instance, "terms_path", None)
        if arcs is None or terms is None:
            raise QoblibError(
                "SteinerInstance is missing arcs_path/terms_path. "
                "Load the instance via SteinerProblem.load_instance() to populate these."
            )
        return [str(binary), "--arcs", str(arcs), "--terms", str(terms), "--sol", str(sol_path)]

    if slug == "network":
        n = getattr(instance, "n", None)
        demand = getattr(instance, "demand_path", None)
        if n is None or demand is None:
            raise QoblibError(
                "NetworkInstance is missing n or demand_path. "
                "Load the instance via NetworkProblem.load_instance() to populate these."
            )
        return [str(binary), str(n), str(demand), str(sol_path)]

    if slug == "topology":
        n = getattr(instance, "n", None) or getattr(solution, "n", None)
        degree = getattr(instance, "degree", None) or getattr(solution, "degree", None)
        diameter = getattr(instance, "diameter", None) or getattr(solution, "diameter", None)
        if n is None or degree is None or diameter is None:
            raise QoblibError(
                "TopologyInstance is missing n, degree, or diameter. "
                "Ensure diameter is set on the instance (or load via TopologyProblem.load_instance())."
            )
        sol_path_topo = _write_solution_file(solution, tmp_dir)
        return [str(binary), str(n), str(degree), str(diameter), str(sol_path_topo)]

    if slug == "portfolio":
        inst_dir = getattr(instance, "instance_dir", None)
        if inst_dir is None:
            if isinstance(instance, Path) and instance.is_dir():
                inst_dir = instance
            else:
                raise QoblibError(
                    "PortfolioInstance is missing instance_dir. "
                    "Load the instance via PortfolioProblem.load_instance()."
                )
        return [str(binary), str(inst_dir), str(sol_path)]

    # Default: binary <instance-file> <solution-file>
    # Covers: marketsplit, birkhoff, independentset, routing
    inst_path = instance if isinstance(instance, Path) else getattr(instance, "path", None)
    if inst_path is None:
        raise QoblibError(
            f"Instance for {slug!r} has no backing file path. "
            "Load the instance via the problem's load_instance() method so that "
            "the .path attribute is populated."
        )
    return [str(binary), str(inst_path), str(sol_path)]


def rust_check(
    problem: "Problem",
    instance: Any,
    solution: Any,
    *,
    ref: Optional[str] = None,
) -> "CheckResult":
    """Invoke the official Rust checker and return a :class:`CheckResult`.

    Raises:
        :exc:`~qoblib.QoblibError`: if the checker cannot be built or run,
            or if the instance does not have a backing file path.
    """
    from qoblib._problem import CheckResult  # avoid circular at module level
    from qoblib._core import QoblibError

    ref = ref or getattr(problem, "_ref", None)
    binary = get_checker_binary(problem.slug, ref)  # raises QoblibError on failure

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        cmd = _build_cmd(problem.slug, binary, instance, solution, tmp_dir)  # raises on missing attrs

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except subprocess.TimeoutExpired as exc:
            raise QoblibError(
                f"Checker for {problem.slug!r} timed out after 60 seconds."
            ) from exc
        except OSError as exc:
            raise QoblibError(
                f"Failed to execute checker for {problem.slug!r}: {exc}"
            ) from exc

        exit_code = proc.returncode
        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()

        # USAGE (exit 2) means bad arguments or unreadable file — a library bug,
        # not a solution issue.  Surface it clearly.
        if exit_code == _EXIT_USAGE:
            raise QoblibError(
                f"Checker for {problem.slug!r} exited with USAGE error (exit 2), "
                f"indicating an argument or file problem.\n"
                f"Command: {' '.join(cmd)}\n"
                f"stderr: {stderr}"
            )

        feasible, status = _EXIT_MAP.get(exit_code, (False, "USAGE"))

        # Collect violations from checker stdout for infeasible results
        violations: list[str] = []
        if not feasible:
            for line in stdout.splitlines():
                ll = line.lower()
                if "failed" in ll or "violat" in ll or "invalid" in ll or "error" in ll:
                    violations.append(line.strip())

        # Objective: ask the plugin to compute it from parsed data structures.
        # This is authoritative, uniform, and free of stdout-format assumptions.
        objective: Optional[float] = None
        if feasible:
            try:
                objective = problem.compute_objective(instance, solution)
            except Exception:
                pass  # compute_objective is best-effort; never fail the check

        return CheckResult(
            feasible=feasible,
            status=status,
            objective=objective,
            violations=violations,
            details={
                "checker": "rust",
                "exit_code": exit_code,
                "stdout": stdout,
                "stderr": stderr,
            },
        )
