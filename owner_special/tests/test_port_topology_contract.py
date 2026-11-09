import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "owner_special" / "team_center_contract.json"


def test_owner_service_contract_uses_service_identity_not_fixed_ports():
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    services = contract["owner"]["services"]
    boundaries = contract["service_boundaries"]

    assert services == ["research_os_api", "team_engineering", "friend_internal", "developer_api"]
    assert set(boundaries) == set(services)
    assert contract["port_policy"].startswith("OS-assigned ephemeral loopback ports")
    assert "port is not identity" in contract["authorization_rule"]
    assert contract["runtime_endpoint_registry"]["research_os_api"].endswith("api.json")
    assert contract["runtime_endpoint_registry"]["friend_internal"].endswith("friend.json")
    assert contract["runtime_endpoint_registry"]["developer_api"].endswith("developer.json")
    assert contract["runtime_endpoint_registry"]["team_engineering"].endswith("service.json")


def test_local_service_launchers_request_operating_system_assigned_ports():
    api = (ROOT / "tools" / "research_os_api" / "server.py").read_text(encoding="utf-8")
    friend = (ROOT / "owner_special" / "scripts" / "run_friend_service.py").read_text(encoding="utf-8")
    v3 = (ROOT / "v3" / "scripts" / "run_service.py").read_text(encoding="utf-8")
    flutter_store = (ROOT / "apps" / "research_os_flutter" / "lib" / "src" / "api" / "api_endpoint_store.dart").read_text(encoding="utf-8")
    api_docs = (ROOT / "tools" / "research_os_api" / "README.md").read_text(encoding="utf-8")

    assert 'default=int(os.getenv("RESEARCH_OS_API_PORT", "0"))' in api
    assert 'default=0' in friend
    assert 'RESEARCH_OS_V3_PORT", "0"' in v3
    assert 'api.json' in flutter_store
    assert 'friend.json' in api_docs
    assert "127.0.0.1:8787" not in api
    assert "127.0.0.1:8790" not in friend
    assert '"8788"' not in v3
