"""Market-split problem plugin.

The market-split problem asks: given a binary matrix *A* and a right-hand
side vector *b*, find a binary vector *x* such that ``A x = b``.

Instance file format
--------------------
The ``.dat`` files in the repository use the format expected by the official
Rust checker.  The first non-comment line is::

    <n_rows> <n_cols>

Each subsequent row has ``n_cols`` integer weights followed by the RHS (all
whitespace or comma-separated; the RHS is ``sum(weights) / 2``)::

    w1 w2 ... wn rhs

Comments start with ``#`` and commas are treated as whitespace.

Solution file format
--------------------
The official Rust checker accepts several formats.  The simplest (and the one
we write for round-trip use) is a compact binary string::

    01001101...

References:
    Cornuejols & Dawande (1999). "A class of hard small 0-1 programs."
    INFORMS Journal on Computing.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from qoblib._problem import Problem, register_problem


@dataclass
class MarketSplitInstance:
    """Parsed representation of a market-split instance.

    Attributes:
        n_rows:  Number of rows in the constraint matrix.
        n_cols:  Number of binary variables (columns).
        A:       Constraint matrix as a list-of-lists (row-major).
        b:       Right-hand side vector.
        name:    Logical instance name (e.g. ``"ms_03_050_002"``).
        path:    Local path to the raw ``.dat`` file (set by :meth:`load_instance`).
                 Used by the Rust checker as the instance argument.
    """

    n_rows: int
    n_cols: int
    A: List[List[int]]
    b: List[int]
    name: str = ""
    path: Optional[Path] = None


@dataclass
class MarketSplitSolution:
    """Parsed representation of a market-split solution.

    Attributes:
        x:    Binary assignment vector.
        name: Logical instance name this solution corresponds to.
        path: Local path to the raw solution file, if fetched from the repo.
    """

    x: List[int]
    name: str = ""
    path: Optional[Path] = None

    def to_checker_string(self) -> str:
        """Serialise to the compact ``01...`` format expected by the Rust checker."""
        return "".join(str(v) for v in self.x)


@register_problem
class MarketSplitProblem(Problem):
    """Plugin for the market-split problem class.

    Quickstart::

        import qoblib
        ms = qoblib.get_problem("marketsplit")

        inst   = ms.load_instance("ms_03_050_002")
        sol    = ms.load_solution("ms_03_050_002")
        result = ms.check_solution(inst, sol)
        print(result.status, result.feasible)
    """

    slug = "marketsplit"
    description = "Market Split"

    # ---------------------------------------------------------------- parsing

    def load_instance(self, name: str) -> MarketSplitInstance:
        """Parse a market-split ``.dat`` file and return a :class:`MarketSplitInstance`.

        Downloads the file if it is not already cached.  The returned object's
        ``path`` attribute is set to the local file path so the Rust checker
        can use it directly.
        """
        path = self.fetch(name, kind="instance")
        inst = _parse_instance(path, name)
        inst.path = path
        return inst

    def load_solution(self, name: str) -> MarketSplitSolution:
        """Parse a market-split solution file and return a :class:`MarketSplitSolution`.

        Downloads the file if it is not already cached.  The returned object's
        ``path`` attribute is set so the Rust checker can pass the file directly.
        """
        path = self.fetch(name, kind="solution")
        sol = _parse_solution(path, name)
        sol.path = path
        return sol

    # ---------------------------------------------------------------- objective

    def compute_objective(
        self,
        instance: MarketSplitInstance,
        solution: MarketSplitSolution,
    ) -> Optional[float]:
        """Return 0.0 — market split is a pure feasibility problem."""
        return 0.0


# ------------------------------------------------------------------ file parsers


def _parse_instance(path: Path, name: str = "") -> MarketSplitInstance:
    """Parse a ``.dat`` market-split instance file.

    Format (authoritative: matches the Rust checker)::

        <n_rows> <n_cols>
        <w1> <w2> ... <wn> <rhs>   # one row per constraint
        ...

    Commas are treated as whitespace.  Comment lines start with ``#``.
    The RHS value on each row is ``sum(weights) / 2`` and equals ``b[row]``.
    """
    text = path.read_text(encoding="utf-8").replace(",", " ")
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    it = iter(lines)
    try:
        header = next(it).split()
        n_rows = int(header[0])
        n_cols = int(header[1])
        A: List[List[int]] = []
        b: List[int] = []
        for row_idx in range(n_rows):
            fields = next(it).split()
            if len(fields) < n_cols + 1:
                raise ValueError(
                    f"row {row_idx}: expected {n_cols + 1} values, got {len(fields)}"
                )
            A.append([int(fields[i]) for i in range(n_cols)])
            b.append(int(fields[n_cols]))
    except (StopIteration, ValueError, IndexError) as exc:
        raise ValueError(f"Failed to parse market-split instance at {path}: {exc}") from exc
    return MarketSplitInstance(n_rows=n_rows, n_cols=n_cols, A=A, b=b, name=name)


def _parse_solution(path: Path, name: str = "") -> MarketSplitSolution:
    """Parse the simplest solution format (whitespace/comma-separated 0/1 values).

    More exotic formats (``x#N value``, index-list) are handled by the Rust checker;
    the Python parser only needs to cover the common case for round-trip use.
    """
    text = path.read_text(encoding="utf-8")
    tokens: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if stripped.lower().startswith("x#") or stripped.lower().startswith("x #"):
            parts = stripped.split()
            if len(parts) >= 2:
                try:
                    tokens_by_idx = {int(parts[0].lstrip("xX#").strip()): int(parts[-1])}
                except ValueError:
                    pass
            continue
        tokens.extend(stripped.replace(",", " ").split())

    try:
        x = [int(v) for v in tokens if v in ("0", "1")]
        if not x:
            x = [int(v) for v in tokens]
    except ValueError as exc:
        raise ValueError(f"Failed to parse market-split solution at {path}: {exc}") from exc
    return MarketSplitSolution(x=x, name=name)
