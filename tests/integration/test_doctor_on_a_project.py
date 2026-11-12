import pytest

from precedent import service
from precedent.adapters.falkor import save_decision
from precedent.core.model import DecisionRecord, Scope

pytestmark = pytest.mark.integration


def test_doctor_finds_the_stale_line_in_a_projects_instruction_files(graph, tmp_path):
    avoid = {
        "kind": "package",
        "value": "node-fetch",
        "polarity": "avoid",
        "quote": "move away from node-fetch",
        "extracted": True,
    }
    save_decision(
        graph,
        DecisionRecord.model_validate(
            {
                "id": "acme/ADR014",
                "org": "acme",
                "title": "Use native fetch",
                "status": "accepted",
                "tier": "structured",
                "confirmed": True,
                "scopes": [avoid],
                "sources": [{"url": "https://example.test/adr014.md", "kind": "adr"}],
            }
        ),
    )
    (tmp_path / "CLAUDE.md").write_text("# Repo\n\n- Use `node-fetch` for HTTP.\n")
    (tmp_path / "node_modules" / "x").mkdir(parents=True)
    (tmp_path / "node_modules" / "x" / "CLAUDE.md").write_text("- Use `node-fetch`.\n")  # vendored: ignored

    def read_stances(text: str) -> list[Scope]:
        return [
            Scope(
                kind="package",
                value="node-fetch",
                polarity="prefer",
                quote="Use `node-fetch` for HTTP.",
                extracted=True,
            )
        ]

    files, found = service.doctor(graph, str(tmp_path), read_stances)

    assert [f.name for f in files] == ["CLAUDE.md"]
    assert [(s.file, s.line, s.decision) for s in found] == [("CLAUDE.md", 3, "acme/ADR014")]
