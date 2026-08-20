"""Python interface to QOBLIB, the Quantum Optimization Benchmarking Library.

List, download, verify, and cache problem instances, models, solutions,
and submissions from https://github.com/ZIB-AOPT/QOBLIB without cloning
the repository.

Functional quickstart::

    import qoblib

    qoblib.problem_classes()
    qoblib.instances("marketsplit")
    path = qoblib.fetch("marketsplit", "ms_03_050_002")

Object-oriented quickstart (with parsing and solution checking)::

    ms = qoblib.get_problem("marketsplit")
    ms.instances()
    inst   = ms.load_instance("ms_03_050_002")
    sol    = ms.load_solution("ms_03_050_002")
    result = ms.check_solution(inst, sol)
    print(result.feasible, result.objective)
"""
from qoblib._core import (
    FileEntry,
    Kind,
    KINDS,
    REPOSITORY,
    QoblibError,
    cache_dir,
    fetch,
    fetch_all,
    files,
    get_ref,
    get_version,
    info,
    instances,
    models,
    problem_classes,
    set_manifest_source,
    set_ref,
    set_version,
    solutions,
)
from qoblib._problem import (
    CheckResult,
    CheckStatus,
    Problem,
    get_problem,
    register_problem,
    registered_problems,
)

# Register all built-in problem plugins.
import qoblib.problems as _problems  # noqa: F401, E402

__version__ = "0.1.0"

__all__ = [
    # --- constants ---
    "FileEntry",
    "Kind",
    "KINDS",
    "REPOSITORY",
    "__version__",
    # --- errors ---
    "QoblibError",
    # --- functional API ---
    "cache_dir",
    "fetch",
    "fetch_all",
    "files",
    "get_ref",
    "get_version",   # deprecated alias
    "info",
    "instances",
    "models",
    "problem_classes",
    "set_manifest_source",
    "set_ref",
    "set_version",   # deprecated alias
    "solutions",
    # --- OO / plugin API ---
    "CheckResult",
    "CheckStatus",
    "Problem",
    "get_problem",
    "register_problem",
    "registered_problems",
]
