"""Minimum Birkhoff Decomposition (03-birkhoff): write a doubly stochastic
matrix as a combination of as few permutation matrices as possible."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

import numpy as np

from qoblib._base import BestKnown, CheckResult, Problem
from qoblib._download import fetch, open_text
from qoblib._index import QoblibError, index

_COLLECTION = re.compile(r"qbench_(\d+)_(sparse|dense)\.json$")


def _entries(path: str | os.PathLike) -> list[dict]:
    with open_text(path) as handle:
        data = json.load(handle)
    return [entry for key, entry in data.items() if not key.startswith("_")]


@dataclass(eq=False)
class Birkhoff(Problem):
    """One scaled doubly stochastic matrix.

    QOBLIB stores ten matrices per file; each matrix is an instance here,
    named by its id such as ``"B3_9_1"`` (size 3, built from 9 permutations).

    A solution is a pair ``(weights, permutations)``: ``k`` weights that sum
    to :attr:`scale`, and a (k, n) array whose row ``i`` gives, for every
    matrix row, the 1-based column of permutation ``i``. The objective is the
    number of permutations with non-zero weight.

    Attributes:
        matrix: Integer matrix of shape (n, n); rows and columns sum to ``scale``.
        scale:  Common row and column sum.
    """

    matrix: np.ndarray
    scale: int
    name: str = ""

    directory = "03-birkhoff"
    _objective = re.compile(r"with (\d+) permutation matrices")

    @classmethod
    def from_file(cls, path: str | os.PathLike, name: str | None = None) -> Birkhoff:
        """Read the matrix with id *name* from a QOBLIB ``.json`` collection.

        *name* may be omitted if the file holds a single matrix.
        """
        entries = _entries(path)
        chosen = [entry for entry in entries if name in (None, entry["id"])]
        if len(chosen) != 1:
            ids = ", ".join(entry["id"] for entry in entries)
            raise QoblibError(f"pass name= to pick one matrix of {path}: {ids}")
        n = chosen[0]["n"]
        matrix = np.array(chosen[0]["scaled_doubly_stochastic_matrix"], dtype=np.int64)
        return cls(matrix.reshape(n, n), chosen[0]["scale"], chosen[0]["id"])

    @classmethod
    def _instance_files(cls) -> dict[str, list[str]]:
        found = {}
        for path in index().under(f"{cls.directory}/instances/"):
            if match := _COLLECTION.search(path):
                n = int(match[1])
                k = n if match[2] == "sparse" else n * n
                found.update({f"B{n}_{k}_{i}": [path] for i in range(1, 11)})
        return found

    @classmethod
    def _curated(cls, name: str) -> str | None:
        """Return the solution collection that belongs to the instance file of *name*."""
        files = cls._instance_files().get(name)
        path = files[0].replace("/instances/", "/solutions/") if files else None
        return path if path in index().files else None

    @classmethod
    def _solution_paths(cls, name: str) -> list[str]:
        curated = cls._curated(name)
        return [curated] if curated else super()._solution_paths(name)

    @cached_property
    def best_known(self) -> BestKnown | None:
        # Curated collections (which record optimality) take precedence over
        # the per-instance files that hold the best submitted solution.
        if curated := self._curated(self.name):
            path = fetch(curated)
            for entry in _entries(path):
                if entry["id"] == self.name:
                    solution = self._parse_solution(json.dumps({"1": entry}))
                    return BestKnown(solution, bool(entry.get("optimal")), path)
        return super().best_known

    def check(self, solution, **options) -> CheckResult:
        # Solution files may hold several matrices; hand only ours to the checker.
        if isinstance(solution, (str, os.PathLike)):
            solution = self.read_solution(solution)
        return super().check(solution, **options)

    def _parse_solution(self, text: str) -> tuple[list, np.ndarray]:
        entries = [e for key, e in json.loads(text).items() if not key.startswith("_")]
        chosen = [e for e in entries if e.get("id") == self.name] or entries
        if len(chosen) != 1:
            raise QoblibError(f"the solution file has no single entry for {self.name}")
        n = len(self.matrix)
        permutations = np.array(chosen[0]["permutations"], dtype=np.int64).reshape(-1, n)
        return list(chosen[0]["weights"]), permutations

    def _entry(self) -> dict:
        return {
            "id": self.name,
            "n": len(self.matrix),
            "scale": int(self.scale),
            "scaled_doubly_stochastic_matrix": self.matrix.ravel().tolist(),
        }

    def _format_solution(self, solution) -> str:
        weights, permutations = solution
        entry = self._entry() | {
            "weights": np.asarray(weights).tolist(),
            "permutations": np.asarray(permutations).ravel().tolist(),
        }
        return json.dumps({"1": entry})

    def _checker_args(self, solution: Path, tmp: Path) -> list:
        instance = tmp / "instance.json"
        entry = self._entry() | {"weights": [], "permutations": []}
        instance.write_text(json.dumps({"1": entry}), encoding="utf-8")
        return [instance, solution]
