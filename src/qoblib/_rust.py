"""Build and locate the official Rust solution checkers of QOBLIB.

Each problem directory of the repository ships a small Cargo project under
``check/``. It is downloaded and compiled on first use; the binary is kept
in the cache next to the data of the same commit.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from qoblib._download import data_dir, fetch_many
from qoblib._index import QoblibError, index


def _find_binary(directory: Path) -> Path | None:
    if not directory.is_dir():
        return None
    for path in sorted(directory.iterdir()):
        if path.is_file() and path.stem.startswith("check") and path.suffix in ("", ".exe"):
            if os.access(path, os.X_OK):
                return path
    return None


def checker(problem_directory: str) -> Path:
    """Return the checker binary for e.g. ``"01-marketsplit"``, building it if needed."""
    bin_dir = data_dir() / "checkers" / problem_directory
    if binary := _find_binary(bin_dir):
        return binary

    sources = index().under(f"{problem_directory}/check/")
    if not sources:
        raise QoblibError(f"QOBLIB provides no solution checker for {problem_directory}")
    if shutil.which("cargo") is None:
        raise QoblibError(
            "Checking solutions runs the official QOBLIB checkers, which are written "
            "in Rust, but 'cargo' was not found on PATH. Install the Rust toolchain "
            "from https://rustup.rs and try again."
        )

    manifest = fetch_many(sources)[sources.index(f"{problem_directory}/check/Cargo.toml")]
    with tempfile.TemporaryDirectory() as target:
        build = subprocess.run(
            ["cargo", "build", "--release", "--manifest-path", str(manifest), "--target-dir", target],
            capture_output=True,
            text=True,
        )
        built = _find_binary(Path(target) / "release")
        if build.returncode != 0 or built is None:
            raise QoblibError(
                f"building the checker for {problem_directory} failed:\n{build.stderr}"
            )
        bin_dir.mkdir(parents=True, exist_ok=True)
        return Path(shutil.copy2(built, bin_dir / built.name))
