"""Portfolio optimization problem plugin.

Multi-period portfolio optimization: given stock prices and a covariance
matrix, find binary buy/sell decisions that maximize return subject to a
budget constraint.

Instance structure
------------------
Each instance lives in a subdirectory (e.g. ``po_a010_t10_orig/``) containing:

- ``stock_prices_<name>.csv.gz``      — time-series of closing prices
- ``covariance_matrices_<name>.csv.gz`` — per-period covariance matrices

Stock prices CSV columns (after decompression)::

    date, symbol, price

Covariance matrices CSV columns::

    date, symbol_i, symbol_j, covariance

The Rust checker reads the instance directory and a solution file::

    check_portfolio <instance-dir> <solution.sol>

Solution file format
--------------------
Plain text, key-value header followed by position lines::

    instance po_a010_t10_orig
    budget 4
    lambda 0.0001
    objective -69482
    # period  symbol  long  short
    0 AAPL  0 1
    1 META  1 0
"""
from __future__ import annotations

import csv
import gzip
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from qoblib._problem import Problem, register_problem


@dataclass
class PortfolioPrices:
    """Parsed stock price time-series.

    Attributes:
        symbols:  Sorted list of stock symbols present in the data.
        dates:    Sorted list of date strings (ISO format, one per period).
        prices:   ``{(date, symbol): price}`` — closing price as a float.
    """

    symbols: List[str]
    dates: List[str]
    prices: Dict[Tuple[str, str], float]


@dataclass
class PortfolioCovariances:
    """Parsed per-period covariance matrices.

    Attributes:
        dates:       Sorted list of date strings (one per period).
        symbols:     Sorted list of stock symbols.
        covariances: ``{(date, symbol_i, symbol_j): covariance}`` — float.
    """

    dates: List[str]
    symbols: List[str]
    covariances: Dict[Tuple[str, str, str], float]


@dataclass
class PortfolioInstance:
    """A fully parsed portfolio instance.

    Attributes:
        instance_dir:  Local path to the instance directory (used by the
                       Rust checker, which reads the raw CSV files directly).
        name:          Logical instance name (e.g. ``"po_a010_t10_orig"``).
        n_periods:     Number of trading periods.
        n_assets:      Number of assets (stocks).
        symbols:       Sorted list of stock symbols.
        prices:        Parsed price time-series (:class:`PortfolioPrices`).
        covariances:   Parsed covariance matrices (:class:`PortfolioCovariances`).
    """

    instance_dir: Path
    name: str
    n_periods: int
    n_assets: int
    symbols: List[str]
    prices: PortfolioPrices
    covariances: PortfolioCovariances


@dataclass
class PortfolioPosition:
    """One holding in a portfolio solution."""

    period: int
    symbol: str
    long_units: int
    short_units: int


@dataclass
class PortfolioSolution:
    """A parsed portfolio solution.

    Attributes:
        instance_name: Instance name from the solution header.
        budget:        Budget parameter *B*.
        lambda_:       Risk weight λ.
        objective:     Claimed objective value (or ``None``).
        positions:     List of non-zero holdings.
        name:          Logical solution name.
        path:          Local path to the ``.sol`` file.
    """

    instance_name: Optional[str] = None
    budget: Optional[int] = None
    lambda_: Optional[float] = None
    objective: Optional[float] = None
    positions: List[PortfolioPosition] = field(default_factory=list)
    name: str = ""
    path: Optional[Path] = None

    def to_checker_string(self) -> str:
        """Serialise back to the canonical solution format."""
        lines: list[str] = []
        if self.instance_name:
            lines.append(f"instance {self.instance_name}")
        if self.budget is not None:
            lines.append(f"budget {self.budget}")
        if self.lambda_ is not None:
            lines.append(f"lambda {self.lambda_}")
        if self.objective is not None:
            lines.append(f"objective {int(self.objective)}")
        lines.append("# period  symbol  long  short")
        for pos in self.positions:
            lines.append(f"{pos.period} {pos.symbol} {pos.long_units} {pos.short_units}")
        return "\n".join(lines) + "\n"


@register_problem
class PortfolioProblem(Problem):
    """Plugin for the Portfolio Optimization problem class.

    Quickstart::

        import qoblib
        pf = qoblib.get_problem("portfolio")
        inst = pf.load_instance("po_a010_t10_orig")
        sol  = pf.load_solution("po_a010_t10_orig")

        print(inst.n_periods, inst.n_assets)   # problem dimensions
        print(inst.symbols)                     # ['AAPL', 'META', ...]
        # prices: {(date, symbol): price}
        # covariances: {(date, sym_i, sym_j): cov}

        result = pf.check_solution(inst, sol)
        print(result.status, result.objective)  # claimed objective from file
    """

    slug = "portfolio"
    description = "Multi-Period Portfolio Optimization"

    def load_instance(self, name: str) -> PortfolioInstance:
        """Fetch, decompress, and parse all instance files for *name*.

        Downloads all files in the instance directory, decompresses them,
        and parses prices and covariances into structured Python objects.
        The Rust checker reads the raw directory directly, so all files
        are retained on disk after this call.
        """
        entries = [e for e in self.files(kind="instance") if name in e["path"]]
        if not entries:
            raise KeyError(f"No instance files found for {name!r}")

        prices_path: Optional[Path] = None
        cov_path: Optional[Path] = None

        for entry in entries:
            path = self.fetch(entry["path"], kind="instance")
            fname = entry["filename"].lower()
            if "stock_prices" in fname or "prices" in fname:
                prices_path = path
            elif "covariance" in fname or "cov" in fname:
                cov_path = path

        if prices_path is None:
            raise ValueError(f"No stock prices file found for instance {name!r}")
        if cov_path is None:
            raise ValueError(f"No covariance matrices file found for instance {name!r}")

        instance_dir = prices_path.parent
        prices = _parse_prices(prices_path)
        covariances = _parse_covariances(cov_path)

        return PortfolioInstance(
            instance_dir=instance_dir,
            name=name,
            n_periods=len(prices.dates),
            n_assets=len(prices.symbols),
            symbols=prices.symbols,
            prices=prices,
            covariances=covariances,
        )

    def load_solution(self, name: str) -> PortfolioSolution:
        """Fetch and parse a portfolio solution file."""
        path = self.fetch(name, kind="solution")
        sol = _parse_solution(path, name)
        sol.path = path
        return sol

    def compute_objective(
        self,
        instance: PortfolioInstance,
        solution: PortfolioSolution,
    ) -> Optional[float]:
        """Return the claimed objective value from the solution file header."""
        return solution.objective


# ------------------------------------------------------------------ parsers


def _open_csv(path: Path):
    """Open a plain or gzip-compressed CSV file and return a csv.DictReader."""
    if path.suffix == ".gz":
        f = gzip.open(path, "rt", encoding="utf-8")
    else:
        f = path.open("r", encoding="utf-8")
    return f


def _parse_prices(path: Path) -> PortfolioPrices:
    """Parse a stock_prices CSV (possibly gzip-compressed).

    Expected columns: ``date``, ``symbol``, ``price``
    (column names are matched case-insensitively; extra columns are ignored).
    """
    prices: Dict[Tuple[str, str], float] = {}
    dates_seen: set[str] = set()
    symbols_seen: set[str] = set()

    with _open_csv(path) as f:
        reader = csv.DictReader(f)
        # normalise column names to lower-case
        for row in reader:
            norm = {k.strip().lower(): v.strip() for k, v in row.items()}
            date = norm.get("date", "")
            symbol = norm.get("symbol", "")
            try:
                price = float(norm.get("price", "nan"))
            except ValueError:
                continue
            prices[(date, symbol)] = price
            dates_seen.add(date)
            symbols_seen.add(symbol)

    return PortfolioPrices(
        symbols=sorted(symbols_seen),
        dates=sorted(dates_seen),
        prices=prices,
    )


def _parse_covariances(path: Path) -> PortfolioCovariances:
    """Parse a covariance_matrices CSV (possibly gzip-compressed).

    Expected columns: ``date``, ``symbol_i``, ``symbol_j``, ``covariance``
    (column names are matched case-insensitively; extra columns are ignored).
    """
    covariances: Dict[Tuple[str, str, str], float] = {}
    dates_seen: set[str] = set()
    symbols_seen: set[str] = set()

    with _open_csv(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            norm = {k.strip().lower(): v.strip() for k, v in row.items()}
            date = norm.get("date", "")
            # Accept a few common column name variants
            si = norm.get("symbol_i") or norm.get("symbol1") or norm.get("asset_i", "")
            sj = norm.get("symbol_j") or norm.get("symbol2") or norm.get("asset_j", "")
            try:
                cov = float(norm.get("covariance") or norm.get("cov", "nan"))
            except ValueError:
                continue
            covariances[(date, si, sj)] = cov
            dates_seen.add(date)
            symbols_seen.add(si)
            symbols_seen.add(sj)

    return PortfolioCovariances(
        dates=sorted(dates_seen),
        symbols=sorted(symbols_seen),
        covariances=covariances,
    )


def _parse_solution(path: Path, name: str = "") -> PortfolioSolution:
    """Parse a portfolio ``.sol`` file."""
    sol = PortfolioSolution(name=name, path=path)
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if parts[0] == "instance" and len(parts) >= 2:
            sol.instance_name = parts[1]
        elif parts[0] == "budget" and len(parts) >= 2:
            try:
                sol.budget = int(parts[1])
            except ValueError:
                pass
        elif parts[0] == "lambda" and len(parts) >= 2:
            try:
                sol.lambda_ = float(parts[1])
            except ValueError:
                pass
        elif parts[0] == "objective" and len(parts) >= 2:
            try:
                sol.objective = float(parts[1])
            except ValueError:
                pass
        elif len(parts) == 4:
            try:
                sol.positions.append(PortfolioPosition(
                    period=int(parts[0]),
                    symbol=parts[1],
                    long_units=int(parts[2]),
                    short_units=int(parts[3]),
                ))
            except ValueError:
                pass
    return sol
