"""Command line interface: ``qoblib list | download | check``."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from qoblib._base import Problem
from qoblib._index import QoblibError, index
from qoblib.problems import PROBLEMS


def problem_class(name: str) -> type[Problem]:
    """Return the problem class for a class name or repository directory, ignoring case."""
    key = name.lower()
    for problem in PROBLEMS:
        if key in (problem.__name__.lower(), problem.directory, problem.directory[3:]):
            return problem
    known = ", ".join(problem.__name__ for problem in PROBLEMS)
    raise QoblibError(f"unknown problem {name!r}; choose one of {known}")


def download(
    dest: str | os.PathLike | None = None, *, solutions: bool = True, progress: bool = True
) -> Path:
    """Download the instances and reference solutions of every problem.

    This is about 0.8 GB. Files go to the cache, or below *dest* in the
    layout of the QOBLIB repository. Returns the directory they are in.
    """
    for problem in PROBLEMS:
        if progress:
            print(f"{problem.__name__}:", file=sys.stderr)
        root = problem.download(dest=dest, solutions=solutions, progress=progress).parent
    return root


def _megabytes(prefix: str) -> float:
    return sum(index().files[path][0] for path in index().under(prefix)) / 1e6


def _list(args: argparse.Namespace) -> None:
    if args.problem:
        print("\n".join(problem_class(args.problem).instances()))
        return
    print(f"{'problem':<16}{'instances':>10}{'solutions':>11}{'download':>12}")
    for problem in PROBLEMS:
        size = _megabytes(f"{problem.directory}/instances/") + _megabytes(
            f"{problem.directory}/solutions/"
        )
        print(
            f"{problem.__name__:<16}{len(problem.instances()):>10}"
            f"{len(index().under(f'{problem.directory}/solutions/')):>11}{size:>9.1f} MB"
        )


def _download(args: argparse.Namespace) -> None:
    solutions = not args.no_solutions
    if args.problem == "all":
        print(download(args.dest, solutions=solutions))
    else:
        problem = problem_class(args.problem)
        print(problem.download(*args.instances, dest=args.dest, solutions=solutions))


def _check(args: argparse.Namespace) -> int:
    result = problem_class(args.problem).load(args.instance).check(args.solution)
    print(result.output)
    return 0 if result.feasible else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="qoblib", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    listing = commands.add_parser("list", help="list problems, or the instances of one problem")
    listing.add_argument("problem", nargs="?")
    listing.set_defaults(run=_list)

    fetching = commands.add_parser("download", help="download instances and reference solutions")
    fetching.add_argument("problem", help="a problem name, or 'all'")
    fetching.add_argument("instances", nargs="*", help="instance names (default: all)")
    fetching.add_argument("--dest", help="target directory (default: the cache)")
    fetching.add_argument("--no-solutions", action="store_true")
    fetching.set_defaults(run=_download)

    checking = commands.add_parser("check", help="check a solution file with the official checker")
    checking.add_argument("problem")
    checking.add_argument("instance")
    checking.add_argument("solution", help="path of the solution file")
    checking.set_defaults(run=_check)

    args = parser.parse_args(argv)
    try:
        return args.run(args) or 0
    except QoblibError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
