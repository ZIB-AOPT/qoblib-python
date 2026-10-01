"""The QOBLIB problem classes."""
from qoblib.problems.birkhoff import Birkhoff
from qoblib.problems.independentset import IndependentSet
from qoblib.problems.labs import Labs
from qoblib.problems.marketsplit import MarketSplit
from qoblib.problems.network import Network
from qoblib.problems.portfolio import Portfolio
from qoblib.problems.routing import Routing
from qoblib.problems.sports import Sports
from qoblib.problems.steiner import Steiner
from qoblib.problems.topology import Topology

#: All problem classes, in the order of the QOBLIB repository.
PROBLEMS = (
    MarketSplit,
    Labs,
    Birkhoff,
    Steiner,
    Sports,
    Portfolio,
    IndependentSet,
    Network,
    Routing,
    Topology,
)

__all__ = ["PROBLEMS", *(problem.__name__ for problem in PROBLEMS)]
