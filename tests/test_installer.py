from tldrgraph.agent_commands import INSTRUCTIONS_BODY
from tldrgraph.installer import ensure_gitignore, install_agent_rules


def test_installer_writes_graph_free_contract_and_rules(tmp_path):
    result = install_agent_rules(str(tmp_path))
    contract = (tmp_path / ".tldrgraph/AGENT_CONTRACT.md").read_text(encoding="utf-8")
    agents = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert "source-backed" in contract
    assert INSTRUCTIONS_BODY.strip() in agents
    assert "query" not in INSTRUCTIONS_BODY
    assert "graphify" not in INSTRUCTIONS_BODY.lower()
    assert "contract" in result


def test_gitignore_preserves_only_contract(tmp_path):
    ensure_gitignore(str(tmp_path))
    text = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert "!.tldrgraph/AGENT_CONTRACT.md" in text
    assert "layers.config.yaml" not in text


def test_install_does_not_delete_legacy_generated_state(tmp_path):
    state = tmp_path / ".tldrgraph"
    state.mkdir()
    legacy = state / "graph.json"
    legacy.write_text("{}", encoding="utf-8")
    install_agent_rules(str(tmp_path))
    assert legacy.exists()
