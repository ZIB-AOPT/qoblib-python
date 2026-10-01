"""Low Autocorrelation Binary Sequences (02-labs): minimise the energy of a ±1 sequence."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from qoblib._base import Problem, binary_vector


@dataclass(eq=False)
class Labs(Problem):
    """The LABS instance of sequence length ``n``.

    There are no instance files, so ``Labs(n)`` works for any ``n``;
    :meth:`instances` lists the lengths with a reference solution.

    A solution is a sequence of ``n`` values +1 and -1. In solution files
    QOBLIB writes +1 as ``0`` and -1 as ``1``; sequences of zeros and ones
    are accepted in that encoding as well. The objective is the energy.
    """

    n: int

    directory = "02-labs"
    _objective = re.compile(r"E\(S\)=(\d+)")

    @property
    def name(self) -> str:
        return f"labs{self.n:03d}"

    @classmethod
    def _instance_files(cls) -> dict[str, list[str]]:
        return {name: [] for name in cls._solution_files()}

    @classmethod
    def _build(cls, name: str, paths: list[Path]) -> Labs:
        return cls(int(name.removeprefix("labs")))

    def _parse_solution(self, text: str) -> list[int]:
        return [1 - 2 * bit for bit in binary_vector(text, self.n)]

    def _format_solution(self, solution) -> str:
        values = [int(value) for value in solution]
        bits = [(1 - value) // 2 for value in values] if -1 in values else values
        return "\n".join(map(str, bits)) + "\n"

    def _checker_args(self, solution: Path, tmp: Path) -> list:
        return [self.n, solution]
