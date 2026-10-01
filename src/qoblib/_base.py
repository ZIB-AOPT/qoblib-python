"""Base class shared by the ten QOBLIB problem classes."""
from __future__ import annotations

import difflib
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any, ClassVar, Iterator

import numpy as np

from qoblib._download import data_dir, fetch, fetch_many, open_text, strip_compression
from qoblib._index import QoblibError, index
from qoblib._rust import checker

# Exit codes of the checkers, see misc/ci/CHECKER_CONTRACT.md in QOBLIB.
_STATUS = {0: "VALID", 20: "SUBOPTIMAL", 21: "INFEASIBLE", 10: "INVALID_FILE"}
_REFERENCE = re.compile(r"^(?P<name>.+)\.(?P<status>opt|bst)\.\w+$")


@dataclass(frozen=True)
class CheckResult:
    """Verdict of the official checker on one solution.

    ``status`` is ``"VALID"`` (feasible; optimal where the checker knows the
    optimum), ``"SUBOPTIMAL"`` (feasible, not optimal), ``"INFEASIBLE"`` or
    ``"INVALID_FILE"``. ``objective`` is the value the checker computed, when
    the solution is feasible and the problem has an objective. ``output`` is
    everything the checker printed.
    """

    status: str
    objective: int | float | None
    output: str

    @property
    def feasible(self) -> bool:
        return self.status in ("VALID", "SUBOPTIMAL")

    def __bool__(self) -> bool:
        return self.feasible


@dataclass(frozen=True)
class BestKnown:
    """Reference solution shipped with QOBLIB; ``optimal`` tells whether it is proven optimal."""

    solution: Any
    optimal: bool
    path: Path


class Problem:
    """A QOBLIB problem; every object is one instance of it.

    Subclasses set :attr:`directory` and implement the hooks below
    ``# ---- hooks``. Node, team and item numbers keep the numbering of the
    QOBLIB files (usually 1-based), so data and solutions can be compared
    with the repository directly.
    """

    #: Directory of the problem in the QOBLIB repository, e.g. ``"01-marketsplit"``.
    directory: ClassVar[str]
    #: Extension of single-file instances, e.g. ``".dat"``.
    _instance_suffix: ClassVar[str] = ""
    #: Where the checker prints the objective value.
    _objective: ClassVar[re.Pattern | None] = None

    name: str

    # ---- catalogue

    @classmethod
    def instances(cls) -> list[str]:
        """Return the names of all instances; works offline."""
        return sorted(cls._instance_files())

    @classmethod
    def download(
        cls,
        *names: str,
        dest: str | os.PathLike | None = None,
        solutions: bool = True,
        progress: bool = True,
    ) -> Path:
        """Download instances and their reference solutions.

        Without *names* everything of this problem is downloaded. Files go to
        the cache, or below *dest* in the layout of the QOBLIB repository.
        Returns the local directory of the problem.
        """
        if names:
            paths = []
            for name in names:
                paths += cls._files_of(name)
                paths += cls._solution_paths(name) if solutions else []
        else:
            paths = index().under(f"{cls.directory}/instances/")
            paths += index().under(f"{cls.directory}/solutions/") if solutions else []
        root = Path(dest) if dest is not None else data_dir()
        fetch_many(dict.fromkeys(paths), root, progress)
        return root / cls.directory

    @classmethod
    def load(cls, name: str):
        """Return the instance called *name*, downloading its files if needed."""
        return cls._build(name, fetch_many(cls._files_of(name)))

    # ---- solutions

    def read_solution(self, path: str | os.PathLike) -> Any:
        """Parse a solution file in the format of the QOBLIB repository."""
        with open_text(path) as handle:
            return self._parse_solution(handle.read())

    def write_solution(self, solution: Any, path: str | os.PathLike) -> Path:
        """Write *solution* in the format the official checker reads."""
        path = Path(path)
        path.write_text(self._format_solution(solution), encoding="utf-8")
        return path

    @cached_property
    def best_known(self) -> BestKnown | None:
        """The reference solution of this instance, or ``None`` if there is none."""
        found = self._solution_files().get(self.name)
        if found is None:
            return None
        path = fetch(found[0])
        return BestKnown(self.read_solution(path), found[1], path)

    def check(self, solution: Any, **options: Any) -> CheckResult:
        """Check *solution* with the official QOBLIB checker.

        *solution* is either solution data (as returned by
        :meth:`read_solution`) or the path of a solution file. The checkers
        are Rust programs that are compiled on first use, which needs
        ``cargo``; a :class:`QoblibError` explains what to install otherwise.
        """
        binary = checker(self.directory)
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            if isinstance(solution, (str, os.PathLike)):
                file = Path(solution)
                if not file.is_file():
                    raise QoblibError(f"solution file {file} does not exist")
                if strip_compression(file.name) != file.name:
                    plain = tmp / strip_compression(file.name)
                    with open_text(file) as source, open(plain, "w", encoding="utf-8") as out:
                        shutil.copyfileobj(source, out)
                    file = plain
            else:
                file = self.write_solution(solution, tmp / "solution.sol")
            args = [str(arg) for arg in self._checker_args(file, tmp, **options)]
            run = subprocess.run([str(binary), *args], capture_output=True, text=True)
        output = (run.stdout + run.stderr).strip()
        status = _STATUS.get(run.returncode)
        if status is None:
            raise QoblibError(
                f"the {type(self).__name__} checker could not judge the solution "
                f"(exit code {run.returncode}):\n{output}"
            )
        result = CheckResult(status, None, output)
        if result.feasible and self._objective is not None:
            if match := self._objective.search(run.stdout):
                value = match.group(1)
                result = CheckResult(status, float(value) if "." in value else int(value), output)
        return result

    # ---- hooks

    @classmethod
    def _instance_files(cls) -> dict[str, list[str]]:
        """Map instance names to their repository files."""
        found = {}
        for path in index().under(f"{cls.directory}/instances/"):
            filename = strip_compression(path.split("/")[-1])
            if path.count("/") == 2 and filename.endswith(cls._instance_suffix):
                found[filename[: -len(cls._instance_suffix)]] = [path]
        return found

    @classmethod
    def _solution_files(cls) -> dict[str, tuple[str, bool]]:
        """Map instance names to (reference solution file, proven optimal)."""
        found = {}
        for path in index().under(f"{cls.directory}/solutions/"):
            if match := _REFERENCE.match(strip_compression(path.split("/")[-1])):
                found[match["name"]] = (path, match["status"] == "opt")
        return found

    @classmethod
    def _solution_paths(cls, name: str) -> list[str]:
        found = cls._solution_files().get(name)
        return [found[0]] if found else []

    @classmethod
    def _build(cls, name: str, paths: list[Path]):
        return cls.from_file(paths[0], name=name)

    def _parse_solution(self, text: str) -> Any:
        raise NotImplementedError

    def _format_solution(self, solution: Any) -> str:
        raise NotImplementedError

    def _checker_args(self, solution: Path, tmp: Path) -> list:
        raise NotImplementedError

    # ---- helpers

    @classmethod
    def _files_of(cls, name: str) -> list[str]:
        files = cls._instance_files()
        if name not in files:
            close = difflib.get_close_matches(name, files, n=3)
            hint = f"; did you mean {', '.join(close)}?" if close else ""
            raise QoblibError(f"{cls.__name__} has no instance named {name!r}{hint}")
        return files[name]

    def _instance_path(self) -> Path:
        path = getattr(self, "path", None)
        if path is None:
            raise QoblibError(
                f"this {type(self).__name__} instance has no file for the checker; "
                "create it with load() or from_file()"
            )
        return path


def data_lines(text: str, comment: str = "#") -> Iterator[str]:
    """Yield the stripped, non-empty lines of *text* with comments removed."""
    for line in text.splitlines():
        line = line.split(comment, 1)[0].strip()
        if line:
            yield line


def binary_vector(text: str, n: int) -> list[int]:
    """Parse the 0/1 vector formats the checkers accept into a list of length *n*.

    Understood are a 0/1 string (compact or separated), solver output with
    ``x#<index> <value>`` lines, and a list of the 1-based indices set to 1.
    """
    if "x#" in text:
        vector = [0] * n
        for index_, value in re.findall(r"x#(\d+)\s+([01])", text):
            vector[int(index_) - 1] = int(value)
        return vector
    tokens = " ".join(data_lines(text)).replace(",", " ").split()
    if len(tokens) == 1 and len(tokens[0]) == n and set(tokens[0]) <= {"0", "1"}:
        return [int(char) for char in tokens[0]]
    if len(tokens) == n and set(tokens) <= {"0", "1"}:
        return [int(token) for token in tokens]
    vector = [0] * n
    for token in tokens:
        vector[int(token) - 1] = 1
    return vector


def read_graph(path: str | os.PathLike) -> tuple[int, np.ndarray]:
    """Read a DIMACS ``p edge`` file; return the node count and an (m, 2) edge array."""
    n = 0
    edges = []
    with open_text(path) as handle:
        for line in handle:
            if line.startswith("e"):
                _, u, v = line.split()
                edges.append((int(u), int(v)))
            elif line.startswith("p"):
                n = int(line.split()[2])
    return n, np.array(edges, dtype=np.int64).reshape(-1, 2)
