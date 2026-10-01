"""Portfolio Optimization (06-portfolio): trade a set of assets over several
periods to balance risk, return and transaction costs under a budget."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from fractions import Fraction
from functools import cached_property
from pathlib import Path

import numpy as np

from qoblib._base import BestKnown, Problem, data_lines
from qoblib._download import fetch, fetch_many, open_text
from qoblib._index import QoblibError, index

_PARAMETERS = re.compile(r"(.+)_b(\d+)_l(.+)")


def _data_file(directory: Path, stem: str) -> Path:
    for path in sorted(directory.glob(f"{stem}.txt*")):
        return path
    raise QoblibError(f"no {stem}.txt[.gz] in {directory}")


def _header(text: str) -> dict[str, str]:
    """Return the ``key value`` header lines of a portfolio solution file."""
    pairs = (line.split() for line in data_lines(text))
    return {pair[0]: pair[1] for pair in pairs if len(pair) == 2}


@dataclass(eq=False)
class Portfolio(Problem):
    """One portfolio instance: market data plus a budget and a risk aversion.

    QOBLIB ships the market data sets (listed by :meth:`instances`); the
    benchmark instances combine each with a budget and a risk aversion
    ``lambda``, written like ``"po_a010_t10_orig_b004_l1e-4"``. :meth:`load`
    accepts both spellings.

    A solution is a list of ``(period, symbol, long, short)`` tuples giving
    the units held long and short; unlisted positions are zero. The objective
    is the value computed by the checker (smaller is better).

    Attributes:
        path:          Directory with ``stock_prices.txt[.gz]`` and
                       ``covariance_matrices.txt[.gz]``.
        budget:        Maximum number of units held per period.
        risk_aversion: The risk weight ``lambda``, kept as a decimal string.
    """

    path: Path
    budget: int | None = None
    risk_aversion: str | None = None
    name: str = ""

    directory = "06-portfolio"
    _objective = re.compile(r"Objective value = (-?\d+)")
    _manifest = "06-portfolio/instances/manifest.json"

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        self.name = self.name or self.path.name
        if self.risk_aversion is not None:
            self.risk_aversion = str(self.risk_aversion)

    @classmethod
    def from_file(
        cls,
        path: str | os.PathLike,
        budget: int | None = None,
        risk_aversion: str | float | None = None,
        name: str | None = None,
    ) -> Portfolio:
        """Use the market data in directory *path*."""
        return cls(Path(path), budget, risk_aversion, name or "")

    @classmethod
    def load(
        cls, name: str, budget: int | None = None, risk_aversion: str | float | None = None
    ) -> Portfolio:
        """Return an instance, downloading its market data if needed.

        *name* is a data set such as ``"po_a010_t10_orig"``, optionally with
        the parameters appended (``"po_a010_t10_orig_b004_l1e-4"``). Without
        a budget, the one QOBLIB uses for the number of assets is taken.
        """
        if match := _PARAMETERS.fullmatch(name):
            name, budget, risk_aversion = match[1], int(match[2]), match[3]
        directory = fetch_many(cls._files_of(name))[0].parent
        if budget is None and cls._manifest in index().files:
            budgets = json.loads(fetch(cls._manifest).read_text())["budget_by_assets"]
            assets = re.search(r"_a(\d+)_", name)
            budget = budgets.get(str(int(assets[1]))) if assets else None
        return cls(directory, budget, risk_aversion, name)

    # ---- market data

    @cached_property
    def _prices(self) -> tuple[list[str], np.ndarray]:
        with open_text(_data_file(self.path, "stock_prices")) as handle:
            rows = [line.split() for line in data_lines(handle.read())]
        symbols = list(dict.fromkeys(symbol for _, symbol, _ in rows))
        prices = np.zeros((max(int(day) for day, _, _ in rows) + 1, len(symbols)))
        for day, symbol, price in rows:
            prices[int(day), symbols.index(symbol)] = float(price)
        return symbols, prices

    @property
    def symbols(self) -> list[str]:
        """Asset symbols, in the order of the data files."""
        return self._prices[0]

    @property
    def prices(self) -> np.ndarray:
        """Array of shape (days, assets) with the price of every asset per day."""
        return self._prices[1]

    @cached_property
    def covariances(self) -> np.ndarray:
        """Array of shape (days, assets, assets) with one covariance matrix per day."""
        position = {symbol: number for number, symbol in enumerate(self.symbols)}
        matrices = np.zeros((len(self.prices), len(position), len(position)))
        with open_text(_data_file(self.path, "covariance_matrices")) as handle:
            for line in handle:
                if line[0].isdigit():
                    day, first, second, value = line.split()
                    matrices[int(day), position[first], position[second]] = float(value)
        return matrices

    # ---- catalogue and solutions

    @classmethod
    def _instance_files(cls) -> dict[str, list[str]]:
        found: dict[str, list[str]] = {}
        for path in index().under(f"{cls.directory}/instances/"):
            parts = path.split("/")
            if len(parts) == 4:
                found.setdefault(parts[2], []).append(path)
        return found

    @classmethod
    def _solution_paths(cls, name: str) -> list[str]:
        solutions = index().under(f"{cls.directory}/solutions/")
        return [path for path in solutions if path.split("/")[-1].startswith(name)]

    @cached_property
    def best_known(self) -> BestKnown | None:
        if self.budget is None or self.risk_aversion is None:
            return None
        wanted = (self.budget, Fraction(self.risk_aversion))
        pattern = re.compile(re.escape(self.name) + r"(?:_b(\d+)_l(.+))?\.(opt|bst)\.sol")
        for path in self._solution_paths(self.name):
            match = pattern.fullmatch(path.split("/")[-1])
            if not match:
                continue
            budget, risk_aversion = match[1], match[2]
            if budget is None:  # parameters are in the file header instead
                header = _header(fetch(path).read_text())
                budget, risk_aversion = header.get("budget", -1), header.get("lambda", -1)
            if (int(budget), Fraction(risk_aversion)) == wanted:
                local = fetch(path)
                return BestKnown(self.read_solution(local), match[3] == "opt", local)
        return None

    def _parse_solution(self, text: str) -> list[tuple[int, str, int, int]]:
        rows = (line.split() for line in data_lines(text))
        return [(int(r[0]), r[1], int(r[2]), int(r[3])) for r in rows if r[0].isdigit()]

    def _format_solution(self, solution) -> str:
        return "".join(
            f"{period} {symbol} {int(long)} {int(short)}\n"
            for period, symbol, long, short in solution
        )

    def _checker_args(self, solution: Path, tmp: Path) -> list:
        args = [self.path, solution]
        if self.budget is not None:
            args += ["--budget", self.budget]
        if self.risk_aversion is not None:
            args += ["--lambda", self.risk_aversion]
        return args
