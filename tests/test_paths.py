import sys
from pathlib import Path

from tbg.data import paths


def test_get_definitions_path_base_path(tmp_path: Path) -> None:
    assert paths.get_definitions_path(tmp_path) == tmp_path


def test_get_definitions_path_source_repo_exists() -> None:
    definitions_path = paths.get_definitions_path()
    assert definitions_path.name == "definitions"
    assert definitions_path.exists()


def test_get_definitions_path_pyinstaller_meipass(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    expected = tmp_path / "data" / "definitions"
    assert paths.get_definitions_path() == expected
