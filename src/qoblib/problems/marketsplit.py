"""Market Split (01-marketsplit): find x in {0,1}^n with A x = b."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from qoblib._base import Problem, binary_vector, data_lines


@dataclass(eq=False)
class MarketSplit(Problem):
    """One market split instance.

    A solution is a sequence of ``n`` zeros and ones. The problem is a pure
    feasibility problem, so checks report no objective.

    Attributes:
        A: Integer matrix of shape (m, n).
        b: Right-hand side of length m.
    """

    A: np.ndarray
    b: np.ndarray
    name: str = ""
    path: Path | None = None

    directory = "01-marketsplit"
    _instance_suffix = ".dat"

    @classmethod
    def from_file(cls, path: str | os.PathLike, name: str | None = None) -> MarketSplit:
        """Read an instance from a ``.dat`` file."""
        path = Path(path)
        rows = [line.replace(",", " ").split() for line in data_lines(path.read_text())]
        m, n = int(rows[0][0]), int(rows[0][1])
        data = np.array(rows[1 : m + 1], dtype=np.int64).reshape(m, n + 1)
        return cls(A=data[:, :n], b=data[:, n], name=name or path.stem, path=path)

    def _parse_solution(self, text: str) -> np.ndarray:
        return np.array(binary_vector(text, self.A.shape[1]), dtype=np.int64)

    def _format_solution(self, solution) -> str:
        return " ".join(str(int(value)) for value in solution) + "\n"

    def _checker_args(self, solution: Path, tmp: Path) -> list:
        return [self._instance_path(), solution]
