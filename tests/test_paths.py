"""Data files stay next to the packaged executable."""

from app.utils import paths


def test_packaged_data_dir_is_next_to_the_executable(monkeypatch, tmp_path):
    monkeypatch.delenv("BTA_DATA_DIR", raising=False)
    executable = tmp_path / "BrowserTaskAutomation.exe"
    executable.write_bytes(b"")
    monkeypatch.setattr(paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths.sys, "executable", str(executable))
    assert paths.get_project_root() == tmp_path
    assert paths.get_data_dir() == tmp_path / "data"
    assert (tmp_path / "data").is_dir()
