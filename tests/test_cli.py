import pytest

import qoblib
from qoblib.cli import main, problem_class

pytestmark = pytest.mark.usefixtures("repo")


def test_problem_names():
    assert problem_class("marketsplit") is qoblib.MarketSplit
    assert problem_class("IndependentSet") is qoblib.IndependentSet
    assert problem_class("07-independentset") is qoblib.IndependentSet
    with pytest.raises(qoblib.QoblibError, match="choose one of MarketSplit"):
        problem_class("knapsack")


def test_list(capsys):
    assert main(["list"]) == 0
    assert "MarketSplit" in capsys.readouterr().out
    assert main(["list", "routing"]) == 0
    assert capsys.readouterr().out == "XSH-n20-k4-01\n"


def test_download_one(tmp_path, capsys):
    assert main(["download", "steiner", "stp_s003_l1_t2_h0_rs97531", "--dest", str(tmp_path)]) == 0
    assert capsys.readouterr().out.strip() == str(tmp_path / "04-steiner")
    assert len(list(tmp_path.rglob("*.dat"))) == 4 and len(list(tmp_path.rglob("*.sol"))) == 1


def test_download_all(repo, tmp_path):
    assert qoblib.download(tmp_path, progress=False) == tmp_path

    def files(root):
        return {path.relative_to(root) for path in root.rglob("*") if path.is_file()}

    assert files(tmp_path) == files(repo)


def test_errors_are_reported(capsys):
    assert main(["list", "knapsack"]) == 2
    assert "unknown problem" in capsys.readouterr().err
