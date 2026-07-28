from pathlib import Path
import os
import sys

import pytest

from py_shell import Shell


def test_file_operations_and_find_tree_sed(tmp_path: Path):
    sh = Shell(tmp_path)

    created = sh.mkdir("src/nested")
    assert created == tmp_path / "src/nested"

    (tmp_path / "src/a.txt").write_text("hello 123\n", encoding="utf-8")
    (tmp_path / "src/nested/b.log").write_text("hello 456\n", encoding="utf-8")

    copied = sh.cp("src/a.txt", "copy.txt")
    assert copied.read_text(encoding="utf-8") == "hello 123\n"

    moved = sh.mv("copy.txt", "moved.txt")
    assert moved.exists()
    assert not (tmp_path / "copy.txt").exists()

    found = sh.find("src", pattern="*.txt")
    assert found == [tmp_path / "src/a.txt"]

    result = sh.sed("moved.txt", r"\d+", "999")
    assert result.substitutions == 1
    assert (tmp_path / "moved.txt").read_text(encoding="utf-8") == "hello 999\n"

    rendered = sh.tree("src")
    assert "a.txt" in rendered
    assert "nested" in rendered
    assert "b.log" in rendered

    sh.rm("moved.txt")
    assert not (tmp_path / "moved.txt").exists()

    sh.rm("src", recursive=True)
    assert not (tmp_path / "src").exists()


def test_run_without_shell_parsing(tmp_path: Path):
    sh = Shell(tmp_path)
    result = sh.run(
        sys.executable,
        "-c",
        "import os; print(os.getcwd()); print(os.environ['X_TEST'])",
        env={"X_TEST": "ok"},
    )
    assert result.returncode == 0
    assert str(tmp_path) in result.stdout
    assert "ok" in result.stdout


def test_run_requires_explicit_argv_for_command_arguments(tmp_path: Path):
    sh = Shell(tmp_path)
    with pytest.raises(FileNotFoundError):
        sh.run(f"{sys.executable} -c print(1)")


def test_rm_unlinks_symlink_instead_of_target(tmp_path: Path):
    sh = Shell(tmp_path)
    target = tmp_path / "target.txt"
    target.write_text("keep", encoding="utf-8")
    link = tmp_path / "link.txt"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are not available")

    sh.rm("link.txt")

    assert target.read_text(encoding="utf-8") == "keep"
    assert not link.exists()
    assert not link.is_symlink()


def test_cp_can_preserve_symlink(tmp_path: Path):
    sh = Shell(tmp_path)
    target = tmp_path / "target.txt"
    target.write_text("data", encoding="utf-8")
    link = tmp_path / "link.txt"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are not available")

    copied = sh.cp("link.txt", "copied-link.txt", follow_symlinks=False)

    assert copied.is_symlink()
    assert copied.read_text(encoding="utf-8") == "data"