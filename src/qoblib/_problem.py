"""Problem class abstraction, registry, and Rust-checker integration for QOBLIB.

Each problem class in QOBLIB can be addressed through the generic functional
API (``qoblib.fetch``, ``qoblib.instances``, …) *or* through a richer
:class:`Problem` object that additionally knows how to parse its data files
and verify solutions.

Usage::

    import qoblib

    ms = qoblib.get_problem("marketsplit")
    ms.instances()                              # list of logical names
    path  = ms.fetch("ms_03_050_002")          # download & cache
    inst  = ms.load_instance("ms_03_050_002")  # parsed data structure
    sol   = ms.load_solution("ms_03_050_002")  # parsed solution
    result = ms.check_solution(inst, sol)
    print(result.feasible, result.objective)

Checker design
--------------
Feasibility is determined exclusively by the official Rust checkers shipped
in the main QOBLIB repository.  ``check_solution`` builds (via Cargo) and
invokes the appropriate binary; the exit code is the canonical verdict.

Plugins do **not** re-implement feasibility logic in Python.  They only
implement :meth:`Problem.compute_objective`, a cheap pure-Python function
that computes the objective value from already-parsed data structures.  The
checker layer calls this after a VALID/SUBOPTIMAL result to enrich the
:class:`CheckResult` with a numeric objective when the Rust binary does not
print one in a structured way.

If Cargo is not available or the checker source cannot be downloaded,
``check_solution`` raises :exc:`~qoblib.QoblibError` with a clear message
rather than silently falling back to a second Python implementation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from qoblib._core import (
    Kind,
    QoblibError,
    fetch as _fetch,
    fetch_all as _fetch_all,
    files as _files,
    instances as _instances,
    models as _models,
    solutions as _solutions,
)

__all__ = [
    "CheckResult",
    "CheckStatus",
    "Problem",
    "get_problem",
    "register_problem",
    "registered_problems",
]

# ------------------------------------------------------------------ status / result


class CheckStatus:
    """String constants for the checker exit-code contract.

    These mirror the exit codes defined in ``misc/ci/CHECKER_CONTRACT.md``
    in the main QOBLIB repository and are used as the ``status`` field of
    :class:`CheckResult`.

    =========  ====  =====================================================
    Constant   Code  Meaning
    =========  ====  =====================================================
    VALID        0   Solution is feasible; optimal where the optimum is
                     known.
    SUBOPTIMAL  20   Solution is feasible but not optimal.
                     Only emitted by problems with a known optimum (LABS).
    INFEASIBLE  21   Solution parses correctly but violates a constraint.
    INVALID_FILE 10  Solution file is malformed, wrong length, or
                     unparseable.
    USAGE        2   Infrastructure error (bad arguments, unreadable file).
    =========  ====  =====================================================
    """

    VALID = "VALID"
    SUBOPTIMAL = "SUBOPTIMAL"
    INFEASIBLE = "INFEASIBLE"
    INVALID_FILE = "INVALID_FILE"
    USAGE = "USAGE"


@dataclass
class CheckResult:
    """Outcome of :meth:`Problem.check_solution`.

    Attributes:
        feasible:   ``True`` iff the solution satisfies all constraints
                    (status is ``VALID`` or ``SUBOPTIMAL``).
        status:     One of the :class:`CheckStatus` string constants.
        objective:  Objective value, or ``None`` if not computed.
        violations: Human-readable descriptions of violations reported by the
                    Rust checker.  Empty when *feasible* is ``True``.
        details:    Supplementary information: ``checker`` (``"rust"``),
                    ``exit_code``, ``stdout``, ``stderr``.
    """

    feasible: bool
    status: Optional[str] = None
    objective: Optional[float] = None
    violations: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:  # noqa: D105
        return self.feasible

    def __repr__(self) -> str:  # noqa: D105
        st = self.status or ("feasible" if self.feasible else "infeasible")
        suffix = f" ({len(self.violations)} violation(s))" if not self.feasible and self.violations else ""
        obj = f", obj={self.objective}" if self.objective is not None else ""
        return f"CheckResult({st}{suffix}{obj})"


# ------------------------------------------------------------------ base class


class Problem:
    """Base class for a QOBLIB problem-class plugin.

    Subclasses must set :attr:`slug` (matching the manifest key) and
    :attr:`description`, and should override :meth:`load_instance`,
    :meth:`load_solution`, and optionally :meth:`compute_objective`.

    The generic data-access methods (:meth:`instances`, :meth:`fetch`, …) work
    out of the box for every problem class without any subclass implementation.

    Feasibility is checked exclusively by the official Rust binaries from the
    main QOBLIB repository.  :meth:`check_solution` builds them on first use
    (requires ``cargo`` on ``PATH``) and caches the result.

    Args:
        ref:         Git ref to use for downloads (branch, tag, or commit SHA).
                     ``None`` uses the globally pinned ref.
        progressbar: Show a progress bar during downloads (requires ``tqdm``).
    """

    #: Manifest slug, e.g. ``"marketsplit"``.  Must be set by subclasses.
    slug: str = ""
    #: Human-readable name, e.g. ``"Market Split"``.
    description: str = ""

    def __init__(
        self,
        *,
        ref: Optional[str] = None,
        progressbar: bool = False,
    ) -> None:
        if not self.slug:
            raise TypeError(f"{type(self).__name__} must define a non-empty 'slug'")
        self._ref = ref
        self._progressbar = progressbar

    # ---------------------------------------------------------------- listing

    def instances(self) -> List[str]:
        """Return sorted logical names of all instances."""
        return _instances(self.slug, ref=self._ref)

    def solutions(self) -> List[str]:
        """Return sorted logical names of all solutions."""
        return _solutions(self.slug, ref=self._ref)

    def models(self) -> List[str]:
        """Return sorted logical names of all model files."""
        return _models(self.slug, ref=self._ref)

    def files(self, *, kind: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return manifest entries (dicts) for this problem class.

        Each entry has ``path``, ``kind``, ``name``, ``filename``, ``size``,
        and ``sha256``. Pass *kind* to filter to one category (use
        :class:`~qoblib.Kind` constants or plain strings).
        """
        return _files(self.slug, kind=kind, ref=self._ref)

    # ---------------------------------------------------------------- fetching

    def fetch(
        self,
        name: str,
        *,
        kind: Optional[str] = None,
        decompress: bool = False,
    ) -> Path:
        """Download one file and return the path to the cached local copy.

        Accepts a logical name, an exact file name, or a full repository path.
        *kind* defaults to ``None`` (search all kinds), which works well when
        passing a full path.  Pass ``kind=qoblib.Kind.INSTANCE`` etc. to
        restrict the search and resolve ambiguity.

        See :func:`qoblib.fetch` for full semantics.
        """
        return _fetch(
            self.slug,
            name,
            kind=kind,
            decompress=decompress,
            progressbar=self._progressbar,
            ref=self._ref,
        )

    def fetch_all(
        self,
        *,
        kind: str,
        decompress: bool = False,
    ) -> List[Path]:
        """Download all files of *kind*; return their local paths.

        *kind* is required — use a :class:`~qoblib.Kind` constant or a plain
        string such as ``"instance"``.
        """
        return _fetch_all(
            self.slug,
            kind=kind,
            decompress=decompress,
            progressbar=self._progressbar,
            ref=self._ref,
        )

    # ---------------------------------------------------------------- model loading

    def load_model(
        self,
        name: str,
        *,
        formulation: Optional[str] = None,
        decompress: bool = True,
        backend: str = "path",
    ) -> Any:
        """Fetch and optionally open an LP/MIP model file.

        Args:
            name:        Logical instance name or full repository path.
            formulation: Subdirectory hint (e.g. ``"binary_linear"``).
                         When ``None``, uses the first available model for
                         *name*; raises if ambiguous.
            decompress:  Decompress ``.xz``/``.gz`` files (default: ``True``).
            backend:     One of:

                         - ``"path"`` — return the local :class:`~pathlib.Path`
                           (no solver library needed).
                         - ``"pyscipopt"`` — load with
                           ``pyscipopt.Model.readProblem()``.
                         - ``"docplex"`` — load with
                           ``docplex.mp.model_reader.ModelReader.read()``.

        Returns:
            A :class:`~pathlib.Path`, a ``pyscipopt.Model``, or a
            ``docplex.mp.model.Model`` depending on *backend*.
        """
        entries = self.files(kind=Kind.MODEL)
        if formulation is not None:
            entries = [e for e in entries if formulation in e["path"]]
        name_matches = [e for e in entries if e["name"] == name or e["path"] == name]
        if not name_matches:
            name_matches = [e for e in entries if e["filename"].startswith(name)]
        if len(name_matches) > 1 and formulation is None:
            paths = "\n  ".join(e["path"] for e in name_matches[:10])
            raise ValueError(
                f"Multiple model files for {name!r}. "
                f"Specify formulation=, or pass the full path.\n  {paths}"
            )
        if not name_matches:
            raise KeyError(f"No model file found for {name!r}")

        path = self.fetch(name_matches[0]["path"], kind=Kind.MODEL, decompress=decompress)

        if backend == "path":
            return path
        if backend == "pyscipopt":
            try:
                import pyscipopt  # type: ignore[import]
            except ImportError as exc:
                raise ImportError(
                    "pyscipopt is required for backend='pyscipopt'. "
                    "Install it with: pip install pyscipopt"
                ) from exc
            m = pyscipopt.Model()
            m.readProblem(str(path))
            return m
        if backend == "docplex":
            try:
                from docplex.mp.model_reader import ModelReader  # type: ignore[import]
            except ImportError as exc:
                raise ImportError(
                    "docplex is required for backend='docplex'. "
                    "Install it with: pip install docplex"
                ) from exc
            return ModelReader.read(str(path))
        raise ValueError(
            f"Unknown backend {backend!r}; choose 'path', 'pyscipopt', or 'docplex'"
        )

    # ---------------------------------------------------------------- parsing / checking

    def load_instance(self, name: str) -> Any:
        """Parse and return the instance data for *name*.

        Downloads the file if necessary. Returns a problem-specific data
        structure (documented by each subclass). Raises
        :exc:`NotImplementedError` for problem classes that have not
        implemented a parser.
        """
        raise NotImplementedError(
            f"{type(self).__name__} ({self.slug!r}) does not implement load_instance(). "
            "Use .fetch() to obtain the raw file path instead."
        )

    def load_solution(self, name: str) -> Any:
        """Parse and return the solution for *name*.

        Downloads the file if necessary. Raises :exc:`NotImplementedError` for
        problem classes that have not implemented a solution parser.
        """
        raise NotImplementedError(
            f"{type(self).__name__} ({self.slug!r}) does not implement load_solution(). "
            "Use .fetch(name, kind='solution') to obtain the raw file path instead."
        )

    def compute_objective(self, instance: Any, solution: Any) -> Optional[float]:
        """Compute and return the objective value from parsed data structures.

        Called by the checker layer after the Rust checker confirms a solution
        is VALID or SUBOPTIMAL, to enrich :class:`CheckResult` with a numeric
        objective when the Rust binary does not print one in a structured way.

        Subclasses should override this with a cheap, pure-Python computation
        (e.g. summing route costs, counting set size, computing energy).
        Return ``None`` if the objective is not applicable or not computable
        from the parsed representation alone.

        This method must **not** perform feasibility checks — the Rust checker
        is the sole authority on feasibility.
        """
        return None

    def check_solution(self, instance: Any, solution: Any) -> CheckResult:
        """Verify *solution* against *instance* using the official Rust checker.

        Builds the checker binary on first call (requires ``cargo`` on
        ``PATH``), then caches it for subsequent calls.  The binary is
        downloaded from the main QOBLIB repository at the pinned ref.

        After a VALID or SUBOPTIMAL verdict the library calls
        :meth:`compute_objective` to populate ``result.objective``.

        Raises:
            :exc:`~qoblib.QoblibError`: if Cargo is not installed, the checker
                source cannot be downloaded, or the build fails.
        """
        from qoblib._checker import rust_check  # lazy import — only when needed
        return rust_check(self, instance, solution)

    def objective_value(self, instance: Any, solution: Any) -> float:
        """Return the objective value for *solution* against *instance*.

        Delegates to :meth:`check_solution` and returns ``result.objective``,
        or ``float('nan')`` if objective is not available.
        """
        result = self.check_solution(instance, solution)
        return result.objective if result.objective is not None else float("nan")

    # ---------------------------------------------------------------- dunder

    def __repr__(self) -> str:  # noqa: D105
        ref = f", ref={self._ref!r}" if self._ref else ""
        return f"{type(self).__name__}(slug={self.slug!r}{ref})"


# ------------------------------------------------------------------ registry

_REGISTRY: Dict[str, type] = {}  # slug -> Problem subclass


def register_problem(cls: type) -> type:
    """Register a :class:`Problem` subclass in the global registry.

    Can be used as a class decorator::

        @qoblib.register_problem
        class MyProblem(qoblib.Problem):
            slug = "myproblem"
            ...

    Returns *cls* unchanged so the decorator is transparent.
    """
    if not (isinstance(cls, type) and issubclass(cls, Problem)):
        raise TypeError("register_problem() expects a Problem subclass")
    slug = getattr(cls, "slug", "")
    if not slug:
        raise ValueError(f"{cls.__name__} must define a non-empty 'slug'")
    _REGISTRY[slug] = cls
    return cls


def registered_problems() -> List[str]:
    """Return sorted slugs of all registered problem classes."""
    return sorted(_REGISTRY)


def get_problem(
    slug: str,
    *,
    ref: Optional[str] = None,
    progressbar: bool = False,
) -> Problem:
    """Return a :class:`Problem` instance for the given slug.

    If no plugin has been registered for *slug*, a generic :class:`Problem`
    instance is returned that supports all data-access methods
    (:meth:`~Problem.instances`, :meth:`~Problem.fetch`, …) but raises
    :exc:`NotImplementedError` for ``load_instance`` and ``load_solution``.

    Args:
        slug:        Problem class slug, e.g. ``"marketsplit"``.
        ref:         Git ref to pin for this instance.
        progressbar: Enable download progress bars.
    """
    slug = slug.strip().lower()
    if slug in _REGISTRY:
        return _REGISTRY[slug](ref=ref, progressbar=progressbar)
    # Build a one-off Problem subclass so that slug is part of the class,
    # not instance state — keeps __repr__ consistent with real plugins.
    generic_cls = type(
        f"_Problem_{slug}",
        (Problem,),
        {"slug": slug, "description": f"(no plugin registered for {slug!r})"},
    )
    return generic_cls(ref=ref, progressbar=progressbar)
