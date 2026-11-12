import pytest

from precedent.surfaces.cli import main


@pytest.mark.parametrize("org", ["Backstage", "my org", "a/b", "test_x"], ids=["upper", "space", "slash", "underscore"])
def test_an_org_that_cannot_be_a_graph_name_is_refused(tmp_path, org):
    with pytest.raises(SystemExit) as exited:
        main(["ingest", str(tmp_path), "--org", org])
    assert exited.value.code == 2


def test_a_missing_folder_is_refused_before_touching_the_database(tmp_path):
    with pytest.raises(SystemExit) as exited:
        main(["ingest", str(tmp_path / "missing"), "--org", "backstage"])
    assert exited.value.code == 2


def test_no_falkordb_gives_a_clear_error_and_exit_code_1(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("FALKORDB_URL", "redis://localhost:1")

    assert main(["ingest", str(tmp_path), "--org", "backstage"]) == 1
    assert "No FalkorDB at redis://localhost:1" in capsys.readouterr().err
