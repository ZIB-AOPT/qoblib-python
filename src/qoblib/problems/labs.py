"""Low Autocorrelation Binary Sequences (LABS) problem plugin.

LABS asks for a binary sequence ``s ∈ {-1, +1}^n`` that minimises the
energy function::

    E(s) = sum_{k=1}^{n-1} C_k(s)^2

where ``C_k(s) = sum_{i=1}^{n-k} s_i * s_{i+k}`` is the *k*-lag
autocorrelation.  The merit factor is ``F = n^2 / (2 E(s))``.

LABS has **no instance files** — problem instances are parameterised by a
single integer *n* (the sequence length).  The downloadable artifacts are
model files in various QUBO/ILP formulations.

References:
    Bernasconi (1987). "Low autocorrelation binary sequences: statistical
    mechanics and configuration space analysis." J. Physique.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

from qoblib._problem import Problem, register_problem


# Known-optimal energies for n=0..66, from Packebusch & Mertens, arXiv:1512.02475v2.
# Index is the sequence length n; value is E*(n).  Entry 0/1/2 are unused (n<3).
_OPTIMAL_ENERGY = (
    0, 0, 0, 1, 2, 2, 7, 3, 8, 12, 13, 5, 10, 6, 19, 15, 24, 32, 25, 29,
    26, 26, 39, 47, 36, 36, 45, 37, 50, 62, 59, 67, 64, 64, 65, 73, 82, 86,
    87, 99, 108, 108, 101, 109, 122, 118, 131, 135, 140, 136, 153, 153, 166,
    170, 175, 171, 192, 188, 197, 205, 218, 226, 235, 207, 208, 240, 257,
)


@dataclass
class LABSSolution:
    """A candidate LABS solution.

    Attributes:
        s:    Binary sequence with values in ``{-1, +1}`` (or ``{0, 1}``
              depending on the formulation; :meth:`~LABSProblem.compute_objective`
              accepts both).
        n:    Sequence length (inferred from *s* if not provided).
        name: Optional label, e.g. the instance size as a string.
    """

    s: List[int]
    n: int = field(init=False)
    name: str = ""

    def __post_init__(self) -> None:
        self.n = len(self.s)

    def to_checker_string(self) -> str:
        """Serialise to the ``01...`` format expected by the Rust checker.

        The Rust LABS checker maps ``0`` → ``-1`` and ``1`` → ``+1``
        internally, so passing a ``{0,1}`` string is correct regardless of
        whether the solution was originally in ``{-1,+1}`` encoding.
        """
        return "".join("0" if v <= 0 else "1" for v in self.s)


@register_problem
class LABSProblem(Problem):
    """Plugin for the LABS (Low Autocorrelation Binary Sequences) problem.

    Because LABS instances are defined implicitly by a single integer *n*,
    this plugin does not implement :meth:`load_instance` or
    :meth:`load_solution` in the usual file-based sense.  Instead:

    - Use :meth:`make_instance` to create an instance object for a given *n*.
    - Use :meth:`check_solution` to verify a solution (requires Cargo).
    - Use :meth:`fetch_all` with ``kind="model"`` to download QUBO/ILP
      formulations, or :meth:`load_model` to open them directly.

    Quickstart::

        import qoblib
        from qoblib.problems.labs import LABSSolution

        labs = qoblib.get_problem("labs")

        sol    = LABSSolution(s=[1, -1, -1, 1, -1, 1, 1, -1])
        result = labs.check_solution(8, sol)
        print(result.status)               # "VALID" or "SUBOPTIMAL"
        print(result.objective)            # energy E(s)
        print(result.details["merit_factor"])
    """

    slug = "labs"
    description = "Low Autocorrelation Binary Sequences (LABS)"

    # ---------------------------------------------------------------- instance helpers

    def make_instance(self, n: int) -> int:
        """Return *n* as the instance descriptor for LABS.

        LABS instances have no external data file; the problem is fully
        specified by the sequence length *n*.
        """
        if not isinstance(n, int) or n < 1:
            raise ValueError(f"n must be a positive integer, got {n!r}")
        return n

    def load_instance(self, name: str) -> int:
        """Return the sequence length *n* encoded in *name*.

        *name* may be an integer-valued string (e.g. ``"32"``) or a file
        name whose stem encodes *n* (e.g. ``"labs_032.lp.xz"``).
        """
        m = re.search(r"(\d+)", str(name))
        if not m:
            raise ValueError(
                f"Cannot infer sequence length n from name {name!r}. "
                "Pass an integer string like '32'."
            )
        return int(m.group(1))

    # ---------------------------------------------------------------- objective

    def compute_objective(  # type: ignore[override]
        self,
        instance: int,
        solution: LABSSolution,
    ) -> Optional[float]:
        """Compute the energy E(s) and annotate ``details`` with the merit factor.

        This is called by the checker layer after the Rust checker confirms
        VALID or SUBOPTIMAL.  The result is placed in ``CheckResult.objective``.

        Args:
            instance: Sequence length *n*.
            solution: A :class:`LABSSolution`.  Accepts ``{-1, +1}`` or
                      ``{0, 1}`` encodings.
        """
        n = instance
        s_pm = [-1 if v <= 0 else 1 for v in solution.s]
        energy = 0
        for k in range(1, n):
            ck = sum(s_pm[i] * s_pm[i + k] for i in range(n - k))
            energy += ck * ck
        return float(energy)
